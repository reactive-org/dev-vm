#!/usr/bin/env bash
# Read-only preflight shared by the installer and its installed-disk refusal test.
workstation_blank_disk() {
  local disk=$1
  [[ $disk == /dev/sda && -b $disk ]] || { echo 'Expected /dev/sda.' >&2; return 1; }
  [[ $(lsblk -dn -o TYPE "$disk") == disk ]] || { echo 'Expected a whole disk.' >&2; return 1; }
  [[ $(lsblk -nr -o NAME "$disk" | wc -l) -eq 1 ]] || { echo 'Disk already has partitions.' >&2; return 1; }
  [[ -z $(wipefs --noheadings --no-act "$disk") ]] || { echo 'Disk already contains signatures.' >&2; return 1; }
  [[ -z $(lsblk -nr -o MOUNTPOINTS "$disk" | tr -d '[:space:]') ]] || { echo 'Disk is mounted.' >&2; return 1; }
}
