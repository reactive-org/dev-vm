import argparse
import contextlib
import io
import json
import os
import shutil
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))
import omarchy_setup as SETUP


class SetupFixture(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory(prefix="omarchy-setup-test-")
        self.addCleanup(self.temporary.cleanup)
        self.root = Path(self.temporary.name).resolve()

    def file(self, name, content):
        path = self.root / name
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(content)
        return path

    def manifest(self, **values):
        self.file("vm.json", json.dumps({"schema_version": 1, "id": "fixture", **values}))
        return SETUP.Setup(self.root, "vm.json")

    def args(self, **values):
        return argparse.Namespace(command="apply", repo=self.root, manifest="vm.json", vm_name="fixture",
                                  cli_path=None, manager_app=None, cpus=None, memory_gib=None, disk_gib=None,
                                  factory=None, tasks=None, trust_tasks=False, check=False, check_tasks=False,
                                  dotfiles_conflict="fail", yes=True, **values)


class RepositoryTests(SetupFixture):
    def test_separate_repo_composes_profiles_catalogues_layout_and_private_assets(self):
        self.file("catalogue.json", json.dumps({"schema_version": 1, "namespace": "team", "features": {
            "extra": {"description": "Extra tools", "packages": ["jq"], "mise": {}}}}))
        self.file("layouts/coding.lua", "-- layout\n")
        self.file("private-token", "must not be selected")
        self.file(".git/config", "must not be selected")
        setup = self.manifest(setup={"profiles": ["project-managed"], "catalogues": ["catalogue.json"],
                                    "features": {"enable": ["team.extra"]},
                                    "options": {"workstation": {"layout": "layouts/coding.lua"}}})
        self.assertIn("team.extra", setup.plan["features"])
        self.assertEqual(setup.plan["mise"], {})
        self.assertEqual(setup.plan["options"]["workstation"]["layout"], str(self.root / "layouts/coding.lua"))
        with setup.snapshot() as frozen:
            self.assertFalse((frozen.root / "private-token").exists())
            self.assertFalse((frozen.root / ".git").exists())
            self.assertEqual(frozen.proposal()["features"]["options"]["workstation"]["layout"], "layouts/coding.lua")

    def test_snapshot_uses_reviewed_bytes_and_detects_edits_additions_removals_and_modes(self):
        path = self.file("assets/config", "before")
        setup = self.manifest(assets=["assets"])
        with setup.snapshot() as frozen:
            path.write_text("after")
            self.assertEqual((frozen.root / "assets/config").read_text(), "before")
            with self.assertRaisesRegex(ValueError, "changed after planning"):
                setup.verify()
        path.write_text("before")
        self.file("assets/new", "new")
        with self.assertRaises(ValueError):
            setup.verify()
        (self.root / "assets/new").unlink()
        path.chmod(0o700)
        with self.assertRaises(ValueError):
            setup.verify()
        path.unlink()
        with self.assertRaises(ValueError):
            setup.verify()

    def test_source_escapes_symlinks_git_and_unsupported_files_are_refused(self):
        self.file("asset", "data")
        (self.root / "link").symlink_to(self.root / "asset")
        self.file("nested/.git/config", "git data")
        os.mkfifo(self.root / "pipe")
        for path in ("../asset", "/etc/passwd", "link", "nested", "pipe", "./asset", "asset/../asset"):
            with self.subTest(path=path), self.assertRaises(ValueError):
                self.manifest(assets=[path])
        with self.assertRaises(ValueError):
            self.manifest(setup={"catalogues": ["../outside.yml"]})

    def test_manifest_validation_rejects_unknown_fields_and_invalid_types(self):
        for values in ({"inventory": "custom"}, {"schema_version": 2}, {"id": "../other"},
                       {"vm": {"cpus": True}}, {"vm": {"memory_gib": 2}},
                       {"vm": {"disk_gib": 32}}, {"vm": {"ssh": {}}},
                       {"vm": {"packages": ["pkg:bad;command"]}}, {"vm": {"factory": "bad\npath"}},
                       {"vars": []}, {"tasks": "tasks.yml"}):
            with self.subTest(values=values), self.assertRaises(ValueError):
                self.manifest(**values)

    def test_custom_task_yaml_is_opaque_until_explicit_execution(self):
        self.file("tasks/main.yml", "- ansible.builtin.debug:\n    msg: '{{ workstation_home }}'\n")
        setup = self.manifest(tasks=[{"name": "custom", "file": "tasks/main.yml"}])
        self.assertEqual(setup.tasks[0]["tag"], "setup.custom")
        for selected in ("missing", "custom,custom"):
            with self.assertRaises(ValueError):
                SETUP.task_selection(setup, selected)
        self.assertEqual(SETUP.task_selection(setup, ""), [])
        self.assertEqual(SETUP.task_selection(setup, "custom"), setup.tasks)
        with self.assertRaises(ValueError):
            self.manifest(tasks=[{"name": "custom", "file": "tasks/main.yml"}] * 2)

    def test_dotfile_tree_expands_to_explicit_files_and_rejects_overlaps(self):
        self.file("dotfiles/nvim/init.lua", "-- personal\n")
        setup = self.manifest(dotfiles=[{"source": "dotfiles/nvim", "target": "~/.config/nvim", "mode": "0600"}])
        self.assertEqual(setup.dotfiles[0]["target"], ".config/nvim/init.lua")
        self.assertEqual(setup.dotfiles[0]["mode"], 0o600)
        with self.assertRaisesRegex(ValueError, "overlap"):
            self.manifest(dotfiles=[{"source": "dotfiles/nvim", "target": ".config/nvim"},
                                    {"source": "dotfiles/nvim/init.lua", "target": ".config/nvim/init.lua"}])

    def test_plan_never_contacts_manager_or_evaluates_external_tasks(self):
        self.file("tasks.yml", "not even valid YAML: [")
        self.manifest(tasks=[{"name": "custom", "file": "tasks.yml"}])
        args = self.args()
        args.command = "plan"
        output = io.StringIO()
        with mock.patch.object(SETUP.manager, "cli_call") as manager, \
                mock.patch.object(SETUP.subprocess, "run") as execute, contextlib.redirect_stdout(output):
            SETUP.run(args)
        manager.assert_not_called()
        execute.assert_not_called()
        self.assertEqual(json.loads(output.getvalue())["tasks"][0]["file"], "tasks.yml")

    def test_untrusted_tasks_fail_before_manager_or_sudo_even_with_yes(self):
        self.file("tasks.yml", "[]")
        self.manifest(tasks=[{"name": "custom", "file": "tasks.yml"}])
        with mock.patch.object(SETUP.playbook, "ready_connection") as ready, \
                mock.patch.object(SETUP.manager, "enable_bootstrap_sudo") as sudo, \
                contextlib.redirect_stdout(io.StringIO()), self.assertRaisesRegex(ValueError, "--trust-tasks"):
            SETUP.run(self.args())
        ready.assert_not_called()
        sudo.assert_not_called()

    def test_bootstrap_merges_manifest_and_explicit_resources_without_selecting_runtimes(self):
        setup = self.manifest(vm={"cpus": 4, "memory_gib": 8, "disk_gib": 128},
                              setup={"profiles": ["project-managed"]})
        args = self.args()
        args.cpus = 12
        native = SETUP.bootstrap_args(setup, args)
        self.assertEqual((native.cpus, native.memory_gib, native.disk_gib), (12, 8, 128))
        self.assertIsNone(native.factory)
        self.assertEqual(native.packages, ())

    def test_execute_uses_private_pinned_inventory_and_keeps_check_tasks_opt_in(self):
        self.file("tasks.yml", "[]")
        setup = self.manifest(tasks=[{"name": "custom", "file": "tasks.yml"}])
        guest = {"ssh": {"user": "owner", "port": 2224}}
        connection = SETUP.manager.ManagedSSH(Path("/manager/config"), "omarchy-fixture")
        calls = []

        def execute(command, **kwargs):
            values = [json.loads(Path(command[i + 1][1:]).read_text())
                      for i, value in enumerate(command) if value == "--extra-vars"]
            inventory = Path(command[command.index("-i") + 1])
            self.assertEqual(inventory.stat().st_mode & 0o777, 0o600)
            host = json.loads(inventory.read_text())["all"]["children"]["omarchy"]["hosts"]["workstation"]
            if str(ROOT / 'setup.yml') in command:
                self.assertNotIn('ansible_become', host, 'Custom task keywords must be able to request become')
            else:
                self.assertFalse(host['ansible_become'])
            calls.append((command, values))

        args = self.args()
        args.check = True
        with mock.patch.object(SETUP.subprocess, "run", side_effect=execute), \
                mock.patch.object(SETUP.manager, "install_selected_software") as install:
            SETUP.execute(setup, args, guest, connection, "/existing/ansible-playbook")
        install.assert_not_called()
        self.assertEqual(calls[-1][1][-1]["omarchy_setup_tasks"], [])
        self.assertIn("--check", calls[-1][0])
        self.assertEqual(calls[-1][1][0]["ansible_host"], "omarchy-fixture")
        self.assertNotIn("ansible_become", calls[-1][1][0])
        args.check_tasks = True
        with self.assertRaisesRegex(ValueError, "--trust-tasks"):
            SETUP.execute(setup, args, guest, connection, "/existing/ansible-playbook")
        args.trust_tasks = True
        with mock.patch.object(SETUP.subprocess, "run", side_effect=execute):
            SETUP.execute(setup, args, guest, connection, "/existing/ansible-playbook")
        self.assertEqual(calls[-1][1][-1]["omarchy_setup_tasks"][0]["name"], "custom")

    def test_apply_failure_and_partial_grant_revoke_without_restarting(self):
        self.manifest()
        for stage in ("grant", "execute", "interrupt", "success"):
            with self.subTest(stage=stage), \
                    mock.patch.object(SETUP.sys, "platform", "darwin"), \
                    mock.patch.object(SETUP.platform, "machine", return_value="arm64"), \
                    mock.patch.object(SETUP.shutil, "which", return_value="/existing/ansible-playbook"), \
                    mock.patch.object(SETUP.manager, "installed_cli", return_value=Path("/manager")), \
                    mock.patch.object(SETUP.manager, "require_file", side_effect=lambda path, *_a, **_kw: path), \
                    mock.patch.object(SETUP.playbook, "ready_connection", return_value=({}, mock.sentinel.connection)), \
                    mock.patch.object(SETUP.manager, "confirm"), \
                    mock.patch.object(SETUP.manager, "enable_bootstrap_sudo", side_effect=ValueError("partial") if stage == "grant" else None), \
                    mock.patch.object(SETUP.manager, "disable_bootstrap_sudo") as revoke, \
                    mock.patch.object(SETUP.manager, "restart_guest") as restart, \
                    mock.patch.object(SETUP, "execute", side_effect=KeyboardInterrupt() if stage == "interrupt" else ValueError("failed") if stage == "execute" else None), \
                    contextlib.redirect_stdout(io.StringIO()):
                if stage == "success":
                    SETUP.run(self.args())
                else:
                    with self.assertRaises(BaseException):
                        SETUP.run(self.args())
                revoke.assert_called_once_with(mock.sentinel.connection)
                restart.assert_not_called()

    def test_bootstrap_custom_stage_failure_revokes_and_prevents_restart(self):
        setup = self.manifest()
        native = SETUP.bootstrap_args(setup, self.args())
        native.setup_apply = mock.Mock(side_effect=ValueError("custom failed"))
        with mock.patch.object(SETUP.manager, "ready_guest", return_value=({}, "version")), \
                mock.patch.object(SETUP.manager, "managed_ssh", return_value=mock.sentinel.connection), \
                mock.patch.object(SETUP.manager, "enable_bootstrap_sudo"), \
                mock.patch.object(SETUP.manager, "update_guest_system"), \
                mock.patch.object(SETUP.manager, "apply_workstation"), \
                mock.patch.object(SETUP.manager, "disable_bootstrap_sudo") as revoke, \
                mock.patch.object(SETUP.manager, "restart_guest") as restart:
            with self.assertRaisesRegex(ValueError, "custom failed"):
                SETUP.manager.bootstrap_command(native)
            revoke.assert_called_once_with(mock.sentinel.connection)
            restart.assert_not_called()

    def test_changed_inputs_after_confirmation_stop_before_grant(self):
        self.manifest()
        with mock.patch.object(SETUP.sys, "platform", "darwin"), \
                mock.patch.object(SETUP.platform, "machine", return_value="arm64"), \
                mock.patch.object(SETUP.shutil, "which", return_value="/existing/ansible-playbook"), \
                mock.patch.object(SETUP.manager, "installed_cli", return_value=Path("/manager")), \
                mock.patch.object(SETUP.manager, "require_file", side_effect=lambda path, *_a, **_kw: path), \
                mock.patch.object(SETUP.playbook, "ready_connection", return_value=({}, mock.sentinel.connection)), \
                mock.patch.object(SETUP.manager, "confirm", side_effect=lambda _: self.file("vm.json", "changed")), \
                mock.patch.object(SETUP.manager, "enable_bootstrap_sudo") as grant, \
                contextlib.redirect_stdout(io.StringIO()):
            with self.assertRaisesRegex(ValueError, "changed after planning"):
                SETUP.run(self.args())
            grant.assert_not_called()

    def test_plan_resource_and_factory_overrides_match_bootstrap_interpretation(self):
        self.manifest(vm={"cpus": 4})
        args = self.args()
        args.command, args.cpus, args.factory = "plan", 12, "./factory.img.zst"
        output = io.StringIO()
        with contextlib.redirect_stdout(output):
            SETUP.run(args)
        proposed = json.loads(output.getvalue())
        self.assertEqual(proposed["vm"]["cpus"], 12)
        self.assertEqual(proposed["vm"]["factory"], str(Path("factory.img.zst").resolve()))

    def test_make_routes_external_bootstrap_without_overriding_manifest_defaults(self):
        command = ["make", "-n", "bootstrap-omarchy-vm"]
        legacy = subprocess.run(command, cwd=ROOT, capture_output=True, text=True, check=True).stdout
        self.assertIn("scripts/omarchy_vm_manager.py", legacy)
        self.assertNotIn("scripts/omarchy_setup.py", legacy)
        external = subprocess.run(command + ["OMARCHY_SETUP_REPO=/separate setup", "OMARCHY_VM_CPUS=4"],
                                  cwd=ROOT, capture_output=True, text=True, check=True).stdout
        self.assertIn("scripts/omarchy_setup.py bootstrap", external)
        self.assertIn('--repo "/separate setup"', external)
        self.assertIn('--cpus "4"', external)
        self.assertNotIn('--memory-gib "20"', external)

    def test_explicit_legacy_overrides_are_refused_in_external_mode(self):
        args = self.args()
        args.unsupported_option = ["OMARCHY_VM_PACKAGES"]
        with self.assertRaisesRegex(ValueError, "legacy overrides"):
            SETUP.run(args)

    def test_bootstrap_runs_external_stage_before_revoke_restart_and_validation(self):
        setup = self.manifest()
        native = SETUP.bootstrap_args(setup, self.args())
        operations = []
        native.setup_apply = lambda *_: operations.append("external")
        native.setup_after_revoke = lambda *_: operations.append("verify-access")
        with mock.patch.object(SETUP.manager, "ready_guest", return_value=({}, "version")), \
                mock.patch.object(SETUP.manager, "managed_ssh", return_value=mock.sentinel.connection), \
                mock.patch.object(SETUP.manager, "enable_bootstrap_sudo", side_effect=lambda *_: operations.append("grant")), \
                mock.patch.object(SETUP.manager, "update_guest_system", side_effect=lambda *_: operations.append("update")), \
                mock.patch.object(SETUP.manager, "apply_workstation", side_effect=lambda *_: operations.append("preferences")), \
                mock.patch.object(SETUP.manager, "disable_bootstrap_sudo", side_effect=lambda *_: operations.append("revoke")), \
                mock.patch.object(SETUP.manager, "restart_guest", side_effect=lambda *_: operations.append("restart") or {}), \
                mock.patch.object(SETUP.manager, "check_guest_workstation", side_effect=lambda *_: operations.append("validate")), \
                contextlib.redirect_stdout(io.StringIO()):
            SETUP.manager.bootstrap_command(native)
        self.assertEqual(operations, ["grant", "update", "preferences", "external", "revoke", "verify-access", "restart", "validate"])


class DotfileTests(SetupFixture):
    def entries(self, content="configured"):
        source = self.file("source", content)
        import hashlib
        return [{"source": str(source), "target": ".config/tool/config", "mode": 0o640,
                 "sha256": hashlib.sha256(source.read_bytes()).hexdigest()}]

    def home(self):
        path = self.root / "home"
        path.mkdir(exist_ok=True)
        return path

    def test_deploy_reapply_update_and_deselection_preserve_unrelated_files(self):
        home = self.home()
        (home / "unrelated").write_text("personal")
        entries = self.entries()
        self.assertTrue(SETUP.dotfiles.deploy(home, "fixture", entries)["changed"])
        self.assertFalse(SETUP.dotfiles.deploy(home, "fixture", entries)["changed"])
        destination = home / entries[0]["target"]
        self.assertEqual(destination.stat().st_mode & 0o777, 0o640)
        self.assertTrue(SETUP.dotfiles.deploy(home, "fixture", self.entries("updated"))["changed"])
        SETUP.dotfiles.deploy(home, "fixture", [])
        self.assertEqual(destination.read_text(), "updated")
        self.assertEqual((home / "unrelated").read_text(), "personal")

    def test_edit_conflict_is_checked_before_any_write_and_backup_is_explicit(self):
        home = self.home()
        entries = self.entries()
        SETUP.dotfiles.deploy(home, "fixture", entries)
        destination = home / entries[0]["target"]
        destination.write_text("guest edit")
        first = {**entries[0], "target": "first"}
        with self.assertRaisesRegex(ValueError, "Dotfile conflict"):
            SETUP.dotfiles.deploy(home, "fixture", [first, *entries])
        self.assertFalse((home / "first").exists())
        result = SETUP.dotfiles.deploy(home, "fixture", entries, conflict="backup")
        backup = Path(result["actions"][0]["backup_path"])
        self.assertEqual(backup.read_text(), "guest edit")
        self.assertEqual(destination.read_text(), "configured")

    def test_check_mode_never_writes_state_files_or_backups(self):
        home = self.home()
        entries = self.entries()
        self.assertTrue(SETUP.dotfiles.deploy(home, "fixture", entries, check=True)["changed"])
        self.assertEqual(list(home.iterdir()), [])
        SETUP.dotfiles.deploy(home, "fixture", entries)
        destination = home / entries[0]["target"]
        destination.write_text("guest edit")
        before = {p: p.read_bytes() for p in home.rglob("*") if p.is_file()}
        SETUP.dotfiles.deploy(home, "fixture", entries, check=True, conflict="backup")
        self.assertEqual(before, {p: p.read_bytes() for p in home.rglob("*") if p.is_file()})

    def test_symlink_credential_and_other_setup_destinations_are_refused(self):
        home = self.home()
        entries = self.entries()
        (home / ".config").symlink_to(self.root, target_is_directory=True)
        with self.assertRaisesRegex(ValueError, "symlink"):
            SETUP.dotfiles.deploy(home, "fixture", entries)
        (home / ".config").unlink()
        for target in ("/etc/config", "../escape", "~other/config", ".ssh/id_rsa", ".gnupg/config", ".local/state/dev-vm/state"):
            with self.subTest(target=target), self.assertRaises(ValueError):
                SETUP.dotfiles.deploy(home, "fixture", [{**entries[0], "target": target}])
        SETUP.dotfiles.deploy(home, "fixture", entries)
        with self.assertRaisesRegex(ValueError, "another setup"):
            SETUP.dotfiles.deploy(home, "other", entries, conflict="backup")


@unittest.skipUnless(shutil.which("ansible-playbook"), "Ansible is not installed")
class ExternalAnsibleTests(unittest.TestCase):
    def test_real_ansible_dotfiles_tasks_templates_check_mode_and_idempotence(self):
        with tempfile.TemporaryDirectory(prefix="omarchy-external-ansible-") as directory:
            folder = Path(directory)
            home = folder / "home"
            home.mkdir()
            (home / '.config/git').mkdir(parents=True)
            native_git = home / '.config/git/config'
            native_git.write_text('[user]\n\tname = Native Owner\n')
            native_git.chmod(0o600)
            repo = folder / "repo"
            shutil.copytree(ROOT / "omarchy/examples/setup-repo", repo)
            setup = SETUP.Setup(repo)
            interpreter = Path(shutil.which("ansible-playbook")).resolve().read_text().splitlines()[0][2:].strip()
            inventory = folder / "inventory.json"
            inventory.write_text(json.dumps({"all": {"children": {"omarchy": {"hosts": {"fixture": {
                "ansible_connection": "local", "ansible_python_interpreter": interpreter,
                "ansible_remote_tmp": str(folder / "remote")}}}}}}))
            variables = folder / "vars.json"
            variables.write_text(json.dumps({"ansible_facts": {"user_id": "fixture", "user_gid": 1000,
                "user_dir": str(home), "architecture": "aarch64"}, "omarchy_setup_id": setup.id,
                "omarchy_setup_dir": str(repo), "omarchy_setup_vars": setup.variables,
                "omarchy_setup_files": setup.dotfiles, "omarchy_setup_tasks": setup.tasks,
                "omarchy_setup_record": {"id": setup.id}}))
            play = folder / "play.yml"
            play.write_text("---\n- hosts: omarchy\n  gather_facts: false\n  roles:\n    - omarchy_setup\n")
            command = [shutil.which("ansible-playbook"), "-i", str(inventory), str(play), "-e", "@" + str(variables)]
            env = {**os.environ, "ANSIBLE_CONFIG": str(ROOT / "ansible.cfg"), "ANSIBLE_LOCAL_TEMP": str(folder / "local")}

            def run(*flags, expected=0):
                result = subprocess.run([*command, *flags], env=env, cwd=ROOT, capture_output=True, text=True)
                self.assertEqual(result.returncode, expected, result.stdout + result.stderr)
                return result.stdout

            # External tasks are omitted by the launcher; this also checks dotfiles-only tag isolation.
            run("--check", "--tags", "dotfiles")
            self.assertEqual(native_git.read_text(), '[user]\n\tname = Native Owner\n')
            self.assertEqual([p.relative_to(home).as_posix() for p in home.rglob('*') if p.is_file()], ['.config/git/config'])
            run()
            self.assertTrue((home / "Development/Projects").is_dir())
            self.assertEqual(json.loads((home / ".config/dev-vm-example/editor.json").read_text())["editor.fontSize"], 14)
            self.assertIn("changed=0", run())
            self.assertIn("changed=0", run("--check"))
            git_result = subprocess.run(['git', 'config', '--includes', '--file', str(home / '.config/git/config'),
                                         '--get', 'init.defaultBranch'], capture_output=True, text=True)
            self.assertEqual(git_result.returncode, 0, git_result.stderr)
            self.assertEqual(git_result.stdout.strip(), 'main')
            self.assertIn('[user]\n\tname = Native Owner\n', native_git.read_text())
            self.assertEqual(native_git.stat().st_mode & 0o777, 0o600)
            (home / ".config/git/dev-vm-preferences.conf").write_text("guest edit")
            output = run("--tags", "dotfiles", expected=2)
            self.assertIn("Dotfile conflict", output)
            self.assertNotIn("A 'changed_when' expression failed", output)
            self.assertIn("Remove the temporary dotfile payload", output)
