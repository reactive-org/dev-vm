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
