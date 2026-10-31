import importlib.util
import json
import unittest
from pathlib import Path


REPOSITORY = Path(__file__).resolve().parents[1]
CONTROLLER_PATH = REPOSITORY / "scripts" / "try_omarchy.py"
LOCK_PATH = REPOSITORY / "omarchy" / "try-omarchy.lock.json"
RUNBOOK_PATH = REPOSITORY / "docs" / "try-omarchy-runbook.md"

SPEC = importlib.util.spec_from_file_location("try_omarchy", CONTROLLER_PATH)
CONTROLLER = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(CONTROLLER)


def launcher_preferences(
    *,
    cpus=8,
    memory_gib=20,
    disk_gib=64,
    share_path="/Users/operator/Shared",
    share_enabled=True,
    mappings=None,
):
    if mappings is None:
        mappings = [{"hostPort": 2222, "guestPort": 22, "protocol": "tcp"}]
    return {
        "vmResourcePreferences": json.dumps(
            {
                "schemaVersion": 1,
                "resources": {
                    "cpuCount": cpus,
                    "memoryGiB": memory_gib,
                    "diskGiB": disk_gib,
                },
            }
        ).encode(),
        "portForwardingPreferences": json.dumps(
            {"schemaVersion": 1, "mappings": mappings}
        ).encode(),
        "sharedFolderPreferences": json.dumps(
            {
                "schemaVersion": 1,
                "path": share_path,
                "isEnabled": share_enabled,
            }
        ).encode(),
    }


class TryOmarchyControllerTests(unittest.TestCase):
    def test_reviewed_release_is_pinned(self):
        lock = CONTROLLER.load_lock(LOCK_PATH)
        self.assertEqual(lock["app"]["version"], "1.2.0")
        self.assertEqual(lock["app"]["bundle_id"], "dev.tryomarchy.native")
        self.assertEqual(lock["app"]["team_id"], "RZC79MPD34")
        self.assertRegex(lock["app"]["dmg_sha256"], r"^[0-9a-f]{64}$")

    def test_launcher_settings_accept_the_documented_configuration(self):
        errors = CONTROLLER.validate_launcher_settings(
            launcher_preferences(),
            cpus=8,
            memory_gib=20,
            disk_gib=64,
            share_path=Path("/Users/operator/Shared"),
            ssh_port=2222,
        )
        self.assertEqual(errors, [])

    def test_launcher_settings_report_each_unsafe_mismatch(self):
        errors = CONTROLLER.validate_launcher_settings(
            launcher_preferences(
                cpus=4,
                share_path="/Users/operator/Other",
                share_enabled=False,
                mappings=[],
            ),
            cpus=8,
            memory_gib=20,
            disk_gib=64,
            share_path=Path("/Users/operator/Shared"),
            ssh_port=2222,
        )
        self.assertTrue(any("cpuCount" in error for error in errors))
        self.assertTrue(any("SSH forwarding" in error for error in errors))
        self.assertIn("shared folder is disabled", errors)

    def test_remote_cleanup_path_is_narrowly_validated(self):
        self.assertEqual(
            CONTROLLER.validate_remote_dir("/tmp/dev-ubuntu-workstation.A1b2c3\n"),
            "/tmp/dev-ubuntu-workstation.A1b2c3",
        )
        for unsafe in ("/tmp", "/", "/tmp/dev-ubuntu-workstation.bad/path"):
            with self.assertRaises(CONTROLLER.TryOmarchyError):
                CONTROLLER.validate_remote_dir(unsafe)

    def test_controller_delegates_application_installs_to_omarchy(self):
        source = CONTROLLER_PATH.read_text(encoding="utf-8")
        self.assertIn("omarchy install ai claude", source)
        self.assertIn("omarchy install service 1password", source)
        self.assertNotIn("pacman -S", source)
        self.assertNotIn("brew install", source)
        self.assertNotIn("prlctl", source)

    def test_layout_selection_supports_preserve_install_and_remove(self):
        parser = CONTROLLER.build_parser()
        preserved = parser.parse_args(["bootstrap"])
        installed = parser.parse_args(["--layout-file", "layout.lua", "bootstrap"])
        removed = parser.parse_args(["--remove-layout", "bootstrap"])
        self.assertIsNone(preserved.layout_file)
        self.assertFalse(preserved.remove_layout)
        self.assertEqual(installed.layout_file, Path("layout.lua"))
        self.assertTrue(removed.remove_layout)

    def test_runbook_stops_at_the_make_handoff(self):
        runbook = RUNBOOK_PATH.read_text(encoding="utf-8")
        self.assertIn("make bootstrap-try-omarchy", runbook)
        self.assertIn("127.0.0.1:2222", runbook)
        self.assertIn("Restart Try Omarchy", runbook)
        self.assertNotIn("brew install", runbook)


if __name__ == "__main__":
    unittest.main()
