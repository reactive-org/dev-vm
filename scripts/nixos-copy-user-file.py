#!/usr/bin/env python3
"""Explicit one-file SSH provisioning into a mutable guest home, never Nix."""
import argparse
import pathlib
import re
import shlex
import subprocess
import sys


REMOTE_COPY = r'''
set -euo pipefail
umask 077
cd "$HOME"
destination=$1
mode=$2
parent=$(dirname -- "$destination")
# Refuse symlinked parents rather than following them outside the home.
current=.
IFS=/ read -r -a parts <<< "$parent"
for part in "${parts[@]}"; do
    [[ "$part" == . ]] && continue
    current="$current/$part"
    [[ ! -L "$current" ]] || { echo 'Destination parent is a symlink.' >&2; exit 1; }
    if [[ ! -d "$current" ]]; then mkdir -m 700 -- "$current"; fi
done
temporary=$(mktemp "$parent/.nixos-user-copy.XXXXXXXX")
trap 'rm -f -- "$temporary"' EXIT
cat > "$temporary"
chmod "$mode" "$temporary"
# A same-directory hard link publishes atomically and refuses existing files,
# including existing symlinks. No overwrite option is provided.
ln -T -- "$temporary" "$destination"
'''


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--host", required=True)
    parser.add_argument("--user", required=True)
    parser.add_argument("--known-hosts", default="")
    parser.add_argument("--source", type=pathlib.Path, required=True)
    parser.add_argument("--destination", required=True, help="Relative path inside the guest home")
    parser.add_argument("--mode", choices=["600", "644", "700", "755"], default="600")
    args = parser.parse_args()
    if not re.fullmatch(r"[a-z_][a-z0-9_-]*", args.user):
        parser.error("Invalid guest user")
    if not re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9.:-]*", args.host):
        parser.error("Invalid SSH host")
    parts = args.destination.split("/")
    if any(part in ("", ".", "..") for part in parts) or "\n" in args.destination:
        parser.error("Destination must be a normalized relative home path")
    if not args.source.is_file():
        parser.error("Source must be an explicitly selected regular file")
    command = ["ssh", "-o", "BatchMode=yes", "-o", "StrictHostKeyChecking=yes"]
    if args.known_hosts:
        command += ["-o", f"UserKnownHostsFile={args.known_hosts}"]
    command += [f"{args.user}@{args.host}", shlex.join([
        "/run/current-system/sw/bin/bash", "-c", REMOTE_COPY,
        "nixos-user-copy", args.destination, args.mode,
    ])]
    # Only the selected payload is streamed over SSH; nothing is logged or
    # staged on the Mac, and no directory tree or authentication state is copied.
    with args.source.open("rb") as payload:
        subprocess.run(command, stdin=payload, check=True)
    print(f"Copied the selected file into the guest home with mode {args.mode}.")


if __name__ == "__main__":
    try:
        main()
    except (OSError, subprocess.CalledProcessError) as error:
        # Avoid echoing the SSH command or file contents in exception messages.
        print(f"User-file copy failed ({type(error).__name__}).", file=sys.stderr)
        sys.exit(1)
