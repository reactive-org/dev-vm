#!/usr/bin/env python3
"""Build-time only: bind the Swift engine to reviewed source/resource bytes."""
import hashlib
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
OUTPUT = ROOT / "Sources/DevVMProvisioningCore/Resources/engine-identity.json"


def inventory():
    paths = [p for p in (ROOT / "Sources").rglob("*") if p.is_file() and p != OUTPUT]
    paths += [ROOT / "Package.swift", ROOT / "Package.resolved", ROOT / "ThirdParty/ParserInventory.json"]
    return {"setup_api": 1, "controller": "swift", "sources": {
        str(p.relative_to(ROOT)): hashlib.sha256(p.read_bytes()).hexdigest() for p in sorted(paths)}}


if __name__ == "__main__":
    data = json.dumps(inventory(), indent=2, sort_keys=True) + "\n"
    if not OUTPUT.exists() or OUTPUT.read_text() != data:
        OUTPUT.write_text(data)
