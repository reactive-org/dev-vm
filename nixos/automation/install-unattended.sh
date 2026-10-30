#!/usr/bin/env bash
set -euo pipefail
export PATH=/run/wrappers/bin:/run/current-system/sw/bin
media=/iso/workstation
die() { printf 'Installation refused: %s\n' "$*" >&2; exit 1; }
[[ $EUID == 0 && $(uname -m) == aarch64 && -d /iso ]] || die 'ARM64 NixOS live ISO required.'
[[ $(systemd-detect-virt) == parallels ]] || die 'Parallels VM required.'
# This manifest is generated shell code on the deliberately attached media.
# shellcheck disable=SC1091
source "$media/manifest.sh"
[[ $INSTALL_TOKEN =~ ^[a-f0-9]{32}$ ]] || die 'Invalid installation token.'
grep -Fqw -- "workstation.install=$INSTALL_TOKEN" /proc/cmdline || die 'Boot token does not match this media.'
[[ $GUEST_USER =~ ^[a-z_][a-z0-9_-]*$ && $GUEST_HOSTNAME =~ ^[a-z0-9][a-z0-9-]{0,62}$ ]] || die 'Invalid identity.'
# shellcheck disable=SC1091
source "$media/source/automation/disk-guard.sh"
workstation_blank_disk "$DISK" || die 'A blank, unmounted VM disk is required.'
password_hash=$(cat "$media/password.hash")
[[ $password_hash =~ ^\$2[aby]\$[0-9]{2}\$[./A-Za-z0-9]{53}$ ]] || die 'Invalid password hash.'
[[ ! -e /run/workstation-install-started ]] || die 'Installer already started in this boot.'
touch /run/workstation-install-started
umask 077
exec > >(tee /var/log/workstation-install.log /dev/tty1) 2>&1
echo 'Starting unattended workstation installation on the confirmed blank VM disk.'
# Start only the upstream live ISO's network daemon. Pulling in its full
# multi-user target can also start the graphical/manual installer.
if [[ $(systemctl show -p LoadState --value systemd-resolved.service) == loaded ]]; then
  systemctl start systemd-resolved.service
fi
network_started=false
for unit in NetworkManager.service dhcpcd.service systemd-networkd.service; do
  if [[ $(systemctl show -p LoadState --value "$unit") == loaded ]]; then
    systemctl start "$unit"
    network_started=true
    break
  fi
done
[[ $network_started == true ]] || die 'No live ISO network service found.'
network_ready=false
for _attempt in {1..120}; do
  if getent ahosts cache.nixos.org >/dev/null && getent ahosts dl.google.com >/dev/null; then
    network_ready=true
    break
  fi
  sleep 2
done
[[ $network_ready == true ]] || die 'DNS for the Nix cache and Chrome vendor did not become ready.'
work=$(mktemp -d /tmp/workstation-install.XXXXXXXX)
cp -R "$media/source/." "$work/"
host_dir="$work/hosts/workstation-test"
cp "$media/authorized-key.pub" "$host_dir/authorized-keys.pub"
cat > "$host_dir/identity.nix" <<NIX
{ lib, ... }: {
  workstation.userName = lib.mkForce "$GUEST_USER";
  networking.hostName = lib.mkForce "$GUEST_HOSTNAME";
}
NIX
cat > "$host_dir/installation.nix" <<'NIX'
{ lib, ... }: {
  workstation.authorizedKeys = lib.filter (line: line != "")
    (lib.splitString "\n" (builtins.readFile ./authorized-keys.pub));
}
NIX
printf '{ ... }: { workstation.sharedFolder.enable = %s; }\n' "$SHARED_FOLDER" > "$host_dir/integration.nix"
if [[ -d $media/local ]]; then
  rm -r "$work/local"
  cp -R "$media/local" "$work/local"
  (cd "$work"; nix --extra-experimental-features 'nix-command flakes' flake lock)
fi
# Reuse the manually validated installer and its mounted-disk guard. The
# controller's confirmed VM proposal and the checks above authorize this path.
printf '%s\n' "$DISK" | NIXOS_UNATTENDED_INSTALL=yes bash "$work/install.sh" "$DISK"
# Neither the password nor its hash enters a Nix expression or store path.
printf '%s:%s\n' "$GUEST_USER" "$password_hash" |
  nixos-enter --root /mnt -c 'chpasswd -e'
unset password_hash
nixos-enter --root /mnt -c 'usermod -L root'
install -d -m 700 /mnt/var/lib/nixos-workstation
printf '%s\n' "$INSTALL_TOKEN" > /mnt/var/lib/nixos-workstation/install-token
printf '%s\n' "$GUEST_USER" > /mnt/var/lib/nixos-workstation/user-name
echo 'Installation completed. Powering off so the controller can detach the ISO.'
sync
