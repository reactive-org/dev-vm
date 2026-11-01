import argparse
import contextlib
import importlib.util
import io
import json
import os
import shlex
import shutil
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))
import omarchy_playbook as PLAYBOOK


class LauncherTests(unittest.TestCase):
    def guest(self):
        return {"id": "B909099C-8965-4DC2-BE0E-0392269E798B", "active": True,
                "ssh": {"enabled": True, "status": "ready", "user": "owner", "port": 2224}}

    def test_feature_selection_is_explicit_and_rejects_unknown_or_duplicate_names(self):
        self.assertEqual(PLAYBOOK.features("browsers,docker"), ["browsers", "docker"])
        for value in ("", "browsers,", "docker,docker", "--inventory", "all", "ubuntu"):
            with self.subTest(value=value), self.assertRaises(argparse.ArgumentTypeError):
                PLAYBOOK.features(value)

    def test_pinned_connection_and_non_root_owner_are_preserved(self):
        connection = PLAYBOOK.manager.ManagedSSH(Path("/manager path/config"), "omarchy-example")
        values = PLAYBOOK.connection_values(self.guest(), connection)
        self.assertEqual(shlex.split(values["ansible_ssh_common_args"]), ["-F", "/manager path/config"])
        self.assertEqual(values["ansible_host"], connection.alias)
        self.assertFalse(values["ansible_become"])
        self.assertEqual(values["ansible_python_interpreter"], "/usr/bin/python3")
        self.assertIn("ControlMaster=no", values["ansible_ssh_args"])
        self.assertIn("StrictHostKeyChecking=yes", values["ansible_ssh_args"])
        self.assertTrue(values["ansible_host_key_checking"])
        self.assertEqual(values["ansible_private_key_file"], "")
        guest = self.guest()
        guest["ssh"]["user"] = "root"
        with self.assertRaises(PLAYBOOK.manager.WorkstationError):
            PLAYBOOK.connection_values(guest, connection)

    def test_stopped_guest_is_refused_without_start_or_resource_update(self):
        guest = {**self.guest(), "active": False}
        with mock.patch.object(PLAYBOOK.manager, "manager_version"), \
                mock.patch.object(PLAYBOOK.manager, "list_guests", return_value=[guest]), \
                mock.patch.object(PLAYBOOK.manager, "find_guest", return_value=guest), \
                mock.patch.object(PLAYBOOK.manager, "immutable_guest_errors", return_value=[]), \
                mock.patch.object(PLAYBOOK.manager, "cli_call") as cli:
            with self.assertRaisesRegex(PLAYBOOK.manager.WorkstationError, "never starts"):
                PLAYBOOK.ready_connection(argparse.Namespace(vm_name="fixture"))
            cli.assert_not_called()

    def run_launcher(self, *, check=False, failure=None, grant_failure=False):
        args = argparse.Namespace(cli_path=Path("/manager/bin"), vm_name="fixture", features=["docker"],
                                  vars_file=None, check=check, plan=False, yes=True)
        connection = PLAYBOOK.manager.ManagedSSH(Path("/manager/config"), "omarchy-example")
        seen = {}

        def execute(command, **kwargs):
            inventory = Path(command[command.index("-i") + 1])
            variables = Path(command[command.index("--extra-vars") + 1][1:])
            seen["inventory"] = json.loads(inventory.read_text())
            seen["variables"] = json.loads(variables.read_text())
            seen["command"] = command
            self.assertEqual(inventory.stat().st_mode & 0o777, 0o600)
            seen["path"] = inventory
            if failure:
                raise failure
            return subprocess.CompletedProcess(command, 0)

        with mock.patch.object(PLAYBOOK.sys, "platform", "darwin"), \
                mock.patch.object(PLAYBOOK.platform, "machine", return_value="arm64"), \
                mock.patch.object(PLAYBOOK.manager, "require_file", side_effect=lambda p, *_a, **_kw: p), \
                mock.patch.object(PLAYBOOK.shutil, "which", side_effect=lambda name: "/existing/" + name), \
                mock.patch.object(PLAYBOOK, "read_options", return_value={"omarchy_browsers": ["firefox"]}), \
                mock.patch.object(PLAYBOOK, "ready_connection", return_value=(self.guest(), connection)), \
                mock.patch.object(PLAYBOOK.manager, "confirm"), \
                mock.patch.object(PLAYBOOK.manager, "enable_bootstrap_sudo",
                                  side_effect=PLAYBOOK.manager.WorkstationError("partial grant") if grant_failure else None) as enable, \
                mock.patch.object(PLAYBOOK.manager, "disable_bootstrap_sudo") as disable, \
                mock.patch.object(PLAYBOOK.subprocess, "run", side_effect=execute), \
                contextlib.redirect_stdout(io.StringIO()):
            if failure or grant_failure:
                with self.assertRaises(BaseException):
                    PLAYBOOK.playbook(args)
            else:
                PLAYBOOK.playbook(args)
            if check:
                enable.assert_not_called()
                disable.assert_not_called()
            else:
                enable.assert_called_once_with(connection)
                disable.assert_called_once_with(connection)
        if seen:
            self.assertFalse(seen["path"].exists())
        return seen

    def test_real_apply_uses_private_inventory_and_revokes_grant(self):
        seen = self.run_launcher()
        self.assertEqual(seen["variables"]["omarchy_features"], ["docker"])
        self.assertEqual(seen["variables"]["ansible_connection"], "ssh")

    def test_check_mode_never_enables_or_revokes_a_sudo_grant(self):
        self.assertIn("--check", self.run_launcher(check=True)["command"])

    def test_failure_interrupt_and_partial_grant_all_attempt_cleanup(self):
        for error in (subprocess.CalledProcessError(2, ["ansible"]), KeyboardInterrupt()):
            self.run_launcher(failure=error)
        self.run_launcher(grant_failure=True)


