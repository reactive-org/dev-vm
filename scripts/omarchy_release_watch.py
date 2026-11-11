#!/usr/bin/env python3
"""Compare each channel's current Omarchy release with the reviewed set.

Advisory: it downloads the channel's Omarchy package pair, checks each
archive against the repository database's SHA-256 (not its signature; the
builder verifies signatures), applies the factory builder's guards and runs
its behaviour checks, which source the release's guarded install scripts
with only pacman, systemctl and ufw stubbed. Run it only somewhere disposable
that holds no credentials, as the scheduled workflow does. It writes a
review draft when a release would build for manual owner setup only or would
stop for review. It never edits inputs.lock.json, builds an image or starts
a VM.
"""

import argparse
import difflib
import hashlib
import importlib.util
import io
import json
import re
import shutil
import subprocess
import sys
import tarfile
import tempfile
import urllib.request
from pathlib import Path, PurePosixPath

ROOT = Path(__file__).resolve().parents[1]
IMAGE = ROOT / "omarchy/image"
FIXTURE = ROOT / "tests/fixtures/omarchy-image/source"
REPOSITORY = "https://pkgs.omarchy.org/{channel}/aarch64/"
CHANNELS = {"stable": ("omarchy", "omarchy-settings"), "edge": ("omarchy-dev", "omarchy-settings-dev")}
MAXIMUM_DOWNLOAD = 256 * 1024 * 1024
DRAFTS = "omarchy-review-drafts"


def load(name, path):
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


COMPAT = load("omarchy_compatibility", IMAGE / "compatibility.py")
CHECKS = load("omarchy_provisioning_checks", IMAGE / "check-provisioning.py")


def decompress(data):
    """Return tar bytes from a zstd, gzip or plain archive."""
    if data[:4] == b"\x28\xb5\x2f\xfd":
        try:
            from compression import zstd
            return zstd.decompress(data)
        except ImportError:
            return subprocess.run(["zstd", "-dc"], input=data, capture_output=True, check=True).stdout
    if data[:2] == b"\x1f\x8b":
        import gzip
        return gzip.decompress(data)
    return data


def parse_database(data):
    """Map package name to its desc fields from a pacman repository database."""
    packages = {}
    with tarfile.open(fileobj=io.BytesIO(decompress(data))) as archive:
        for member in archive:
            if not member.isfile() or PurePosixPath(member.name).name != "desc":
                continue
            fields, key = {}, None
            for line in archive.extractfile(member).read().decode().splitlines():
                if re.fullmatch(r"%[A-Z0-9]+%", line):
                    key = line.strip("%"); fields[key] = []
                elif key and line:
                    fields[key].append(line)
            name = fields.get("NAME", [None])[0]
            if name:
                if name in packages:
                    raise ValueError(f"Duplicate package in repository database: {name}")
                packages[name] = {key: values[0] if len(values) == 1 else values for key, values in fields.items()}
    return packages


def wanted(relative):
    """Archive paths for the guarded install scripts and owner programs."""
    names = set()
    for script in COMPAT.INSTALL_SCRIPTS:
        names.add("usr/bin/" + script[4:] if script.startswith("bin/") else "usr/share/omarchy/" + script)
    names.update(program.lstrip("/") for program in COMPAT.OWNER_PROGRAMS)
    return relative in names


def extract(package, root):
    """Write only the reviewed files, as regular files, into an installed root."""
    with tarfile.open(fileobj=io.BytesIO(decompress(package))) as archive:
        for member in archive:
            relative = PurePosixPath(member.name.lstrip("./")).as_posix()
            if not wanted(relative):
                continue
            if not member.isfile():
                raise ValueError(f"Reviewed file is not a regular file: {relative}")
            target = Path(root) / relative
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_bytes(archive.extractfile(member).read())
            target.chmod(0o755 if member.mode & 0o111 else 0o644)


def source_relative(installed):
    """Map an installed path to the fixture's source-tree path."""
    if installed.startswith("usr/bin/"):
        return "bin/" + installed[len("usr/bin/"):]
    return installed[len("usr/share/omarchy/"):]


