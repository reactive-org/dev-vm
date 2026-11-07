import shutil
import subprocess
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


class LayoutTests(unittest.TestCase):
    @unittest.skipUnless(shutil.which("lua"), "Lua is not installed; the same fixture can run inside the guest")
    def test_claude_layout_terminal_recovery_uses_native_bindings(self):
        result = subprocess.run([
            shutil.which("lua"), str(ROOT / "tests/fixtures/claude-layout.lua"),
            str(ROOT / "omarchy/examples/layouts/claude-two-terminals-browser.lua"),
        ], capture_output=True, text=True)
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertIn("PASS layout terminal recovery", result.stdout)


if __name__ == "__main__":
    unittest.main()


class LayoutCatalogueTests(unittest.TestCase):
    """The shared catalogue's needs must match the apps each layout's runbook installs."""

    LAYOUTS = ROOT / "omarchy/examples/layouts"
    BUNDLED = ROOT / "Sources/DevVMProvisioningCore/Resources/Provisioning/omarchy/examples/layouts"
    # Apps no setup feature installs yet; the catalogue lists them without a feature.
    UNPROVIDED = {"claude-desktop": "Claude Desktop"}

    def catalogue(self):
        import json
        return json.loads((self.LAYOUTS / "catalogue.json").read_text())

    def runbook_packages(self, layout_id):
        import re
        text = (ROOT / f"docs/omarchy-layout-{layout_id}.md").read_text()
        lists = {tuple(sorted(item.removeprefix("pkg:") for item in value.split(",")))
                 for value in re.findall(r"OMARCHY_VM_PACKAGES=(\S+)", text)}
        self.assertLessEqual(len(lists), 1, f"{layout_id} runbooks disagree on packages")
        return set(next(iter(lists), ()))

    def test_needs_match_each_runbooks_packages(self):
        import json
        features = json.loads((ROOT / "omarchy/features/catalogue.json").read_text())["features"]
        examples = self.catalogue()["examples"]
        self.assertEqual(len(examples), 7)
        for example in examples:
            with self.subTest(layout=example["id"]):
                packages = set()
                for need in example["needs"]:
                    self.assertIn(need["application"], example["applications"])
                    if "feature" not in need:
                        self.assertIn(need["application"], self.UNPROVIDED.values())
                        packages.add(next(k for k, v in self.UNPROVIDED.items() if v == need["application"]))
                        continue
                    choices = features[need["feature"]]["choices"]
                    for items in need["options"].values():
                        packages.update(choices[item] for item in items)
                self.assertEqual(packages, self.runbook_packages(example["id"]))

    def test_bundled_catalogue_and_lua_match_the_maintained_copies(self):
        for name in ["catalogue.json"] + [example["file"] for example in self.catalogue()["examples"]]:
            with self.subTest(file=name):
                self.assertEqual((self.BUNDLED / name).read_bytes(), (self.LAYOUTS / name).read_bytes())
