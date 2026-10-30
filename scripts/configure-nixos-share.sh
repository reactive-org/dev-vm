#!/usr/bin/env bash
set -euo pipefail
prlctl=${1:-/usr/local/bin/prlctl}
vm=${2:-}
share_path=${3:-$HOME/Parallels/Shared}
[[ -n "$vm" ]] || { printf 'Set VM_NAME to the NixOS VM.\n' >&2; exit 1; }
if [[ ! -d "$share_path" ]]; then
  printf 'Optional share absent: %s. No directory was created or sharing enabled.\n' "$share_path"
  printf 'Create it yourself if wanted, then rerun configure-nixos-share.\n'
  exit 0
fi
"$prlctl" set "$vm" --shf-host on --shf-host-defined off --shf-host-automount off
if ! "$prlctl" set "$vm" --shf-host-set Shared --path "$share_path" --mode rw --enable; then
  "$prlctl" set "$vm" --shf-host-add Shared --path "$share_path" --mode rw --enable
fi
printf 'Configured the explicit Shared folder. Enable workstation.sharedFolder.enable in the guest and rebuild to mount /mnt/shared.\n'
