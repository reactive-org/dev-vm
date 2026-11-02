import importlib.util
import json
import shutil
import subprocess
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest import mock


ROOT = Path(__file__).resolve().parents[1]
SPEC = importlib.util.spec_from_file_location("guest_features", ROOT / "omarchy/guest/apply-features.py")
FEATURE = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(FEATURE)


def reply(code=0, stdout="", stderr=""):
    return subprocess.CompletedProcess([], code, stdout, stderr)


class Guest:
    def __init__(self, official=False):
        self.packages = {"try-omarchy", "python", "foot", "ufw", "bash"}
        self.tools = {}
        self.configured = {"node", "claude", "codex", "opencode"}
        self.calls = []
        self.active = False
        self.enabled = False
        self.service = False
        self.firewall = False
        self.ufw_active = True
        self.home = None
        self.shell = "/bin/bash"
        self.zsh_syntax = self.zsh_environment = self.zsh_activation = True
        self.docker_configured = self.docker_access = True
        # Observed on both live ARM64 factories; do not let fixtures silently
        # validate a nonexistent ShellCheck repository package again.
        self.unavailable = {"shellcheck"}
        self.unknown_tools = set()
        if official:
            self.packages.update(["chromium", "mise-bin", "1password", "1password-cli", *FEATURE.DOCKER_PACKAGES])
            self.tools = {"node": "/tools/node/default", "claude": "/tools/claude/default"}
            self.active = self.enabled = self.firewall = True

    def run(self, argv, **kwargs):
        self.calls.append(tuple(argv))
        if argv[:2] == ["pacman", "-Qq"]:
            return reply(0 if argv[-1] in self.packages else 1)
        if argv[:2] == ["pacman", "-Si"]:
            return reply(1 if argv[-1] in self.unavailable else 0)
        if argv == ["sudo", "-n", "true"]:
            return reply()
        raise AssertionError(argv)

    def native(self, argv, **kwargs):
        self.calls.append(tuple(argv))
        if argv[:2] == ["command", "-v"]:
            return reply()
        if argv[:2] == ["bash", "-ic"]:
            return reply()
        if argv[:2] == ["test", "-x"]:
            return reply(0 if Path(argv[-1]).name in self.packages else 1)
        if argv[:2] == ["zsh", "-n"]:
            return reply(0 if self.zsh_syntax else 1, stderr="invalid zsh configuration")
        if argv[:2] == ["zsh", "-ic"]:
            return reply(0 if (self.zsh_environment if "OMARCHY_PATH" in argv[-1] else self.zsh_activation) else 1)
        if argv[:3] == ["env", "DISABLE_AUTO_UPDATE=true", "zsh"]:
            return reply(0 if (self.zsh_environment if "OMARCHY_PATH" in argv[-1] else self.zsh_activation) else 1)
        if argv[:4] == ["env", "GIT_TERMINAL_PROMPT=0", "GIT_ASKPASS=/bin/false", "git"]:
            path = Path(argv[-1])
            path.mkdir()
            (path / "oh-my-zsh.sh").write_text("# upstream fixture\n")
            for name in ("git", "docker", "docker-compose"):
                plugin = path / "plugins" / name
                plugin.mkdir(parents=True)
                (plugin / (name + ".plugin.zsh")).touch()
            return reply()
        if argv[:3] == ["sudo", "-n", "chsh"]:
            self.shell = argv[argv.index("-s") + 1]
            return reply()
        if argv[0] == "omarchy-pkg-add":
            self.packages.update(argv[1:])
            return reply()
        if argv[0] == "omarchy-install-browser":
            self.packages.add(FEATURE.BROWSERS[argv[1]])
            return reply()
        if argv[:2] == ["mise", "reshim"]:
            return reply()
        if argv[:2] == ["mise", "registry"]:
            return reply(1 if argv[-1] in self.unknown_tools else 0, "registry-backend")
        if argv[:2] == ["mise", "where"]:
            path = self.tools.get(argv[2])
            return reply(0 if path else 1, (path + "\n") if path else "")
        if argv[:2] == ["mise", "ls"]:
            tool = argv[-1]
            return reply(stdout=json.dumps([{"requested_version": "latest", "active": True}]
                                           if tool in self.configured else []))
        if argv[:2] == ["mise", "install"]:
            self.tools[argv[-1]] = "/tools/" + argv[-1] + "/default"
            return reply()
        if argv[:3] == ["mise", "use", "--global"]:
            selector = argv[-1]
            tool = selector.split("@", 1)[0]
            self.tools[tool] = self.tools[selector] = "/tools/" + selector
            self.configured.add(tool)
            return reply()
        if argv[0] == "omarchy-sudo-docker":
            return reply(1 if (self.docker_configured if "--configured" in argv else self.docker_access) else 0)
        if argv[:4] == ["env", "-u", "DOCKER_HOST", "-u"] and "/usr/bin/docker" in argv:
            permitted = "sudo" in argv or self.docker_access
            return reply(0 if permitted else 1, stdout="29.9.2\n" if permitted else "", stderr="permission denied" if not permitted else "")
        if argv[:2] in (["/usr/bin/docker", "compose"], ["/usr/bin/docker", "buildx"]):
            return reply(stdout="native plugin version\n")
        if argv[:3] == ["sudo", "-n", "ufw"]:
            return reply(stdout="Status: active\n" if self.ufw_active else "Status: inactive\n")
        if argv[:3] == ["sudo", "-n", "sha256sum"]:
            return reply(stdout="configured" if self.firewall else "unconfigured")
        if argv == ["sudo", "-n", "ufw-docker", "install"]:
            self.firewall = True
            return reply()
        if argv == ["systemctl", "is-enabled", "--quiet", "docker.socket"]:
            return reply(0 if self.enabled else 1)
        if argv == ["systemctl", "is-active", "--quiet", "docker.socket"]:
            return reply(0 if self.active else 1)
        if argv == ["systemctl", "is-active", "--quiet", "docker.service"]:
            return reply(0 if self.service else 1)
        if argv == ["sudo", "-n", "systemctl", "enable", "--now", "docker.socket"]:
            self.active = self.enabled = True
            return reply()
        if argv[0] == "bash" and argv[1].endswith(("apply-workstation.sh", "repair-try-omarchy-black-screen.sh")):
            return reply()
        raise AssertionError(argv)


