import importlib.util
import json
import subprocess
import sys
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest import mock


REPOSITORY = Path(__file__).resolve().parents[1]
CONTROLLER_PATH = REPOSITORY / "scripts" / "omarchy_vm_manager.py"
RUNBOOK_PATH = REPOSITORY / "docs" / "omarchy-vm-manager-runbook.md"

SPEC = importlib.util.spec_from_file_location("omarchy_vm_manager", CONTROLLER_PATH)
CONTROLLER = importlib.util.module_from_spec(SPEC)
sys.modules[SPEC.name] = CONTROLLER
SPEC.loader.exec_module(CONTROLLER)

GUEST_ID = "B909099C-8965-4DC2-BE0E-0392269E798B"


def managed_guest(**overrides):
    value = {
        "active": False,
        "clipboard": True,
        "cpus": 8,
        "diskGiB": 64,
        "id": GUEST_ID,
        "immersive": False,
        "memoryMiB": 20 * 1024,
        "name": "Dev Omarchy",
        "network": {
            "addressesVerified": False,
            "guestIPs": [],
            "hostAddress": "127.0.0.1",
            "mode": "nat",
        },
        "protected": False,
        "ssh": {
            "enabled": True,
            "host": "127.0.0.1",
            "port": 2224,
            "status": "stopped",
        },
        "state": "stopped",
        "unattended": True,
    }
    value.update(overrides)
    return value


