import importlib.util
import json
import tempfile
import unittest
from pathlib import Path


MODULE_PATH = Path(__file__).resolve().parents[1] / "scripts" / "omarchy_vm.py"
SPEC = importlib.util.spec_from_file_location("omarchy_vm", MODULE_PATH)
omarchy_vm = importlib.util.module_from_spec(SPEC)
assert SPEC.loader is not None
SPEC.loader.exec_module(omarchy_vm)


class OmarchyVmTests(unittest.TestCase):
    def test_parallels_ipv4_prefers_routable_ipv4(self):
        info = """Network:
  IP Addresses: 192.0.2.28,2001:db8::1,fe80::1
"""
        self.assertEqual(omarchy_vm.parallels_ipv4_from_info(info), "192.0.2.28")
        self.assertEqual(
            omarchy_vm.parallels_ipv4_from_info("IP Addresses: fe80::1\n"), ""
        )

    def test_vm_state_is_parsed_from_parallels_info(self):
        original_vm_info = omarchy_vm.vm_info
        try:
            omarchy_vm.vm_info = (
                lambda _prlctl, _name: "Name: Dev Omarchy\nState: running\n"
            )
            self.assertEqual(omarchy_vm.vm_state("prlctl", "Dev Omarchy"), "running")
        finally:
            omarchy_vm.vm_info = original_vm_info

    def test_omarchy_shell_workaround_is_scoped_to_shell_unit(self):
        drop_in = (
            MODULE_PATH.parents[1] / "omarchy" / "guest" / "omarchy-shell-software.conf"
        ).read_text(encoding="utf-8")
        self.assertIn("QT_QUICK_BACKEND=software", drop_in)
        self.assertIn("QSG_RHI_BACKEND=software", drop_in)
        self.assertNotIn("LIBGL_ALWAYS_SOFTWARE", drop_in)

    def test_guest_idle_and_suspend_lock_are_disabled(self):
        configure = (
            MODULE_PATH.parents[1] / "omarchy" / "guest" / "configure.sh"
        ).read_text(encoding="utf-8")
        self.assertIn(".idle.screensaver = 0", configure)
        self.assertIn(".idle.lock = 0", configure)
        self.assertIn(
            "systemctl --user disable --now omarchy-sleep-lock.service", configure
        )
        self.assertIn(
            '"$workstation_home/.config/systemd/user/omarchy-sleep-lock.service"',
            configure,
        )

    def test_vendor_clipboard_chain_is_used_without_standalone_service(self):
        repository = MODULE_PATH.parents[1]
        drop_in = (repository / "omarchy" / "guest" / "parallels-prlcc.conf").read_text(
            encoding="utf-8"
        )
        configure = (repository / "omarchy" / "guest" / "configure.sh").read_text(
            encoding="utf-8"
        )
        self.assertIn("Restart=always", drop_in)
        self.assertIn("RuntimeMaxSec=4h", drop_in)
        self.assertIn("app-prlcc@autostart.service.d/10-dev-vm.conf", configure)
        self.assertIn("disable --now parallels-prlcp.service", configure)

        workstation = (repository / "omarchy" / "guest" / "workstation.lua").read_text(
            encoding="utf-8"
        )
        self.assertIn("Parallels Shared Clipboard", workstation)
        self.assertNotIn("no_focus", workstation)

    def test_app_layout_is_optional_and_not_baked_into_core(self):
        repository = MODULE_PATH.parents[1]
        core = (repository / "omarchy" / "guest" / "workstation.lua").read_text(
            encoding="utf-8"
        )
        example = (
            repository
            / "omarchy"
            / "examples"
            / "layouts"
            / "claude-two-terminals-browser.lua"
        ).read_text(encoding="utf-8")
        for app_marker in ("com.anthropic.Claude", "terminal-top", "chromium"):
            self.assertNotIn(app_marker, core)
            self.assertIn(app_marker, example)

    def test_per_vm_layout_selection_supports_install_keep_and_remove(self):
        self.assertEqual(
            omarchy_vm.resolve_layout(None, default_mode="keep"), ("keep", None)
        )
        self.assertEqual(
            omarchy_vm.resolve_layout("off", default_mode="keep"),
            ("remove", None),
        )
        with tempfile.TemporaryDirectory() as directory:
            layout = Path(directory) / "layout.lua"
            layout.write_text("-- custom layout\n", encoding="utf-8")
            mode, resolved = omarchy_vm.resolve_layout(str(layout), default_mode="keep")
            self.assertEqual(mode, "install")
            self.assertEqual(resolved, layout.resolve())

    def test_manifest_requires_aarch64_and_checksum(self):
        manifest = omarchy_vm.validate_manifest(
            {
                "version": "2026.10.30.470",
                "channel": "edge-aarch64",
                "arch": "aarch64",
                "url": "https://example.test/omarchy-aarch64.iso",
                "sha256": "a" * 64,
                "size": 1024,
            }
        )
        self.assertEqual(manifest["arch"], "aarch64")
        with self.assertRaises(omarchy_vm.OmarchyError):
            omarchy_vm.validate_manifest({**manifest, "arch": "x86_64"})

    def test_partition_layout_reserves_efi_and_backup_gpt(self):
        boot_start, boot_size, root_start, root_size = omarchy_vm.partition_sizes(64)
        self.assertEqual(boot_start, 1024 * 1024)
        self.assertEqual(boot_size, 2 * 1024**3)
        self.assertEqual(root_start, boot_start + boot_size)
        self.assertEqual(root_start + root_size + 1024 * 1024, 64 * 1024**3)

    def test_arm_configuration_targets_only_parallels_disk(self):
        configuration = omarchy_vm.build_user_configuration(
            disk_gb=64,
            hostname="dev-omarchy",
            timezone="Australia/Melbourne",
            keyboard_layout="us",
            channel="edge-aarch64",
            image_name="omarchy-edge-aarch64.iso",
        )
        self.assertEqual(
            configuration["omarchy_install"]["boot"]["efi_binary"],
            "limine_aa64.efi",
        )
        self.assertEqual(configuration["kernels"], ["linux-omarchy"])
        modification = configuration["disk_config"]["device_modifications"][0]
        self.assertEqual(modification["device"], "/dev/sda")
        self.assertTrue(modification["wipe"])
        self.assertIn("omarchy-dev", configuration["packages"])
        self.assertEqual(
            configuration["mirror_config"]["custom_servers"],
            [{"url": "https://arm-mirror.omarchy.org/$arch/$repo"}],
        )

    def test_cidata_contains_hash_not_plaintext(self):
        configuration = omarchy_vm.build_user_configuration(
            disk_gb=64,
            hostname="dev-omarchy",
            timezone="UTC",
            keyboard_layout="us",
            channel="stable",
            image_name="omarchy-aarch64.iso",
        )
        with tempfile.TemporaryDirectory() as directory:
            directory_path = Path(directory)
            key = directory_path / "id_ed25519.pub"
            key.write_text("ssh-ed25519 TEST test\n", encoding="utf-8")
            captured = {}
            original_run = omarchy_vm.run

            def fake_run(argv, **_kwargs):
                source = Path(argv[-1])
                captured["credentials"] = json.loads(
                    (source / "user_credentials.json").read_text(encoding="utf-8")
                )
                output = Path(argv[argv.index("-o") + 1])
                output.write_text("iso", encoding="utf-8")

            try:
                omarchy_vm.run = fake_run
                omarchy_vm.build_cidata_iso(
                    output=directory_path / "cidata.iso",
                    xorriso="xorriso",
                    guest_user="developer",
                    password_hash="$6$hashed",
                    public_key=key,
                    configuration=configuration,
                )
            finally:
                omarchy_vm.run = original_run

            self.assertEqual(
                captured["credentials"]["users"][0]["enc_password"], "$6$hashed"
            )
            self.assertNotIn("plaintext", json.dumps(captured["credentials"]))

    def test_display_mode_rejects_shell_content(self):
        self.assertEqual(
            omarchy_vm.validate_display_mode("2560x1600@59.99"),
            "2560x1600@59.99",
        )
        with self.assertRaises(omarchy_vm.OmarchyError):
            omarchy_vm.validate_display_mode("2560x1600@59.99; reboot")

    def test_host_window_size_uses_supported_rectangle_actions(self):
        self.assertEqual(omarchy_vm.validate_window_size(""), 75)
        self.assertEqual(omarchy_vm.validate_window_size("75%"), 75)
        self.assertEqual(omarchy_vm.validate_window_size("67"), 67)
        self.assertIsNone(omarchy_vm.validate_window_size("off"))
        with self.assertRaises(omarchy_vm.OmarchyError):
            omarchy_vm.validate_window_size("80")

    def test_host_window_resize_targets_frontmost_parallels_window(self):
        original_platform = omarchy_vm.sys.platform
        original_which = omarchy_vm.shutil.which
        original_run = omarchy_vm.run
        original_sleep = omarchy_vm.time.sleep
        calls = []

        def successful_run(argv, **_kwargs):
            calls.append(list(argv))
            return omarchy_vm.subprocess.CompletedProcess(argv, 0, "", "")

        try:
            omarchy_vm.sys.platform = "darwin"
            omarchy_vm.shutil.which = lambda name: "/usr/bin/open"
            omarchy_vm.run = successful_run
            omarchy_vm.time.sleep = lambda _seconds: None
            self.assertTrue(omarchy_vm.resize_host_window(75))
        finally:
            omarchy_vm.sys.platform = original_platform
            omarchy_vm.shutil.which = original_which
            omarchy_vm.run = original_run
            omarchy_vm.time.sleep = original_sleep

        self.assertIn(["/usr/bin/open", "-a", "Parallels Desktop"], calls)
        self.assertIn(
            [
                "/usr/bin/open",
                "-g",
                "rectangle-pro://execute-action?name=center-three-fourths",
            ],
            calls,
        )

    def test_existing_vm_is_never_replaced_implicitly(self):
        original_vm_exists = omarchy_vm.vm_exists
        try:
            omarchy_vm.vm_exists = lambda _prlctl, _name: True
            with self.assertRaisesRegex(omarchy_vm.OmarchyError, "never replaced"):
                omarchy_vm.configure_vm(
                    prlctl="prlctl",
                    name="Existing workstation",
                    cpus=4,
                    memory_mb=12288,
                    disk_gb=64,
                    installer_iso=Path("omarchy.iso"),
                    cidata_iso=Path("cidata.iso"),
                    resume=False,
                )
        finally:
            omarchy_vm.vm_exists = original_vm_exists

    def test_nonfatal_command_timeout_becomes_failed_probe(self):
        original_run = omarchy_vm.subprocess.run

        def timeout(*_args, **_kwargs):
            raise omarchy_vm.subprocess.TimeoutExpired(["ssh"], 10)

        try:
            omarchy_vm.subprocess.run = timeout
            result = omarchy_vm.run(["ssh"], check=False, timeout=10)
        finally:
            omarchy_vm.subprocess.run = original_run

        self.assertEqual(result.returncode, 124)


if __name__ == "__main__":
    unittest.main()
