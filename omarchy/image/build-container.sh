#!/bin/bash
set -euo pipefail
umask 022

mode=${1:?check or build}
size_gib=${2:?virtual disk size}
[[ $mode == check || $mode == build ]]
[[ $(uname -m) == aarch64 ]]
[[ -d /input-profile && -d /workspace/guest && -d /downloads && -d /output ]]
available=$(df --output=avail -B1 /work | tail -1 | tr -d ' ')
((available >= 3 * 1024 * 1024 * 1024)) || {
  printf 'Docker needs at least 3 GiB free for source/package work; no other data is pruned.\n' >&2
  exit 1
}

cp -a /input-profile /profile
lock=/profile/inputs.lock.json
field() { jq -er ".$1" "$lock"; }

mkdir -p /work/sources /work/recipes /work/package-build /output/packages
tar -xzf "/downloads/omarchy-$(field omarchy_commit).tar.gz" --strip-components=1 -C /work/sources
tar -xzf "/downloads/omarchy-pkgs-$(field recipes_commit).tar.gz" --strip-components=1 -C /work/recipes
python3 - <<'PY'
import sys
sys.path.insert(0, '/profile')
from compatibility import normalize_source_permissions
for root in ('/work/sources', '/work/recipes'):
    normalize_source_permissions(root)
PY
python3 /profile/compatibility.py patch-source /work/sources /profile /profile/source-compatibility.json
cp /profile/source-compatibility.json /output/source-compatibility.json

pacman-key --populate omarchy
sed -i '/^\[core\]/i [omarchy]\nServer = https://pkgs.omarchy.org/edge/$arch\n' /etc/pacman.conf
pacman -Syu --needed --noconfirm imagemagick
mkdir -p /output/repositories
cp /var/lib/pacman/sync/*.db /output/repositories/

useradd --create-home builder
chown -R builder:builder /work/sources /work/package-build

build_package() {
  local name=$1 recipe=$2
  cp -a "$recipe" "/work/package-build/$name"
  chown -R builder:builder "/work/package-build/$name"
  (
    cd "/work/package-build/$name"
    runuser -u builder -- env OMARCHY_SRC=/work/sources PKGEXT=.pkg.tar.zst \
      makepkg --nodeps --force --noconfirm
    local packages=(./*.pkg.tar.zst)
    ((${#packages[@]} == 1))
    install -m 0644 "${packages[0]}" /output/packages/
  )
}

for package in omarchy-settings-dev omarchy-dev; do
  recipe=/work/recipes/pkgbuilds/$package
  grep -qx "pkgver=$(field omarchy_version)" "$recipe/PKGBUILD"
  grep -qx "_commit=$(field omarchy_commit)" "$recipe/PKGBUILD"
  grep -qx 'pkgrel=1' "$recipe/PKGBUILD"
  sed -i 's/^pkgrel=1$/pkgrel=1.1/' "$recipe/PKGBUILD"
  build_package "$package" "$recipe"
done
build_package try-omarchy /workspace/guest/package/try-omarchy
build_package dev-workstation-preferences /profile/preferences

python3 /profile/check-provisioning.py /work/sources /output/provisioning-check.json

for package in /output/packages/*.pkg.tar.zst; do
  bsdtar -xOf "$package" .PKGINFO
done >/output/local-package-metadata.txt
mkdir -p /work/local-repository /work/resolution/var/lib/pacman
cp /output/packages/*.pkg.tar.zst /work/local-repository/
repo-add /work/local-repository/dev-workstation-image.db.tar.gz /work/local-repository/*.pkg.tar.zst
sed -i '/^\[omarchy\]/i [dev-workstation-image]\nServer = file:///work/local-repository\n' /etc/pacman.conf
pacman --root /work/resolution --dbpath /work/resolution/var/lib/pacman \
  --gpgdir /etc/pacman.d/gnupg -Sy --noconfirm
python3 - <<'PY'
import json, re, subprocess, sys
from pathlib import Path
sys.path.insert(0, '/profile')
from compatibility import check_package_set, package_list

metadata = Path('/output/local-package-metadata.txt').read_text().splitlines()
local = set()
targets = set(package_list('/profile/base.packages'))
for line in metadata:
    key, _, value = line.partition(' = ')
    if key == 'pkgname':
        local.add(value)
    if key == 'optdepend':
        targets.add(value.split(': ', 1)[0])
targets.update(local)
try:
    result = subprocess.run(['pacman', '--root', '/work/resolution', '--dbpath',
                            '/work/resolution/var/lib/pacman', '--gpgdir', '/etc/pacman.d/gnupg',
                            '-Sp', '--print-format', '%n %v', *sorted(targets)],
                            check=True, capture_output=True, text=True)
except subprocess.CalledProcessError as error:
    raise SystemExit('Dependency resolution failed: ' + error.stderr.strip())
Path('/output/resolved-repository-packages.txt').write_text(result.stdout)
installed = {line.split()[0] for line in result.stdout.splitlines()}
check_package_set(installed, package_list('/profile/base.packages') + sorted(local),
                  package_list('/profile/excluded.packages'))
Path('/output/package-resolution.json').write_text(json.dumps({
    'format': 1, 'package_resolution': 'passed', 'local_packages': sorted(local),
    'resolved_packages': len(installed), 'owner_first_boot': 'not-tested',
    'hardware_rendering': 'not-tested', 'manager_admitted': False,
}, indent=2) + '\n')
PY

if [[ $mode == check ]]; then
  printf 'Compatibility package build, source checks and dependency resolution passed.\n'
  exit 0
fi

mkdir -p /packages
cp /output/packages/*.pkg.tar.zst /packages/
integration=(/packages/try-omarchy-*.pkg.tar.zst)
preferences=(/packages/dev-workstation-preferences-*.pkg.tar.zst)
((${#integration[@]} == 1 && ${#preferences[@]} == 1))
bash /workspace/guest/factory/build-image.sh \
  --output /output --work /factory-work --size-gib "$size_gib" \
  --package "${integration[0]}" --package "${preferences[0]}"
