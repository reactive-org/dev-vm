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

    def test_developer_docker_selection_requests_native_sudoless_opt_in(self):
        self.assertEqual(Resolver().resolve(features=["docker"])["options"]["docker"], {"access": "native"})
        self.assertNotIn("docker", Resolver().resolve(profiles=["developer"])["features"])
        for profile in ("developer", "web", "project-managed"):
            plan = Resolver().resolve(profiles=[profile], features=["docker"])
            self.assertEqual(plan["options"]["docker"], {"access": "sudoless"})
            self.assertTrue(any("root-equivalent" in item for item in plan["effects"]["files"]))
            native = Resolver().resolve(profiles=[profile], features=["docker"], overrides={"docker": {"access": "native"}})
            self.assertEqual(native["options"]["docker"], {"access": "native"})
        for value in (True, None, "", "group", "sudoless;id"):
            with self.subTest(access=value), self.assertRaises(ProfileError):
                Resolver().resolve(features=["docker"], overrides={"docker": {"access": value}})

    def test_workstation_shell_defaults_to_zsh_with_selection_and_legacy_overrides(self):
        default = Resolver().resolve()
        self.assertEqual(default["options"]["workstation"]["shell"], "zsh")
        self.assertIn("zsh", default["packages"])
        self.assertIn("starship", default["packages"])
        self.assertIn("git", default["packages"])
        self.assertTrue(default["options"]["workstation"]["oh_my_zsh"])
        self.assertTrue(default["options"]["workstation"]["starship"])
        self.assertEqual(default["effects"]["sources"][0]["url"], "https://github.com/ohmyzsh/ohmyzsh.git")
        self.assertEqual(launcher.plan_variables(default)["omarchy_shell"], "zsh")
        for selected in ("bash", "keep"):
            plan = Resolver().resolve(setup_file=self.setup(options={"workstation": {"shell": selected}}))
            self.assertEqual(plan["options"]["workstation"]["shell"], selected)
            self.assertEqual(launcher.plan_variables(plan)["omarchy_shell"], selected)
            self.assertNotIn("zsh", plan["packages"])
            self.assertNotIn("starship", plan["packages"])
            self.assertEqual(plan["effects"]["sources"], [])
        legacy = launcher.overrides({"omarchy_shell": "bash"})
        plan = Resolver().resolve(setup_file=self.setup(options={"workstation": {"shell": "zsh"}}), overrides=legacy)
        self.assertEqual(plan["options"]["workstation"]["shell"], "bash")
        for invalid in ("fish", "/bin/zsh", "zsh;id", "", None, ["zsh"]):
            with self.subTest(shell=invalid), self.assertRaises(ProfileError):
                Resolver().resolve(setup_file=self.setup(options={"workstation": {"shell": invalid}}))

    def test_zsh_extras_resolve_independently_with_strict_boolean_overrides(self):
        for omz, starship in ((True, True), (True, False), (False, True), (False, False)):
            plan = Resolver().resolve(overrides=launcher.overrides({"omarchy_oh_my_zsh": omz, "omarchy_starship": starship}))
            self.assertEqual("starship" in plan["packages"], starship)
            self.assertEqual("git" in plan["packages"], omz)
            self.assertEqual(bool(plan["effects"]["sources"]), omz)
            self.assertEqual(launcher.plan_variables(plan)["omarchy_oh_my_zsh"], omz)
            self.assertEqual(launcher.plan_variables(plan)["omarchy_starship"], starship)
        for field in ("oh_my_zsh", "starship"):
            for value in ("false", 1, None, []):
                with self.subTest(field=field, value=value), self.assertRaises(ProfileError):
                    Resolver().resolve(overrides={"workstation": {field: value}})

    def test_shell_configuration_round_trips_selection_legacy_vars_and_effects(self):
        config = {"oh_my_zsh_plugins": ["git", "docker", "docker-compose"], "oh_my_zsh_update_mode": "disabled",
                  "starship_config": "add_newline = false\n[character]\nsuccess_symbol = '[❯](green)'\n"}
        plan = Resolver().resolve(setup_file=self.setup(options={"workstation": config}))
        for name, value in config.items():
            self.assertEqual(plan["options"]["workstation"][name], value)
            self.assertEqual(launcher.plan_variables(plan)["omarchy_" + name], value)
        legacy = launcher.overrides({"omarchy_" + name: value for name, value in config.items()})
        self.assertEqual(legacy["workstation"], config)
        self.assertTrue(any(".config/dev-vm/starship.toml" in path for path in plan["effects"]["files"]))
        disabled = Resolver().resolve(overrides={"workstation": {**config, "starship": False}})
        self.assertFalse(any(".config/dev-vm/starship.toml" in path for path in disabled["effects"]["files"]))
        default = Resolver().resolve()["options"]["workstation"]
        self.assertIsNone(default["oh_my_zsh_plugins"])
        self.assertEqual(default["oh_my_zsh_update_mode"], "reminder")
        self.assertEqual(default["starship_config"], "")

    def test_developer_profiles_inherit_the_compact_prompt_without_extra_configuration(self):
        expected = read_data(ROOT / "omarchy/examples/setup.yml")["options"]["workstation"]["starship_config"]
        for profile in ("developer", "web", "python", "project-managed"):
            with self.subTest(profile=profile):
                plan = Resolver().resolve(profiles=[profile])
                self.assertEqual(plan["options"]["workstation"]["starship_config"], expected)
                self.assertEqual(launcher.plan_variables(plan)["omarchy_starship_config"], expected)
                self.assertTrue(any(".config/dev-vm/starship.toml" in path for path in plan["effects"]["files"]))
                unrelated = Resolver().resolve(profiles=[profile], overrides={"workstation": {"font_size": "13"}})
                self.assertEqual(unrelated["options"]["workstation"]["starship_config"], expected)
        project = Resolver().resolve(setup_file=ROOT / "omarchy/examples/project-managed.yml")
        self.assertEqual(project["options"]["workstation"]["starship_config"], expected)
        self.assertEqual(Resolver().resolve()["options"]["workstation"]["starship_config"], "")

    def test_developer_prompt_can_be_replaced_emptied_or_disabled_with_legacy_precedence(self):
        custom = "format = '$character'\n"
        for profile in ("developer", "web", "python", "project-managed"):
            for text in (custom, ""):
                with self.subTest(profile=profile, custom=text):
                    path = self.setup(options={"workstation": {"starship_config": text}})
                    plan = Resolver().resolve(profiles=[profile], setup_file=path)
                    self.assertEqual(plan["options"]["workstation"]["starship_config"], text)
                    self.assertEqual(any(".config/dev-vm/starship.toml" in p for p in plan["effects"]["files"]), bool(text))
            disabled = Resolver().resolve(profiles=[profile], overrides={"workstation": {"starship": False}})
            self.assertNotIn("starship", disabled["packages"])
            self.assertFalse(any(".config/dev-vm/starship.toml" in p for p in disabled["effects"]["files"]))
            for text in (custom, ""):
                plan = Resolver().resolve(profiles=[profile], setup_file=self.setup(
                    options={"workstation": {"starship_config": "format = '$directory$character'"}}),
                    overrides=launcher.overrides({"omarchy_starship_config": text}))
                self.assertEqual(plan["options"]["workstation"]["starship_config"], text)

    def test_shell_configuration_rejects_invalid_names_modes_and_toml_locally(self):
        invalid = [{"oh_my_zsh_plugins": value} for value in
                   ("git", ["git", "git"], ["../git"], ["$(id)"], ["git;id"], ["git\nwhoami"], [1])]
        invalid += [{"oh_my_zsh_update_mode": value} for value in (None, [], True, "bogus", "auto;id")]
        invalid += [{"starship_config": value} for value in (None, {}, True, "bad = [", "a=1\na=2", "#" * 65537)]
        for config in invalid:
            with self.subTest(config=str(config)[:100]), self.assertRaises(ProfileError):
                Resolver().resolve(overrides={"workstation": config})

    def test_missing_toml_parser_only_blocks_explicit_starship_configuration(self):
        with mock.patch.dict(sys.modules, {"tomllib": None}):
            self.assertEqual(Resolver().resolve()["options"]["workstation"]["starship_config"], "")
            with self.assertRaisesRegex(ProfileError, "Python 3.11"):
                Resolver().resolve(overrides={"workstation": {"starship_config": "add_newline = false"}})
            with self.assertRaisesRegex(ProfileError, "Python 3.11"):
                Resolver().resolve(profiles=["developer"])
            opted_out = Resolver().resolve(profiles=["developer"], overrides={"workstation": {"starship_config": ""}})
            self.assertEqual(opted_out["options"]["workstation"]["starship_config"], "")
            for config in ({"starship": False}, {"shell": "bash"}, {"shell": "keep"}):
                plan = Resolver().resolve(profiles=["developer"], overrides={"workstation": config})
                self.assertNotIn("starship", plan["packages"])

    def test_selected_profile_prompt_toml_is_validated_after_overrides(self):
        path = self.catalogue(profiles={"bad": {"extends": ["builtin.developer"],
                                              "options": {"workstation": {"starship_config": "bad = ["}}}})
        with self.assertRaisesRegex(ProfileError, "Invalid starship_config TOML"):
            Resolver().resolve(profiles=["example.bad"], catalogues=[path])
        repaired = Resolver().resolve(profiles=["example.bad"], catalogues=[path],
                                      overrides={"workstation": {"starship_config": ""}})
        self.assertEqual(repaired["options"]["workstation"]["starship_config"], "")

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
