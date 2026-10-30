import argparse
import importlib.util
import pathlib
import sys
import tarfile
import tempfile
import unittest
from unittest import mock

SCRIPTS = pathlib.Path(__file__).resolve().parents[1] / "scripts"
sys.path.insert(0, str(SCRIPTS))
from nixos_media import FatImage, copy_tree, grub_menu, source_archive  # noqa: E402

spec = importlib.util.spec_from_file_location("nixos_vm", SCRIPTS / "nixos-vm.py")
controller = importlib.util.module_from_spec(spec)
spec.loader.exec_module(controller)


class InstallerSafety(unittest.TestCase):
    def test_existing_vm_refused_before_password_or_media_operations(self):
        args = argparse.Namespace(prlctl="prlctl", name="Disposable test")
        with mock.patch.object(controller, "output", return_value='[{"name":"Disposable test"}]'), mock.patch.object(controller, "prepare") as prepare:
            with self.assertRaisesRegex(ValueError, "already exists"):
                controller.bootstrap(args)
            prepare.assert_not_called()

    def test_only_arm64_nixos_menu_is_accepted(self):
        with self.assertRaises(ValueError):
            grub_menu("linux /casper/vmlinuz autoinstall\ninitrd /casper/initrd\n", "a" * 32)
        with self.assertRaises(ValueError):
            grub_menu("linux /boot/store/Image init=/nix/store/system/init\ninitrd /boot/store/initrd\n", "bad token")

    def test_media_boot_token_and_failure_policy(self):
        original = "linux /boot/store/Image init=/nix/store/system/init splash root=fstab\ninitrd /boot/store/initrd\n"
        menu = grub_menu(original, "b" * 32)
        self.assertIn("workstation.install=" + "b" * 32, menu)
        self.assertIn("systemd.run_failure_action=none", menu)
        self.assertIn("systemd.unit=kernel-command-line.target", menu)
        self.assertNotIn(" splash ", menu)

    def test_archive_cannot_overwrite_instance_or_private_local_state(self):
        with tempfile.TemporaryDirectory() as folder:
            root = pathlib.Path(folder)
            source = root / "source"
            host = source / "hosts/workstation-test"
            host.mkdir(parents=True)
            for filename in ("default.nix", "hardware-configuration.nix", "installation.nix", "integration.nix", "identity.nix", "authorized-keys.pub"):
                (host / filename).write_text("fixture")
            (source / "local").mkdir()
            (source / "local/flake.nix").write_text("private override fixture")
            archive = root / "source.tar"
            source_archive(source, archive)
            with tarfile.open(archive) as package:
                self.assertEqual(package.getnames(), ["hosts/workstation-test/default.nix"])
            self.assertEqual(archive.stat().st_mode & 0o777, 0o600)

    def test_source_symlink_outside_tree_is_rejected(self):
        with tempfile.TemporaryDirectory() as folder:
            root = pathlib.Path(folder)
            (root / "source").mkdir()
            (root / "outside").write_text("not source")
            (root / "source/escape.nix").symlink_to(root / "outside")
            with self.assertRaisesRegex(ValueError, "symlinks"):
                source_archive(root / "source", root / "source.tar")

    def test_invalid_fat_geometry_is_refused(self):
        with self.assertRaises(ValueError):
            FatImage(bytes(512))

    def test_generated_media_cannot_be_remastered_as_upstream(self):
        with self.assertRaisesRegex(ValueError, "upstream ISO"):
            grub_menu("linux /boot/store/Image init=/nix/store/system/init systemd.run=/iso/workstation/boot.sh\ninitrd /boot/store/initrd\n", "a" * 32)

    def test_copy_into_source_tree_is_refused(self):
        with tempfile.TemporaryDirectory() as directory:
            source = pathlib.Path(directory)
            with self.assertRaisesRegex(ValueError, "outside"):
                copy_tree(source, source / "nested")

    def test_guest_channel_read_retries_transport_error(self):
        args = argparse.Namespace(prlctl="prlctl", name="Disposable test")
        with mock.patch.object(controller, "output", side_effect=[controller.GuestChannelError("not ready"), "developer P"]), mock.patch.object(controller.time, "sleep"):
            self.assertEqual(controller.guest_root(args, ["passwd", "-S", "developer"], retry=True), "developer P")


if __name__ == "__main__":
    unittest.main()
