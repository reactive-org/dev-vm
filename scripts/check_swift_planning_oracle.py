#!/usr/bin/env python3
"""Development oracle for complete offline proposals on synthetic roots only."""
import argparse
import json
import subprocess
import tempfile
from pathlib import Path
from unittest import mock

import omarchy_data
import omarchy_profiles
import omarchy_setup

ROOT = Path(__file__).resolve().parents[1]


def difference(a, b, path="proposal"):
    if type(a) is not type(b):
        return path
    if isinstance(a, dict):
        if a.keys() != b.keys():
            return path + ".keys"
        return next((d for key in sorted(a) if (d := difference(a[key], b[key], path + "." + key))), None)
    if isinstance(a, list):
        if len(a) != len(b):
            return path + ".length"
        return next((d for i, (x, y) in enumerate(zip(a, b)) if (d := difference(x, y, path + f"[{i}]"))), None)
    return None if a == b else path


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--binary", required=True)
    args = parser.parse_args()
    binary = str(Path(args.binary).resolve(strict=True))
    cases = json.loads((ROOT / "tests/DevVMProvisioningCoreTests/Fixtures/planning-contract.json").read_text())
    loader = omarchy_data.read_data
    for case in cases:
        with tempfile.TemporaryDirectory(prefix="dev-vm-planning-oracle-") as directory:
            root = Path(directory)
            for name, text in {"vm.json": json.dumps(case["manifest"]), **case["files"]}.items():
                path = root / name
                path.parent.mkdir(parents=True, exist_ok=True)
                path.write_text(text, encoding="utf-8")
                path.chmod(0o644)
            expected = None

            def plain(path):
                return loader(path, fallback=False)

            # Forbid loader interpreter fallback, process creation and manager access.
            with mock.patch.object(omarchy_profiles, "read_data", side_effect=plain), \
                    mock.patch.object(omarchy_setup, "read_data", side_effect=plain), \
                    mock.patch.object(subprocess, "run", side_effect=AssertionError("Oracle attempted a subprocess")), \
                    mock.patch.object(omarchy_setup.manager, "cli_call", side_effect=AssertionError("Oracle attempted manager access")):
                try:
                    expected = omarchy_setup.Setup(root, "vm.json").proposal()
                except (ValueError, FileNotFoundError):
                    if case["valid"]:
                        raise AssertionError("Python rejected valid fixture: " + case["name"]) from None
            # The only child outside that guard is the explicitly built Swift CLI.
            native = subprocess.run([binary, "plan", str(root), "vm.json"],
                                    env={"PATH": "/nonexistent"}, capture_output=True, text=True)
            if (native.returncode == 0) != case["valid"] or (expected is not None) != case["valid"]:
                raise AssertionError("Planning admission mismatch: " + case["name"])
            if "synthetic-canary-never-output" in native.stdout + native.stderr:
                raise AssertionError("Opaque data escaped the planning boundary")
            if expected is not None:
                actual = json.loads(native.stdout)
                for source in expected["features"]["sources"]:
                    if source["path"] == str(omarchy_profiles.contract.CATALOGUE_PATH.resolve()):
                        source["path"] = "builtin/catalogue.json"
                # Engine sources/API differ by design. Compare every legacy
                # proposal field except engine; Swift digests have separate tests.
                keys = set(expected) - {"engine"}
                diff = difference({k: expected[k] for k in keys}, {k: actual[k] for k in keys})
                if diff:
                    raise AssertionError("Proposal mismatch in " + case["name"] + " at " + diff)
                if actual["execution_available"] or len(actual["plan_digest"]) != 64:
                    raise AssertionError("Invalid native planning boundary")
    print(f"Planning oracle: {len(cases)} complete proposal/error fixtures passed; no Python subprocesses or guest access")


if __name__ == "__main__":
    main()
