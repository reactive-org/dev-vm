#!/usr/bin/env bash
# Run from this directory on the NixOS live ISO, only in the disposable VM.
set -euo pipefail
[[ "$EUID" == 0 && "$(uname -m)" == aarch64 && -d /iso ]] || {
  echo 'Run as root on the NixOS aarch64 live ISO.' >&2; exit 1;
}
cd -- "$(dirname -- "${BASH_SOURCE[0]}")"
[[ -f flake.lock ]] || { echo 'A pinned flake.lock is required.' >&2; exit 1; }
disk=${1:?Usage: sudo bash install.sh /dev/WHOLE_DISK}
[[ -b "$disk" && "$(lsblk -dn -o TYPE "$disk")" == disk ]] || { echo 'Expected a whole disk.' >&2; exit 1; }
lsblk -o NAME,SIZE,TYPE,FSTYPE,MOUNTPOINTS "$disk"
if lsblk -nr -o MOUNTPOINTS "$disk" | grep -q '[^[:space:]]'; then
  echo 'Refusing a disk with mounted filesystems.' >&2; exit 1
fi
read -r -p "Erase this disposable VM disk? Type the full path $disk: " answer
[[ "$answer" == "$disk" ]] || exit 1
parted --script "$disk" -- mklabel gpt mkpart ESP fat32 1MiB 1025MiB set 1 esp on mkpart primary ext4 1025MiB 100%
udevadm settle
suffix=''
[[ "$disk" =~ [0-9]$ ]] && suffix=p
mkfs.fat -F 32 -n EFI "${disk}${suffix}1"
mkfs.ext4 -L nixos "${disk}${suffix}2"
mount "${disk}${suffix}2" /mnt
mkdir -p /mnt/boot
mount -o fmask=0077,dmask=0077 "${disk}${suffix}1" /mnt/boot
mkdir -p /mnt/etc/nixos/workstation
cp -R . /mnt/etc/nixos/workstation/
nixos-generate-config --root /mnt
cp /mnt/etc/nixos/hardware-configuration.nix /mnt/etc/nixos/workstation/hosts/workstation-test/hardware-configuration.nix
host_dir=/mnt/etc/nixos/workstation/hosts/workstation-test
if [[ -s /home/nixos/.ssh/authorized_keys ]]; then
  cp /home/nixos/.ssh/authorized_keys "$host_dir/authorized-keys.pub"
  printf '%s\n' \
    '{ lib, ... }: {' \
    '  workstation.authorizedKeys = lib.filter (line: line != "" && !(lib.hasPrefix "#" line))' \
    '    (lib.splitString "\n" (builtins.readFile ./authorized-keys.pub));' \
    '}' > "$host_dir/installation.nix"
fi
# Root stays locked; set the normal user's local/sudo password out of band.
nixos-install --no-root-passwd --flake path:/mnt/etc/nixos/workstation#workstation-test
user_name=$(nix --extra-experimental-features 'nix-command flakes' eval --raw \
  path:/mnt/etc/nixos/workstation#nixosConfigurations.workstation-test.config.workstation.userName)
if [[ ${NIXOS_UNATTENDED_INSTALL:-no} == yes ]]; then
  echo 'System installed; the unattended worker will set the selected password and power off.'
else
  printf 'Installed. Before reboot, run in the live console:\n  sudo nixos-enter --root /mnt -c "passwd %s"\n' "$user_name"
  echo 'Then shut down, disconnect the ISO, and boot the virtual hard disk.'
fi
