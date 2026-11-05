"""Offline resource checks preserve existing compression bytes and Swift pins."""
import contextlib
import gzip
import importlib.util
import io
from pathlib import Path
import shutil
import tempfile
import unittest
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location("swift_factory_resources", ROOT / "scripts/sync_swift_factory_resources.py")
resources = importlib.util.module_from_spec(spec)
spec.loader.exec_module(resources)


class SwiftFactoryResourceTests(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory()
        self.addCleanup(self.temporary.cleanup)
        self.output = Path(self.temporary.name) / "FactoryBuild"
        shutil.copytree(resources.OUT, self.output)
        self.original = {p.name: p.read_bytes() for p in self.output.iterdir()}

    def check(self):
        with patch.object(resources, "OUT", self.output), contextlib.redirect_stdout(io.StringIO()):
            resources.generate(check=True)

    def test_check_never_recompresses_or_changes_committed_bytes(self):
        pin = ROOT / "Sources/DevVMProvisioningCore/FactoryRecipePin.swift"
        original_pin = pin.read_bytes()
        with patch.object(resources, "compress_template", side_effect=AssertionError("check must not recompress")):
            self.check()
        self.assertEqual({p.name: p.read_bytes() for p in self.output.iterdir()}, self.original)
        self.assertEqual(pin.read_bytes(), original_pin)

    def test_changed_archive_contents_are_refused(self):
        data = bytearray(gzip.decompress(self.original["template.tar.gz"]))
        data[0] ^= 1
        (self.output / "template.tar.gz").write_bytes(resources.compress_template(data))
        with self.assertRaisesRegex(ValueError, "archive contents"):
            self.check()

    def test_equivalent_reencoding_still_requires_matching_recipe_and_swift_pin(self):
        encoded = gzip.compress(gzip.decompress(self.original["template.tar.gz"]), compresslevel=1, mtime=42)
        self.assertNotEqual(encoded, self.original["template.tar.gz"])
        (self.output / "template.tar.gz").write_bytes(encoded)
        with self.assertRaisesRegex(ValueError, "recipe.json"):
            self.check()


if __name__ == "__main__":
    unittest.main()
