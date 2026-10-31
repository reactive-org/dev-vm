#!/usr/bin/env bash

set -euo pipefail

failures=0

# A non-interactive SSH session does not inherit Hyprland's display variables.
# Import only the known graphical-session keys from the existing user manager.
if command -v systemctl >/dev/null && systemctl --user show-environment >/dev/null 2>&1; then
  while IFS='=' read -r name value; do
    case "$name" in
      DISPLAY|WAYLAND_DISPLAY|HYPRLAND_INSTANCE_SIGNATURE|XDG_CURRENT_DESKTOP|XDG_SESSION_TYPE|XDG_RUNTIME_DIR)
        export "$name=$value"
        ;;
    esac
  done < <(systemctl --user show-environment)
fi

pass() {
  printf 'PASS  %s\n' "$1"
}

fail() {
  printf 'FAIL  %s\n' "$1" >&2
  failures=$((failures + 1))
}

if [[ $(uname -m) == aarch64 ]]; then
  pass 'guest architecture is aarch64'
else
  fail "guest architecture is $(uname -m), expected aarch64"
fi

if command -v omarchy >/dev/null; then
  pass 'Omarchy command is available'
  omarchy-version 2>/dev/null || true
else
  fail 'Omarchy command is unavailable'
fi

renderer_output=""
if command -v glxinfo >/dev/null; then
  renderer_output=$(glxinfo -B 2>&1 || true)
elif command -v eglinfo >/dev/null; then
  renderer_output=$(eglinfo -B 2>&1 || true)
else
  hyprland_log=$(find "${XDG_RUNTIME_DIR:-/run/user/$(id -u)}/hypr" \
    -maxdepth 3 -type f -name hyprland.log -print -quit 2>/dev/null || true)
  if [[ -n "$hyprland_log" ]]; then
    renderer_output=$(grep -Ei 'Renderer:|llvmpipe|softpipe|software raster' \
      "$hyprland_log" | head -20 || true)
  fi
fi

if [[ -z "$renderer_output" ]]; then
  fail 'unable to inspect the graphical renderer with Omarchy-provided tools'
elif grep -Eiq 'llvmpipe|softpipe|software raster' <<< "$renderer_output"; then
  fail 'graphical session is using software rendering'
elif grep -Eiq 'renderer:.*virgl|OpenGL renderer.*virgl|ANGLE.*Apple' <<< "$renderer_output"; then
  pass 'graphical renderer is hardware-backed VirGL'
  grep -Ei 'renderer' <<< "$renderer_output" | head -5 || true
else
  fail 'graphical renderer did not report the required VirGL/Apple path'
  grep -Ei 'renderer|device|gpu|virgl|angle|metal' <<< "$renderer_output" | head -20 || true
fi

if [[ -e /dev/virtio-ports/dev.tryomarchy.clipboard ]]; then
  pass 'Try Omarchy clipboard channel is present'
else
  fail 'Try Omarchy clipboard channel is missing'
fi

if command -v hyprctl >/dev/null && hyprctl monitors -j >/dev/null 2>&1; then
  pass 'Hyprland monitor state is available'
  hyprctl monitors -j | jq -c '.[] | {name,width,height,scale,focused}'
else
  fail 'Hyprland monitor state is unavailable'
fi

shell_config="$HOME/.config/omarchy/shell.json"
if [[ -f "$shell_config" ]] && \
  [[ $(jq -r '.idle.screensaver // "missing"' "$shell_config") == 0 ]] && \
  [[ $(jq -r '.idle.lock // "missing"' "$shell_config") == 0 ]]; then
  pass 'guest idle screensaver and lock are disabled'
else
  fail 'guest idle screensaver and lock are not both disabled'
fi

if [[ $(systemctl --user is-enabled omarchy-sleep-lock.service 2>/dev/null || true) == masked ]]; then
  pass 'guest lock-before-suspend service is masked'
else
  fail 'guest lock-before-suspend service is not masked'
fi

if [[ -n ${TRY_OMARCHY_SHARED_FOLDER:-} ]]; then
  if [[ -d "$HOME/$TRY_OMARCHY_SHARED_FOLDER" ]]; then
    pass "shared Mac folder is mounted at ~/$TRY_OMARCHY_SHARED_FOLDER"
  else
    fail "expected shared Mac folder is missing: ~/$TRY_OMARCHY_SHARED_FOLDER"
  fi
fi

if (( failures > 0 )); then
  printf '\n%d workstation check(s) failed.\n' "$failures" >&2
  exit 1
fi

printf '\nTry Omarchy workstation checks passed.\n'
