#!/bin/bash
set -euo pipefail

[[ $EUID -ne 0 && $(uname -m) == aarch64 ]]
state=${XDG_STATE_HOME:-$HOME/.local/state}/dev-workstation
[[ ! -e $state/image-preferences-v1 ]] || exit 0
bash /usr/lib/dev-workstation/apply-workstation.sh --foot-font-size 16 --idle-mode host
bash /usr/lib/dev-workstation/repair-try-omarchy-black-screen.sh
editor_state=${XDG_STATE_HOME:-$HOME/.local/state}/omarchy/defaults/editor
if [[ ! -e $editor_state ]]; then
  install -d -m 0755 "$(dirname "$editor_state")"
  printf 'nano\n' >"$editor_state"
fi
install -d -m 0700 "$state"
touch "$state/image-preferences-v1"
