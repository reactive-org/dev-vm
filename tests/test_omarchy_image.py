import contextlib
import importlib.util
import io
import json
import os
import shutil
import shlex
import subprocess
import tempfile
import tarfile
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest import mock


ROOT = Path(__file__).resolve().parents[1]
FIXTURES = ROOT / "tests/fixtures/omarchy-image"


def load(name, path):
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


IMAGE = load("omarchy_image", ROOT / "scripts/omarchy_image.py")
COMPAT = IMAGE.compat
CHECKS = load("provisioning_checks", ROOT / "omarchy/image/check-provisioning.py")
LOCK = json.loads((ROOT / "omarchy/image/inputs.lock.json").read_text())
# Omarchy 4.5.0's six guarded install scripts, as reviewed on 8 November 2026.
# They are no longer a build gate; this only proves the fixture is that release.
REVIEWED_4_5_SCRIPTS = {
    "install/hardware/bluetooth.sh": "9eaf62a12619b6561b10be2e6bf51c3ee820dd7543203fe333e3ed8c390a99a0",
    "install/config/enable-services.sh": "346a98f550a2582faa668f8a699cfd027d1365a0672623a618ef26b196826f69",
    "install/config/firewall.sh": "c15b76478355ae633b990520b7f8db829e2c3ab4a850922bb2c75072a99d4fcd",
    "install/user/chromium.sh": "ed467ddb356aaeaa1750bfb00bc07fd9d2daccd0a19da91d4afdc29e8f878858",
    "install/user/mise.sh": "b21565cf3416441682594bffe8dc56125de65c1134d2d996f8ea6dd5244b0476",
    "bin/omarchy-provision-user": "995e33939c0aca98d7c3576d23f10cc0e38e56cc18f2008fbc8feede8a8c278e",
}


