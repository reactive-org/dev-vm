import importlib.util
import io
import subprocess
import unittest
from contextlib import redirect_stdout
from pathlib import Path
from unittest import mock


SCRIPT = Path(__file__).resolve().parents[1] / "omarchy/guest/apply-lean-developer.py"
SPEC = importlib.util.spec_from_file_location("lean_developer", SCRIPT)
LEAN = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(LEAN)


class LeanDeveloperTests(unittest.TestCase):
    def apply(self, installed, candidates, plans, keep=(), failure=None):
        self.installed = set(installed) | {"try-omarchy"}
        self.removals = []
        self.events = []

        def run(argv, *, check=True):
            self.events.append(argv)
            if argv == ["pacman", "-Qq"]:
                return subprocess.CompletedProcess(argv, 0, "\n".join(sorted(self.installed)), "")
            name = argv[-1]
            plan = plans[name](self.installed) if callable(plans[name]) else plans[name]
            if argv[0] == "pacman":
                self.assertEqual(argv[:-1], ["pacman", "-Rs", "--print", "--print-format", "%n"])
                if plan is None:
                    return subprocess.CompletedProcess(argv, 1, "", "could not satisfy dependencies: required by retained application")
                if isinstance(plan, str):
                    return subprocess.CompletedProcess(argv, 1, "", plan)
                return subprocess.CompletedProcess(argv, 0, "\n".join(plan), "")
            self.assertEqual(argv, ["omarchy-pkg-drop", name])
            if failure:
                raise failure
            self.removals.append(name)
            self.installed.difference_update(plan)
            return subprocess.CompletedProcess(argv, 0, "", "")

        output = io.StringIO()
        with mock.patch.object(LEAN.platform, "machine", return_value="aarch64"), mock.patch.object(
            LEAN.shutil, "which", return_value="/usr/bin/native-command"
        ), mock.patch.object(LEAN, "candidates", return_value=candidates), mock.patch.object(
            LEAN, "run", side_effect=run
        ), redirect_stdout(output):
            LEAN.apply(keep)
        return output.getvalue()

    def test_native_removal_is_previewed_and_reapplying_is_a_noop(self):
        self.apply({"obsidian", "unused-library"}, ["obsidian"], {"obsidian": ["obsidian", "unused-library"]})
        self.assertEqual(self.removals, ["obsidian"])
        self.assertEqual(self.events[-2][0:2], ["pacman", "-Rs"])
        self.apply(self.installed, ["obsidian"], {})
        self.assertEqual(self.removals, [])
        self.assertEqual(self.events, [["pacman", "-Qq"]])

    def test_core_and_integration_packages_are_protected_from_recursive_removal(self):
        for protected in ("try-omarchy", "upower", "mesa", "networkmanager", "linux-omarchy-headers", "omarchy-settings-dev", "wf-recorder", "postgresql-libs", "qemu-user-static"):
            with self.subTest(protected=protected):
                output = self.apply({"pinta", protected}, ["pinta"], {"pinta": ["pinta", protected]})
                self.assertEqual(self.removals, [])
                self.assertIn("protected packages", output)

    def test_explicit_selection_wins_for_roots_and_recursive_dependencies(self):
        self.apply({"obsidian"}, ["obsidian"], {}, keep=["obsidian"])
        self.assertEqual(self.removals, [])
        self.assertEqual(len(self.events), 1)
        self.apply({"pinta", "custom-tool"}, ["pinta"], {"pinta": ["pinta", "custom-tool"]}, keep=["custom-tool"])
        self.assertEqual(self.removals, [])

    def test_required_candidate_is_retained_and_later_candidates_still_removed(self):
        output = self.apply({"bluez", "obsidian"}, ["bluez", "obsidian"], {"bluez": None, "obsidian": ["obsidian"]})
        self.assertEqual(self.removals, ["obsidian"])
        self.assertIn("Retained bluez", output)
        self.assertIn("required by retained application", output)

    def test_candidates_are_retried_after_a_dependent_candidate_is_removed(self):
        self.apply(
            {"cups", "cups-filters"}, ["cups", "cups-filters"],
            {"cups": lambda installed: None if "cups-filters" in installed else ["cups"], "cups-filters": ["cups-filters"]},
        )
        self.assertEqual(self.removals, ["cups-filters", "cups"])

    def test_candidates_removed_as_dependencies_are_not_removed_twice(self):
        self.apply({"cups", "cups-filters"}, ["cups-filters", "cups"], {"cups-filters": ["cups-filters", "cups"]})
        self.assertEqual(self.removals, ["cups-filters"])

    def test_native_power_profile_replacement_is_an_explicit_removal_candidate(self):
        name = "omarchy-power-profiles-daemon"
        self.apply({name}, [name], {name: [name]})
        self.assertEqual(self.removals, [name])

    def test_malformed_or_empty_transaction_never_reaches_native_removal(self):
        for plan in ([], ["other-package"], ["obsidian", "bad name"]):
            with self.subTest(plan=plan), self.assertRaises(RuntimeError):
                self.apply({"obsidian"}, ["obsidian"], {"obsidian": plan})
            self.assertEqual(self.removals, [])

    def test_native_failure_stops_the_profile(self):
        failure = subprocess.CalledProcessError(1, ["omarchy-pkg-drop"], stderr="native failure")
        with self.assertRaises(subprocess.CalledProcessError):
            self.apply({"obsidian", "pinta"}, ["obsidian", "pinta"], {"obsidian": ["obsidian"]}, failure=failure)
        self.assertEqual(self.removals, [])

    def test_unexpected_preview_error_stops_instead_of_reporting_success(self):
        with self.assertRaisesRegex(RuntimeError, "Unable to preview"):
            self.apply({"obsidian"}, ["obsidian"], {"obsidian": "invalid option: --nosave and --print may not be used together"})
        self.assertEqual(self.removals, [])

    def test_host_wrong_architecture_or_missing_integration_cannot_remove_packages(self):
        with mock.patch.object(LEAN.platform, "machine", return_value="arm64"), mock.patch.object(LEAN, "run") as run:
            with self.assertRaisesRegex(RuntimeError, "aarch64"):
                LEAN.apply([])
            run.assert_not_called()
        with mock.patch.object(LEAN.platform, "machine", return_value="aarch64"), mock.patch.object(
            LEAN.shutil, "which", return_value="/usr/bin/native-command"
        ), mock.patch.object(LEAN, "run", return_value=subprocess.CompletedProcess([], 0, "obsidian", "")) as run:
            with self.assertRaisesRegex(RuntimeError, "integration package"):
                LEAN.apply([])
            run.assert_called_once_with(["pacman", "-Qq"])

    def test_allowlist_is_explicit_and_keeps_development_and_integration_tools(self):
        selected = LEAN.candidates()
        self.assertEqual(len(selected), len(set(selected)))
        self.assertFalse(set(selected) & LEAN.PROTECTED)
        for name in ("qemu-user-static", "qemu-user-static-binfmt", "mariadb-libs", "postgresql-libs", "1password", "claude-desktop"):
            self.assertNotIn(name, selected)


if __name__ == "__main__":
    unittest.main()
