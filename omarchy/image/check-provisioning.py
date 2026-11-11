#!/usr/bin/env python3
"""Exercise the actual patched optional leaves without starting services."""

import json
import subprocess
import sys
from pathlib import Path

# Must match compatibility.UPDATE_REQUIRED: the manager recognises this sentence.
UPDATE_REQUIRED = ("This Omarchy release changes setup programs that Omarchy VM Manager hasn't "
                   "reviewed yet. Update Omarchy VM Manager, or try the other channel.")
# Install scripts are no longer byte-pinned. What they do on a lean image with
# every optional package absent must stay within these reviewed sets, so a new
# unit or firewall rule (perhaps for a package the lean profile omits) stops
# for review instead of building.
REVIEWED_SERVICE_COMMANDS = frozenset({
    "enable linux-modules-cleanup.service", "enable systemd-resolved.service",
    "enable NetworkManager.service", "mask NetworkManager-wait-online.service",
    "enable sddm.service", "enable systemd-oomd.service",
})
REVIEWED_FIREWALL_COMMANDS = frozenset({"default deny incoming", "default allow outgoing"})
FIREWALL_TAIL = "# Installs are followed by reboot"


class ReviewRequired(RuntimeError):
    def __init__(self, detail):
        super().__init__(f"{UPDATE_REQUIRED} ({detail})")


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
    unreviewed = sorted(set(commands) - REVIEWED_SERVICE_COMMANDS)
    if unreviewed:
        raise ReviewRequired("New service commands: " + ", ".join(unreviewed))
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
    if body.count(FIREWALL_TAIL) != 1:
        raise ReviewRequired("Firewall setup layout changed")
    body = body[:body.index(FIREWALL_TAIL)]
    result = subprocess.run(
        ["bash", "-c", 'set -euo pipefail\npacman() { return 1; }\n'
         'ufw() { printf "%s\\n" "$*"; }\n' + body],
        check=True, text=True, capture_output=True,
    )
    if "53317" in result.stdout or "allow-docker-dns" in result.stdout:
        raise RuntimeError("Absent optional applications received firewall exceptions")
    unreviewed = sorted(set(result.stdout.splitlines()) - REVIEWED_FIREWALL_COMMANDS)
    if unreviewed:
        raise ReviewRequired("New firewall rules: " + ", ".join(unreviewed))
    tail = firewall.read_text().split(FIREWALL_TAIL, 1)[1]
    tail_commands = sorted(line.strip() for line in tail.splitlines()
                           if line.strip().startswith(("ufw ", "systemctl ")))
    if tail_commands != ["systemctl enable ufw"]:
        raise ReviewRequired("Firewall activation changed")
    return {"format": 1, "optional_service_guards": "passed",
            "optional_bluetooth_hardware": "passed",
            "absent_browser_and_mise": "passed", "optional_firewall_rules": "passed",
            "full_system_provisioning": "requires-image-build",
            "owner_first_boot": "requires-disposable-vm-validation"}


if __name__ == "__main__":
    try:
        result = check(sys.argv[1])
    except (RuntimeError, ValueError, subprocess.CalledProcessError) as error:
        sys.exit(f"Provisioning check failed: {error}")
    Path(sys.argv[2]).write_text(json.dumps(result, indent=2, sort_keys=True) + "\n")
