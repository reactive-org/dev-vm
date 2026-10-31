#!/usr/bin/env bash

set -euo pipefail

workstation_user=""
display_mode=""
layout_mode="keep"
layout_file=""
share_enabled="no"
payload_dir=""

while [[ $# -gt 0 ]]; do
  case "$1" in
    --user) workstation_user="$2"; shift 2 ;;
    --display-mode) display_mode="$2"; shift 2 ;;
    --layout-mode) layout_mode="$2"; shift 2 ;;
    --layout-file) layout_file="$2"; shift 2 ;;
    --share) share_enabled="$2"; shift 2 ;;
    --payload) payload_dir="$2"; shift 2 ;;
    *) printf 'Unknown option: %s\n' "$1" >&2; exit 2 ;;
  esac
done

[[ $EUID -eq 0 ]] || { printf 'Run configure.sh as root.\n' >&2; exit 1; }
[[ "$workstation_user" =~ ^[a-z_][a-z0-9_-]{0,31}$ ]] || {
  printf 'Invalid workstation user.\n' >&2
  exit 1
}
[[ "$display_mode" =~ ^[1-9][0-9]{2,4}x[1-9][0-9]{2,4}@[1-9][0-9]*(\.[0-9]+)?$ ]] || {
  printf 'Invalid display mode.\n' >&2
  exit 1
}
[[ "$share_enabled" == yes || "$share_enabled" == no ]] || {
  printf 'Share must be yes or no.\n' >&2
  exit 1
}
[[ "$layout_mode" == keep || "$layout_mode" == install || "$layout_mode" == remove ]] || {
  printf 'Layout mode must be keep, install, or remove.\n' >&2
  exit 1
}
if [[ "$layout_mode" == install && ! -f "$layout_file" ]]; then
  printf 'The requested app layout file is missing.\n' >&2
  exit 1
fi
[[ -d "$payload_dir" ]] || { printf 'Payload directory is missing.\n' >&2; exit 1; }

workstation_home=$(getent passwd "$workstation_user" | cut -d: -f6)
workstation_group=$(id -gn "$workstation_user")
workstation_uid=$(id -u "$workstation_user")
[[ -n "$workstation_home" && -d "$workstation_home" ]] || {
  printf 'Unable to resolve the workstation home.\n' >&2
  exit 1
}

install -d -m 0755 /etc/ssh/sshd_config.d
cat > /etc/ssh/sshd_config.d/99-dev-vm.conf <<'EOF'
PasswordAuthentication no
KbdInteractiveAuthentication no
PermitRootLogin no
EOF
systemctl restart sshd.service

# The controller runs `omarchy update -y` first, so repository databases and
# the base system are current through Omarchy's supported migration path.
pacman -S --needed --noconfirm \
  base-devel dkms fuse2 linux-omarchy-headers mesa-utils

if [[ ! -x /usr/bin/prltoolsd ]]; then
  tools_device=$(blkid -L 'Parallels Tools' || true)
  [[ -n "$tools_device" ]] || {
    printf 'The attached Parallels Tools media was not found.\n' >&2
    exit 1
  }
  tools_mount=/mnt/parallels-tools
  install -d -m 0755 "$tools_mount"
  mountpoint -q "$tools_mount" || mount -o ro "$tools_device" "$tools_mount"
  [[ -f "$tools_mount/install" ]] || {
    printf 'The Parallels Tools installer is missing.\n' >&2
    exit 1
  }
  "$tools_mount/install" --install-unattended --verbose
fi

[[ -x /usr/bin/prltoolsd ]] || {
  printf 'Parallels Tools did not install; inspect /var/log/parallels-tools-install.log.\n' >&2
  exit 1
}
systemctl enable prltoolsd.service

