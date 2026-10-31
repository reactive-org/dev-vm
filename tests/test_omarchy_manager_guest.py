import unittest
import os
import subprocess
import tempfile
from pathlib import Path


REPOSITORY = Path(__file__).resolve().parents[1]
APPLY = REPOSITORY / "omarchy" / "guest" / "apply-workstation.sh"
CHECK = REPOSITORY / "omarchy" / "guest" / "check-workstation.sh"
REPAIR = REPOSITORY / "omarchy" / "guest" / "repair-try-omarchy-black-screen.sh"
THEME = REPOSITORY / "omarchy" / "guest" / "apply-theme.sh"


class OmarchyThemeGuestTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.home = Path(self.temp.name)
        commands = self.home / "bin"
        commands.mkdir()
        self.log = self.home / "calls"
        for name, source in {
            "omarchy": '''#!/bin/bash
printf "%s|%s|%s\\n" "$OMARCHY_THEME_HEADLESS" "${GIT_TERMINAL_PROMPT:-}" "$*" >> "$TEST_CALLS"
if [[ ${TEST_OMARCHY_EXIT:-0} != 0 ]]; then exit "$TEST_OMARCHY_EXIT"; fi
if [[ ${TEST_SKIP_GENERATION:-0} != 1 ]]; then
  mkdir -p "$HOME/.local/state/omarchy/current/theme"
  printf '[colors-dark]\\nforeground=ffffff\\n' > "$HOME/.local/state/omarchy/current/theme/foot.ini"
fi
''',
            "git": '#!/bin/bash\nprintf "%s\\n" "$TEST_ORIGIN"\n',
        }.items():
            path = commands / name
            path.write_text(source)
            path.chmod(0o755)
        self.env = dict(os.environ, HOME=str(self.home), TEST_CALLS=str(self.log))
        self.env["PATH"] = str(commands) + os.pathsep + os.environ["PATH"]
        self.env["TEST_ORIGIN"] = "https://github.com/o/omarchy-blue-theme.git"
        templates = self.home / "native-omarchy/default/themed"
        templates.mkdir(parents=True)
        self.env["OMARCHY_PATH"] = str(templates.parents[1])

    def apply(self, url="https://github.com/o/omarchy-blue-theme.git/"):
        return subprocess.run(
            ["bash", str(THEME), url], env=self.env, capture_output=True, text=True
        )

    def installed_theme(self):
        path = self.home / ".config/omarchy/themes/blue"
        (path / ".git").mkdir(parents=True)
        return path

    def test_new_theme_uses_native_headless_installer(self):
        result = self.apply()
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(
            self.log.read_text(),
            "1|0|theme install https://github.com/o/omarchy-blue-theme\n",
        )

    def test_installed_theme_is_selected_without_reinstalling_then_skipped(self):
        self.installed_theme()
        result = self.apply()
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(self.log.read_text(), "1|0|theme set blue\n")
        current = self.home / ".local/state/omarchy/current/theme.name"
        current.parent.mkdir(parents=True, exist_ok=True)
        current.write_text("blue\n")
        for _ in range(2):
            result = self.apply()
            self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(self.log.read_text(), "1|0|theme set blue\n")

    def test_active_theme_is_regenerated_when_foot_include_is_missing(self):
        self.installed_theme()
        current = self.home / ".local/state/omarchy/current/theme.name"
        current.parent.mkdir(parents=True)
        current.write_text("blue\n")
        result = self.apply()
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(self.log.read_text(), "1|0|theme set blue\n")
        self.assertTrue((current.parent / "theme/foot.ini").is_file())

    def test_omitted_url_repairs_current_theme_once_without_changing_selection(self):
        current = self.home / ".local/state/omarchy/current/theme.name"
        current.parent.mkdir(parents=True)
        current.write_text("blue\n")
        for _ in range(2):
            result = self.apply("")
            self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(current.read_text(), "blue\n")
        self.assertEqual(self.log.read_text(), "1|0|theme set blue\n")

    def test_missing_login_environment_fails_before_native_theme_changes(self):
        self.env.pop("OMARCHY_PATH")
        result = self.apply()
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("login shell", result.stderr)
        self.assertFalse(self.log.exists())

    def test_native_success_without_generated_foot_config_is_rejected(self):
        self.env["TEST_SKIP_GENERATION"] = "1"
        result = self.apply()
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("did not generate", result.stderr)

    def test_repository_name_collision_preserves_existing_files(self):
        path = self.installed_theme()
        marker = path / "local-changes"
        marker.write_text("keep me")
        self.env["TEST_ORIGIN"] = "https://github.com/another/omarchy-blue-theme"
        result = self.apply()
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("collision", result.stderr)
        self.assertEqual(marker.read_text(), "keep me")
        self.assertFalse(self.log.exists())

    def test_local_theme_and_symlink_are_never_replaced(self):
        path = self.home / ".config/omarchy/themes/blue"
        path.mkdir(parents=True)
        result = self.apply()
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("existing local theme", result.stderr)
        path.rmdir()
        path.symlink_to(self.home / "missing")
        result = self.apply()
        self.assertNotEqual(result.returncode, 0)
        self.assertTrue(path.is_symlink())
        self.assertFalse(self.log.exists())

    def test_invalid_urls_and_install_failure_stop_application(self):
        for url in (
            "random", "--upload-pack=bad", "https://github.com/o/..",
            "https://github.com/o/omarchy--theme", "https://github.com/o/r/tree/main",
            "https://github.com/o/theme.git.git",
        ):
            with self.subTest(url=url):
                self.assertNotEqual(self.apply(url).returncode, 0)
                self.assertFalse(self.log.exists())
        self.env["TEST_OMARCHY_EXIT"] = "3"
        self.assertEqual(self.apply().returncode, 3)


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