class OmarchyManagerControllerTests(unittest.TestCase):
    def test_manager_version_requires_protocol_one_and_minimum_release(self):
        args = SimpleNamespace(cli_path=Path("/manager/omarchy-vm"))
        valid = subprocess.CompletedProcess(
            [], 0, json.dumps({"commandProtocol": 1, "version": "0.6.0"}), ""
        )
        with mock.patch.object(CONTROLLER, "run", return_value=valid):
            self.assertEqual(CONTROLLER.manager_version(args), "0.6.0")

        old = subprocess.CompletedProcess(
            [], 0, json.dumps({"commandProtocol": 1, "version": "0.5.0"}), ""
        )
        with mock.patch.object(CONTROLLER, "run", return_value=old):
            with self.assertRaises(CONTROLLER.WorkstationError):
                CONTROLLER.manager_version(args)

    def test_managed_guest_contract_accepts_expected_configuration(self):
        args = SimpleNamespace(cpus=8, memory_gib=20, disk_gib=64)
        guest = managed_guest()
        self.assertEqual(CONTROLLER.immutable_guest_errors(guest), [])
        self.assertEqual(CONTROLLER.mutable_guest_errors(args, guest), [])

    def test_managed_guest_contract_reports_boundary_mismatches(self):
        args = SimpleNamespace(cpus=8, memory_gib=20, disk_gib=64)
        guest = managed_guest(
            protected=True,
            cpus=4,
            clipboard=False,
            network={"mode": "bridged", "hostAddress": "0.0.0.0"},
            ssh={"enabled": False, "status": "disabled"},
        )
        immutable = CONTROLLER.immutable_guest_errors(guest)
        mutable = CONTROLLER.mutable_guest_errors(args, guest)
        self.assertTrue(any("protected" in error for error in immutable))
        self.assertTrue(any("managed SSH" in error for error in immutable))
        self.assertTrue(any("NAT" in error for error in immutable))
        self.assertTrue(any("cpus" in error for error in mutable))
        self.assertTrue(any("clipboard" in error for error in mutable))

    def test_manager_owned_ssh_command_is_narrowly_validated(self):
        home = Path("/Users/operator")
        config = (
            home
            / "Library/Application Support/Omarchy VM Manager/VMs"
            / GUEST_ID
            / ".manager-ssh/config"
        )
        command = f"/usr/bin/ssh -F {str(config)!r} omarchy-{GUEST_ID.lower()}"
        guest = managed_guest(
            ssh={
                "enabled": True,
                "status": "ready",
                "host": "127.0.0.1",
                "port": 2224,
                "user": "owner",
                "command": command,
            }
        )
        with mock.patch.object(Path, "home", return_value=home), mock.patch.object(
            CONTROLLER, "require_file", side_effect=lambda path, *_args, **_kwargs: path
        ):
            connection = CONTROLLER.managed_ssh(guest)
        self.assertEqual(connection.config, config)
        self.assertEqual(connection.alias, f"omarchy-{GUEST_ID.lower()}")

        guest["ssh"]["command"] = "/usr/bin/ssh owner@127.0.0.1"
        with self.assertRaises(CONTROLLER.WorkstationError):
            CONTROLLER.managed_ssh(guest)

    def test_remote_cleanup_path_is_narrowly_validated(self):
        self.assertEqual(
            CONTROLLER.validate_remote_dir("/tmp/dev-ubuntu-workstation.A1b2c3\n"),
            "/tmp/dev-ubuntu-workstation.A1b2c3",
        )
        for unsafe in ("/tmp", "/", "/tmp/dev-ubuntu-workstation.bad/path"):
            with self.assertRaises(CONTROLLER.WorkstationError):
                CONTROLLER.validate_remote_dir(unsafe)

    def test_layout_selection_supports_preserve_install_and_remove(self):
        parser = CONTROLLER.build_parser()
        preserved = parser.parse_args(["bootstrap"])
        installed = parser.parse_args(["--layout-file", "layout.lua", "bootstrap"])
        removed = parser.parse_args(["--remove-layout", "bootstrap"])
        self.assertIsNone(preserved.layout_file)
        self.assertFalse(preserved.remove_layout)
        self.assertEqual(installed.layout_file, Path("layout.lua"))
        self.assertTrue(removed.remove_layout)

    def test_packages_default_and_override_are_explicit(self):
        parser = CONTROLLER.build_parser()
        default = parser.parse_args(["bootstrap"])
        overridden = parser.parse_args(
            ["--packages", "opencode,mise:pi,pkg:ripgrep", "bootstrap"]
        )
        empty = parser.parse_args(["--packages", "", "bootstrap"])
        self.assertEqual(
            tuple(item.name for item in default.packages),
            ("claude-desktop", "1password", "1password-cli"),
        )
        self.assertEqual(
            tuple((item.source, item.name) for item in overridden.packages),
            ((None, "opencode"), ("mise", "pi"), ("pkg", "ripgrep")),
        )
        self.assertEqual(empty.packages, ())

    def test_packages_reject_unsafe_or_ambiguous_entries(self):
        for value in ("opencode,,pi", "npm:tool", "tool; reboot", "pi,pi"):
            with self.assertRaises(CONTROLLER.argparse.ArgumentTypeError):
                CONTROLLER.parse_packages(value)

    def test_selected_software_uses_omarchy_packages_and_configured_mise_tools(self):
        connection = CONTROLLER.ManagedSSH(Path("/manager/config"), "managed-vm")
        selection = CONTROLLER.parse_packages(
            "claude-desktop,1password,1password-cli,opencode,mise:pi,pkg:ripgrep"
        )
        with mock.patch.object(
            CONTROLLER,
            "mise_tool_configured",
            side_effect=lambda _connection, name: name == "opencode",
        ), mock.patch.object(
            CONTROLLER, "mise_tool_installed", return_value=False
        ), mock.patch.object(
            CONTROLLER, "package_installed", return_value=False
        ), mock.patch.object(CONTROLLER, "guest_login_command") as command:
            CONTROLLER.install_selected_software(connection, selection)
        self.assertEqual(
            command.call_args.args[1],
            "omarchy install ai claude && "
            "omarchy install service 1password && "
            "mise install opencode && mise install pi && omarchy-pkg-add ripgrep",
        )
        self.assertTrue(command.call_args.kwargs["tty"])

    def test_system_update_uses_omarchy_supported_entrypoint(self):
        connection = CONTROLLER.ManagedSSH(Path("/manager/config"), "managed-vm")
        with mock.patch.object(CONTROLLER, "guest_login_command") as command:
            CONTROLLER.update_guest_system(connection)
        command.assert_called_once_with(connection, "omarchy update -y", tty=True)

    def test_guest_login_command_loads_omarchy_environment(self):
        connection = CONTROLLER.ManagedSSH(Path("/manager/config"), "managed-vm")
        with mock.patch.object(CONTROLLER, "ssh_command") as command:
            CONTROLLER.guest_login_command(
                connection,
                "omarchy update -y",
                tty=True,
            )
        command.assert_called_once_with(
            connection,
            "bash -lc 'omarchy update -y'",
            check=True,
            capture=False,
            tty=True,
        )

    def test_restart_waits_for_managed_ssh_and_revalidates_the_guest(self):
        args = SimpleNamespace(
            timeout=3600,
            cpus=8,
            memory_gib=20,
            disk_gib=64,
        )
        restarted = managed_guest(active=True, state="running")
        with mock.patch.object(
            CONTROLLER,
            "cli_call",
            return_value={"ok": True, "guest": restarted},
        ) as call:
            result = CONTROLLER.restart_guest(args, managed_guest())
        self.assertEqual(result, restarted)
        self.assertEqual(
            call.call_args.args[1:],
            (
                "restart",
                GUEST_ID,
                "--wait",
                "ssh",
                "--timeout",
                "3600",
            ),
        )

    def test_bootstrap_updates_before_customizing_then_restarts_and_checks(self):
        args = SimpleNamespace(timeout=3600)
        initial = managed_guest()
        restarted = managed_guest(active=True, state="running")
        connection = CONTROLLER.ManagedSSH(Path("/manager/config"), "managed-vm")
        events = []

        with mock.patch.object(
            CONTROLLER, "ready_guest", return_value=(initial, "0.6.0")
        ), mock.patch.object(
            CONTROLLER,
            "managed_ssh",
            side_effect=lambda _guest: events.append("connect") or connection,
        ), mock.patch.object(
            CONTROLLER,
            "update_guest_system",
            side_effect=lambda _connection: events.append("update"),
        ), mock.patch.object(
            CONTROLLER,
            "apply_workstation",
            side_effect=lambda _args, _connection: events.append("customize"),
        ), mock.patch.object(
            CONTROLLER,
            "restart_guest",
            side_effect=lambda _args, _guest: events.append("restart") or restarted,
        ), mock.patch.object(
            CONTROLLER,
            "check_guest_workstation",
            side_effect=lambda _connection: events.append("check"),
        ):
            CONTROLLER.bootstrap_command(args)

        self.assertEqual(
            events,
            ["connect", "update", "customize", "restart", "connect", "check"],
        )

    def test_new_guest_creation_is_one_explicit_manager_mutation(self):
        args = SimpleNamespace(
            vm_name="Dev Omarchy",
            memory_gib=20,
            cpus=8,
            disk_gib=64,
            timeout=3600,
            remove_layout=False,
            layout_file=None,
            foot_font_size="16",
            idle_mode="host",
            packages=CONTROLLER.parse_packages(
                "claude-desktop,1password,1password-cli"
            ),
        )
        ready = managed_guest(
            active=True,
            state="running",
            ssh={
                "enabled": True,
                "status": "ready",
                "host": "127.0.0.1",
                "port": 2224,
                "user": "owner",
                "command": "unused by ready_guest",
            },
        )
        with mock.patch.object(
            CONTROLLER, "preflight", return_value="0.6.0"
        ), mock.patch.object(
            CONTROLLER, "list_guests", return_value=[]
        ), mock.patch.object(
            CONTROLLER, "print_proposal"
        ), mock.patch.object(
            CONTROLLER, "confirm"
        ), mock.patch.object(
            CONTROLLER, "cli_call", return_value={"ok": True, "guest": ready}
        ) as call:
            result, version = CONTROLLER.ready_guest(args)
        self.assertEqual(result, ready)
        self.assertEqual(version, "0.6.0")
        values = call.call_args.args[1:]
        self.assertEqual(values[0:2], ("create", "Dev Omarchy"))
        self.assertIn("--owner-defaults", values)
        self.assertIn("--disk", values)
        self.assertIn("64GiB", values)
        self.assertIn("--start", values)
        self.assertIn("--wait", values)
        self.assertIn("ssh", values)
        call.assert_called_once()

    def test_controller_uses_manager_and_omarchy_ownership_boundaries(self):
        source = CONTROLLER_PATH.read_text(encoding="utf-8")
        self.assertIn('"create"', source)
        self.assertIn('"--wait"', source)
        self.assertIn('"ssh"', source)
        self.assertIn("omarchy install ai claude", source)
        self.assertIn("omarchy install service 1password", source)
        self.assertIn("omarchy update -y", source)
        self.assertIn('"restart"', source)
        for forbidden in (
            "codesign",
            "spctl",
            "plistlib",
            "id_rsa",
            "StrictHostKeyChecking=accept-new",
            "pacman -S",
            "prlctl",
        ):
            self.assertNotIn(forbidden, source)

    def test_runbook_stops_at_the_manager_make_handoff(self):
        runbook = RUNBOOK_PATH.read_text(encoding="utf-8")
        self.assertIn("Guest Defaults", runbook)
        self.assertIn("make bootstrap-omarchy-vm", runbook)
        self.assertIn("managed SSH", runbook)
        self.assertNotIn("brew install", runbook)
        self.assertNotIn("port 2222", runbook)


if __name__ == "__main__":
    unittest.main()
