import gzip
import hashlib
import importlib.util
import io
import json
import tarfile
import tempfile
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
FIXTURES = ROOT / "tests/fixtures/omarchy-image/source"


def load(name, path):
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


WATCH = load("omarchy_release_watch", ROOT / "scripts/omarchy_release_watch.py")
LOCK = json.loads((ROOT / "omarchy/image/inputs.lock.json").read_text())


def tar(entries, links=()):
    data = io.BytesIO()
    with tarfile.open(fileobj=data, mode="w") as archive:
        for name, body in entries.items():
            info = tarfile.TarInfo(name); info.size = len(body); info.mode = 0o755
            archive.addfile(info, io.BytesIO(body))
        for name, target in links:
            info = tarfile.TarInfo(name); info.type = tarfile.SYMTYPE; info.linkname = target
            archive.addfile(info)
    return data.getvalue()


def release(changes=None):
    """The reviewed 4.5.0 files in installed package layout, optionally changed."""
    entries = {}
    for path in FIXTURES.rglob("*"):
        if path.is_file():
            relative = path.relative_to(FIXTURES).as_posix()
            name = "usr/bin/" + relative[4:] if relative.startswith("bin/") else "usr/share/omarchy/" + relative
            text = path.read_text()
            if changes and relative in changes:
                text = changes[relative](text)
            entries[name] = text.encode()
    entries["usr/share/omarchy/unrelated.txt"] = b"ignored"
    return entries


def desc(name, version, filename, sha):
    return (f"%FILENAME%\n{filename}\n\n%NAME%\n{name}\n\n%VERSION%\n{version}\n\n%SHA256SUM%\n{sha}\n\n").encode()


class ReleaseWatchTests(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory()
        self.addCleanup(self.temporary.cleanup)
        self.root = Path(self.temporary.name)

    def repository(self, channel, runtime_files, settings_files=None, corrupt=False):
        runtime, settings = WATCH.CHANNELS[channel]
        packages = {f"{runtime}-1.0-1-aarch64.pkg.tar.zst": gzip.compress(tar(runtime_files)),
                    f"{settings}-1.0-1-any.pkg.tar.zst": gzip.compress(tar(settings_files or {"etc/x": b"x"}))}
        entries = {}
        for (filename, body), name in zip(packages.items(), (runtime, settings)):
            sha = "0" * 64 if corrupt and name == runtime else hashlib.sha256(body).hexdigest()
            entries[f"{name}-1.0-1/desc"] = desc(name, "1.0-1", filename, sha)
        files = {WATCH.REPOSITORY.format(channel=channel) + "omarchy.db": gzip.compress(tar(entries))}
        files.update({WATCH.REPOSITORY.format(channel=channel) + name: body for name, body in packages.items()})
        return files.__getitem__

    def test_database_parsing_reads_desc_fields(self):
        data = gzip.compress(tar({"omarchy-4.5.0-3/desc": desc("omarchy", "4.5.0-3", "omarchy-4.5.0-3-any.pkg.tar.zst", "a" * 64)}))
        parsed = WATCH.parse_database(data)
        self.assertEqual(parsed["omarchy"]["VERSION"], "4.5.0-3")
        self.assertEqual(parsed["omarchy"]["SHA256SUM"], "a" * 64)

    def test_reviewed_release_writes_no_draft(self):
        result = WATCH.watch("stable", LOCK, self.root / "out", fetcher=self.repository("stable", release()))
        self.assertEqual(result["outcome"], "reviewed")
        self.assertFalse((self.root / "out").exists())

    def test_unreviewed_owner_program_drafts_a_manual_review(self):
        changed = release({"install/provisioning/progress-icon.sh": lambda text: text + "\n# VT colour fix\n"})
        result = WATCH.watch("edge", LOCK, self.root / "out", fetcher=self.repository("edge", changed))
        self.assertEqual(result["outcome"], "manual")
        draft = json.loads((self.root / "out/omarchy/image/review-drafts" / (result["draft"] + ".json")).read_text())
        self.assertEqual(draft["draft_entry"]["owner_setup_contract_sha256"], "TO REVIEW")
        self.assertEqual(set(draft["draft_entry"]["owner_programs"]), set(LOCK["reviewed_omarchy"][0]["owner_programs"]))
        diff = (self.root / "out/omarchy/image/review-drafts" / (result["draft"] + ".diff")).read_text()
        self.assertIn("+++ release/install/provisioning/progress-icon.sh", diff)
        self.assertIn("+# VT colour fix", diff)
        self.assertNotIn("enable-services.sh", diff)
        # The lock is never edited.
        self.assertEqual(json.loads((ROOT / "omarchy/image/inputs.lock.json").read_text()), LOCK)

    def test_new_service_drafts_a_blocked_review(self):
        changed = release({"install/config/enable-services.sh": lambda text: text + "systemctl enable bolt.service\n"})
        result = WATCH.watch("stable", LOCK, self.root / "out", fetcher=self.repository("stable", changed))
        self.assertEqual(result["outcome"], "blocked")
        draft = json.loads((self.root / "out/omarchy/image/review-drafts" / (result["draft"] + ".json")).read_text())
        self.assertIn("bolt.service", draft["detail"])

    def test_checksum_mismatch_or_linked_reviewed_file_is_refused(self):
        with self.assertRaisesRegex(ValueError, "checksum"):
            WATCH.watch("stable", LOCK, self.root / "out", fetcher=self.repository("stable", release(), corrupt=True))
        files = release()
        del files["usr/bin/omarchy-provision-owner"]
        data = gzip.compress(tar(files, links=[("usr/bin/omarchy-provision-owner", "/etc/passwd")]))
        with self.assertRaisesRegex(ValueError, "regular file"):
            WATCH.extract(data, self.root / "linked")


if __name__ == "__main__":
    unittest.main()
