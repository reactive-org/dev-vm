#!/bin/bash
set -euo pipefail

check_root=${1:?isolated Btrfs snapshot root}
output=${2:?report directory}
arch-chroot "$check_root" useradd --create-home --uid 1000 --shell /bin/bash image-check
arch-chroot "$check_root" install -d -o image-check -g image-check -m 0700 /var/lib/image-check-runtime

if ! timeout 180 arch-chroot "$check_root" runuser -u image-check -- env \
  HOME=/home/image-check USER=image-check LOGNAME=image-check \
  XDG_RUNTIME_DIR=/var/lib/image-check-runtime LANG=C.UTF-8 LC_ALL=C.UTF-8 OMARCHY_SETUP_CONTEXT=provision-owner \
  OMARCHY_PATH=/usr/share/omarchy OMARCHY_INSTALL=/usr/share/omarchy/install \
  OMARCHY_USER_NAME='Image validation' OMARCHY_USER_EMAIL=image-check@example.invalid \
  OMARCHY_INSTALL_LOG_FILE=/tmp/image-user-check.log OMARCHY_LOG_TO_STDOUT=1 \
  /usr/bin/omarchy-provision-user --force --first-install >"$output/user-provisioning.log" 2>&1; then
  cat "$output/user-provisioning.log" >&2
  exit 1
fi

for attempt in 1 2; do
  arch-chroot "$check_root" runuser -u image-check -- env \
    HOME=/home/image-check USER=image-check XDG_RUNTIME_DIR=/var/lib/image-check-runtime LANG=C.UTF-8 LC_ALL=C.UTF-8 \
    /usr/lib/dev-workstation/first-login.sh >>"$output/user-provisioning.log" 2>&1
done
arch-chroot "$check_root" runuser -u image-check -- env HOME=/home/image-check LANG=C.UTF-8 LC_ALL=C.UTF-8 \
  /usr/bin/foot --check-config >>"$output/user-provisioning.log" 2>&1

# Check the native AUR tools as the owner without starting an update or build.
for program in yay makepkg gcc make fakeroot; do
  arch-chroot "$check_root" runuser -u image-check -- env HOME=/home/image-check LANG=C.UTF-8 LC_ALL=C.UTF-8 \
    "/usr/bin/$program" --version >>"$output/user-provisioning.log" 2>&1
done

arch-chroot "$check_root" runuser -u image-check -- env HOME=/home/image-check LANG=C.UTF-8 LC_ALL=C.UTF-8 \
  bash -euc '
    build_dir=$(mktemp -d)
    trap '\''rm -rf "$build_dir"'\'' EXIT
    printf "int main(void) { return 0; }\n" > "$build_dir/check.c"
    gcc "$build_dir/check.c" -o "$build_dir/check"
    "$build_dir/check"
  ' >>"$output/user-provisioning.log" 2>&1

python3 - "$check_root" "$output/user-provisioning-check.json" <<'PY'
import json, sys
from pathlib import Path
sys.path.insert(0, '/profile')
from compatibility import check_user_log
check_user_log((Path(sys.argv[2]).parent / 'user-provisioning.log').read_text())
root = Path(sys.argv[1]) / 'home/image-check'
if not (root / '.local/state/dev-workstation/image-preferences-v1').is_file():
    raise SystemExit('First-owner preferences were not completed')
if 'size=16' not in (root / '.config/foot/foot.ini').read_text():
    raise SystemExit('Foot preference was not applied')
idle = json.loads((root / '.config/omarchy/shell.json').read_text())['idle']
if idle['screensaver'] != 0 or idle['lock'] != 0:
    raise SystemExit('Host-owned idle preferences were not applied')
Path(sys.argv[2]).write_text(json.dumps({
    'format': 1, 'user_finalization': 'passed-in-isolated-chroot',
    'workstation_preferences': 'passed-in-isolated-chroot', 'foot_configuration': 'passed',
    'aur_build_tools': 'passed-in-isolated-chroot',
    'base_development_tools': 'passed-compile-in-isolated-chroot',
    'owner_account_wizard': 'not-tested', 'hardware_rendering': 'not-tested',
}, indent=2) + '\n')
PY
