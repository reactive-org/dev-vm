import importlib.util
import io
import json
import subprocess
import sys
import os
import shlex
import unittest
from contextlib import ExitStack, redirect_stderr, redirect_stdout
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
    def test_theme_urls_reject_options_credentials_and_non_repository_paths(self):
        for value in (
            "--upload-pack=bad", "git@github.com:owner/theme", "http://github.com/o/r",
            "https://github.com/o/r/tree/main", "https://user:secret@github.com/o/r",
            "https://github.com/o/r?token=secret", "https://github.com/o/..",
            "https://github.com/o/omarchy--theme", "https://example.com/o/r",
            "https://github.com/o/r$(id)",
            "https://github.com/o/theme.git.git",
        ):
            with self.subTest(value=value), self.assertRaises(CONTROLLER.WorkstationError):
                CONTROLLER.resolve_theme(value)
        with mock.patch.object(CONTROLLER, "fetch_theme_resource") as fetch:
            self.assertEqual(CONTROLLER.resolve_theme(""), "")
            self.assertEqual(
                CONTROLLER.resolve_theme("https://github.com/owner/omarchy-blue-theme.git/"),
                "https://github.com/owner/omarchy-blue-theme",
            )
        fetch.assert_not_called()

    def test_theme_network_failure_hides_request_and_response_details(self):
        request = CONTROLLER.Request(
            "https://api.github.com/graphql", headers={"Authorization": "Bearer secret"}
        )
        with mock.patch.object(
            CONTROLLER, "urlopen", side_effect=CONTROLLER.URLError("secret")
        ):
            with self.assertRaises(CONTROLLER.WorkstationError) as error:
                CONTROLLER.fetch_theme_resource(request)
        self.assertNotIn("secret", str(error.exception))

    def test_random_uses_only_deduplicated_catalog_theme_figures(self):
        page = b'''<a href="https://github.com/site/source">Site</a>
        <figure class="themes__theme"><a href="https://github.com/o/blue">Blue</a>
        <a href="https://github.com/o/blue.git">Image</a></figure>
        <figure class="themes__theme"><a href="https://github.com/o/red">Red</a></figure>
        <figure><a href="https://github.com/o/other">Other</a></figure>'''
        with mock.patch.object(CONTROLLER, "fetch_theme_resource", return_value=page), mock.patch.object(
            CONTROLLER.random, "SystemRandom"
        ) as random:
            random.return_value.choice.return_value = "https://github.com/o/red"
            self.assertEqual(CONTROLLER.resolve_theme("random", min_stars=0), "https://github.com/o/red")
            random.return_value.choice.assert_called_once_with(
                ["https://github.com/o/blue", "https://github.com/o/red"]
            )
        with mock.patch.object(CONTROLLER, "fetch_theme_resource", return_value=b"<html></html>"):
            with self.assertRaises(CONTROLLER.WorkstationError):
                CONTROLLER.resolve_theme("random", min_stars=0)

    def test_random_star_minimum_is_inclusive_and_uniform_over_eligible_themes(self):
        page = b'<figure class="themes__theme"><a href="https://github.com/o/blue">Blue</a></figure>'
        counts = [
            ("https://github.com/o/low", 9),
            ("https://github.com/o/boundary", 10),
            ("https://github.com/o/popular", 80),
        ]
        with mock.patch.object(CONTROLLER, "fetch_theme_resource", return_value=page), mock.patch.object(
            CONTROLLER, "theme_github_auth", return_value=("/existing/gh", None)
        ), mock.patch.object(CONTROLLER, "theme_star_counts", return_value=counts), mock.patch.object(
            CONTROLLER.random, "SystemRandom"
        ) as random:
            random.return_value.choice.return_value = counts[1]
            self.assertEqual(CONTROLLER.resolve_theme("random"), counts[1][0])
            random.return_value.choice.assert_called_once_with(counts[1:])

    def test_random_star_minimum_fails_when_nothing_qualifies(self):
        page = b'<figure class="themes__theme"><a href="https://github.com/o/blue">Blue</a></figure>'
        with mock.patch.object(CONTROLLER, "fetch_theme_resource", return_value=page), mock.patch.object(
            CONTROLLER, "theme_github_auth", return_value=("/existing/gh", None)
        ), mock.patch.object(
            CONTROLLER, "theme_star_counts", return_value=[("https://github.com/o/blue", 9)]
        ):
            with self.assertRaisesRegex(CONTROLLER.WorkstationError, "at least 10"):
                CONTROLLER.resolve_theme("random", min_stars=10)

    def test_random_star_minimum_rejects_invalid_values_before_lookup(self):
        for theme, minimum in (
            ("random", -1), ("random", 1.5), ("random", True),
            ("", -1), ("most-starred", -1), ("https://github.com/o/blue", -1),
        ):
            with self.subTest(theme=theme, minimum=minimum), mock.patch.object(
                CONTROLLER, "fetch_theme_resource"
            ) as fetch:
                with self.assertRaises(CONTROLLER.WorkstationError):
                    CONTROLLER.resolve_theme(theme, min_stars=minimum)
                fetch.assert_not_called()

    def test_random_star_minimum_reaches_selection_before_confirmation(self):
        args = CONTROLLER.build_parser().parse_args([
            "--theme", "random", "bootstrap"
        ])
        with mock.patch.object(CONTROLLER, "preflight", return_value="0.6.0"), mock.patch.object(
            CONTROLLER, "list_guests", return_value=[]
        ), mock.patch.object(
            CONTROLLER, "resolve_theme", return_value="https://github.com/o/blue"
        ) as resolve, mock.patch.object(CONTROLLER, "print_proposal"), mock.patch.object(
            CONTROLLER, "confirm", side_effect=CONTROLLER.WorkstationError("cancelled")
        ), mock.patch.object(CONTROLLER, "cli_call") as mutate:
            with self.assertRaises(CONTROLLER.WorkstationError):
                CONTROLLER.ready_guest(args)
        resolve.assert_called_once_with("random", min_stars=10)
        mutate.assert_not_called()

    @mock.patch.object(CONTROLLER.shutil, "which", return_value=None)
    def test_star_ranking_batches_metadata_and_breaks_ties_by_url(self, _which):
        urls = [f"https://github.com/o/theme-{index:02}" for index in range(51)]
        replies = [
            json.dumps({"data": {f"r{i}": {"stargazerCount": 1} for i in range(50)}}).encode(),
            b'{"data":{"r0":{"stargazerCount":20}}}',
        ]
        with mock.patch.dict(os.environ, {"GH_TOKEN": "test-token"}, clear=True), mock.patch.object(
            CONTROLLER, "fetch_theme_resource", side_effect=replies
        ) as fetch:
            self.assertEqual(CONTROLLER.most_starred_theme(urls), (urls[-1], 20))
            self.assertEqual(fetch.call_count, 2)
            request = fetch.call_args_list[0].args[0]
            self.assertEqual(request.full_url, "https://api.github.com/graphql")
            self.assertEqual(request.get_header("Authorization"), "Bearer test-token")
            self.assertNotIn("test-token", request.data.decode())
        tied = b'{"data":{"r0":{"stargazerCount":9},"r1":{"stargazerCount":9}}}'
        with mock.patch.dict(os.environ, {"GITHUB_TOKEN": "test-token"}, clear=True), mock.patch.object(
            CONTROLLER, "fetch_theme_resource", return_value=tied
        ):
            self.assertEqual(CONTROLLER.most_starred_theme(list(reversed(urls[:2]))), (urls[0], 9))

    @mock.patch.object(CONTROLLER.shutil, "which", return_value=None)
    def test_star_lookup_requires_credentials_and_complete_metadata(self, _which):
        with mock.patch.dict(os.environ, {}, clear=True), mock.patch.object(
            CONTROLLER, "fetch_theme_resource"
        ) as fetch:
            with self.assertRaises(CONTROLLER.WorkstationError):
                CONTROLLER.resolve_theme("most-starred")
            fetch.assert_not_called()
        for reply in (b'{"errors":[{"message":"secret"}]}', b'{"data":{"r0":null}}', b'bad json'):
            with mock.patch.dict(os.environ, {"GH_TOKEN": "test-token"}, clear=True), mock.patch.object(
                CONTROLLER, "fetch_theme_resource", return_value=reply
            ):
                with self.assertRaises(CONTROLLER.WorkstationError) as error:
                    CONTROLLER.most_starred_theme(["https://github.com/o/blue"])
                self.assertNotIn("secret", str(error.exception))

    def test_star_lookup_prefers_existing_gh_without_exporting_its_token(self):
        reply = '{"data":{"r0":{"stargazerCount":12}}}'
        with mock.patch.dict(os.environ, {"GH_HOST": "enterprise.example"}, clear=True), mock.patch.object(
            CONTROLLER.shutil, "which", return_value="/existing/gh"
        ), mock.patch.object(
            CONTROLLER.subprocess, "run", return_value=subprocess.CompletedProcess([], 0, reply, "")
        ) as run, mock.patch.object(CONTROLLER, "fetch_theme_resource") as fetch:
            self.assertEqual(
                CONTROLLER.most_starred_theme(["https://github.com/o/blue"]),
                ("https://github.com/o/blue", 12),
            )
        fetch.assert_not_called()
        self.assertEqual(
            run.call_args.args[0],
            ["/existing/gh", "api", "--hostname", "github.com", "graphql", "--input", "-"],
        )
        options = run.call_args.kwargs
        self.assertIn('repository(owner: "o", name: "blue")', json.loads(options["input"])["query"])
        self.assertEqual(options["env"]["GH_PROMPT_DISABLED"], "1")
        self.assertTrue(options["capture_output"])
        self.assertEqual(options["timeout"], 30)

    def test_gh_preference_keeps_environment_token_overrides(self):
        with mock.patch.dict(os.environ, {"GH_TOKEN": "test-token"}, clear=True), mock.patch.object(
            CONTROLLER.shutil, "which", return_value="/existing/gh"
        ), mock.patch.object(
            CONTROLLER.subprocess, "run", return_value=subprocess.CompletedProcess([], 0, "{}", "")
        ) as run, mock.patch.object(CONTROLLER, "fetch_theme_resource") as fetch:
            CONTROLLER.github_theme_query("query { viewer { login } }", *CONTROLLER.theme_github_auth())
        self.assertEqual(run.call_args.kwargs["env"]["GH_TOKEN"], "test-token")
        self.assertNotIn("test-token", run.call_args.kwargs["input"])
        fetch.assert_not_called()

    def test_gh_failure_is_sanitized_without_falling_back_to_another_login(self):
        failures = (
            subprocess.CompletedProcess([], 1, "secret response", "secret token"),
            subprocess.TimeoutExpired(["gh"], 30, output="secret token"),
            OSError("secret token"),
        )
        for failure in failures:
            options = {"side_effect": failure} if isinstance(failure, Exception) else {"return_value": failure}
            with self.subTest(failure=type(failure).__name__), mock.patch.object(
                CONTROLLER.subprocess, "run", **options
            ), mock.patch.object(CONTROLLER, "fetch_theme_resource") as fetch:
                with self.assertRaises(CONTROLLER.WorkstationError) as error:
                    CONTROLLER.github_theme_query("query { viewer { login } }", "/existing/gh", "test-token")
                self.assertNotIn("secret", str(error.exception))
                fetch.assert_not_called()

    def test_star_ranking_skips_only_explicitly_unavailable_repositories(self):
        reply = json.dumps({
            "data": {"r0": None, "r1": {"stargazerCount": 15}},
            "errors": [{"type": "NOT_FOUND", "path": ["r0"]}],
        })
        urls = ["https://github.com/o/missing", "https://github.com/o/blue"]
        with mock.patch.object(CONTROLLER.shutil, "which", return_value="/existing/gh"), mock.patch.object(
            CONTROLLER.subprocess, "run", return_value=subprocess.CompletedProcess([], 1, reply, "")
        ):
            self.assertEqual(CONTROLLER.most_starred_theme(urls), (urls[1], 15))
        for errors in (
            [{"type": "FORBIDDEN", "path": ["r0"]}],
            [{"type": "NOT_FOUND", "path": ["unexpected"]}],
            [{"type": "NOT_FOUND", "path": []}],
        ):
            with self.subTest(errors=errors), mock.patch.object(
                CONTROLLER, "theme_github_auth", return_value=(None, "test-token")
            ), mock.patch.object(
                CONTROLLER, "github_theme_query", return_value=json.dumps({
                    "data": {"r0": None, "r1": {"stargazerCount": 15}}, "errors": errors,
                })
            ):
                with self.assertRaises(CONTROLLER.WorkstationError):
                    CONTROLLER.most_starred_theme(urls)

    def test_star_ranking_fails_if_every_catalog_repository_is_unavailable(self):
        reply = json.dumps({
            "data": {"r0": None}, "errors": [{"type": "NOT_FOUND", "path": ["r0"]}],
        })
        with mock.patch.object(CONTROLLER, "theme_github_auth", return_value=(None, "test-token")), mock.patch.object(
            CONTROLLER, "github_theme_query", return_value=reply
        ):
            with self.assertRaisesRegex(CONTROLLER.WorkstationError, "No available"):
                CONTROLLER.most_starred_theme(["https://github.com/o/missing"])

    def test_theme_is_resolved_before_proposal_confirmation_or_vm_mutation(self):
        args = CONTROLLER.build_parser().parse_args(["--theme", "random", "bootstrap"])
        events = []
        selected = "https://github.com/o/blue"

        def proposal(*_args, **_kwargs):
            self.assertEqual(args.theme, selected)
            events.append("proposal")

        with mock.patch.object(CONTROLLER, "preflight", return_value="0.6.0"), mock.patch.object(
            CONTROLLER, "list_guests", return_value=[]
        ), mock.patch.object(
            CONTROLLER, "resolve_theme", side_effect=lambda _value, **_kwargs: events.append("resolve") or selected
        ), mock.patch.object(CONTROLLER, "print_proposal", side_effect=proposal), mock.patch.object(
            CONTROLLER, "confirm", side_effect=CONTROLLER.WorkstationError("cancelled")
        ), mock.patch.object(CONTROLLER, "cli_call") as mutate:
            with self.assertRaises(CONTROLLER.WorkstationError):
                CONTROLLER.ready_guest(args)
        self.assertEqual(events, ["resolve", "proposal"])
        mutate.assert_not_called()

    def test_apply_stages_theme_helper_and_forwards_only_resolved_url(self):
        args = CONTROLLER.build_parser().parse_args([
            "--theme", "https://github.com/o/blue", "bootstrap"
        ])
        connection = CONTROLLER.ManagedSSH(Path("/manager/config"), "managed-vm")
        remote = "/tmp/dev-omarchy-workstation.ABC123"
        with mock.patch.object(CONTROLLER, "stage_payload", return_value=(remote, [])) as stage, mock.patch.object(
            CONTROLLER, "install_selected_software"
        ), mock.patch.object(
            CONTROLLER, "ssh_command", return_value=subprocess.CompletedProcess([], 0, "", "")
        ) as ssh, mock.patch.object(CONTROLLER, "cleanup_payload") as cleanup:
            CONTROLLER.apply_workstation(args, connection)
        self.assertIn(CONTROLLER.GUEST_THEME, stage.call_args.args[1])
        login_command = shlex.split(ssh.call_args_list[0].args[1])
        self.assertEqual(login_command[:2], ["bash", "-lc"])
        command = shlex.split(login_command[2])
        self.assertEqual(command[-2:], ["--theme-url", args.theme])
        cleanup.assert_called_once_with(connection, remote)

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
            CONTROLLER.validate_remote_dir("/tmp/dev-omarchy-workstation.A1b2c3\n"),
            "/tmp/dev-omarchy-workstation.A1b2c3",
        )
        for unsafe in ("/tmp", "/", "/tmp/dev-omarchy-workstation.bad/path"):
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
            (),
        )
        self.assertEqual(
            tuple((item.source, item.name) for item in overridden.packages),
            ((None, "opencode"), ("mise", "pi"), ("pkg", "ripgrep")),
        )
        self.assertEqual(empty.packages, ())

    def test_lean_profile_defaults_off_and_proposal_names_the_removals(self):
        parser = CONTROLLER.build_parser()
        args = parser.parse_args(["bootstrap"])
        self.assertFalse(args.lean_developer)
        args = parser.parse_args(["--lean-developer", "--packages", "pkg:obsidian", "bootstrap"])
        output = io.StringIO()
        with redirect_stdout(output):
            CONTROLLER.print_proposal(args, manager="0.6.0", action="start", guest=None, mutable_errors=[])
        profile_line = next(line for line in output.getvalue().splitlines() if "Lean developer:" in line)
        self.assertIn("libreoffice-fresh", profile_line)
        self.assertNotIn("obsidian", profile_line)

    def test_lean_profile_payload_and_keep_selection_are_opt_in(self):
        for enabled in (False, True):
            with self.subTest(enabled=enabled):
                args = CONTROLLER.build_parser().parse_args(
                    (["--lean-developer"] if enabled else []) + ["--packages", "pkg:obsidian", "bootstrap"]
                )
                remote = "/tmp/dev-omarchy-workstation.ABC123"
                events = []
                with mock.patch.object(CONTROLLER, "stage_payload", return_value=(remote, [])) as stage, mock.patch.object(
                    CONTROLLER, "install_selected_software", side_effect=lambda *_args: events.append("install")
                ), mock.patch.object(
                    CONTROLLER, "guest_login_command", side_effect=lambda *_args, **_kwargs: events.append(_args[1])
                ) as login, mock.patch.object(
                    CONTROLLER, "ssh_command", return_value=subprocess.CompletedProcess([], 0, "", "")
                ), mock.patch.object(CONTROLLER, "cleanup_payload") as cleanup:
                    CONTROLLER.apply_workstation(args, mock.sentinel.connection)
                payloads = stage.call_args.args[1]
                self.assertEqual(CONTROLLER.GUEST_LEAN in payloads, enabled)
                self.assertEqual(CONTROLLER.GUEST_LEAN_PACKAGES in payloads, enabled)
                self.assertEqual(events[0], "install")
                if enabled:
                    self.assertEqual(shlex.split(events[1]), ["python3", remote + "/apply-lean-developer.py", "--keep", "obsidian"])
                    self.assertTrue(login.call_args_list[0].kwargs["tty"])
                else:
                    self.assertNotIn("apply-lean-developer.py", " ".join(events))
                cleanup.assert_called_once()

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
            "enable_bootstrap_sudo",
            side_effect=lambda _connection: events.append("enable sudo"),
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
            "disable_bootstrap_sudo",
            side_effect=lambda _connection: events.append("disable sudo"),
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
            ["connect", "enable sudo", "update", "customize", "disable sudo", "restart", "connect", "check"],
        )

    def test_bootstrap_sudo_uses_native_timed_grant_and_checks_confirmation(self):
        connection = CONTROLLER.ManagedSSH(Path("/manager/config"), "managed-vm")
        with mock.patch.object(CONTROLLER, "guest_login_command") as login:
            CONTROLLER.enable_bootstrap_sudo(connection)
        login.assert_called_once_with(
            connection,
            "omarchy sudo passwordless 60 && omarchy sudo passwordless --active",
            tty=True,
        )

    def test_bootstrap_sudo_cleanup_is_noninteractive_and_bounded(self):
        connection = CONTROLLER.ManagedSSH(Path("/manager/config"), "managed-vm")
        with mock.patch.object(
            CONTROLLER.subprocess, "run", return_value=subprocess.CompletedProcess([], 0, "", "")
        ) as run:
            CONTROLLER.disable_bootstrap_sudo(connection)
        command = run.call_args.args[0]
        self.assertEqual(command[:-1], connection.ssh_argv())
        login = shlex.split(command[-1])
        self.assertEqual(login, ["bash", "-lc", "omarchy sudo passwordless --disable"])
        self.assertEqual(run.call_args.kwargs["stdin"], subprocess.DEVNULL)
        self.assertEqual(run.call_args.kwargs["timeout"], 30)
        self.assertTrue(run.call_args.kwargs["capture_output"])

    def test_bootstrap_sudo_cleanup_reports_native_failure_timeout_or_disconnect(self):
        connection = CONTROLLER.ManagedSSH(Path("/manager/config"), "managed-vm")
        for failure in (
            subprocess.CompletedProcess([], 1, "", ""),
            subprocess.CompletedProcess([], 255, "", ""),
            subprocess.TimeoutExpired(["ssh"], 30),
            OSError("disconnected"),
        ):
            options = {"side_effect": failure} if isinstance(failure, Exception) else {"return_value": failure}
            with self.subTest(failure=type(failure).__name__), mock.patch.object(
                CONTROLLER.subprocess, "run", **options
            ):
                with self.assertRaisesRegex(CONTROLLER.WorkstationError, "Could not confirm"):
                    CONTROLLER.disable_bootstrap_sudo(connection)

    def test_bootstrap_revokes_sudo_when_enable_update_or_apply_fails_or_is_interrupted(self):
        connection = CONTROLLER.ManagedSSH(Path("/manager/config"), "managed-vm")
        phases = ("enable_bootstrap_sudo", "update_guest_system", "apply_workstation")
        for phase in phases:
            for error in (CONTROLLER.WorkstationError("setup failed"), KeyboardInterrupt()):
                with self.subTest(phase=phase, error=type(error).__name__), ExitStack() as stack:
                    stack.enter_context(mock.patch.object(
                        CONTROLLER, "ready_guest", return_value=(managed_guest(), "0.6.0")
                    ))
                    stack.enter_context(mock.patch.object(CONTROLLER, "managed_ssh", return_value=connection))
                    for name in phases:
                        stack.enter_context(mock.patch.object(
                            CONTROLLER, name, **({"side_effect": error} if name == phase else {})
                        ))
                    cleanup = stack.enter_context(mock.patch.object(CONTROLLER, "disable_bootstrap_sudo"))
                    restart = stack.enter_context(mock.patch.object(CONTROLLER, "restart_guest"))
                    with self.assertRaises(type(error)) as raised:
                        CONTROLLER.bootstrap_command(SimpleNamespace())
                    self.assertIs(raised.exception, error)
                    cleanup.assert_called_once_with(connection)
                    restart.assert_not_called()

    def test_cleanup_failure_blocks_reboot_and_keeps_original_setup_error_visible(self):
        for setup_error in (None, CONTROLLER.WorkstationError("original setup failure")):
            with self.subTest(setup_error=setup_error), ExitStack() as stack:
                stack.enter_context(mock.patch.object(
                    CONTROLLER, "ready_guest", return_value=(managed_guest(), "0.6.0")
                ))
                stack.enter_context(mock.patch.object(CONTROLLER, "managed_ssh"))
                stack.enter_context(mock.patch.object(CONTROLLER, "enable_bootstrap_sudo"))
                stack.enter_context(mock.patch.object(CONTROLLER, "update_guest_system"))
                stack.enter_context(mock.patch.object(CONTROLLER, "apply_workstation", side_effect=setup_error))
                cleanup_error = CONTROLLER.WorkstationError("sudo cleanup failed")
                stack.enter_context(mock.patch.object(CONTROLLER, "disable_bootstrap_sudo", side_effect=cleanup_error))
                restart = stack.enter_context(mock.patch.object(CONTROLLER, "restart_guest"))
                warnings = stack.enter_context(redirect_stderr(io.StringIO()))
                with self.assertRaises(CONTROLLER.WorkstationError) as raised:
                    CONTROLLER.bootstrap_command(SimpleNamespace())
                self.assertIs(raised.exception, setup_error or cleanup_error)
                if setup_error:
                    self.assertIn("sudo cleanup failed", warnings.getvalue())
                restart.assert_not_called()

    def test_termination_signals_revoke_sudo_and_restore_the_original_handlers(self):
        for signum in (CONTROLLER.signal.SIGTERM, CONTROLLER.signal.SIGHUP):
            original = CONTROLLER.signal.getsignal(signum)
            with self.subTest(signum=signum), ExitStack() as stack:
                stack.enter_context(mock.patch.object(
                    CONTROLLER, "ready_guest", return_value=(managed_guest(), "0.6.0")
                ))
                stack.enter_context(mock.patch.object(CONTROLLER, "managed_ssh"))
                stack.enter_context(mock.patch.object(CONTROLLER, "enable_bootstrap_sudo"))
                stack.enter_context(mock.patch.object(
                    CONTROLLER, "update_guest_system",
                    side_effect=lambda _connection: CONTROLLER.signal.getsignal(signum)(signum, None),
                ))
                cleanup = stack.enter_context(mock.patch.object(CONTROLLER, "disable_bootstrap_sudo"))
                with self.assertRaisesRegex(CONTROLLER.WorkstationError, "Bootstrap interrupted"):
                    CONTROLLER.bootstrap_command(SimpleNamespace())
                cleanup.assert_called_once()
                self.assertEqual(CONTROLLER.signal.getsignal(signum), original)

    def test_new_guest_creation_is_one_explicit_manager_mutation(self):
        args = SimpleNamespace(
            vm_name="Dev Omarchy",
            memory_gib=20,
            cpus=8,
            disk_gib=64,
            timeout=3600,
            remove_layout=False,
            layout_file=None,
            theme="",
            theme_min_stars=10,
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
