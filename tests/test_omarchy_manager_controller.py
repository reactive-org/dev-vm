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
            [], 0, json.dumps({"commandProtocol": 1, "version": "0.5.1"}), ""
        )
        with mock.patch.object(CONTROLLER, "run", return_value=valid):
            self.assertEqual(CONTROLLER.manager_version(args), "0.5.1")

        old = subprocess.CompletedProcess(
            [], 0, json.dumps({"commandProtocol": 1, "version": "0.5.0"}), ""
        )
        with mock.patch.object(CONTROLLER, "run", return_value=old):
            with self.assertRaises(CONTROLLER.WorkstationError):
                CONTROLLER.manager_version(args)

    def test_managed_guest_contract_accepts_expected_configuration(self):
        args = SimpleNamespace(cpus=8, memory_gib=20)
        guest = managed_guest()
        self.assertEqual(CONTROLLER.immutable_guest_errors(guest), [])
        self.assertEqual(CONTROLLER.mutable_guest_errors(args, guest), [])

    def test_managed_guest_contract_reports_boundary_mismatches(self):
        args = SimpleNamespace(cpus=8, memory_gib=20)
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

    def test_new_guest_creation_is_one_explicit_manager_mutation(self):
        args = SimpleNamespace(
            vm_name="Dev Omarchy",
            memory_gib=20,
            cpus=8,
            timeout=3600,
            remove_layout=False,
            layout_file=None,
            foot_font_size="16",
            idle_mode="host",
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
            CONTROLLER, "preflight", return_value="0.5.1"
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
        self.assertEqual(version, "0.5.1")
        values = call.call_args.args[1:]
        self.assertEqual(values[0:2], ("create", "Dev Omarchy"))
        self.assertIn("--owner-defaults", values)
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
