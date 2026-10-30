#!/usr/bin/env python3
"""Transfer clipboard text once, without a persistent host/guest clipboard agent."""

import argparse
import shutil
import subprocess
import sys


WAYLAND_ENV = r'''
set -eu
export XDG_RUNTIME_DIR="${XDG_RUNTIME_DIR:-/run/user/$(id -u)}"
WAYLAND_DISPLAY=$(systemctl --user show-environment | sed -n 's/^WAYLAND_DISPLAY=//p')
if [ -z "$WAYLAND_DISPLAY" ]; then
    echo 'No active Wayland session; log into the workstation desktop first.' >&2
    exit 1
fi
export WAYLAND_DISPLAY
'''


def run(command, data=None):
    return subprocess.run(
        command, input=data, stdout=subprocess.PIPE, stderr=subprocess.PIPE,
        check=True, timeout=15,
    ).stdout


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("direction", choices=("to-vm", "from-vm"))
    parser.add_argument("--host", required=True)
    parser.add_argument("--user", default="developer")
    parser.add_argument("--known-hosts", default="")
    args = parser.parse_args()
    if sys.platform != "darwin":
        parser.error("Run this command on the macOS controller.")
    if not args.host or args.host.startswith("-"):
        parser.error("Set SSH_HOST to the NixOS guest's current address.")
    for program in ("ssh", "pbcopy", "pbpaste"):
        if not shutil.which(program):
            parser.error(f"Required executable is missing: {program}")
    ssh = ["ssh", "-o", "BatchMode=yes", "-o", "ConnectTimeout=10",
           "-o", "StrictHostKeyChecking=yes"]
    if args.known_hosts:
        ssh += ["-o", f"UserKnownHostsFile={args.known_hosts}"]
    ssh += ["-l", args.user or "developer", "--", args.host]

    try:
        # Buffer in memory: a failed source read must not erase the destination.
        # Clipboard contents never appear in arguments, logs or temporary files.
        if args.direction == "to-vm":
            data = run(["pbpaste"])
            # Detach the Wayland owner's output so it cannot hold SSH open.
            run(ssh + [WAYLAND_ENV + "exec wl-copy --type 'text/plain;charset=utf-8' >/dev/null 2>&1"], data)
        else:
            data = run(ssh + [WAYLAND_ENV + "exec timeout -k 1 8 wl-paste --no-newline"])
            run(["pbcopy"], data)
    except subprocess.TimeoutExpired:
        print("Clipboard transfer timed out; no success was recorded.", file=sys.stderr)
        return 1
    except subprocess.CalledProcessError as error:
        print("Clipboard transfer failed: " + error.stderr.decode(errors="replace").strip(), file=sys.stderr)
        return 1
    print(f"Transferred clipboard text {args.direction} ({len(data)} bytes).")
    return 0


if __name__ == "__main__":
    sys.exit(main())
