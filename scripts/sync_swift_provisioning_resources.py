#!/usr/bin/env python3
"""Build-time copy of explicit, maintained resources. No tool/guest execution."""
import hashlib
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DEST = ROOT / "Sources/DevVMProvisioningCore/Resources/Provisioning"


def source_paths():
    names = ["site.yml", "setup.yml", "group_vars/all.yml", "omarchy/features/catalogue.json"]
    names += [str(p.relative_to(ROOT)) for p in sorted((ROOT / "roles").rglob("*.yml"))]
    names += ["omarchy/guest/" + n for n in ["apply-lean-developer.py", "lean-developer.packages", "apply-features.py", "feature_contract.py", "apply-workstation.sh", "apply-theme.sh", "repair-try-omarchy-black-screen.sh", "apply-dotfiles.py", "provisioning-job.py"]]
    names += ["omarchy/examples/layouts/" + n for n in ["catalogue.json", "four-terminals.lua", "terminal-browser.lua", "vscode-browser.lua", "claude-two-terminals-browser.lua"]]
    return names


def sync():
    inventory = {}
    for name in source_paths():
        source = ROOT / name
        if source.is_symlink() or not source.is_file():
            raise ValueError("Resource must be a regular source file")
        data = source.read_bytes()
        target = DEST / name
        target.parent.mkdir(parents=True, exist_ok=True)
        if not target.exists() or target.read_bytes() != data:
            target.write_bytes(data)
        inventory[name] = hashlib.sha256(data).hexdigest()
    text = json.dumps(inventory, indent=2, sort_keys=True) + "\n"
    output = DEST / "inventory.json"
    if not output.exists() or output.read_text() != text:
        output.write_text(text)


if __name__ == "__main__":
    sync()
