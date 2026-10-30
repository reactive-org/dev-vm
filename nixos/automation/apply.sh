#!/usr/bin/env bash
# Root worker launched by the existing Parallels guest administration channel.
set -euo pipefail
export PATH=/run/wrappers/bin:/run/current-system/sw/bin
cd /root
incoming=${1:?Expected private staging directory}
[[ $incoming =~ ^/tmp/nixos-deploy-[a-f0-9]{32}$ ]] || exit 1
[[ $EUID == 0 && $(uname -m) == aarch64 && $(systemd-detect-virt) == parallels ]] || exit 1
# shellcheck disable=SC1091
source /etc/os-release
[[ $ID == nixos && -f /etc/nixos/workstation/flake.nix ]] || { echo 'Existing managed NixOS workstation required.' >&2; exit 1; }
umask 077
state=/var/lib/nixos-workstation
install -d -m 700 "$state" "$state/jobs" "$state/releases"
job_id=${incoming##*/nixos-deploy-}
job="$state/jobs/$job_id"
install -d -m 700 "$job"
if [[ ${2:-} != --worker ]]; then
  # Retrying after an uncertain hypervisor response must not queue the same
  # worker twice or overwrite an active job's staged source/status.
  if [[ -f $job/status ]]; then echo "$job_id"; exit; fi
  cp "$incoming/"{request.sh,source.tar,apply-worker.sh} "$job/"
  if [[ -d $incoming/default-local ]]; then cp -R "$incoming/default-local" "$job/default-local"; fi
  if [[ -d $incoming/local ]]; then cp -R "$incoming/local" "$job/local"; fi
  printf '%s\n' "$job_id" > "$state/latest-job"
  printf queued > "$job/status"
  systemd-run --quiet --no-block --collect --unit="workstation-apply-$job_id" \
    --property=Type=oneshot --property="StandardOutput=append:$job/log" \
    --property="StandardError=append:$job/log" \
    /run/current-system/sw/bin/bash "$job/apply-worker.sh" "$incoming" --worker
  echo "$job_id"
  exit
fi
# A retry must not run two switches concurrently or replace an existing release.
exec 9>/run/lock/nixos-workstation-apply.lock
flock -n 9 || { printf failed > "$job/status"; echo 'Another deployment is running.' >&2; exit 1; }
release="$state/releases/$job_id"
old_system=$(readlink -f /run/current-system)
old_source=$(readlink -f /etc/nixos/workstation)
source_changed=false
switch_started=false
session_unit=''
finish() {
  result=$?
  set +e
  if ((result != 0)); then
    rollback_ok=true
    if [[ $switch_started == true ]]; then
      echo 'Restoring the previous system generation after failed activation.' >&2
      nix-env --profile /nix/var/nix/profiles/system --set "$old_system" || rollback_ok=false
      "$old_system/bin/switch-to-configuration" switch || rollback_ok=false
    fi
    if [[ $source_changed == true ]]; then
      ln -s "$old_source" "/etc/nixos/.workstation-rollback-$job_id" || rollback_ok=false
      mv -Tf "/etc/nixos/.workstation-rollback-$job_id" /etc/nixos/workstation || rollback_ok=false
    fi
    if [[ $rollback_ok != true ]]; then echo 'Automatic recovery did not complete; use the console and previous boot generation.' >&2; fi
    printf failed > "$job/status"
  fi
  if [[ -n $session_unit ]]; then
    systemctl stop "$session_unit" || echo 'Could not stop the temporary deployment login session.' >&2
  fi
  return "$result"
}
trap finish EXIT
# shellcheck disable=SC1091
source "$job/request.sh"
[[ $FLAKE_HOST =~ ^[A-Za-z0-9_-]+$ && $GUEST_USER =~ ^[a-z_][a-z0-9_-]*$ ]] || exit 1
[[ $LOCAL_ACTION == preserve || $LOCAL_ACTION == replace ]] || exit 1
[[ $APPLY_ACTION == build || $APPLY_ACTION == switch ]] || exit 1
# The staging SSH session can end before activation reloads the user's units.
# Keep a real PAM session alive in the guest, including after controller loss,
# without enabling lingering or changing authentication/sudo policy.
session_unit="workstation-apply-session-$job_id.service"
systemd-run --quiet --collect --unit="${session_unit%.service}" \
  --property="User=$GUEST_USER" --property=PAMName=login --property=Type=exec \
  /run/current-system/sw/bin/sleep infinity
systemctl is-active --quiet "user@$(id -u "$GUEST_USER").service"
printf staging > "$job/status"
[[ ! -e $release ]] || { echo 'Release already exists.' >&2; exit 1; }
install -d -m 700 "$release/source"
cp -a /etc/nixos/workstation/. "$release/source/"
printf '%s  %s\n' "$SOURCE_SHA256" "$job/source.tar" | sha256sum --check --status
# The controller excludes instance files. Refuse an archive that violates that
# boundary even if a different caller produced it.
if tar -tf "$job/source.tar" | grep -E '(^/|(^|/)\.\.(/|$)|^hosts/[^/]+/(hardware-configuration\.nix|installation\.nix|integration\.nix|identity\.nix|authorized-keys\.pub)$)' >/dev/null; then
  echo 'Source archive attempts to replace instance data.' >&2; exit 1
fi
tar -xf "$job/source.tar" -C "$release/source" --no-same-owner
host_dir="$release/source/hosts/$FLAKE_HOST"
[[ -f $host_dir/hardware-configuration.nix && -f $host_dir/installation.nix ]] || exit 1
if [[ ! -f $host_dir/integration.nix ]]; then printf '{ ... }: {}\n' > "$host_dir/integration.nix"; fi
if [[ ! -d $release/source/local ]]; then cp -R "$job/default-local" "$release/source/local"; fi
if [[ ! -f $host_dir/identity.nix ]]; then
  current_hostname=$(hostname)
  [[ $current_hostname =~ ^[a-zA-Z0-9][a-zA-Z0-9-]{0,62}$ ]] || exit 1
  cat > "$host_dir/identity.nix" <<NIX
{ lib, ... }: {
  workstation.userName = lib.mkForce "$GUEST_USER";
  networking.hostName = lib.mkForce "$current_hostname";
}
NIX
fi
if [[ $LOCAL_ACTION == replace ]]; then
  [[ -d $job/local ]] || exit 1
  rm -rf -- "$release/source/local"
  cp -R "$job/local" "$release/source/local"
fi
# Preserve all existing pinned remote inputs; only resolve new local input
# dependencies when the operator explicitly supplied new local source.
if [[ $LOCAL_ACTION == replace ]]; then
  (cd "$release/source"; nix flake lock)
fi
flake="path:$release/source#$FLAKE_HOST"
attributes="path:$release/source#nixosConfigurations.$FLAKE_HOST.config"
printf building > "$job/status"
[[ $(nix eval --no-update-lock-file --raw "$attributes.workstation.userName") == "$GUEST_USER" ]] || { echo 'Refusing an implicit workstation-account change.' >&2; exit 1; }
[[ $(nix eval --no-update-lock-file --json "$attributes.security.sudo.wheelNeedsPassword") == true ]] || { echo 'Password-protected sudo is required.' >&2; exit 1; }
nix flake check --no-update-lock-file "path:$release/source"
nixos-rebuild build --flake "$flake" --no-update-lock-file
if [[ $APPLY_ACTION == build ]]; then
  printf success > "$job/status"
  echo 'Build-only validation passed; running system and source pointer are unchanged.'
  exit
fi
printf switching > "$job/status"
switch_started=true
nixos-rebuild switch --flake "$flake" --no-update-lock-file
for unit in sshd prltoolsd greetd; do systemctl is-active --quiet "$unit"; done
[[ $(nix eval --no-update-lock-file --json "$attributes.security.sudo.wheelNeedsPassword") == true ]]
# Publish source only after a successful switch. Preserve the old unmanaged
# directory once; later applies replace this symlink atomically.
if [[ ! -L /etc/nixos/workstation ]]; then
  mv /etc/nixos/workstation "$state/pre-managed-source-$job_id"
  old_source="$state/pre-managed-source-$job_id"
  source_changed=true
fi
printf '%s\n' "$old_source" > "$job/previous-source"
ln -s "$release/source" "/etc/nixos/.workstation-$job_id"
source_changed=true
mv -Tf "/etc/nixos/.workstation-$job_id" /etc/nixos/workstation
printf '%s\n' "$FLAKE_HOST" > "$state/flake-host"
printf '%s\n' "$GUEST_USER" > "$state/user-name"
printf '%s\n' "$old_system" > "$job/previous-system"
printf success > "$job/status"
echo 'Deployment successful. Password-protected sudo remains enabled.'