def review_diff(root):
    """Unified diff of every reviewed file against the reviewed 4.5.0 fixture."""
    chunks = []
    for path in sorted(p for p in Path(root).rglob("*") if p.is_file()):
        relative = source_relative(path.relative_to(root).as_posix())
        before = (FIXTURE / relative).read_text().splitlines(keepends=True) if (FIXTURE / relative).is_file() else []
        chunks.extend(difflib.unified_diff(before, path.read_text().splitlines(keepends=True),
                                           "reviewed/" + relative, "release/" + relative))
    return "".join(chunks)


def classify(root, lock):
    """What the factory builder would do with this installed release."""
    report = None
    try:
        report = COMPAT.patch_sources(root, lock, installed=True)
        CHECKS.check(Path(root) / "usr/share/omarchy")
    except (COMPAT.CompatibilityError, CHECKS.ReviewRequired, RuntimeError,
            ValueError, subprocess.CalledProcessError) as error:
        return {"outcome": "blocked", "detail": str(error), "report": report}
    return {"outcome": "reviewed" if report["owner_setup"] == "managed" else "manual",
            "detail": report["reviewed_omarchy"], "report": report}


def fetch(url):
    with urllib.request.urlopen(url, timeout=120) as response:
        data = response.read(MAXIMUM_DOWNLOAD + 1)
    if len(data) > MAXIMUM_DOWNLOAD:
        raise ValueError(f"Download too large: {url}")
    return data


def safe(value):
    return re.sub(r"[^A-Za-z0-9._-]", "_", value)


def watch(channel, lock, output, fetcher=fetch):
    base = REPOSITORY.format(channel=channel)
    database = parse_database(fetcher(base + "omarchy.db"))
    runtime, settings = CHANNELS[channel]
    entries = {name: database[name] for name in (runtime, settings)}
    with tempfile.TemporaryDirectory(prefix="omarchy-watch-") as temporary:
        release = Path(temporary) / "release"
        for name, entry in entries.items():
            filename = entry["FILENAME"]
            if "/" in filename or filename.startswith("."):
                raise ValueError(f"Unsafe package filename: {filename}")
            package = fetcher(base + filename)
            if hashlib.sha256(package).hexdigest() != entry["SHA256SUM"]:
                raise ValueError(f"{name} does not match the repository database checksum")
            extract(package, release)
        diff = review_diff(release)
        patched = Path(temporary) / "patched"
        shutil.copytree(release, patched)
        result = classify(patched, lock)
    version = entries[runtime]["VERSION"]
    summary = {"channel": channel, "package": runtime, "version": version, "outcome": result["outcome"]}
    if result["outcome"] == "reviewed":
        return summary
    report = result["report"] or {}
    draft = {
        "format": 1, "channel": channel, "outcome": result["outcome"], "detail": result["detail"],
        "packages": {name: {"version": entry["VERSION"], "filename": entry["FILENAME"], "sha256": entry["SHA256SUM"]}
                     for name, entry in entries.items()},
        "install_scripts": {relative: hashes["upstream_sha256"] for relative, hashes in report.get("files", {}).items()},
        # A draft only: an entry needs a reviewed owner contract, guest package
        # and kit before it can be added to inputs.lock.json.
        "draft_entry": {
            "id": "lean-" + safe(version), "description": f"Omarchy {version} ({channel}): DRAFT, not reviewed",
            "owner_setup_contract_sha256": "TO REVIEW", "owner_programs": report.get("owner_programs"),
        },
    }
    name = f"{channel}-{safe(version)}"
    # Outside omarchy/image, which the factory recipe hashes and stages.
    drafts = Path(output) / DRAFTS
    drafts.mkdir(parents=True, exist_ok=True)
    (drafts / f"{name}.json").write_text(json.dumps(draft, indent=2, sort_keys=True) + "\n")
    (drafts / f"{name}.diff").write_text(diff)
    summary["draft"] = name
    return summary


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, required=True, help="Directory for review drafts")
    parser.add_argument("--channel", action="append", choices=sorted(CHANNELS), help="Channel to check (default: all)")
    args = parser.parse_args()
    lock = json.loads((IMAGE / "inputs.lock.json").read_text())
    results = [watch(channel, lock, args.output) for channel in (args.channel or sorted(CHANNELS))]
    print(json.dumps(results, indent=2))


if __name__ == "__main__":
    sys.exit(main())
