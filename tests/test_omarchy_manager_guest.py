import unittest
from pathlib import Path


REPOSITORY = Path(__file__).resolve().parents[1]
APPLY = REPOSITORY / "omarchy" / "guest" / "apply-workstation.sh"
CHECK = REPOSITORY / "omarchy" / "guest" / "check-workstation.sh"
REPAIR = REPOSITORY / "omarchy" / "guest" / "repair-try-omarchy-black-screen.sh"


class OmarchyManagerGuestTests(unittest.TestCase):
    def test_preference_layer_does_not_take_over_omarchy_packages(self):
        script = APPLY.read_text(encoding="utf-8")
        for forbidden in ("pacman", "yay ", "paru ", "prlctl", "prlcp", "Parallels"):
            self.assertNotIn(forbidden, script)

    def test_host_idle_policy_is_reversible(self):
        script = APPLY.read_text(encoding="utf-8")
        self.assertIn('idle_mode="host"', script)
        self.assertIn(".idle.screensaver = 0", script)
        self.assertIn(".idle.lock = 0", script)
        self.assertIn("shell.before-host-idle.json", script)
        self.assertIn("systemctl --user unmask", script)

    def test_layout_remains_an_explicit_option(self):
        script = APPLY.read_text(encoding="utf-8")
        self.assertIn("--layout-file", script)
        self.assertIn("--remove-layout", script)
        self.assertIn('layout_mode="keep"', script)

    def test_health_check_rejects_software_rendering(self):
        script = CHECK.read_text(encoding="utf-8")
        self.assertIn("llvmpipe|softpipe|software raster", script)
        self.assertIn("hardware-backed VirGL", script)
        self.assertIn("hyprland.log", script)
        self.assertIn("/dev/virtio-ports/dev.tryomarchy.clipboard", script)
        self.assertIn("Omarchy VM Manager clipboard channel", script)
        self.assertIn("HYPRLAND_INSTANCE_SIGNATURE", script)
        self.assertIn("systemctl --user show-environment", script)
        self.assertNotIn("SHARED_FOLDER", script)

    def test_black_screen_repair_preserves_hardware_rendering(self):
        script = REPAIR.read_text(encoding="utf-8")
        self.assertIn("skip_non_kms_dmabuf_formats = false", script)
        self.assertIn("hyprland.lua looknfeel.lua", script)
        self.assertIn("before-repair", script)
        self.assertIn("pacman -Q hyprland", script)
        self.assertIn("/usr/share/try-omarchy/hyprland.lua", script)
        self.assertIn("if (( changed )); then", script)
        self.assertNotIn("MESA_LOADER_DRIVER_OVERRIDE", script)
        self.assertNotIn("llvmpipe", script)


if __name__ == "__main__":
    unittest.main()