class ImageCompatibilityTests(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory()
        self.addCleanup(self.temporary.cleanup)
        self.root = Path(self.temporary.name)

    def patched_source(self):
        source = self.root / "source"
        shutil.copytree(FIXTURES / "source", source)
        report = COMPAT.patch_sources(source, LOCK)
        return source, report

    def test_pinned_source_guards_skip_absent_features_and_keep_required_services(self):
        source, report = self.patched_source()
        result = CHECKS.check(source)
        self.assertEqual(result["optional_service_guards"], "passed")
        self.assertEqual(result["absent_browser_and_mise"], "passed")
        self.assertEqual(result["optional_firewall_rules"], "passed")
        self.assertEqual(result["optional_bluetooth_hardware"], "passed")
        self.assertEqual(result["owner_first_boot"], "requires-disposable-vm-validation")
        self.assertEqual(report["format"], 3)
        self.assertEqual(report["owner_setup"], "managed")
        self.assertEqual(report["reviewed_omarchy"], "lean-a948d8a")
        self.assertEqual(report["owner_setup_contract_sha256"], LOCK["reviewed_omarchy"][0]["owner_setup_contract_sha256"])
        self.assertEqual(report["owner_programs"], LOCK["reviewed_omarchy"][0]["owner_programs"])
        self.assertEqual(set(report["files"]), set(REVIEWED_4_5_SCRIPTS))
        for relative, hashes in report["files"].items():
            self.assertEqual(hashes["upstream_sha256"], REVIEWED_4_5_SCRIPTS[relative])
            self.assertNotEqual(hashes["patched_sha256"], hashes["upstream_sha256"])
            self.assertEqual(COMPAT.digest(source / relative), hashes["patched_sha256"])

    def test_check_sentence_matches_the_builder_message(self):
        self.assertEqual(CHECKS.UPDATE_REQUIRED, COMPAT.UPDATE_REQUIRED)

    def test_harmless_install_script_change_builds_with_its_actual_digest(self):
        source = self.root / "source"
        shutil.copytree(FIXTURES / "source", source)
        path = source / "install/user/mise.sh"
        path.write_text(path.read_text() + "\n# offline reshim, a later Omarchy release\n")
        changed = COMPAT.digest(path)
        report = COMPAT.patch_sources(source, LOCK)
        self.assertEqual(report["owner_setup"], "managed")
        self.assertEqual(report["files"]["install/user/mise.sh"]["upstream_sha256"], changed)
        self.assertEqual(CHECKS.check(source)["absent_browser_and_mise"], "passed")

    def test_missing_or_repeated_anchor_stops_before_any_script_is_written(self):
        cases = {
            "removed": ("install/config/enable-services.sh", "systemctl enable docker.socket\n", ""),
            "repeated": ("install/config/firewall.sh", "ufw allow 53317/udp\n", "ufw allow 53317/udp\nufw allow 53317/udp\n"),
            "unparsable": ("install/user/chromium.sh", "", "if then\n"),
        }
        for name, (relative, old, new) in cases.items():
            with self.subTest(name=name):
                source = self.root / ("anchor-" + name)
                shutil.copytree(FIXTURES / "source", source)
                path = source / relative
                text = path.read_text()
                path.write_text(text.replace(old, new, 1) if old else text + new)
                before = {item: item.read_bytes() for item in source.rglob("*") if item.is_file()}
                with self.assertRaisesRegex(COMPAT.CompatibilityError, "hasn't reviewed yet"):
                    COMPAT.patch_sources(source, LOCK)
                self.assertEqual({item: item.read_bytes() for item in source.rglob("*") if item.is_file()}, before)

    def test_new_service_or_firewall_behaviour_stops_for_review(self):
        cases = {
            "service": ("install/config/enable-services.sh", "systemctl enable sddm.service\n",
                        "systemctl enable sddm.service\nsystemctl enable bolt.service\n", "bolt.service"),
            "firewall": ("install/config/firewall.sh", "ufw default allow outgoing\n",
                         "ufw default allow outgoing\nufw allow 22/tcp\n", "22/tcp"),
            "activation": ("install/config/firewall.sh", "systemctl enable ufw\n",
                           "systemctl enable ufw\nsystemctl enable ufw-docker\n", "activation"),
        }
        for name, (relative, old, new, detail) in cases.items():
            with self.subTest(name=name):
                source = self.root / ("behaviour-" + name)
                shutil.copytree(FIXTURES / "source", source)
                path = source / relative
                path.write_text(path.read_text().replace(old, new, 1))
                COMPAT.patch_sources(source, LOCK)
                with self.assertRaisesRegex(CHECKS.ReviewRequired, "hasn't reviewed yet.*" + detail):
                    CHECKS.check(source)

    def test_unreviewed_owner_program_builds_for_manual_owner_setup_only(self):
        for relative in ("bin/omarchy-provision-owner", "install/provisioning/setup-form.sh",
                         "install/provisioning/luks-rekey.sh", "install/provisioning/progress-icon.sh",
                         "bin/omarchy-provision-user"):
            with self.subTest(relative=relative):
                source = self.root / ("owner-" + relative.replace("/", "-"))
                shutil.copytree(FIXTURES / "source", source)
                path = source / relative
                path.write_text(path.read_text() + "\n# a later Omarchy release\n")
                report = COMPAT.patch_sources(source, LOCK)
                self.assertEqual(report["owner_setup"], "manual")
                self.assertIsNone(report["reviewed_omarchy"])
                self.assertIsNone(report["owner_setup_contract_sha256"])
                self.assertNotEqual(report["owner_programs"], LOCK["reviewed_omarchy"][0]["owner_programs"])

    def test_another_default_browser_is_guarded_by_its_desktop_file_and_builds_for_manual_setup(self):
        source = self.root / "source"
        shutil.copytree(FIXTURES / "source", source)
        path = source / "bin/omarchy-provision-user"
        path.write_text(path.read_text().replace("default-web-browser chromium.desktop", "default-web-browser google-chrome.desktop"))
        report = COMPAT.patch_sources(source, LOCK)
        self.assertEqual(report["owner_setup"], "manual")
        text = path.read_text()
        self.assertIn("if [[ -f /usr/share/applications/google-chrome.desktop ]]; then\n"
                      "  env -u BROWSER XDG_CURRENT_DESKTOP= xdg-settings set default-web-browser google-chrome.desktop\nfi\n", text)
        self.assertNotIn("pacman -Qq chromium", text)

    def test_reviewed_browser_guard_keeps_the_reviewed_owner_program_digest(self):
        source, report = self.patched_source()
        self.assertEqual(report["owner_programs"]["/usr/bin/omarchy-provision-user"],
                         LOCK["reviewed_omarchy"][0]["owner_programs"]["/usr/bin/omarchy-provision-user"])
        self.assertIn("if pacman -Qq chromium >/dev/null 2>&1; then", (source / "bin/omarchy-provision-user").read_text())

    def test_ambiguous_or_missing_default_browser_stops_for_review(self):
        for name, change in {"two": lambda t: t.replace("default-web-browser chromium.desktop",
                                                         "default-web-browser a.desktop\nenv -u BROWSER XDG_CURRENT_DESKTOP= xdg-settings set default-web-browser b.desktop"),
                             "none": lambda t: t.replace("env -u BROWSER XDG_CURRENT_DESKTOP= xdg-settings set default-web-browser chromium.desktop\n", "")}.items():
            with self.subTest(name=name):
                source = self.root / ("browser-" + name)
                shutil.copytree(FIXTURES / "source", source)
                path = source / "bin/omarchy-provision-user"
                path.write_text(change(path.read_text()))
                with self.assertRaisesRegex(COMPAT.CompatibilityError, "hasn't reviewed yet"):
                    COMPAT.patch_sources(source, LOCK)

    def test_missing_owner_program_stops_the_build(self):
        source = self.root / "source"
        shutil.copytree(FIXTURES / "source", source)
        (source / "install/provisioning/luks-rekey.sh").unlink()
        with self.assertRaisesRegex(COMPAT.CompatibilityError, "hasn't reviewed yet"):
            COMPAT.patch_sources(source, LOCK)

    def test_overlapping_reviewed_entries_are_refused(self):
        source = self.root / "source"
        shutil.copytree(FIXTURES / "source", source)
        lock = json.loads(json.dumps(LOCK))
        lock["reviewed_omarchy"].append(dict(lock["reviewed_omarchy"][0], id="duplicate"))
        with self.assertRaisesRegex(COMPAT.CompatibilityError, "overlap"):
            COMPAT.patch_sources(source, lock)

    def installed_root(self, name):
        """The signed package's layout: bin programs in /usr/bin, absolute links beside them."""
        root = self.root / name
        share = root / "usr/share/omarchy"
        for path in (FIXTURES / "source").rglob("*"):
            if not path.is_file():
                continue
            relative = path.relative_to(FIXTURES / "source").as_posix()
            if relative.startswith("bin/"):
                target = root / "usr/bin" / path.name
                (share / "bin").mkdir(parents=True, exist_ok=True)
                (share / relative).symlink_to("/usr/bin/" + path.name)
            else:
                target = share / relative
            target.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(path, target)
        return root

    def test_installed_omarchy_is_patched_in_place_and_must_match_the_checked_package(self):
        package = self.installed_root("package")
        profile = self.root / "profile"
        profile.mkdir()
        (profile / "inputs.lock.json").write_text(json.dumps(LOCK))
        report = COMPAT.patch_sources(package, LOCK, installed=True)
        (profile / "source-compatibility.json").write_text(json.dumps(report))
        target = self.installed_root("target")
        COMPAT.patch_installed(target, profile)
        for relative, hashes in report["files"].items():
            installed = target / ("usr/bin/" + relative[4:] if relative.startswith("bin/") else "usr/share/omarchy/" + relative)
            self.assertFalse(installed.is_symlink())
            self.assertEqual(COMPAT.digest(installed), hashes["patched_sha256"])
        # The absolute links still point at /usr/bin and were never followed.
        self.assertEqual(os.readlink(target / "usr/share/omarchy/bin/omarchy-provision-user"), "/usr/bin/omarchy-provision-user")
        other = self.installed_root("other")
        stale = dict(report, reviewed_omarchy="another-entry")
        (profile / "source-compatibility.json").write_text(json.dumps(stale))
        with self.assertRaisesRegex(COMPAT.CompatibilityError, "differs from the checked channel package"):
            COMPAT.patch_installed(other, profile)

    def test_installed_manual_release_must_match_its_checked_manual_report(self):
        package = self.installed_root("package")
        program = package / "usr/share/omarchy/install/provisioning/progress-icon.sh"
        program.write_text(program.read_text() + "\n# VT colour fix\n")
        profile = self.root / "profile"
        profile.mkdir()
        (profile / "inputs.lock.json").write_text(json.dumps(LOCK))
        report = COMPAT.patch_sources(package, LOCK, installed=True)
        self.assertEqual(report["owner_setup"], "manual")
        (profile / "source-compatibility.json").write_text(json.dumps(report))
        target = self.installed_root("target")
        changed = target / "usr/share/omarchy/install/provisioning/progress-icon.sh"
        changed.write_text(program.read_text())
        COMPAT.patch_installed(target, profile)
        # The reviewed release cannot stand in for the checked manual one.
        reviewed = self.installed_root("reviewed")
        with self.assertRaisesRegex(COMPAT.CompatibilityError, "differs from the checked channel package"):
            COMPAT.patch_installed(reviewed, profile)

    def test_audit_records_the_owner_setup_verdict_in_factory_evidence(self):
        for changed in (False, True):
            with self.subTest(manual=changed):
                package = self.installed_root(f"package-{changed}")
                if changed:
                    icon = package / "usr/share/omarchy/install/provisioning/progress-icon.sh"
                    icon.write_text(icon.read_text() + "\n# VT colour fix\n")
                profile = self.root / f"profile-{changed}"
                profile.mkdir()
                for name in ("base.packages", "excluded.packages"):
                    shutil.copy2(ROOT / "omarchy/image" / name, profile / name)
                (profile / "inputs.lock.json").write_text(json.dumps(LOCK))
                report = COMPAT.patch_sources(package, LOCK, installed=True)
                (profile / "source-compatibility.json").write_text(json.dumps(report))
                target = package  # patched in place, as the image is
                for name in ("boot/EFI/BOOT/BOOTAA64.EFI", "boot/limine.conf", "var/lib/omarchy/provisioning/pending",
                             "var/lib/omarchy/image/deferred-steps", "var/lib/omarchy/image/pacman-keyring"):
                    (target / name).parent.mkdir(parents=True, exist_ok=True)
                    (target / name).write_text("")
                (target / "etc").mkdir(exist_ok=True)
                (target / "etc/passwd").write_text("root:x:0:0::/root:/bin/bash\n")
                packages = COMPAT.package_list(profile / "base.packages") + ["omarchy", "omarchy-settings", "try-omarchy", "dev-workstation-preferences"]
                pacman = SimpleNamespace(stdout="".join(f"{name} 1-1\n" for name in packages))
                output = self.root / f"compatibility-{changed}.json"
                with mock.patch.object(COMPAT.subprocess, "run", return_value=pacman), \
                        mock.patch.object(COMPAT, "check_owner_program_permissions"):
                    COMPAT.audit_root(target, profile, output)
                evidence = json.loads(output.read_text())
                self.assertEqual(evidence["owner_setup"], "manual" if changed else "managed")
                self.assertEqual(evidence["reviewed_omarchy"], None if changed else "lean-a948d8a")
                # The four recorded programs omit progress-icon.sh, so only the
                # builder's verdict tells a progress-icon change apart.
                self.assertEqual(evidence["owner_programs"], {name: digest for name, digest in
                                 LOCK["reviewed_omarchy"][0]["owner_programs"].items() if not name.endswith("progress-icon.sh")})

    def test_a_symlinked_install_script_is_never_patched(self):
        root = self.installed_root("linked")
        script = root / "usr/share/omarchy/install/user/mise.sh"
        real = self.root / "elsewhere-mise.sh"
        shutil.move(script, real)
        script.symlink_to(real)
        before = real.read_bytes()
        with self.assertRaisesRegex(COMPAT.CompatibilityError, "hasn't reviewed yet"):
            COMPAT.patch_sources(root, LOCK, installed=True)
        self.assertEqual(real.read_bytes(), before)

    def test_archive_permissions_match_checkout_modes_without_changing_program_bytes(self):
        source = self.root / "source"
        source.mkdir(mode=0o775)
        program = source / "program"
        program.write_text("#!/bin/bash\ntrue\n")
        program.chmod(0o775)
        data = source / "contract.json"
        data.write_text('{"reviewed":true}\n')
        data.chmod(0o664)
        original = {p.name: COMPAT.digest(p) for p in (program, data)}
        external = self.root / "external"
        external.write_text("preserved")
        external.chmod(0o666)
        (source / "link").symlink_to(external)
        COMPAT.normalize_source_permissions(source)
        self.assertEqual(source.stat().st_mode & 0o777, 0o755)
        self.assertEqual(program.stat().st_mode & 0o777, 0o755)
        self.assertEqual(data.stat().st_mode & 0o777, 0o644)
        self.assertEqual(external.stat().st_mode & 0o777, 0o666)
        self.assertEqual(original, {p.name: COMPAT.digest(p) for p in (program, data)})

    def test_owner_program_audit_rejects_writable_parents_links_and_foreign_owners(self):
        root = self.root / "guest"
        program = root / "usr/share/omarchy/install/provisioning/setup-form.sh"
        program.parent.mkdir(parents=True)
        program.write_text("reviewed program")
        relative = str(program.relative_to(root))
        COMPAT.normalize_source_permissions(root)
        COMPAT.check_owner_program_permissions(root, relative, os.getuid())
        for target in (program, program.parent):
            original = target.stat().st_mode & 0o777
            target.chmod(original | 0o020)
            with self.assertRaises(COMPAT.CompatibilityError):
                COMPAT.check_owner_program_permissions(root, relative, os.getuid())
            target.chmod(original)
        with self.assertRaises(COMPAT.CompatibilityError):
            COMPAT.check_owner_program_permissions(root, relative, os.getuid() + 1)
        link = program.parent / "alias"
        link.symlink_to(program)
        with self.assertRaises(COMPAT.CompatibilityError):
            COMPAT.check_owner_program_permissions(root, str(link.relative_to(root)), os.getuid())
        link.unlink()
        os.link(program, link)
        with self.assertRaises(COMPAT.CompatibilityError):
            COMPAT.check_owner_program_permissions(root, relative, os.getuid())

    def test_required_missing_or_excluded_transitive_packages_fail(self):
        for installed in ({"foot"}, {"foot", "try-omarchy", "docker"}):
            with self.subTest(installed=installed), self.assertRaises(COMPAT.CompatibilityError):
                COMPAT.check_package_set(installed, ["foot", "try-omarchy"], ["docker"])
        COMPAT.check_package_set({"foot", "try-omarchy", "shared-lib"}, ["foot"], ["docker"])

    def test_user_log_errors_cannot_be_hidden_by_successful_outer_script(self):
        for line in ("child: command not found", "theme lock: No such file or directory",
                     "flock: Bad file descriptor", "Theme retint failed: command",
                     "Failed: user/setup (exit code: 1)"):
            with self.subTest(line=line), self.assertRaises(COMPAT.CompatibilityError):
                COMPAT.check_user_log(line + "\nUser finalization complete.")
        COMPAT.check_user_log("lspci: Unable to load libkmod resources: error -2\nUser finalization complete.")

    def test_profiles_are_disjoint_and_delegate_full_developer_stack(self):
        base = set(COMPAT.package_list(IMAGE.PROFILE / "base.packages"))
        excluded = set(COMPAT.package_list(IMAGE.PROFILE / "excluded.packages"))
        self.assertFalse(base & excluded)
        self.assertTrue({"foot", "git", "python", "openssh", "mesa", "ufw", "yay", "base-devel"} <= base)
        self.assertTrue({"docker", "chromium", "mise-bin", "nodejs", "ghostty", "kitty", "1password"} <= excluded)

    def test_foundation_profile_has_no_optional_apps_and_keeps_dependency_exclusions(self):
        required, excluded = IMAGE.package_profile()
        self.assertEqual(required, COMPAT.package_list(IMAGE.PROFILE / "base.packages"))
        self.assertEqual(excluded, COMPAT.package_list(IMAGE.PROFILE / "excluded.packages"))
        apps = {"chromium", "firefox", "visual-studio-code-bin", "code", "claude-desktop",
                "docker", "mise-bin", "nodejs", "1password"}
        self.assertFalse(apps & set(required))
        self.assertTrue(apps <= set(excluded))
        self.assertIn("foot", required)
        COMPAT.check_package_set(required, required, excluded)
        for app in apps:
            with self.subTest(app=app), self.assertRaises(COMPAT.CompatibilityError):
                COMPAT.check_package_set([*required, app], required, excluded)

    def test_foundation_identity_records_only_the_minimal_package_profile(self):
        _, provenance = IMAGE.input_identity(LOCK["managed_try_commit"], 20)
        required, excluded = IMAGE.package_profile()
        self.assertEqual(provenance["package_profile"], {
            "name": "foundation", "required": required, "excluded": excluded,
        })
        self.assertFalse(any("/layouts/" in name for name in provenance["inputs"]))

    def test_bundled_guest_source_is_pinned_and_works_without_a_manager_checkout(self):
        args = IMAGE.build_parser().parse_args([])
        source, commit = IMAGE.source_selection(args, LOCK)
        self.assertEqual(commit, LOCK["managed_try_commit"])
        self.assertEqual(source, IMAGE.PROFILE / LOCK["guest_source"]["archive"])
        IMAGE.validate_source(source, commit, LOCK)
        with mock.patch.object(IMAGE, "run", wraps=IMAGE.run) as run:
            IMAGE.stage_inputs(source, self.root, LOCK, commit)
        self.assertTrue((self.root / "upstream/guest/factory/Containerfile").is_file())
        self.assertTrue(all(call.args[0][0] == "bash" for call in run.call_args_list))
        corrupt = self.root / "corrupt.tar.gz"
        corrupt.write_bytes(source.read_bytes() + b"changed")
        with self.assertRaisesRegex(COMPAT.CompatibilityError, "pinned"):
            IMAGE.validate_source(corrupt, commit, LOCK)
        with self.assertRaisesRegex(COMPAT.CompatibilityError, "pinned"):
            IMAGE.validate_source(source, LOCK["try_commit"], LOCK)
        changed_stage = self.root / "changed-stage"
        changed_stage.mkdir()
        def changed_copy(_source, destination):
            destination.write_bytes(b"changed during staging")
        with mock.patch.object(IMAGE.shutil, "copyfile", side_effect=changed_copy):
            with self.assertRaisesRegex(COMPAT.CompatibilityError, "changed while staging"):
                IMAGE.stage_inputs(source, changed_stage, LOCK, commit)
        args.try_source = self.root
        args.try_commit = LOCK["try_commit"]
        self.assertEqual(IMAGE.source_selection(args, LOCK), (self.root, LOCK["try_commit"]))

    def test_single_factory_make_target_preserves_plan_mode_and_rejects_layout_selection(self):
        result = subprocess.run([
            "make", "--no-print-directory", "-n", "build-omarchy-image", "OMARCHY_IMAGE_PLAN=yes",
        ], cwd=ROOT, check=True, capture_output=True, text=True)
        command = result.stdout.replace("\\\n", "").strip()
        args = IMAGE.build_parser().parse_args(shlex.split(command)[2:])
        self.assertTrue(args.plan)
        self.assertIsNone(args.try_source)
        with contextlib.redirect_stderr(io.StringIO()), self.assertRaises(SystemExit):
            IMAGE.build_parser().parse_args(["--layout", "terminal-browser"])

    def test_package_lists_reject_duplicates_empty_names_and_shell_input(self):
        path = self.root / "packages"
        for value in ("", "foot\nfoot\n", "$(touch nope)\n", "--root\n"):
            path.write_text(value)
            with self.subTest(value=value), self.assertRaises(COMPAT.CompatibilityError):
                COMPAT.package_list(path)

    def test_software_rendering_is_detected_in_each_backend(self):
        path = self.root / "environment"
        for value in ("LIBGL_ALWAYS_SOFTWARE=1", "WLR_RENDERER_ALLOW_SOFTWARE=1",
                      "QT_QUICK_BACKEND=software", "QSG_RHI_BACKEND=software",
                      "GALLIUM_DRIVER=llvmpipe", "GALLIUM_DRIVER=softpipe"):
            path.write_text(value)
            with self.subTest(value=value):
                self.assertEqual(COMPAT.software_settings(self.root), ["environment"])
        path.write_text("MOZ_ENABLE_WAYLAND=1\n")
        self.assertEqual(COMPAT.software_settings(self.root), [])

    def integration_recipe(self):
        recipe = self.root / "integration"
        recipe.mkdir()
        (recipe / "PKGBUILD").write_text("pkgname=try-omarchy\npkgrel=40\n")
        files = recipe / "files"
        hyprland = files / "usr/share/try-omarchy/hyprland.lua"
        hyprland.parent.mkdir(parents=True)
        shutil.copyfile(FIXTURES / "integration-hyprland.lua", hyprland)
        for relative in (
            "usr/lib/environment.d/90-try-omarchy.conf",
            "usr/lib/try-omarchy/bin/ghostty", "usr/lib/try-omarchy/bin/kitty",
            "usr/lib/systemd/user/app-com.mitchellh.ghostty.service.d/10-try-omarchy-software-gl.conf",
            "usr/share/try-omarchy/ghostty/com.mitchellh.ghostty.desktop",
            "usr/share/libalpm/hooks/try-omarchy-ghostty.hook",
            "usr/share/libalpm/hooks/try-omarchy-ghostty-remove.hook",
        ):
            path = files / relative
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text("WLR_RENDERER_ALLOW_SOFTWARE=1\n" if "environment.d" in relative else "LIBGL_ALWAYS_SOFTWARE=1\n")
        return recipe

    def test_integration_is_versioned_and_all_software_paths_are_removed(self):
        recipe = self.integration_recipe()
        COMPAT.prepare_integration(recipe)
        self.assertIn("pkgrel=40.1", (recipe / "PKGBUILD").read_text())
        self.assertIn("skip_non_kms_dmabuf_formats = false",
                      (recipe / "files/usr/share/try-omarchy/hyprland.lua").read_text())
        self.assertEqual(COMPAT.software_settings(recipe / "files"), [])
        self.assertFalse((recipe / "files/usr/lib/try-omarchy/bin/ghostty").exists())

    def test_unknown_integration_software_path_blocks_build(self):
        recipe = self.integration_recipe()
        (recipe / "files/unreviewed.conf").write_text("QT_QUICK_BACKEND=software")
        with self.assertRaisesRegex(COMPAT.CompatibilityError, "Unreviewed software"):
            COMPAT.prepare_integration(recipe)

    def test_changed_native_hyprland_policy_is_not_silently_rewritten(self):
        recipe = self.integration_recipe()
        policy = recipe / "files/usr/share/try-omarchy/hyprland.lua"
        policy.write_text(policy.read_text() + "\n-- changed upstream policy\n")
        with self.assertRaisesRegex(COMPAT.CompatibilityError, "Unreviewed integration Hyprland"):
            COMPAT.prepare_integration(recipe)

    def test_builder_retains_disk_boot_and_sealing_and_changes_package_selection(self):
        upstream = FIXTURES / "build-image.sh"
        self.assertEqual(COMPAT.digest(upstream), LOCK["builder_sha256"])
        result = IMAGE.adapt_builder(upstream.read_text(), LOCK)
        self.assertNotIn("/usr/bin/omarchy-pkg-defaults aarch64", result)
        self.assertNotIn("target_install omarchy-nvim", result)
        for required in ("losetup --find --show", "BOOTAA64.EFI", "btrfs -q subvolume snapshot -r",
                         "omarchy-apply-system --defer-provisioning --first-install",
                         "omarchy-provision-owner.service", 'rm -rf "$target/etc/pacman.d/gnupg"',
                         "compatibility.py audit-root", "node-v26.13.0-linux-arm64.tar.gz"):
            self.assertIn(required, result)
        path = self.root / "builder.sh"
        path.write_text(result)
        subprocess.run(["bash", "-n", str(path)], check=True)

    def test_builder_installs_the_checked_channel_pair_and_patches_it_in_place(self):
        result = IMAGE.adapt_builder((FIXTURES / "build-image.sh").read_text(), LOCK)
        self.assertNotIn("published on the edge channel only", result)
        self.assertIn('[[ $channel == stable || $channel == edge ]]', result)
        self.assertIn('runtime_package=omarchy\n  settings_package=omarchy-settings\n', result)
        self.assertIn('runtime_package=omarchy-dev\n  settings_package=omarchy-settings-dev\n', result)
        self.assertIn('/packages/"$runtime_package"-[0-9]*.pkg.tar.zst\n'
                      'python3 /profile/compatibility.py patch-installed "$target" /profile\n', result)
        self.assertLess(result.index("patch-installed"), result.index("omarchy-apply-system --defer-provisioning"))
        self.assertIn("image_name=omarchy-workstation-aarch64-$channel.img", result)
        self.assertIn("arm_mirror='https://arm-stable-mirror.omarchy.org/$arch/$repo'", result)
        self.assertIn("arm_mirror='https://arm-mirror.omarchy.org/$arch/$repo'", result)

    def test_container_script_takes_the_channel_and_no_pinned_omarchy_sources(self):
        script = (ROOT / "omarchy/image/build-container.sh").read_text()
        self.assertIn('channel=${3:-edge}', script)
        self.assertIn('Server = https://pkgs.omarchy.org/$channel/', script)
        self.assertIn('pacman -Swdd', script)
        self.assertIn("arm_mirror='https://arm-stable-mirror.omarchy.org/$arch/$repo'", script)
        self.assertLess(script.index(">/etc/pacman.d/mirrorlist"), script.index("pacman -Syyu"))
        self.assertIn('--channel "$channel"', script)
        for removed in ("omarchy_commit", "recipes_commit", "makepkg --nodeps --force --noconfirm\n    local packages=(./*.pkg.tar.zst)\n    ((${#packages[@]} == 1))\n    install -m 0644 \"${packages[0]}\" /output/packages/\n  )\n}\n\nfor package in omarchy"):
            self.assertNotIn(removed, script)
        for key in ("omarchy_commit", "recipes_commit", "omarchy_version", "archives", "scripts"):
            self.assertNotIn(key, LOCK)

    def test_upstream_builder_anchor_drift_is_refused(self):
        upstream = (FIXTURES / "build-image.sh").read_text()
        with self.assertRaises(COMPAT.CompatibilityError):
            IMAGE.adapt_builder(upstream.replace('target_install "$runtime_package"', "different"), LOCK)

    def test_plan_never_invokes_docker_downloads_or_creates_artifacts(self):
        args = IMAGE.build_parser().parse_args(["--try-source", str(self.root), "--plan"])
        with mock.patch.object(IMAGE, "validate_source"), \
                mock.patch.object(IMAGE, "download") as download, mock.patch.object(IMAGE, "run") as run, \
                mock.patch.object(IMAGE, "ARTIFACTS", self.root / "artifacts"), \
                contextlib.redirect_stdout(io.StringIO()) as output:
            IMAGE.build(args)
        download.assert_not_called()
        run.assert_not_called()
        self.assertFalse((self.root / "artifacts").exists())
        self.assertIn("no VM operations", output.getvalue())
        self.assertIn("Optional applications: none", output.getvalue())

    def test_download_cache_checksum_and_symlinks_are_refused_without_network(self):
        cached = self.root / "cached"
        cached.write_text("corrupt")
        with mock.patch.object(IMAGE.urllib.request, "urlopen") as request:
            with self.assertRaisesRegex(COMPAT.CompatibilityError, "checksum"):
                IMAGE.download("https://example.invalid", cached, "0" * 64)
            linked = self.root / "linked"
            linked.symlink_to(cached)
            with self.assertRaisesRegex(COMPAT.CompatibilityError, "linked"):
                IMAGE.download("https://example.invalid", linked, "0" * 64)
            request.assert_not_called()

    def test_source_must_be_clean_and_at_exact_commit(self):
        with mock.patch.object(IMAGE, "git", return_value="other"):
            with self.assertRaisesRegex(COMPAT.CompatibilityError, "clean"):
                IMAGE.validate_source(self.root, LOCK["try_commit"], LOCK)
        with self.assertRaisesRegex(COMPAT.CompatibilityError, "40-character"):
            IMAGE.validate_source(self.root, "main", LOCK)

    def test_export_uses_selected_commit_and_refuses_archive_links_or_traversal(self):
        for name, kind in (("guest/link", tarfile.SYMTYPE),
                           ("guest/hardlink", tarfile.LNKTYPE),
                           ("guest/../../escape", tarfile.REGTYPE)):
            stage = self.root / str(len(list(self.root.iterdir())))
            stage.mkdir()

            def export(argv, **kwargs):
                self.assertEqual(argv[4], LOCK["try_commit"])
                with tarfile.open(fileobj=kwargs["stdout"], mode="w") as archive:
                    member = tarfile.TarInfo(name)
                    member.type = kind
                    member.linkname = "/outside"
                    archive.addfile(member)

            with self.subTest(name=name), mock.patch.object(IMAGE, "run", side_effect=export):
                with self.assertRaisesRegex(COMPAT.CompatibilityError, "Unsafe upstream"):
                    IMAGE.stage_inputs(self.root, stage, LOCK)
            self.assertFalse((self.root / "escape").exists())

    def test_staging_keeps_the_foundation_bare_and_configuration_inputs_unchanged(self):
        original = {name: (IMAGE.PROFILE / name).read_bytes()
                    for name in ("base.packages", "excluded.packages")}
        stage = self.root / "foundation"
        stage.mkdir()
        IMAGE.stage_inputs(IMAGE.PROFILE / LOCK["guest_source"]["archive"], stage, LOCK,
                           LOCK["managed_try_commit"])
        required, excluded = IMAGE.package_profile()
        self.assertEqual(COMPAT.package_list(stage / "profile/base.packages"), required)
        self.assertEqual(COMPAT.package_list(stage / "profile/resolved-base.packages"), required)
        self.assertEqual(COMPAT.package_list(stage / "profile/excluded.packages"), excluded)
        self.assertEqual((stage / "profile/preferences/first-login.sh").read_bytes(),
                         (IMAGE.PROFILE / "preferences/first-login.sh").read_bytes())
        self.assertFalse((stage / "profile/layout.lua").exists())
        self.assertEqual(original, {name: (IMAGE.PROFILE / name).read_bytes() for name in original})

    def test_reviewed_integration_reuse_rejects_archive_and_complete_recipe_changes(self):
        IMAGE.stage_inputs(IMAGE.PROFILE / LOCK["guest_source"]["archive"], self.root, LOCK,
                           LOCK["managed_try_commit"])
        profile = self.root / "profile"
        recipe = self.root / "upstream/guest/package/try-omarchy"
        archive = profile / LOCK["reviewed_integration"]["archive"]
        original = archive.read_bytes()
        self.assertEqual(COMPAT.digest(archive), LOCK["reviewed_integration"]["sha256"])
        for problem in ("bytes", "mode", "addition", "license"):
            with self.subTest(problem=problem):
                target = recipe / ("LICENSE" if problem == "license" else "PKGBUILD")
                contents, mode = target.read_bytes(), target.stat().st_mode & 0o777
                if problem == "mode":
                    target.chmod(0o755)
                elif problem == "addition":
                    (recipe / "unexpected").write_text("unreviewed")
                else:
                    target.write_bytes(contents + b"changed")
                with self.assertRaisesRegex(COMPAT.CompatibilityError, "manager policy review"):
                    IMAGE.verify_reviewed_integration(profile, recipe, LOCK)
                target.write_bytes(contents)
                target.chmod(mode)
                (recipe / "unexpected").unlink(missing_ok=True)
        archive.write_bytes(original + b"repacked")
        with self.assertRaisesRegex(COMPAT.CompatibilityError, "archive checksum"):
            IMAGE.verify_reviewed_integration(profile, recipe, LOCK)
        archive.unlink()
        archive.symlink_to(IMAGE.PROFILE / LOCK["reviewed_integration"]["archive"])
        with self.assertRaisesRegex(COMPAT.CompatibilityError, "archive checksum"):
            IMAGE.verify_reviewed_integration(profile, recipe, LOCK)

    def test_foundation_artifacts_publish_checksums_and_unproven_validation_flags(self):
        def stage_inputs(source, stage, lock, commit):
            profile = stage / "profile"
            profile.mkdir()
            required, excluded = IMAGE.package_profile()
            (profile / "base.packages").write_text("\n".join(required) + "\n")
            (profile / "excluded.packages").write_text("\n".join(excluded) + "\n")

        def container(argv, **kwargs):
            if argv[:2] != ["docker", "run"]:
                return
            mount = next(str(arg) for arg in argv if str(arg).endswith(",dst=/output"))
            output = Path(mount.removeprefix("type=bind,src=").removesuffix(",dst=/output"))
            image = output / "omarchy-workstation-aarch64-edge.img.zst"
            image.write_bytes(b"simulated-container-output")
            (output / "factory.json").write_text(json.dumps({
                "compressed": {"path": image.name, "sha256": COMPAT.digest(image)},
                "disk": {"sha256": "a" * 64},
            }))

        for check_only in (False, True):
            artifacts = self.root / str(check_only)
            artifacts.mkdir()
            args = IMAGE.build_parser().parse_args(["--try-source", str(self.root)] + (["--check-only"] if check_only else []))
            with self.subTest(check_only=check_only), mock.patch.object(IMAGE, "ARTIFACTS", artifacts), \
                    mock.patch.object(IMAGE, "validate_source"), mock.patch.object(IMAGE, "download"), \
                    mock.patch.object(IMAGE.platform, "system", return_value="Darwin"), \
                    mock.patch.object(IMAGE.platform, "machine", return_value="arm64"), \
                    mock.patch.object(IMAGE.shutil, "which", return_value="/existing/docker"), \
                    mock.patch.object(IMAGE.shutil, "disk_usage", return_value=SimpleNamespace(free=2**40)), \
                    mock.patch.object(IMAGE.subprocess, "check_output", side_effect=["aarch64\n", "sha256:builder\n"]), \
                    mock.patch.object(IMAGE, "stage_inputs", side_effect=stage_inputs), \
                    mock.patch.object(IMAGE, "run", side_effect=container) as run, \
                    contextlib.redirect_stdout(io.StringIO()):
                IMAGE.build(args)
            published, = (entry for entry in artifacts.iterdir() if not entry.is_symlink() and (entry / "image-build.json").is_file())
            provenance = json.loads((published / "image-build.json").read_text())
            self.assertEqual(provenance["package_profile"]["name"], "foundation")
            self.assertFalse(provenance["guest_boot_tested"])
            self.assertFalse(provenance["manager_admitted"])
            self.assertEqual(provenance["package_profile"]["required"],
                             COMPAT.package_list(published / "base.packages"))
            self.assertEqual(provenance["package_profile"]["excluded"],
                             COMPAT.package_list(published / "excluded.packages"))
            self.assertFalse((published / "layout.lua").exists())
            checksums = dict(line.split("  ", 1)[::-1] for line in (published / "SHA256SUMS").read_text().splitlines())
            for name in ("base.packages", "excluded.packages", "image-build.json"):
                self.assertEqual(checksums[name], COMPAT.digest(published / name))
            self.assertTrue(all(call.args[0][0] == "docker" for call in run.call_args_list))
            if check_only:
                self.assertFalse((artifacts / "latest").exists())
            else:
                self.assertEqual((artifacts / "latest").resolve(), published.resolve())

    def test_latest_link_preserves_prior_builds_and_refuses_unrelated_paths(self):
        artifacts = self.root / "artifacts"
        artifacts.mkdir()
        first = artifacts / ("a" * 16 + "-" + "b" * 16)
        second = artifacts / ("c" * 16 + "-" + "d" * 16)
        first.mkdir()
        second.mkdir()
        with mock.patch.object(IMAGE, "ARTIFACTS", artifacts):
            IMAGE.publish_latest(first)
            self.assertEqual((artifacts / "latest").resolve(), first.resolve())
            IMAGE.publish_latest(second)
            self.assertEqual((artifacts / "latest").resolve(), second.resolve())
            self.assertTrue(first.is_dir())
            (artifacts / "latest").unlink()
            (artifacts / "latest").write_text("unrelated")
            with self.assertRaises(COMPAT.CompatibilityError):
                IMAGE.publish_latest(first)
            self.assertEqual((artifacts / "latest").read_text(), "unrelated")
            (artifacts / "latest").unlink()
            (artifacts / "latest").symlink_to("../unrelated")
            with self.assertRaises(COMPAT.CompatibilityError):
                IMAGE.publish_latest(first)
            self.assertEqual(os.readlink(artifacts / "latest"), "../unrelated")

    def sealed_root(self):
        for name in ("etc/ssh", "etc/pacman.d", "var/lib/systemd", "var/cache/pacman/pkg"):
            (self.root / name).mkdir(parents=True)
        (self.root / "etc/machine-id").write_text("")
        (self.root / "etc/shadow").write_text("root:!*:1:0:99999:7:::\n")
        report = self.root / "compatibility.json"
        report.write_text('{"owner_provisioning":"not-tested"}')
        return report

    def test_sealing_requires_unique_first_boot_identities_and_locked_root(self):
        report = self.sealed_root()
        COMPAT.audit_seal(self.root, report)
        result = json.loads(report.read_text())
        self.assertEqual(result["identity_sealing"], "passed")
        self.assertEqual(result["owner_provisioning"], "not-tested")
        for name in ("etc/machine-id", "etc/ssh/ssh_host_ed25519_key",
                     "var/lib/systemd/random-seed", "var/cache/pacman/pkg/package.pkg.tar.zst"):
            path = self.root / name
            path.write_text("must-not-be-shared")
            with self.subTest(name=name), self.assertRaises(COMPAT.CompatibilityError):
                COMPAT.audit_seal(self.root, report)
            path.unlink()
            if name == "etc/machine-id":
                path.touch()

    def test_unlocked_root_password_is_never_published(self):
        report = self.sealed_root()
        (self.root / "etc/shadow").write_text("root::1:0:99999:7:::\n")
        with self.assertRaisesRegex(COMPAT.CompatibilityError, "locked password"):
            COMPAT.audit_seal(self.root, report)


if __name__ == "__main__":
    unittest.main()