# These are Omarchy repository packages. Omarchy continues to own their updates.
pacman -S --needed --noconfirm claude-desktop 1password 1password-cli
install -d -m 0755 /usr/share/chromium/extensions
cat > /usr/share/chromium/extensions/aeblfdkhhhdcdjpifhhbdiojplfjncoa.json <<'EOF'
{ "external_update_url": "https://clients2.google.com/service/update2/crx" }
EOF
chmod 0644 /usr/share/chromium/extensions/aeblfdkhhhdcdjpifhhbdiojplfjncoa.json

install -d -o "$workstation_user" -g "$workstation_group" -m 0755 \
  "$workstation_home/.config/hypr" \
  "$workstation_home/.config/systemd/user/app-prlcc@autostart.service.d" \
  "$workstation_home/.config/systemd/user/wayland-wm@hyprland.desktop.service.d" \
  "$workstation_home/.config/systemd/user/graphical-session.target.wants" \
  "$workstation_home/.local/bin" \
  "$workstation_home/.local/state/dev-vm"

sed "s/__DISPLAY_MODE__/$display_mode/g" \
  "$payload_dir/monitors.lua" > "$workstation_home/.config/hypr/monitors.lua"
install -o "$workstation_user" -g "$workstation_group" -m 0644 \
  "$payload_dir/workstation.lua" "$workstation_home/.config/hypr/workstation.lua"

hyprland_config="$workstation_home/.config/hypr/hyprland.lua"
if [[ -f "$hyprland_config" ]] && ! grep -Fq 'require("hypr.workstation")' "$hyprland_config"; then
  printf '\n-- Parallels workstation overrides.\nrequire("hypr.workstation")\n' >> "$hyprland_config"
fi

managed_layout="$workstation_home/.config/hypr/dev-vm-layout.lua"
case "$layout_mode" in
  install)
    install -o "$workstation_user" -g "$workstation_group" -m 0644 \
      "$layout_file" "$managed_layout"
    if [[ -f "$hyprland_config" ]] && ! grep -Fq 'require("hypr.dev-vm-layout")' "$hyprland_config"; then
      printf '\n-- Optional per-VM app layout.\nrequire("hypr.dev-vm-layout")\n' >> "$hyprland_config"
    fi
    ;;
  remove)
    rm -f "$managed_layout"
    if [[ -f "$hyprland_config" ]]; then
      sed -i '/require("hypr\.dev-vm-layout")/d' "$hyprland_config"
    fi
    ;;
esac

# Remove the old globally managed browser launcher. App launch policy now lives
# exclusively in the optional per-VM layout.
rm -f \
  "$workstation_home/.local/bin/omarchy-work-browser" \
  "$workstation_home/.local/share/applications/omarchy-work-browser.desktop"

install -o "$workstation_user" -g "$workstation_group" -m 0755 \
  "$payload_dir/dev-vm-display-init" "$workstation_home/.local/bin/dev-vm-display-init"
install -o "$workstation_user" -g "$workstation_group" -m 0755 \
  "$payload_dir/dev-vm-session-check" "$workstation_home/.local/bin/dev-vm-session-check"

# Keep application UI compact while making Foot readable on the host's
# high-density displays. Omarchy updates shell/GTK/terminal text together, then
# Foot is deliberately raised from the resulting 12pt to 15pt.
runuser -u "$workstation_user" -- env \
  HOME="$workstation_home" \
  XDG_RUNTIME_DIR="/run/user/$workstation_uid" \
  DBUS_SESSION_BUS_ADDRESS="unix:path=/run/user/$workstation_uid/bus" \
  OMARCHY_PATH=/usr/share/omarchy \
  /usr/bin/omarchy display text size 16
sed -i -E 's/:size=[0-9.]+/:size=15/' "$workstation_home/.config/foot/foot.ini"

# The host owns idle blanking and session security. Disable Omarchy's idle
# screensaver and lock while preserving all other user shell customization.
shell_config="$workstation_home/.config/omarchy/shell.json"
shell_config_source="$shell_config"
if [[ ! -f "$shell_config_source" ]]; then
  shell_config_source=/usr/share/omarchy/config/omarchy/shell.json
