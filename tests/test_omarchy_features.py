import importlib.util
import json
import subprocess
import tempfile
import unittest
from pathlib import Path
from unittest import mock


ROOT = Path(__file__).resolve().parents[1]
SPEC = importlib.util.spec_from_file_location("guest_features", ROOT / "omarchy/guest/apply-features.py")
FEATURE = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(FEATURE)


def reply(code=0, stdout="", stderr=""):
    return subprocess.CompletedProcess([], code, stdout, stderr)


class Guest:
    def __init__(self, official=False):
        self.packages = {"try-omarchy", "python", "foot", "ufw"}
        self.tools = {}
        self.configured = {"node", "claude", "codex", "opencode"}
        self.calls = []
        self.active = False
        self.enabled = False
        self.service = False
        self.firewall = False
        self.ufw_active = True
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
    def apply(self, guest, feature, config, check=False, extension=False):
        with mock.patch.object(FEATURE, "run", side_effect=guest.run), \
                mock.patch.object(FEATURE, "native", side_effect=guest.native), \
                mock.patch.object(FEATURE.platform, "system", return_value="Linux"), \
                mock.patch.object(FEATURE.platform, "machine", return_value="aarch64"), \
                mock.patch.object(FEATURE.os, "geteuid", return_value=1000):
            return FEATURE.FeatureRunner(feature, config, check, extension=extension).apply()

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
        config = {"font_size": "16", "idle_mode": "host", "theme": "", "layout": "", "remove_layout": False}
        with mock.patch.object(FEATURE.FeatureRunner, "snapshot", return_value={}):
            self.assertTrue(self.apply(guest, "workstation", config)["changed"])
            self.assertFalse(self.apply(guest, "workstation", config)["changed"])
        self.assertTrue(set(FEATURE.WORKSTATION_PACKAGES) <= guest.packages)
        self.assertNotIn("docker", guest.packages)
        self.assertNotIn("chromium", guest.packages)
        self.assertEqual(sum(call[0] == "omarchy-pkg-add" for call in guest.calls), 1)

    def test_first_login_ordering_repairs_only_the_known_unit_and_preserves_custom_overrides(self):
        content = (ROOT / "omarchy/image/preferences/first-login.service").read_text().replace(
            "After=graphical-session.target try-omarchy-session.service", "After=try-omarchy-session.service")
        with tempfile.TemporaryDirectory() as folder:
            home = Path(folder)
            unit = home / "first-login.service"
            unit.write_text(content)
            config = {"font_size": "16", "idle_mode": "host", "theme": "", "layout": "", "remove_layout": False}
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
        self.assertTrue(self.apply(guest, "docker", {})["changed"])
        self.assertTrue(guest.firewall and guest.active and guest.enabled)
        self.assertFalse(self.apply(guest, "docker", {})["changed"])
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
        self.assertFalse(self.apply(guest, "docker", {})["changed"])
        self.assertNotIn(("sudo", "-n", "systemctl", "enable", "--now", "docker.socket"), guest.calls)

    def test_inactive_firewall_is_not_silently_replaced_or_new_socket_started(self):
        guest = Guest()
        guest.ufw_active = False
        with self.assertRaisesRegex(FEATURE.FeatureError, "UFW policy"):
            self.apply(guest, "docker", {})
        self.assertFalse(guest.active)
        self.assertNotIn(("sudo", "-n", "ufw-docker", "install"), guest.calls)

    def test_check_mode_never_installs_tools_changes_services_or_enables_sudo(self):
        configs = {"browsers": {"browsers": ["firefox"]}, "docker": {},
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
                    FEATURE.FeatureRunner("docker", {}).apply()
                native.assert_not_called()


if __name__ == "__main__":
    unittest.main()
