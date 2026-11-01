import contextlib
import io
import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))
from omarchy_data import read_data
from omarchy_profiles import ProfileError, Resolver, contract, schemas
import omarchy_playbook as launcher


class ProfileTests(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory()
        self.addCleanup(self.temporary.cleanup)
        self.folder = Path(self.temporary.name)

    def file(self, name, value):
        path = self.folder / name
        path.write_text(json.dumps(value))
        return path

    def setup(self, **value):
        return self.file("setup.json", {"schema_version": 1, **value})

    def catalogue(self, **value):
        return self.file("catalogue.json", {"schema_version": 1, "namespace": "example", "features": {}, **value})

    def test_legacy_defaults_and_explicit_selection_are_preserved(self):
        self.assertEqual(Resolver().resolve()["features"], ["workstation"])
        plan = Resolver().resolve(features=["languages"])
        self.assertEqual(plan["options"], {"languages": {"tools": {"node": ""}}})
        self.assertNotIn("docker", plan["features"])

    def test_profiles_have_complete_separate_toolchains_and_no_credentials(self):
        for name in ("developer", "web", "python"):
            with self.subTest(profile=name):
                plan = Resolver().resolve(profiles=[name])
                self.assertTrue({"cli", "vcs", "editors", "api", "workstation"} <= set(plan["features"]))
                self.assertFalse({"agents", "credentials"} & set(plan["features"]))
                self.assertEqual(len(plan["features"]), len(set(plan["features"])))
        web = Resolver().resolve(profiles=["web"])
        python = Resolver().resolve(profiles=["python"])
        self.assertEqual(web["options"]["languages"]["tools"], {"node": "lts", "pnpm": ""})
        self.assertEqual(python["options"]["languages"]["tools"], {"python": "3", "uv": ""})
        self.assertIn("postgresql-libs", web["packages"])
        self.assertNotIn("postgresql", web["packages"])
        self.assertNotIn("docker", python["features"])
        self.assertEqual(python["packages"]["base-devel"], ["languages", "build"])

    def test_project_managed_profile_leaves_versions_to_projects(self):
        plan = Resolver().resolve(profiles=["project-managed"])
        self.assertEqual(plan["mise"], {})
        self.assertIn("mise-bin", plan["packages"])
        self.assertTrue({"build", "docker", "browsers", "toolchain"} <= set(plan["features"]))
        self.assertNotIn("languages", plan["features"])
        self.assertEqual(plan["options"]["databases"]["clients"], ["postgresql", "sqlite"])
        configured = Resolver().resolve(setup_file=ROOT / "omarchy/examples/project-managed.yml")
        self.assertEqual(set(configured["mise"]), {"claude"})
        self.assertTrue({"libyaml", "gmp"} <= set(configured["packages"]))
        self.assertEqual(launcher.plan_variables(configured)["omarchy_toolchain"], {"prerequisites": ["ruby"]})

    def test_sibling_conflicts_require_override_and_disjoint_tools_merge(self):
        for profiles in (["web", "python"], ["python", "web"]):
            with self.assertRaisesRegex(ProfileError, "databases.clients"):
                Resolver().resolve(profiles=profiles)
            plan = Resolver().resolve(profiles=profiles, setup_file=self.setup(
                options={"databases": {"clients": ["sqlite"]}, "languages": {"tools": {"node": "24"}}}))
            self.assertEqual(plan["options"]["languages"]["tools"], {"node": "24", "pnpm": "", "python": "3", "uv": ""})

    def test_empty_map_and_list_clear_without_enabling_or_removing_tools(self):
        plan = Resolver().resolve(profiles=["web"], setup_file=self.setup(
            features={"disable": ["editors"]},
            options={"languages": {"tools": {}}, "browsers": {"browsers": []}, "agents": {"tools": {"codex": ""}}}))
        self.assertEqual(plan["options"]["languages"], {"tools": {}})
        self.assertEqual(plan["options"]["browsers"], {"browsers": []})
        self.assertNotIn("editors", plan["features"])
        self.assertNotIn("agents", plan["features"])
        self.assertNotIn("chromium", plan["packages"])
        self.assertEqual(set(plan["mise"]), {"shellcheck"})

    def test_third_party_profile_and_prerequisites_resolve_with_provenance(self):
        catalogue = self.catalogue(features={
            "api": {"description": "API diagnostics", "requires": ["cli"], "packages": ["jq"], "mise": {"uv": ""}}},
            profiles={"backend": {"extends": ["builtin.web"], "features": ["example.api"],
                                  "options": {"languages": {"tools": {"node": "24"}}}}})
        setup = self.setup(catalogues=[catalogue.name], profiles=["example.backend"],
                           options={"browsers": {"browsers": ["firefox"]}})
        plan = Resolver().resolve(setup_file=setup)
        self.assertIn("example.api", plan["features"])
        self.assertIn("required by example.api", plan["reasons"]["cli"])
        self.assertEqual(plan["options"]["languages"]["tools"], {"node": "24", "pnpm": ""})
        self.assertEqual(len(plan["sources"]), 3)
        self.assertTrue(all(len(source["sha256"]) == 64 for source in plan["sources"]))
        variables = launcher.plan_variables(plan)
        self.assertEqual(variables["omarchy_extensions"], [{"name": "example.api", "config": {"packages": ["jq"], "tools": {"uv": ""}}}])

    def test_disabled_prerequisites_unknown_refs_and_cycles_are_errors(self):
        for definitions, profiles in [
            ({"api": {"description": "x", "requires": ["missing"]}}, {}),
            ({"a": {"description": "x", "requires": ["example.b"]}, "b": {"description": "x", "requires": ["example.a"]}}, {}),
            ({}, {"a": {"extends": ["example.b"]}, "b": {"extends": ["example.a"]}}),
            ({}, {"a": {"features": ["missing"]}}),
        ]:
            with self.subTest(definitions=definitions, profiles=profiles), self.assertRaises(ProfileError):
                Resolver().resolve(catalogues=[self.catalogue(features=definitions, profiles=profiles)])
        path = self.catalogue(features={"api": {"description": "x", "requires": ["cli"]}})
        with self.assertRaisesRegex(ProfileError, "Disabled required"):
            Resolver().resolve(catalogues=[path], features=["example.api"],
                               setup_file=self.setup(features={"disable": ["cli"]}))

    def test_conflicting_tool_selectors_and_package_providers_fail(self):
        for packages, mise, match in [([], {"node": "22"}, "selectors"), (["nodejs"], {}, "providers")]:
            path = self.catalogue(features={"tool": {"description": "x", "packages": packages, "mise": mise}})
            with self.subTest(packages=packages), self.assertRaisesRegex(ProfileError, match):
                Resolver().resolve(profiles=["web"], features=["example.tool"], catalogues=[path])

    def test_catalogue_cannot_register_code_connection_overrides_or_shadow_builtins(self):
        cases = [
            {"namespace": "builtin"}, {"schema_version": 2}, {"schema_version": True},
            {"roles": ["anything"]}, {"features": {"tool": {"description": "x", "command": "id"}}},
            {"features": {"tool": {"description": "x", "packages": ["--help"]}}},
            {"features": {"tool": {"description": "x", "mise": {"npm:tool": "1"}}}},
            {"profiles": {"p": {"options": {"ansible_connection": "local"}}}},
        ]
        for value in cases:
            with self.subTest(value=value), self.assertRaises((ProfileError, ValueError)):
                Resolver().resolve(catalogues=[self.catalogue(**value)])

    def test_local_schema_types_unknown_options_and_duplicate_aliases_fail(self):
        for value in [
            {"schema_version": 2}, {"profiles": ["all"]}, {"features": {"enable": ["all"]}},
            {"profiles": ["web", "builtin.web"]}, {"options": {"languages": {"tools": {"python": 3}}}},
            {"options": {"docker": {"enabled": True}}}, {"ansible_user": "someone"},
            {"options": {"editors": {"editors": ["unknown"]}}},
        ]:
            with self.subTest(value=value), self.assertRaises((ProfileError, ValueError)):
                Resolver().resolve(setup_file=self.setup(**value))

    def test_offline_plan_does_not_resolve_a_manager_or_mutate_a_guest(self):
        args = type("Args", (), {"vars_file": None, "features": None, "profiles": ["web"], "resolve": True})()
        with mock.patch.object(launcher, "ready_connection") as connection, \
                mock.patch.object(launcher.manager, "enable_bootstrap_sudo") as grant, \
                mock.patch.object(launcher.manager, "require_file") as require, \
                contextlib.redirect_stdout(io.StringIO()) as output:
            launcher.playbook(args)
        self.assertEqual(json.loads(output.getvalue())["profiles"], ["web"])
        connection.assert_not_called()
        grant.assert_not_called()
        require.assert_not_called()

    def test_legacy_overrides_preserve_other_inherited_tools(self):
        plan = Resolver().resolve(profiles=["web"], overrides=launcher.overrides({"omarchy_languages": {"node": "24"}}))
        self.assertEqual(plan["options"]["languages"]["tools"], {"node": "24", "pnpm": ""})
        self.assertEqual(launcher.plan_variables(plan)["omarchy_languages"], {"node": "24", "pnpm": ""})

    def test_disabling_a_feature_resolves_its_sibling_option_conflict(self):
        plan = Resolver().resolve(profiles=["web", "python"], setup_file=self.setup(features={"disable": ["databases"]}))
        self.assertNotIn("databases", plan["features"])
        self.assertEqual(set(plan["mise"]), {"node", "pnpm", "python", "uv", "shellcheck"})

    def test_shipped_examples_and_generated_schemas_are_current(self):
        for path in ("setup.yml", "team/setup.yml"):
            plan = Resolver().resolve(setup_file=ROOT / "omarchy/examples" / path)
            self.assertIn("languages", plan["features"])
        for name, schema in schemas().items():
            self.assertEqual(json.loads((ROOT / f"omarchy/features/{name}.schema.json").read_text()), schema)

    def test_parent_override_can_resolve_multiple_inheritance_conflict(self):
        path = self.catalogue(profiles={"combined": {
            "extends": ["web", "python"], "options": {"databases": {"clients": []}}}})
        plan = Resolver().resolve(profiles=["example.combined"], catalogues=[path])
        self.assertEqual(plan["options"]["databases"], {"clients": []})

    def test_changed_source_is_rejected_after_a_proposal(self):
        path = self.setup(profiles=["developer"])
        plan = Resolver().resolve(setup_file=path)
        source = next(source for source in plan["sources"] if source["path"] == str(path.resolve()))
        Resolver.verify_source(source)
        path.write_text('{"schema_version":1,"profiles":["web"]}')
        with self.assertRaisesRegex(ProfileError, "changed after resolution"):
            Resolver.verify_source(source)

    def test_individual_inherited_tools_can_be_deselected_without_uninstalling(self):
        plan = Resolver().resolve(profiles=["web"], setup_file=self.setup(
            options={"languages": {"tools": {"pnpm": None, "node": "24"}}}))
        self.assertEqual(plan["options"]["languages"]["tools"], {"node": "24"})
        self.assertNotIn("pnpm", plan["mise"])
        for key in ("--help", "npm:tool"):
            with self.assertRaises(ProfileError):
                Resolver().resolve(profiles=["web"], setup_file=self.setup(options={"languages": {"tools": {key: None}}}))


class PlainDataTests(unittest.TestCase):
    def test_yaml_json_reject_duplicates_templates_tags_and_aliases(self):
        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder) / "data.yml"
            for source in [
                'a: 1\na: 2\n', '{"a":1,"a":2}', 'a: "{{ lookup(\'pipe\',\'id\') }}"',
                'a: &x [1]\nb: *x', 'a: !!python/object:os.system id', '1: value', 'a: 2026-11-01',
            ]:
                path.write_text(source)
                with self.subTest(source=source), self.assertRaises(ValueError):
                    read_data(path)
            path.write_text('schema_version: 1\noptions:\n  languages:\n    tools:\n      python: "3"\n')
            self.assertEqual(read_data(path)["options"]["languages"]["tools"], {"python": "3"})


if __name__ == "__main__":
    unittest.main()