fi
shell_config_tmp=$(mktemp)
jq '.idle = (.idle // {}) | .idle.screensaver = 0 | .idle.lock = 0' \
  "$shell_config_source" > "$shell_config_tmp"
install -d -o "$workstation_user" -g "$workstation_group" -m 0755 \
  "$workstation_home/.config/omarchy"
install -o "$workstation_user" -g "$workstation_group" -m 0644 \
  "$shell_config_tmp" "$shell_config"
rm -f "$shell_config_tmp"

# Omarchy separately locks before suspend. Mask that per user so a host sleep
# or VM suspend cannot leave a redundant guest lock screen behind.
runuser -u "$workstation_user" -- env \
  XDG_RUNTIME_DIR="/run/user/$workstation_uid" \
  DBUS_SESSION_BUS_ADDRESS="unix:path=/run/user/$workstation_uid/bus" \
  systemctl --user disable --now omarchy-sleep-lock.service || true

install -o "$workstation_user" -g "$workstation_group" -m 0644 \
  "$payload_dir/parallels-prlcc.conf" \
  "$workstation_home/.config/systemd/user/app-prlcc@autostart.service.d/10-dev-vm.conf"
install -o "$workstation_user" -g "$workstation_group" -m 0644 \
  "$payload_dir/omarchy-shell-software.conf" \
  "$workstation_home/.config/systemd/user/wayland-wm@hyprland.desktop.service.d/20-omarchy-vm-shell.conf"

# prlcp needs the vendor prlcc parent process to exchange clipboard data with
# the host. Remove the previous standalone service and any override that hid
# the vendor XDG autostart entry.
runuser -u "$workstation_user" -- env \
  XDG_RUNTIME_DIR="/run/user/$workstation_uid" \
  DBUS_SESSION_BUS_ADDRESS="unix:path=/run/user/$workstation_uid/bus" \
  systemctl --user disable --now parallels-prlcp.service || true
rm -f \
  "$workstation_home/.config/systemd/user/parallels-prlcp.service" \
  "$workstation_home/.config/systemd/user/graphical-session.target.wants/parallels-prlcp.service" \
  "$workstation_home/.config/autostart/prlcc.desktop"

chown -R "$workstation_user:$workstation_group" \
  "$workstation_home/.config/hypr" \
  "$workstation_home/.config/systemd" \
  "$workstation_home/.local/bin" \
  "$workstation_home/.local/state/dev-vm"

ln -sfn /dev/null \
  "$workstation_home/.config/systemd/user/omarchy-sleep-lock.service"
runuser -u "$workstation_user" -- env \
  XDG_RUNTIME_DIR="/run/user/$workstation_uid" \
  DBUS_SESSION_BUS_ADDRESS="unix:path=/run/user/$workstation_uid/bus" \
  systemctl --user daemon-reload || true

if [[ "$share_enabled" == yes ]]; then
  install -d -o "$workstation_user" -g "$workstation_group" -m 0755 /mnt/shared
  if grep -Eq '^#?[[:space:]]*user_allow_other' /etc/fuse.conf; then
    sed -i 's/^#\?[[:space:]]*user_allow_other/user_allow_other/' /etc/fuse.conf
  else
    printf 'user_allow_other\n' >> /etc/fuse.conf
  fi
  sed \
    -e "s/__USER__/$workstation_user/g" \
    -e "s/__GROUP__/$workstation_group/g" \
    "$payload_dir/parallels-shared-folder.service" > \
    /etc/systemd/system/dev-vm-parallels-shared-folder.service
  chmod 0644 /etc/systemd/system/dev-vm-parallels-shared-folder.service
  systemctl enable dev-vm-parallels-shared-folder.service
fi

systemctl daemon-reload
if loginctl show-user "$workstation_user" >/dev/null 2>&1; then
  runuser -u "$workstation_user" -- env XDG_RUNTIME_DIR="/run/user/$workstation_uid" \
    systemctl --user daemon-reload || true
fi

rm -rf "$payload_dir"
printf 'Omarchy guest configuration is ready.\n'
