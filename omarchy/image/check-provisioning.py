#!/usr/bin/env python3
"""Exercise the actual patched optional leaves without starting services."""

import json
import subprocess
import sys
from pathlib import Path


def check(root):
    root = Path(root)
    service_script = root / "install/config/enable-services.sh"
    harness = '''
set -euo pipefail
pacman() { return 1; }
systemctl() { printf '%s\\n' "$*"; }
source "$1"
'''
    result = subprocess.run(["bash", "-c", harness, "bash", str(service_script)],
                            check=True, text=True, capture_output=True)
    commands = result.stdout.splitlines()
    for service in ("cups.service", "docker.socket", "avahi-daemon.service", "power-profiles-daemon.service"):
        if f"enable {service}" in commands:
            raise RuntimeError(f"Absent optional service enabled: {service}")
    for service in ("NetworkManager.service", "sddm.service", "systemd-resolved.service"):
        if f"enable {service}" not in commands:
            raise RuntimeError(f"Mandatory service skipped: {service}")

    present = harness.replace("pacman() { return 1; }", "pacman() { return 0; }")
    result = subprocess.run(["bash", "-c", present, "bash", str(service_script)],
                            check=True, text=True, capture_output=True)
    if "enable docker.socket" not in result.stdout or "enable cups.service" not in result.stdout:
        raise RuntimeError("Installed optional services were not configured")
    for name in ("chromium.sh", "mise.sh"):
        subprocess.run(["bash", "-c", harness, "bash", str(root / "install/user" / name)],
                       check=True, text=True, capture_output=True)
    bluetooth = root / "install/hardware/bluetooth.sh"
    for installed in (False, True):
        for deferred in (False, True):
            test = present if installed else harness
            test = test.replace('source "$1"',
                                f'export OMARCHY_IMAGE_DEFERRED_HARDWARE={int(deferred)}\nsource "$1"')
            result = subprocess.run(["bash", "-c", test, "bash", str(bluetooth)],
                                    check=True, text=True, capture_output=True)
            expected = (["enable bluetooth.service"] if installed else [])
            if installed and deferred:
                expected.append("start --no-block bluetooth.service")
            if result.stdout.splitlines() != expected:
                raise RuntimeError("Optional Bluetooth hardware guard changed native setup behaviour")
    firewall = root / "install/config/firewall.sh"
    body = firewall.read_text()
    # Keep absolute /etc writes out of this source-level test. The real chroot
    # build runs the complete leaf and verifies system provisioning separately.
    body = body[:body.index("# Installs are followed by reboot")]
    result = subprocess.run(
        ["bash", "-c", 'set -euo pipefail\npacman() { return 1; }\n'
         'ufw() { printf "%s\\n" "$*"; }\n' + body],
        check=True, text=True, capture_output=True,
    )
    if "53317" in result.stdout or "allow-docker-dns" in result.stdout:
        raise RuntimeError("Absent optional applications received firewall exceptions")
    return {"format": 1, "optional_service_guards": "passed",
            "optional_bluetooth_hardware": "passed",
            "absent_browser_and_mise": "passed", "optional_firewall_rules": "passed",
            "full_system_provisioning": "requires-image-build",
            "owner_first_boot": "requires-disposable-vm-validation"}


if __name__ == "__main__":
    result = check(sys.argv[1])
    Path(sys.argv[2]).write_text(json.dumps(result, indent=2, sort_keys=True) + "\n")
