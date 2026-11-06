#!/usr/bin/env python3
"""Development-only comparison of synthetic fixtures with the unchanged Python loader.

Never invokes a CLI, Ansible, transport or a VM. PyYAML must already be available;
fallback=False explicitly prohibits discovering or invoking an Ansible interpreter.
"""
import json
import tempfile
from pathlib import Path

from omarchy_data import read_data

ROOT = Path(__file__).resolve().parents[1]


def main():
    cases = json.loads((ROOT / "tests/DevVMProvisioningCoreTests/Fixtures/plain-contract.json").read_text())
    with tempfile.TemporaryDirectory(prefix="dev-vm-parser-oracle-") as directory:
        for case in cases:
            path = Path(directory) / ("manifest.json" if case["format"] == "json" else "manifest.yml")
            path.write_text(case["source"], encoding="utf-8")
            try:
                actual = read_data(path, fallback=False)
            except ValueError:
                if case["valid"]:
                    raise AssertionError("Oracle rejected a supported synthetic fixture") from None
            else:
                if not case["valid"] or actual != case["expected"]:
                    raise AssertionError("Oracle fixture mismatch")
    print(f"Python oracle: {len(cases)} synthetic plain-data fixtures passed (no subprocess fallback)")


if __name__ == "__main__":
    main()
