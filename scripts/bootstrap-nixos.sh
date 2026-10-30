#!/usr/bin/env bash
# Phase 1: create hardware and boot an upstream installer. No disk installation.
set -euo pipefail
prlctl=${1:-/usr/local/bin/prlctl}
vm=${2:-NixOS Workstation Test}
image=${3:-}
cpus=${4:-4}
memory=${5:-12288}
disk=${6:-24}
die() { printf '%s\n' "$*" >&2; exit 1; }
[[ -n "$image" ]] || die 'Set IMAGE to a downloaded NixOS aarch64-linux.iso.'
[[ -f "$image" && "$image" == *aarch64-linux.iso ]] || die 'Expected an existing aarch64-linux.iso.'
[[ "$(uname -m)" == arm64 ]] || die 'This bootstrap requires an Apple Silicon Mac.'
for value in "$cpus" "$memory" "$disk"; do
  [[ "$value" =~ ^[1-9][0-9]*$ ]] || die 'CPU, memory and disk settings must be positive integers.'
done
((disk >= 24)) || die 'Use at least a 24 GB expanding disk.'
# A failed inventory read must never be interpreted as an absent VM.
inventory=$("$prlctl" list --all --output name --no-header)
if printf '%s\n' "$inventory" | sed 's/[[:space:]]*$//' | grep -Fxq "$vm"; then
  die "VM already exists: $vm. Inspect it in Parallels; this target never modifies existing VMs."
fi
printf 'Create %s\nISO: %s\nCPUs: %s; RAM: %s MB; expanding disk: %s GB\n' "$vm" "$image" "$cpus" "$memory" "$disk"
printf 'ARM64 EFI; shared network; bidirectional clipboard; broad sharing disabled.\n'
if [[ ${NIXOS_SKIP_SHARE:-no} == yes ]]; then
  printf 'Optional explicit host share disabled for this run.\n'
elif [[ -d "$HOME/Parallels/Shared" ]]; then
  printf 'Explicit read-write share: %s (guest /mnt/shared is opt-in).\n' "$HOME/Parallels/Shared"
else
  printf 'Optional ~/Parallels/Shared absent; no host share will be configured.\n'
fi
if [[ ${NIXOS_CONFIRMED_CREATE:-} != "$vm" ]]; then
  read -r -p 'Type create to continue: ' confirmation
  [[ "$confirmation" == create ]] || die 'Cancelled.'
fi
"$prlctl" create "$vm" --ostype linux
trap 'printf "VM configuration stopped. The new VM was retained for inspection: %s\n" "$vm" >&2' ERR
"$prlctl" set "$vm" --cpus "$cpus" --memsize "$memory"
"$prlctl" set "$vm" --device-set hdd0 --size "$((disk * 1024))" --type expand --online-compact on
"$prlctl" set "$vm" --bios-type efi-arm64 --efi-secure-boot off --device-bootorder 'hdd0 cdrom0'
"$prlctl" set "$vm" --device-set net0 --type shared
"$prlctl" set "$vm" --video-adapter-type virtio --videosize auto --3d-accelerate highest --high-resolution off --high-resolution-in-guest on --native-scaling-in-guest off
"$prlctl" set "$vm" --hypervisor-type apple --nested-virt off --rosetta-linux off
"$prlctl" set "$vm" --shf-host off --shf-host-defined off --shf-host-automount off --shf-guest off --shared-profile off --shared-cloud off
"$prlctl" set "$vm" --sh-app-host-to-guest off --sh-app-guest-to-host off --show-guest-app-folder-in-dock off
"$prlctl" set "$vm" --smart-mount off --smart-mount-removable-drives off --smart-mount-dvd-drives off --smart-mount-network-shares off
"$prlctl" set "$vm" --sync-host-printers off --sync-default-printer off --show-host-printer-ui off --auto-share-camera off --auto-share-smart-card off
"$prlctl" set "$vm" --auto-share-gamepad off
"$prlctl" set "$vm" --share-host-location off --sync-ssh-ids off --sync-vm-hostname off --shared-clipboard on
"$prlctl" set "$vm" --time-sync on --time-sync-smart-mode off --disable-timezone-sync on --time-sync-interval 60
"$prlctl" set "$vm" --autostart off --autostop suspend --on-window-close suspend --tools-autoupdate no
"$prlctl" set "$vm" --device-set cdrom0 --image "$image" --connect
if [[ -n ${NIXOS_SERIAL_LOG:-} ]]; then
  if "$prlctl" list -i "$vm" --json | python3 -c 'import json,sys; sys.exit("serial0" not in json.load(sys.stdin)[0]["Hardware"])'; then
    "$prlctl" set "$vm" --device-set serial0 --output "$NIXOS_SERIAL_LOG" --connect
  else
    "$prlctl" set "$vm" --device-add serial --output "$NIXOS_SERIAL_LOG"
    "$prlctl" set "$vm" --device-set serial0 --connect
  fi
fi
if [[ ${NIXOS_SKIP_SHARE:-no} != yes ]]; then
  bash "$(dirname "$0")/configure-nixos-share.sh" "$prlctl" "$vm"
fi
"$prlctl" start "$vm"
if [[ ${NIXOS_CONFIRMED_CREATE:-} == "$vm" ]]; then
  printf '\nUnattended installer started; the controller will verify installation and boot.\n'
else
  printf '\nLive installer started. Follow nixos/README.md to install the pinned workstation.\n'
fi