class FeatureTests(unittest.TestCase):
    def apply(self, guest, feature, config, check=False, extension=False, defer_docker_access=False):
        if guest.home is None:
            temporary = tempfile.TemporaryDirectory(prefix="omarchy-feature-home-")
            self.addCleanup(temporary.cleanup)
            guest.home = Path(temporary.name)
            guest.shells_file = guest.home / "shells"
            guest.shells_file.write_text("/bin/bash\n/usr/bin/zsh\n")
        with mock.patch.object(FEATURE, "run", side_effect=guest.run), \
                mock.patch.object(FEATURE, "native", side_effect=guest.native), \
                mock.patch.object(FEATURE.Path, "home", return_value=guest.home), \
                mock.patch.object(FEATURE, "SHELLS_FILE", guest.shells_file), \
                mock.patch.object(FEATURE.pwd, "getpwuid", side_effect=lambda _: SimpleNamespace(pw_name="owner", pw_shell=guest.shell)), \
                mock.patch.object(FEATURE.platform, "system", return_value="Linux"), \
                mock.patch.object(FEATURE.platform, "machine", return_value="aarch64"), \
                mock.patch.object(FEATURE.os, "geteuid", return_value=1000):
            return FEATURE.FeatureRunner(feature, config, check, extension=extension,
                                         defer_docker_access=defer_docker_access).apply()

    def test_new_capabilities_are_selective_and_reapply_without_changes(self):
        for name in ("cli", "vcs", "editors", "build", "databases", "api", "quality"):
            for official in (False, True):
                with self.subTest(feature=name, official=official):
                    guest = Guest(official)
                    config = FEATURE.CATALOGUE["features"][name]["defaults"]
                    self.assertTrue(self.apply(guest, name, config)["changed"])
                    self.assertFalse(self.apply(guest, name, config)["changed"])
                    forbidden = ("git", "config", "--global"), ("git", "lfs", "install"), ("systemctl", "enable")
                    for call in guest.calls:
                        self.assertFalse(any(call[:len(prefix)] == prefix for prefix in forbidden))

    def test_complete_profiles_apply_to_both_factory_fixtures_and_reapply_as_noop(self):
        import sys
        sys.path.insert(0, str(ROOT / "scripts"))
        from omarchy_profiles import Resolver
        for profile in ("developer", "web", "python", "project-managed"):
            for official in (False, True):
                with self.subTest(profile=profile, official=official):
                    guest = Guest(official)
                    plan = Resolver().resolve(profiles=[profile])
                    for feature in plan["features"]:
                        self.apply(guest, feature, plan["options"][feature])
                    for feature in plan["features"]:
                        self.assertFalse(self.apply(guest, feature, plan["options"][feature])["changed"], feature)
                    self.assertNotIn("1password-cli", set(plan["packages"]))
                    if profile == "python":
                        self.assertEqual(set(guest.tools) - ({"node", "claude"} if official else set()),
                                         {"python", "python@3", "uv", "uv@latest", "shellcheck", "shellcheck@latest"})

    def test_project_toolchain_prepares_native_prerequisites_without_installing_runtimes(self):
        for official in (False, True):
            guest = Guest(official)
            original_tools = dict(guest.tools)
            config = {"prerequisites": ["ruby", "python"]}
            self.assertTrue(self.apply(guest, "toolchain", config, check=True)["changed"])
            self.assertNotIn("libyaml", guest.packages)
            self.assertTrue(self.apply(guest, "toolchain", config)["changed"])
            self.assertFalse(self.apply(guest, "toolchain", config)["changed"])
            self.assertTrue({"mise-bin", "libyaml", "gmp", "xz"} <= guest.packages)
            self.assertEqual(guest.tools, original_tools)
            for call in guest.calls:
                self.assertNotIn(call[:2], (("mise", "install"), ("mise", "use"), ("mise", "trust")))

    def test_project_toolchain_refuses_missing_native_shell_activation(self):
        guest = Guest(True)
        native = guest.native
        def without_activation(argv, **kwargs):
            return reply(1) if argv[:2] == ["bash", "-ic"] else native(argv, **kwargs)
        guest.native = without_activation
        with self.assertRaisesRegex(FEATURE.FeatureError, "native Bash mise activation"):
            self.apply(guest, "toolchain", {"prerequisites": []})

    def test_project_toolchain_rejects_arbitrary_prerequisite_names(self):
        for config in ({"prerequisites": ["ruby", "ruby"]}, {"prerequisites": ["node"]},
                       {"prerequisites": [], "project": "/some/project"}):
            with self.assertRaises(FEATURE.FeatureError):
                FEATURE.FeatureRunner("toolchain", config)

    def test_extension_tools_packages_check_mode_and_empty_selection(self):
        guest = Guest()
        config = {"packages": ["jq"], "tools": {"uv": ""}}
        self.assertTrue(self.apply(guest, "example.api", config, check=True, extension=True)["changed"])
        self.assertNotIn("jq", guest.packages)
        self.assertTrue(self.apply(guest, "example.api", config, extension=True)["changed"])
        self.assertFalse(self.apply(guest, "example.api", config, extension=True)["changed"])
        self.assertFalse(self.apply(guest, "example.api", {"packages": [], "tools": {}}, extension=True)["changed"])
        self.assertIn("jq", guest.packages)

    def test_missing_package_preflight_stops_all_roles_before_any_installation(self):
        guest = Guest()
        guest.unavailable.add("nonexistent")
        plan = [{"feature": "cli", "config": {"packages": ["jq"], "tools": {}}, "extension": False},
                {"feature": "example.bad", "config": {"packages": ["nonexistent"], "tools": {}}, "extension": True}]
        with mock.patch.object(FEATURE, "run", side_effect=guest.run), \
                mock.patch.object(FEATURE, "native", side_effect=guest.native), \
                mock.patch.object(FEATURE.platform, "system", return_value="Linux"), \
                mock.patch.object(FEATURE.platform, "machine", return_value="aarch64"), \
                mock.patch.object(FEATURE.os, "geteuid", return_value=1000):
            with self.assertRaisesRegex(FEATURE.FeatureError, "unavailable"):
                FEATURE.preflight_plan(plan)
        self.assertNotIn("jq", guest.packages)
        self.assertFalse(any(call[0] == "omarchy-pkg-add" for call in guest.calls))

    def test_unknown_mise_tool_and_unsafe_extensions_are_rejected(self):
        guest = Guest(official=True)
        guest.unknown_tools.add("unknown-tool")
        with self.assertRaisesRegex(FEATURE.FeatureError, "registry"):
            self.apply(guest, "example.cli", {"packages": [], "tools": {"unknown-tool": ""}}, extension=True)
        for name, config in [("builtin.bad", {"packages": [], "tools": {}}),
                             ("example.bad", {"packages": ["--help"], "tools": {}}),
                             ("example.bad", {"packages": [], "tools": {}, "command": "id"})]:
            with self.assertRaises(FEATURE.FeatureError):
                self.apply(guest, name, config, extension=True)

    def test_native_mise_provider_is_reused_for_legacy_github_cli_selection(self):
        guest = Guest(official=True)
        guest.configured.add("gh")
        self.assertTrue(self.apply(guest, "credentials", {"packages": ["github-cli"]})["changed"])
        self.assertNotIn("github-cli", guest.packages)
        self.assertIn(("mise", "install", "gh"), guest.calls)
        self.assertFalse(self.apply(guest, "credentials", {"packages": ["github-cli"]})["changed"])

    def test_extension_package_cannot_silently_shadow_an_existing_mise_tool(self):
        guest = Guest(official=True)
        guest.configured.add("gh")
        with self.assertRaisesRegex(FEATURE.FeatureError, "competes"):
            self.apply(guest, "example.cli", {"packages": ["github-cli"], "tools": {}}, extension=True)
        self.assertNotIn("github-cli", guest.packages)

    def test_expired_package_archive_reports_native_update_without_running_it(self):
        guest = Guest()
        original = guest.native

        def expired(argv, **kwargs):
            if argv[0] == "omarchy-pkg-add":
                guest.calls.append(tuple(argv))
                raise FEATURE.FeatureError("failed retrieving archive: 404")
            return original(argv, **kwargs)

        with mock.patch.object(FEATURE, "run", side_effect=guest.run), \
                mock.patch.object(FEATURE, "native", side_effect=expired):
            runner = FEATURE.FeatureRunner("cli", {"packages": ["jq"], "tools": {}})
            with self.assertRaisesRegex(FEATURE.FeatureError, "omarchy update"):
                runner.packages(["jq"])
        self.assertFalse(any(call[0].startswith("omarchy-update") or call[:2] == ("omarchy", "update") for call in guest.calls))
        self.assertFalse(any(call[0] == "pacman" and any(arg.startswith("-S") and arg != "-Si" for arg in call[1:]) for call in guest.calls))

    def test_quality_uses_native_mise_shellcheck_when_arm_package_is_unavailable(self):
        for official in (False, True):
            with self.subTest(official=official):
                guest = Guest(official)
                config = FEATURE.CATALOGUE["features"]["quality"]["defaults"]
                self.apply(guest, "quality", config)
                self.assertIn("shellcheck", guest.tools)
                self.assertNotIn("shellcheck", guest.packages)
                self.assertFalse(self.apply(guest, "quality", config)["changed"])

    def test_browser_feature_works_on_official_and_lean_and_reapply_is_noop(self):
        for official in (False, True):
            with self.subTest(official=official):
                guest = Guest(official)
                result = self.apply(guest, "browsers", {"browsers": ["chromium"]})
                self.assertEqual(result["changed"], not official)
                self.assertFalse(self.apply(guest, "browsers", {"browsers": ["chromium"]})["changed"])
                self.assertNotIn("firefox", guest.packages)

    def test_credentials_installs_only_requested_packages_without_auth_or_app_launch(self):
        guest = Guest()
        result = self.apply(guest, "credentials", {"packages": ["1password-cli"]})
        self.assertTrue(result["changed"])
        self.assertIn("1password-cli", guest.packages)
        self.assertNotIn("1password", guest.packages)
        self.assertFalse(self.apply(guest, "credentials", {"packages": ["1password-cli"]})["changed"])
        self.assertFalse(any("login" in call or "signin" in call or "setsid" in call for call in guest.calls))

    def test_keyring_ensures_native_packages_and_only_explicit_seahorse(self):
        for preinstalled in (False, True):
            with self.subTest(preinstalled=preinstalled):
                guest = Guest()
                if preinstalled:
                    guest.packages.update(("gnome-keyring", "libsecret"))
                self.assertEqual(self.apply(guest, "keyring", {"seahorse": False})["changed"], not preinstalled)
                self.assertTrue({"gnome-keyring", "libsecret"} <= guest.packages)
                self.assertNotIn("seahorse", guest.packages)
                self.assertFalse(self.apply(guest, "keyring", {"seahorse": False})["changed"])
                self.assertTrue(self.apply(guest, "keyring", {"seahorse": True})["changed"])
                self.assertIn(("omarchy-pkg-add", "seahorse"), guest.calls)
                self.assertFalse(self.apply(guest, "keyring", {"seahorse": True})["changed"])
                self.assertFalse(self.apply(guest, "keyring", {"seahorse": False})["changed"])
                self.assertIn("seahorse", guest.packages)
                self.assertEqual({call[0] for call in guest.calls}, {"command", "pacman", "sudo", "omarchy-pkg-add"})

    def test_keyring_check_reports_missing_packages_without_installing_or_unlocking(self):
        guest = Guest()
        before = set(guest.packages)
        result = self.apply(guest, "keyring", {"seahorse": True}, check=True)
        self.assertTrue(result["changed"])
        self.assertEqual(guest.packages, before)
        self.assertEqual({call[0] for call in guest.calls}, {"command", "pacman"})

    def test_mise_is_added_to_lean_image_without_installing_unselected_tools(self):
        guest = Guest()
        result = self.apply(guest, "languages", {"tools": {"node": ""}})
        self.assertTrue(result["changed"])
        self.assertIn("mise-bin", guest.packages)
        self.assertEqual(set(guest.tools), {"node"})
        self.assertIn(("mise", "install", "node"), guest.calls)
        self.assertNotIn(("mise", "use", "--global", "node@latest"), guest.calls)
        self.assertFalse(self.apply(guest, "languages", {"tools": {"node": ""}})["changed"])

    def test_workstation_repairs_missing_native_desktop_helpers_once(self):
        guest = Guest()
        config = {**FEATURE.CATALOGUE["features"]["workstation"]["defaults"], "shell": "keep"}
        with mock.patch.object(FEATURE.FeatureRunner, "snapshot", return_value={}):
            self.assertTrue(self.apply(guest, "workstation", config)["changed"])
            self.assertFalse(self.apply(guest, "workstation", config)["changed"])
        self.assertTrue(set(FEATURE.WORKSTATION_PACKAGES) <= guest.packages)
        self.assertNotIn("docker", guest.packages)
        self.assertNotIn("chromium", guest.packages)
        self.assertEqual(sum(call[0] == "omarchy-pkg-add" for call in guest.calls), 1)

    def test_default_zsh_setup_is_idempotent_and_preserves_personal_configuration(self):
        guest = Guest(official=True)
        config = dict(FEATURE.CATALOGUE["features"]["workstation"]["defaults"])
        self.apply(guest, "workstation", config, check=True)
        rc = guest.home / ".zshrc"
        rc.write_text("# Personal configuration\nexport EDITOR=nvim\n")
        rc.chmod(0o640)
        self.assertTrue(self.apply(guest, "workstation", config)["changed"])
        first = {name: (guest.home / name).read_bytes() for name in FEATURE.ZSH_STARTUP}
        self.assertEqual(guest.shell, "/usr/bin/zsh")
        self.assertIn("zsh", guest.packages)
        self.assertTrue(rc.read_text().startswith("# Personal configuration\nexport EDITOR=nvim\n"))
        self.assertEqual(rc.stat().st_mode & 0o777, 0o640)
        self.assertIn("mise activate zsh", rc.read_text())
        self.assertIn('ZSH_THEME=""', rc.read_text())
        self.assertLess(rc.read_text().index('source "$ZSH/oh-my-zsh.sh"'), rc.read_text().index("starship init zsh"))
        self.assertTrue((guest.home / ".oh-my-zsh/oh-my-zsh.sh").is_file())
        self.assertIn("starship", guest.packages)
        self.assertNotIn(".bashrc", rc.read_text())
        self.assertFalse(self.apply(guest, "workstation", config)["changed"])
        self.assertEqual(first, {name: (guest.home / name).read_bytes() for name in FEATURE.ZSH_STARTUP})
        self.assertEqual(sum(call[:3] == ("sudo", "-n", "chsh") for call in guest.calls), 1)
        self.assertEqual(sum("clone" in call for call in guest.calls), 1)
        self.assertFalse(any(call[:2] == ("mise", "use") for call in guest.calls))

    def test_shell_check_mode_reports_work_without_installing_writing_or_changing_accounts(self):
        guest = Guest()
        config = dict(FEATURE.CATALOGUE["features"]["workstation"]["defaults"])
        result = self.apply(guest, "workstation", config, check=True)
        self.assertTrue(result["changed"])
        self.assertIn("Set owner login shell: zsh", result["actions"])
        self.assertEqual(guest.shell, "/bin/bash")
        self.assertNotIn("zsh", guest.packages)
        self.assertNotIn("starship", guest.packages)
        self.assertFalse((guest.home / ".oh-my-zsh").exists())
        self.assertFalse(any((guest.home / name).exists() for name in FEATURE.ZSH_STARTUP))
        self.assertFalse(any(call[0] == "omarchy-pkg-add" or call[:3] == ("sudo", "-n", "chsh")
                             or call[0] == "zsh" for call in guest.calls))

    def test_bash_override_and_keep_leave_zsh_files_and_unrelated_shells_alone(self):
        for selected in ("bash", "keep"):
            guest = Guest()
            config = {**FEATURE.CATALOGUE["features"]["workstation"]["defaults"], "shell": selected,
                      "oh_my_zsh_plugins": ["unused-missing-plugin"], "starship_config": "add_newline = false\n"}
            self.apply(guest, "workstation", config, check=True)
            guest.shell = "/usr/bin/zsh" if selected == "bash" else "/usr/bin/fish"
            rc = guest.home / ".zshrc"
            rc.write_text("# Keep my settings\n")
            self.apply(guest, "workstation", config)
            self.assertEqual(guest.shell, "/bin/bash" if selected == "bash" else "/usr/bin/fish")
            self.assertEqual(rc.read_text(), "# Keep my settings\n")
            self.assertNotIn("zsh", guest.packages)
            self.assertNotIn("starship", guest.packages)
            self.assertFalse((guest.home / ".oh-my-zsh").exists())
            self.assertFalse(any(call[0] == "zsh" for call in guest.calls))
            self.assertFalse(self.apply(guest, "workstation", config)["changed"])

    def test_zsh_extras_are_independent_and_can_be_disabled_without_removing_software(self):
        for omz, starship in ((True, True), (True, False), (False, True), (False, False)):
            with self.subTest(oh_my_zsh=omz, starship=starship):
                guest = Guest()
                config = {**FEATURE.CATALOGUE["features"]["workstation"]["defaults"], "oh_my_zsh": omz, "starship": starship}
                self.apply(guest, "workstation", config)
                rc = guest.home / ".zshrc"
                self.assertEqual("oh-my-zsh.sh" in rc.read_text(), omz)
                self.assertEqual("starship init zsh" in rc.read_text(), starship)
                self.assertEqual("starship" in guest.packages, starship)
                self.assertEqual((guest.home / ".oh-my-zsh").exists(), omz)
                self.assertFalse(self.apply(guest, "workstation", config)["changed"])
                rc.write_text(rc.read_text() + "# My aliases\nalias ll='ls -l'\n")
                disabled = {**config, "oh_my_zsh": False, "starship": False}
                self.apply(guest, "workstation", disabled)
                self.assertIn("alias ll='ls -l'", rc.read_text())
                self.assertNotIn("oh-my-zsh.sh", rc.read_text())
                self.assertNotIn("starship init zsh", rc.read_text())
                self.assertEqual("starship" in guest.packages, starship)
                self.assertEqual((guest.home / ".oh-my-zsh").exists(), omz)
                self.assertFalse(self.apply(guest, "workstation", disabled)["changed"])

    def test_zsh_prompt_toggle_updates_only_untouched_blocks_and_preserves_upstream_and_config(self):
        guest = Guest()
        config = dict(FEATURE.CATALOGUE["features"]["workstation"]["defaults"])
        self.apply(guest, "workstation", config)
        source = guest.home / ".oh-my-zsh/oh-my-zsh.sh"
        source.write_text("# Personal upstream modifications\n")
        prompt = guest.home / ".config/starship.toml"
        prompt.parent.mkdir(exist_ok=True)
        prompt.write_text("add_newline = false\n")
        self.apply(guest, "workstation", {**config, "starship": False})
        rc = guest.home / ".zshrc"
        self.assertIn('ZSH_THEME="${ZSH_THEME-robbyrussell}"', rc.read_text())
        self.apply(guest, "workstation", config)
        self.assertIn('ZSH_THEME=""', rc.read_text())
        self.assertEqual(source.read_text(), "# Personal upstream modifications\n")
        self.assertEqual(prompt.read_text(), "add_newline = false\n")
        self.assertEqual(sum("clone" in call for call in guest.calls), 1)
        rc.write_text(rc.read_text().replace('starship init zsh', 'starship init zsh --print-full-init'))
        before = rc.read_bytes()
        with self.assertRaisesRegex(FEATURE.FeatureError, "Preserving customized"):
            self.apply(guest, "workstation", config)
        self.assertEqual(rc.read_bytes(), before)

    def test_zsh_preserves_incomplete_framework_and_user_managed_initialization(self):
        for personal in ('source "$ZSH/oh-my-zsh.sh"\n', 'eval "$(starship init zsh)"\n',
                         'source ~/powerlevel10k/powerlevel10k.zsh-theme\n', None):
            guest = Guest()
            config = dict(FEATURE.CATALOGUE["features"]["workstation"]["defaults"])
            self.apply(guest, "workstation", config, check=True)
            rc = guest.home / ".zshrc"
            if personal is None:
                (guest.home / ".oh-my-zsh").mkdir()
            else:
                rc.write_text(personal)
            with self.subTest(personal=personal), self.assertRaisesRegex(FEATURE.FeatureError, "Preserving"):
                self.apply(guest, "workstation", config)
            self.assertEqual(rc.read_text() if rc.exists() else None, personal)
            self.assertEqual(guest.shell, "/bin/bash")
            self.assertFalse(any("clone" in call for call in guest.calls))

    def test_failed_framework_clone_leaves_no_partial_install_or_startup_edits(self):
        guest = Guest()
        original = guest.native
        def fail_clone(argv, **kwargs):
            if "clone" in argv:
                path = Path(argv[-1])
                path.mkdir()
                (path / "partial").touch()
                raise FEATURE.FeatureError("clone interrupted")
            return original(argv, **kwargs)
        guest.native = fail_clone
        config = dict(FEATURE.CATALOGUE["features"]["workstation"]["defaults"])
        with self.assertRaisesRegex(FEATURE.FeatureError, "clone interrupted"):
            self.apply(guest, "workstation", config)
        self.assertFalse((guest.home / ".oh-my-zsh").exists())
        self.assertFalse(list(guest.home.glob(".dev-vm-omz-*")))
        self.assertFalse((guest.home / ".zshrc").exists())
        self.assertEqual(guest.shell, "/bin/bash")

    def test_shell_configuration_check_apply_update_and_opt_out_preserve_personal_files(self):
        guest = Guest()
        config = {**FEATURE.CATALOGUE["features"]["workstation"]["defaults"],
                  "oh_my_zsh_plugins": ["git", "docker-compose"], "oh_my_zsh_update_mode": "disabled",
                  "starship_config": "add_newline = false\n[character]\nsuccess_symbol = '[❯](green)'\n"}
        self.apply(guest, "workstation", config, check=True)
        managed = guest.home / FEATURE.STARSHIP_CONFIG
        self.assertFalse(managed.exists())
        personal = guest.home / ".config/starship.toml"
        personal.parent.mkdir()
        personal.write_text("# Personal prompt\n")
        rc = guest.home / ".zshrc"
        rc.write_text("plugins=(docker)\nalias mine='echo personal'\n")
        self.apply(guest, "workstation", config)
        self.assertIn("plugins=(git docker-compose)", rc.read_text())
        self.assertIn("zstyle ':omz:update' mode disabled", rc.read_text())
        self.assertIn('export STARSHIP_CONFIG="$HOME/.config/dev-vm/starship.toml"', rc.read_text())
        self.assertTrue(managed.read_text().endswith(config["starship_config"]))
        self.assertEqual(managed.stat().st_mode & 0o777, 0o600)
        self.assertEqual(personal.read_text(), "# Personal prompt\n")
        original = rc.read_bytes(), managed.read_bytes()
        self.assertFalse(self.apply(guest, "workstation", config)["changed"])
        updated = {**config, "oh_my_zsh_plugins": [], "oh_my_zsh_update_mode": "auto",
                   "starship_config": "add_newline = true\n"}
        self.apply(guest, "workstation", updated, check=True)
        self.assertEqual(original, (rc.read_bytes(), managed.read_bytes()))
        self.apply(guest, "workstation", updated)
        self.assertIn("plugins=()", rc.read_text())
        self.assertIn("zstyle ':omz:update' mode auto", rc.read_text())
        self.assertTrue(managed.read_text().endswith(updated["starship_config"]))
        self.assertFalse(self.apply(guest, "workstation", updated)["changed"])
        self.apply(guest, "workstation", {**config, "oh_my_zsh_plugins": None,
                                         "oh_my_zsh_update_mode": "", "starship_config": ""})
        self.assertIn("plugins=(docker)", rc.read_text())
        self.assertIn("alias mine='echo personal'", rc.read_text())
        self.assertNotIn("zstyle ':omz:update'", rc.read_text())
        self.assertNotIn("export STARSHIP_CONFIG=", rc.read_text())
        self.assertTrue(managed.exists())
        self.assertEqual(personal.read_text(), "# Personal prompt\n")

    def test_configured_plugins_are_checked_before_startup_changes_and_no_custom_downloads(self):
        guest = Guest()
        config = {**FEATURE.CATALOGUE["features"]["workstation"]["defaults"], "oh_my_zsh_plugins": ["missing"]}
        self.apply(guest, "workstation", config, check=True)
        with self.assertRaisesRegex(FEATURE.FeatureError, "plugin unavailable: missing"):
            self.apply(guest, "workstation", config)
        self.assertFalse((guest.home / ".oh-my-zsh").exists())
        self.assertFalse((guest.home / ".zshrc").exists())
        self.assertEqual(guest.shell, "/bin/bash")
        self.apply(guest, "workstation", {**config, "oh_my_zsh_plugins": []})
        # Accept Oh My Zsh's completion-only and default-custom plugin layouts.
        custom = guest.home / ".oh-my-zsh/custom/plugins/missing"
        custom.mkdir(parents=True)
        (custom / "_missing").touch()
        self.apply(guest, "workstation", config)
        self.assertIn("plugins=(missing)", (guest.home / ".zshrc").read_text())
        (custom / "_missing").unlink()
        before = (guest.home / ".zshrc").read_bytes()
        with self.assertRaisesRegex(FEATURE.FeatureError, "plugin unavailable"):
            self.apply(guest, "workstation", config, check=True)
        self.assertEqual((guest.home / ".zshrc").read_bytes(), before)

    def test_managed_starship_file_refuses_custom_content_and_symlinked_paths(self):
        for kind in ("foreign", "modified", "file-link", "directory-link", "parent-file"):
            guest = Guest()
            config = {**FEATURE.CATALOGUE["features"]["workstation"]["defaults"], "starship_config": "add_newline = false\n"}
            self.apply(guest, "workstation", config, check=True)
            path = guest.home / FEATURE.STARSHIP_CONFIG
            if kind == "modified":
                self.apply(guest, "workstation", config)
                path.write_text(path.read_text() + "# personal edit\n")
            else:
                target = guest.home / "personal.toml"
                target.write_text("# personal\n")
                if kind == "directory-link":
                    path.parent.parent.mkdir()
                    path.parent.symlink_to(guest.home, target_is_directory=True)
                elif kind == "parent-file":
                    path.parent.parent.write_text("# preserve\n")
                else:
                    path.parent.mkdir(parents=True)
                    if kind == "file-link":
                        path.symlink_to(target)
                    else:
                        path.write_text("# foreign file\n")
            rc = guest.home / ".zshrc"
            before = rc.read_bytes() if rc.exists() else None
            with self.subTest(kind=kind), self.assertRaisesRegex(FEATURE.FeatureError, "Preserving"):
                self.apply(guest, "workstation", config)
            self.assertEqual(rc.read_bytes() if rc.exists() else None, before)

    def test_dynamic_managed_blocks_preserve_edits_and_upgrade_known_legacy_blocks(self):
        guest = Guest()
        config = dict(FEATURE.CATALOGUE["features"]["workstation"]["defaults"])
        self.apply(guest, "workstation", config)
        rc = guest.home / ".zshrc"
        legacy_omz = FEATURE.OH_MY_ZSH_STARTUP.format(theme=FEATURE.OH_MY_ZSH_THEMES[0])
        rc.write_text("# personal\n" + FEATURE.managed_block("Oh My Zsh", legacy_omz)
                      + FEATURE.managed_block("Starship prompt", FEATURE.STARSHIP_STARTUP))
        self.apply(guest, "workstation", config)
        self.assertIn(FEATURE.CONTENT_HASH, rc.read_text())
        rc.write_text(rc.read_text().replace("mode reminder", "mode disabled"))
        before = rc.read_bytes()
        with self.assertRaisesRegex(FEATURE.FeatureError, "Preserving customized"):
            self.apply(guest, "workstation", config)
        self.assertEqual(rc.read_bytes(), before)

    @unittest.skipUnless(shutil.which("zsh"), "zsh is not installed; no host installation attempted")
    def test_generated_zsh_startup_runs_with_plugins_and_single_prompt_in_order(self):
        guest = Guest()
        config = dict(FEATURE.CATALOGUE["features"]["workstation"]["defaults"])
        self.apply(guest, "workstation", config)
        # Exercise the generated shell with small upstream stand-ins; no network
        # or third-party software installation is needed on the test host.
        (guest.home / ".oh-my-zsh/oh-my-zsh.sh").write_text(
            '[[ -z "$ZSH_THEME" ]] || return 21\n'
            '[[ "$plugins[*]" == docker ]] || return 22\n'
            'typeset -ga loaded=(omz)\n')
        binary = guest.home / "bin"
        binary.mkdir()
        starship = binary / "starship"
        starship.write_text('#!/bin/sh\ncat <<\'INIT\'\n'
                            '[[ "$loaded[*]" == omz ]] || return 23\n'
                            'loaded+=(starship)\nexport STARSHIP_SHELL=zsh\n'
                            'precmd_functions+=(prompt_starship_precmd)\nINIT\n')
        starship.chmod(0o700)
        # Source explicitly under -f so the host's personal rc files cannot run.
        probe = ('plugins=(docker); source "$HOME/.zshrc"; '
                 '[[ "$loaded[*]" == "omz starship" && "$plugins[*]" == docker ]] && '
                 '[[ "$STARSHIP_SHELL" == zsh ]] && (( ${precmd_functions[(I)*starship*]} > 0 ))')
        result = subprocess.run([shutil.which("zsh"), "-dfc", probe], cwd=guest.home,
                                env={"HOME": str(guest.home), "PATH": str(binary) + ":/usr/bin:/bin", "TERM": "xterm-256color"},
                                text=True, capture_output=True)
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)

        # Explicit configuration overrides a personal plugins array, selects our
        # TOML file and sets update behavior before sourcing the framework.
        configured = {**config, "oh_my_zsh_plugins": ["git", "docker-compose"], "oh_my_zsh_update_mode": "disabled",
                      "starship_config": "add_newline = false\n"}
        self.apply(guest, "workstation", configured)
        (guest.home / ".oh-my-zsh/oh-my-zsh.sh").write_text(
            '[[ -z "$ZSH_THEME" && "$plugins[*]" == "git docker-compose" ]] || return 21\n'
            'zstyle -s ":omz:update" mode update_mode\n'
            '[[ "$update_mode" == disabled ]] || return 22\n'
            'typeset -ga loaded=(omz)\n')
        probe = ('plugins=(docker); source "$HOME/.zshrc"; '
                 '[[ "$loaded[*]" == "omz starship" && "$plugins[*]" == "git docker-compose" ]] && '
                 '[[ "$STARSHIP_CONFIG" == "$HOME/.config/dev-vm/starship.toml" && -r "$STARSHIP_CONFIG" ]]')
        result = subprocess.run([shutil.which("zsh"), "-dfc", probe], cwd=guest.home,
                                env={"HOME": str(guest.home), "PATH": str(binary) + ":/usr/bin:/bin", "TERM": "xterm-256color"},
                                text=True, capture_output=True)
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)

    def test_zsh_refuses_customized_blocks_and_symlinks_without_changing_login_shell(self):
        for kind in ("block", "symlink"):
            guest = Guest()
            config = dict(FEATURE.CATALOGUE["features"]["workstation"]["defaults"])
            self.apply(guest, "workstation", config, check=True)
            rc = guest.home / ".zshrc"
            original = "# >>> dev-vm mise activation >>>\n# My replacement\n"
            if kind == "block":
                rc.write_text(original)
            else:
                custom = guest.home / "custom-rc"
                custom.write_text(original)
                rc.symlink_to(custom)
            with self.assertRaisesRegex(FEATURE.FeatureError, "Preserving"):
                self.apply(guest, "workstation", config)
            self.assertEqual(rc.read_text(), original)
            self.assertEqual(guest.shell, "/bin/bash")
            self.assertFalse(any(call[:3] == ("sudo", "-n", "chsh") for call in guest.calls))

    def test_zsh_checks_registration_syntax_and_activation_before_changing_login_shell(self):
        for failure in ("registration", "syntax", "environment", "activation"):
            guest = Guest(official=True)
            config = dict(FEATURE.CATALOGUE["features"]["workstation"]["defaults"])
            self.apply(guest, "workstation", config, check=True)
            if failure == "registration":
                guest.shells_file.write_text("/bin/bash\n")
            elif failure == "syntax":
                guest.zsh_syntax = False
            elif failure == "environment":
                guest.zsh_environment = False
            else:
                guest.zsh_activation = False
            # The native double returns errors; real native() turns checked failures into FeatureError.
            native = guest.native
            def checked_native(argv, *, check=True):
                result = native(argv)
                if check and result.returncode:
                    raise FEATURE.FeatureError(result.stderr)
                return result
            with self.subTest(failure=failure), mock.patch.object(guest, "native", side_effect=checked_native):
                with self.assertRaises(FEATURE.FeatureError):
                    self.apply(guest, "workstation", config)
            self.assertEqual(guest.shell, "/bin/bash")
            self.assertFalse(any(call[:3] == ("sudo", "-n", "chsh") for call in guest.calls))

    def test_toolchain_verifies_zsh_activation_when_it_is_the_login_shell(self):
        guest = Guest(official=True)
        guest.shell = "/usr/bin/zsh"
        guest.zsh_activation = False
        with self.assertRaisesRegex(FEATURE.FeatureError, "Zsh mise activation"):
            self.apply(guest, "toolchain", {"prerequisites": []}, check=True)

    def test_first_login_ordering_repairs_only_the_known_unit_and_preserves_custom_overrides(self):
        content = (ROOT / "omarchy/image/preferences/first-login.service").read_text().replace(
            "After=graphical-session.target try-omarchy-session.service", "After=try-omarchy-session.service")
        with tempfile.TemporaryDirectory() as folder:
            home = Path(folder)
            unit = home / "first-login.service"
            unit.write_text(content)
            config = dict(FEATURE.CATALOGUE["features"]["workstation"]["defaults"])
            runner = FEATURE.FeatureRunner("workstation", config)
            with mock.patch.object(FEATURE.Path, "home", return_value=home), \
                    mock.patch.object(FEATURE, "native", return_value=reply()) as native:
                runner.first_login_ordering(unit)
                runner.first_login_ordering(unit)
                native.assert_called_once_with(["systemctl", "--user", "daemon-reload"])
                path = home / ".config/systemd/user/dev-workstation-first-login.service.d/90-session-order.conf"
                path.write_text("[Unit]\nAfter=custom.target\n")
                with self.assertRaisesRegex(FEATURE.FeatureError, "Preserving"):
                    runner.first_login_ordering(unit)
                self.assertIn("custom.target", path.read_text())

    def test_agent_default_uses_omarchy_declarations_and_preserves_other_agents(self):
        guest = Guest(official=True)
        self.assertFalse(self.apply(guest, "agents", {"tools": {"claude": ""}})["changed"])
        self.apply(guest, "agents", {"tools": {"codex": ""}})
        self.assertIn("claude", guest.tools)
        self.assertIn("codex", guest.tools)
        self.assertNotIn("opencode", guest.tools)

    def test_explicit_version_selects_installed_target_even_when_default_differs(self):
        guest = Guest(official=True)
        guest.tools["node@24"] = "/tools/node/24"
        self.assertTrue(self.apply(guest, "languages", {"tools": {"node": "24"}})["changed"])
        self.assertIn(("mise", "use", "--global", "node@24"), guest.calls)
        self.assertFalse(self.apply(guest, "languages", {"tools": {"node": "24"}})["changed"])

    def test_unconfigured_tool_gets_user_selection_without_replacing_global_config(self):
        guest = Guest(official=True)
        self.apply(guest, "languages", {"tools": {"go": ""}})
        self.assertIn(("mise", "use", "--global", "go@latest"), guest.calls)

    def test_inactive_installed_tool_is_not_mistaken_for_an_omarchy_declaration(self):
        guest = Guest(official=True)
        guest.tools["go"] = "/tools/go/inactive"
        original = guest.native

        def native(argv, **kwargs):
            if argv == ["mise", "ls", "--json", "go"]:
                return reply(stdout=json.dumps({"go": [{"version": "1.2", "installed": True, "active": False}]}))
            return original(argv, **kwargs)

        guest.native = native
        self.apply(guest, "languages", {"tools": {"go": ""}})
        self.assertIn(("mise", "use", "--global", "go@latest"), guest.calls)

    def test_real_tool_filtered_mise_rows_without_names_do_not_reselect_installed_tools(self):
        # Shape observed in mise 2026.10.17 on a disposable official guest.
        for feature, tool, version in (("languages", "node", ""),
                                       ("languages", "python", "3"),
                                       ("agents", "claude", "")):
            with self.subTest(feature=feature, tool=tool):
                guest = Guest(official=True)
                guest.packages.update(FEATURE.LANGUAGE_PACKAGES.get(tool, ()))
                guest.tools[tool] = guest.tools[f"{tool}@{version}"] = f"/tools/{tool}/installed"
                original = guest.native

                def native(argv, **kwargs):
                    if argv == ["mise", "ls", "--json", tool]:
                        return reply(stdout=json.dumps([{
                            "version": "1.2.3", "requested_version": version or "latest",
                            "install_path": f"/tools/{tool}/installed", "installed": True,
                            "active": True, "source": {"type": "mise.toml", "path": "/fixture/mise.toml"},
                        }]))
                    return original(argv, **kwargs)

                guest.native = native
                for _ in range(2):
                    self.assertFalse(self.apply(guest, feature, {"tools": {tool: version}})["changed"])
                self.assertFalse(any(c[:2] in (("mise", "use"), ("mise", "install")) for c in guest.calls))

    def test_mise_mapping_output_remains_supported(self):
        guest = Guest(official=True)
        original = guest.native

        def native(argv, **kwargs):
            if argv == ["mise", "ls", "--json", "node"]:
                return reply(stdout=json.dumps({"node": [{"requested_version": "latest"}]}))
            return original(argv, **kwargs)

        guest.native = native
        self.assertFalse(self.apply(guest, "languages", {"tools": {"node": ""}})["changed"])

    def test_language_native_prerequisites_are_installed_for_selected_language_only(self):
        guest = Guest()
        self.apply(guest, "languages", {"tools": {"ruby": "3"}})
        self.assertIn("libyaml", guest.packages)
        self.assertNotIn("ruby", guest.packages)
        self.assertNotIn("python", guest.tools)

    def test_docker_repairs_firewall_and_enables_socket_without_granting_group_membership(self):
        guest = Guest()
        self.assertTrue(self.apply(guest, "docker", {"access": "native"})["changed"])
        self.assertTrue(guest.firewall and guest.active and guest.enabled)
        self.assertFalse(self.apply(guest, "docker", {"access": "native"})["changed"])
        calls = " ".join(" ".join(c) for c in guest.calls)
        self.assertNotIn("usermod", calls)
        self.assertNotIn("ufw reset", calls)
        self.assertNotIn("ufw default", calls)
        for subnet in ("172.16.0.0/12", "192.168.0.0/16"):
            self.assertIn(("sudo", "-n", "ufw", "allow", "in", "proto", "udp", "from", subnet,
                           "to", "172.17.0.1", "port", "53", "comment", "allow-docker-dns"), guest.calls)

    def test_existing_docker_service_activation_is_preserved(self):
        guest = Guest(official=True)
        guest.active = guest.enabled = False
        guest.service = True
        self.assertFalse(self.apply(guest, "docker", {"access": "native"})["changed"])
        self.assertNotIn(("sudo", "-n", "systemctl", "enable", "--now", "docker.socket"), guest.calls)

    def test_sudoless_docker_cannot_report_success_without_native_opt_in(self):
        guest = Guest(official=True)
        guest.docker_configured = guest.docker_access = False
        config = {"access": "sudoless"}
        result = self.apply(guest, "docker", config, check=True)
        self.assertTrue(any("native Sudoless Docker confirmation" in item for item in result["actions"]))
        with self.assertRaisesRegex(FEATURE.FeatureError, "Owner Docker access is missing"):
            self.apply(guest, "docker", config)
        self.assertFalse(guest.docker_configured)
        deferred = self.apply(guest, "docker", config, defer_docker_access=True)
        self.assertTrue(any("launcher must obtain native Docker consent" in item for item in deferred["notes"]))
        self.assertFalse(guest.docker_configured)

    def test_docker_verifies_owner_api_access_even_with_setup_sudo_available(self):
        guest = Guest(official=True)
        guest.docker_access = False
        # The account is configured, but an existing login still lacks its group.
        with self.assertRaisesRegex(FEATURE.FeatureError, "Docker daemon access failed"):
            self.apply(guest, "docker", {"access": "sudoless"})
        result = self.apply(guest, "docker", {"access": "sudoless"}, check=True)
        self.assertTrue(any("session is stale" in note for note in result["notes"]))
        guest.docker_access = True
        self.assertFalse(self.apply(guest, "docker", {"access": "sudoless"})["changed"])
        probes = [call for call in guest.calls if call[0] == "env" and "/usr/bin/docker" in call]
        self.assertTrue(probes)
        self.assertTrue(all("sudo" not in call for call in probes))
        self.assertIn(("/usr/bin/docker", "compose", "version"), guest.calls)
        self.assertIn(("/usr/bin/docker", "buildx", "version"), guest.calls)

    def test_inactive_firewall_is_not_silently_replaced_or_new_socket_started(self):
        guest = Guest()
        guest.ufw_active = False
        with self.assertRaisesRegex(FEATURE.FeatureError, "UFW policy"):
            self.apply(guest, "docker", {"access": "native"})
        self.assertFalse(guest.active)
        self.assertNotIn(("sudo", "-n", "ufw-docker", "install"), guest.calls)

    def test_check_mode_never_installs_tools_changes_services_or_enables_sudo(self):
        configs = {"browsers": {"browsers": ["firefox"]}, "docker": {"access": "native"},
                   "languages": {"tools": {"node": ""}}, "agents": {"tools": {"codex": ""}},
                   "credentials": {"packages": ["1password"]}}
        for feature, config in configs.items():
            guest = Guest()
            before = set(guest.packages)
            result = self.apply(guest, feature, config, check=True)
            self.assertTrue(result["check_mode"])
            self.assertEqual(guest.packages, before)
            for call in guest.calls:
                self.assertNotIn(call[0], ("omarchy-pkg-add", "omarchy-install-browser", "sudo"))
                self.assertFalse(call[:2] in (("mise", "use"), ("mise", "install")))

    def test_configuration_rejects_options_shell_code_unknown_agents_and_credential_inputs(self):
        cases = [("languages", {"tools": {"--help": "1"}}),
                 ("languages", {"tools": {"node": "$(id)"}}),
                 ("languages", {"tools": {"node": 24}}),
                 ("agents", {"tools": {"unknown-agent": ""}}),
                 ("browsers", {"browsers": ["chrome"]}),
                 ("credentials", {"packages": ["id_rsa"]}),
                 ("credentials", {"packages": [], "token": "never-read"})]
        for feature, config in cases:
            with self.subTest(feature=feature, config=config), self.assertRaises(FEATURE.FeatureError):
                FEATURE.FeatureRunner(feature, config)

    def test_host_wrong_architecture_root_and_missing_integration_are_refused(self):
        for system, arch, uid in (("Darwin", "arm64", 1000), ("Linux", "x86_64", 1000), ("Linux", "aarch64", 0)):
            with mock.patch.object(FEATURE.platform, "system", return_value=system), \
                    mock.patch.object(FEATURE.platform, "machine", return_value=arch), \
                    mock.patch.object(FEATURE.os, "geteuid", return_value=uid), \
                    mock.patch.object(FEATURE, "native") as native:
                with self.assertRaises(FEATURE.FeatureError):
                    FEATURE.FeatureRunner("docker", {"access": "native"}).apply()
                native.assert_not_called()


if __name__ == "__main__":
    unittest.main()