@unittest.skipUnless(shutil.which("ansible-playbook") and shutil.which("ansible-inventory"), "Ansible is not installed")
class AnsibleContractTests(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory(prefix="omarchy-ansible-test-")
        self.addCleanup(self.temporary.cleanup)
        self.folder = Path(self.temporary.name)
        self.inventory = self.folder / "inventory.json"
        executable = Path(shutil.which("ansible-playbook")).resolve()
        interpreter = executable.read_text().splitlines()[0][2:].strip()
        if not Path(interpreter).is_file():
            interpreter = sys.executable
        self.inventory.write_text(json.dumps({"all": {"children": {"omarchy": {"hosts": {
            "fixture": {"ansible_connection": "local", "ansible_python_interpreter": interpreter,
                        "ansible_remote_tmp": str(self.folder / "remote")}
        }}}}}))
        self.env = {**os.environ, "ANSIBLE_CONFIG": str(ROOT / "ansible.cfg"),
                    "ANSIBLE_LOCAL_TEMP": str(self.folder / "local")}

    def ansible(self, *args, expected=0):
        result = subprocess.run([shutil.which("ansible-playbook"), "-i", str(self.inventory), *map(str, args)],
                                cwd=ROOT, env=self.env, text=True, capture_output=True)
        self.assertEqual(result.returncode, expected, result.stdout + result.stderr)
        return result.stdout

    def test_each_tag_selects_only_its_feature(self):
        for selected in PLAYBOOK.FEATURES:
            output = self.ansible(ROOT / "site.yml", "--list-tasks", "--tags", selected)
            self.assertIn(f"Ensure selected {selected} configuration", output)
            for other in set(PLAYBOOK.FEATURES) - {selected}:
                self.assertNotIn(f"Ensure selected {other} configuration", output)

    def test_actual_ansible_check_mode_passes_check_flag_to_read_only_helper(self):
        helper = self.folder / "apply-features.py"
        helper.write_text('''import sys,json
assert '--check' in sys.argv, 'check mode was lost'
assert json.load(sys.stdin) == {'browsers': ['chromium']}
print(json.dumps({'changed':False,'verified_check_flag':True}))
''')
        play = self.folder / "check.yml"
        play.write_text('''---
- hosts: omarchy
  gather_facts: false
  vars:
    omarchy_payload:
      path: "''' + str(self.folder) + '''"
    omarchy_browsers: [chromium]
  tasks:
    - ansible.builtin.import_role:
        name: omarchy_browsers
''')
        output = self.ansible(play, "--check")
        self.assertIn('verified_check_flag', output)
        self.assertIn('changed=0', output)

    def test_workstation_role_receives_default_and_overridden_shell_in_check_mode(self):
        play = self.folder / "shell.yml"
        play.write_text('''---
- hosts: omarchy
  gather_facts: false
  tasks:
    - ansible.builtin.import_role:
        name: omarchy_workstation
''')
        helper = self.folder / "apply-features.py"
        parameters = self.folder / "shell.json"
        for selected in ("zsh", "bash", "keep"):
            helper.write_text("import sys,json\nassert '--check' in sys.argv\n"
                              "config=json.load(sys.stdin)\nassert config['shell']==" + repr(selected) + "\n"
                              "print(json.dumps({'changed':False,'shell_checked':True}))\n")
            plan = PLAYBOOK.Resolver().resolve(overrides={"workstation": {"shell": selected}})
            values = PLAYBOOK.plan_variables(plan)
            values["omarchy_payload"] = {"path": str(self.folder)}
            parameters.write_text(json.dumps(values))
            with self.subTest(shell=selected):
                output = self.ansible(play, "--check", "--extra-vars", "@" + str(parameters))
                self.assertIn("shell_checked", output)
                self.assertIn("changed=0", output)

    def test_extension_tag_selects_only_the_requested_data_operation_in_check_mode(self):
        helper = self.folder / "apply-features.py"
        helper.write_text('''import sys,json
assert '--check' in sys.argv and '--extension' in sys.argv
assert sys.argv[sys.argv.index('--feature')+1] == 'example.api'
assert json.load(sys.stdin) == {'packages':['jq'],'tools':{}}
print(json.dumps({'changed':False,'extension_checked':True}))
''')
        play = self.folder / "extension.yml"
        play.write_text('''---
- hosts: omarchy
  gather_facts: false
  vars:
    omarchy_payload:
      path: "''' + str(self.folder) + '''"
    omarchy_extensions:
      - {name: example.api, config: {packages: [jq], tools: {}}}
      - {name: example.other, config: {packages: [curl], tools: {}}}
    omarchy_selected_features: [example.api, example.other]
  tasks:
    - ansible.builtin.include_tasks:
        file: "''' + str(ROOT / 'roles/omarchy_extension/tasks/main.yml') + '''"
        apply:
          tags: "{{ omarchy_extension.name }}"
      loop: "{{ omarchy_extensions }}"
      loop_control:
        loop_var: omarchy_extension
      when: "'all' in ansible_run_tags or omarchy_extension.name in ansible_run_tags"
      tags: [always]
''')
        output = self.ansible(play, "--tags", "example.api", "--check")
        self.assertIn("extension_checked", output)
        self.assertIn("changed=0", output)

    def test_profile_plan_is_passed_to_an_actual_ansible_preflight(self):
        plan = PLAYBOOK.Resolver().resolve(profiles=["python"])
        variables = PLAYBOOK.plan_variables(plan)
        variables["ansible_facts"] = {"system": "Linux", "architecture": "aarch64", "user_id": "fixture"}
        commands = self.folder / "bin"
        commands.mkdir()
        executable = commands / "pacman"
        executable.write_text("#!/bin/sh\nexit 0\n")
        executable.chmod(0o755)
        self.env["PATH"] = str(commands) + os.pathsep + self.env["PATH"]
        self.env["TMPDIR"] = str(self.folder)
        path = self.folder / "plan.json"
        path.write_text(json.dumps(variables))
        output = self.ansible(ROOT / "site.yml", "--tags", ",".join(plan["features"]), "--check",
                              "--extra-vars", "@" + str(path), expected=2)
        self.assertIn("Preflight all resolved feature requirements", output)
        self.assertIn("Run as the non-root owner", output)
        self.assertIn("Remove the temporary feature payload", output)
        self.assertFalse(list(self.folder.glob("dev-omarchy-features.*")))

    def test_actual_site_cleans_payload_after_a_rejected_guest_helper(self):
        commands = self.folder / "bin"
        commands.mkdir()
        pacman = commands / "pacman"
        pacman.write_text("#!/bin/sh\nexit 0\n")
        pacman.chmod(0o755)
        self.env["PATH"] = str(commands) + os.pathsep + self.env["PATH"]
        self.env["TMPDIR"] = str(self.folder)
        variables = self.folder / "facts.json"
        variables.write_text(json.dumps({
            "ansible_facts": {"system": "Linux", "architecture": "aarch64", "user_id": "fixture"},
            "omarchy_features": ["browsers"],
        }))
        output = self.ansible(ROOT / "site.yml", "--tags", "browsers", "--check",
                              "--extra-vars", "@" + str(variables), expected=2)
        self.assertIn("Create temporary feature payload", output)
        self.assertIn("Remove the temporary feature payload", output)
        self.assertIn("Run as the non-root owner", output)
        self.assertFalse(list(self.folder.glob("dev-omarchy-features.*")))

    def test_configuration_file_is_isolated_and_connection_or_internal_overrides_are_rejected(self):
        value = PLAYBOOK.read_options(ROOT / "omarchy/examples/features.yml", shutil.which("ansible-inventory"), self.folder)
        self.assertEqual(value["omarchy_browsers"], ["chromium", "firefox"])
        self.assertFalse(set(value) - PLAYBOOK.OPTIONS)
        for name in ("ansible_connection", "ansible_ssh_common_args", "omarchy_payload", "omarchy_features"):
            with tempfile.TemporaryDirectory(dir=self.folder) as child:
                path = Path(child) / "unsafe.yml"
                path.write_text(name + ': unsafe\n')
                with self.subTest(name=name), self.assertRaises(PLAYBOOK.manager.WorkstationError):
                    PLAYBOOK.read_options(path, shutil.which("ansible-inventory"), Path(child))


if __name__ == "__main__":
    unittest.main()
