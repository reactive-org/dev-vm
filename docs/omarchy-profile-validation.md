# Developer, web and Python live acceptance — 1 November 2026

All three profiles passed installation and identical zero-change reapplication
on six fresh disposable guests: one official and one lean guest per profile.
Selected runtimes, tool execution, restart persistence and hardware rendering
passed on the tested working tree. All six guests are gracefully stopped and retained for inspection;
temporary sudo grants are inactive and no guest runtime processes or open
disk/firmware handles remain.

## Tested identities and method

| Component | Tested identity |
| --- | --- |
| Manager | Existing Omarchy VM Manager app/CLI `0.9.3 (16)`, command protocol 1 |
| Runtime lock SHA-256 | `37aeca15303be1d491b9ed39109e4d0fc273093fe88dc1ac9f0b56fa05822cfb` |
| Official factory manifest | `1c202c4d9c4087b87d40138d812835a765ff736ff7cf1b9dc233b4fa8945a8cf` |
| Official factory raw disk | `f587d246981b14f1b0537d75ac1be03219368ac78aaefdb98b8e75a8f9a890c3` |
| Lean factory manifest | `6b49ae727ec1865e15c90bc990bb13d46b2747012d7ac5f4ceb93b2fe245e5bf` |
| Lean factory raw disk | `7816326733d14d5367df810c684d1c540794240ff39d1086439a1c319c443494` |
| Lean compressed disk | `cee4ef58f455219afb9a2ca64a072604515733a8f8fcb964779abdabdee25a99` |
| Lean artifact | `.artifacts/omarchy-image/af93b5f10d206637-7816326733d14d53` |
| Official Omarchy after native update | `omarchy-dev 4.0.0.r7525.gae680f1-1`, integration `0.1.0-43` |
| Lean Omarchy | `omarchy-dev 4.0.0.r7481.ge4fffc6-1.1`, integration `0.1.0-43.1` |
| Common graphics packages | Hyprland `0.57.0-2`, Quickshell `0.3.2.r7.g2b4501a-5`, Mesa `1:26.2.6-1` |

Each guest was explicitly created through the manager with its chosen factory,
4 CPUs, 4 GiB RAM, a 64 GiB disk, NAT, native clipboard integration, saved owner
defaults and manager-owned pinned SSH. Existing UUIDs were excluded by an
explicit disposable allowlist. Owner setup and authenticated SSH completed
without an interactive owner wizard. The operator entered passwords only into
native guest authorization/update terminals; installation was operator-authorized,
not an unattended sudo bypass.

The existing manager app signature and executable hashes were verified; the
executables remained unchanged through the run. Every lean artifact checksum
passed independently. The official identity above is the manager's verified
factory identity: a separate host-side cache scan was denied by macOS Downloads
privacy controls. No additional macOS permission was granted, and no host
software was installed or built. The manager retained factory admission,
cloning, lifecycle, SSH and integration ownership throughout.

Profiles were resolved through the shipped resolver and applied with normal
`site.yml`, its exact resolved tags/options and a private temporary inventory
derived from the manager's pinned SSH configuration. Each case ran check mode,
normal application and the identical normal application again. Package,
configuration, firewall and Docker activation snapshots established that check
mode and reapplication preserved persistent state. The supported Python-profile
launcher also passed a live `--check --yes` run on lean with no sudo grant.

## Installation and reapplication

Counts below are changed Ansible tasks for the successful application. They are
not package counts. Each successful apply and reapply had zero unreachable and
failed tasks; every second normal application returned `changed=0`.

| Factory | Profile | Successful apply | Identical reapply | Tool execution after restart | Hardware rendering after restart |
| --- | --- | --- | --- | --- | --- |
| Official | `developer` | `changed=3`, after native update/retry | `changed=0` | Passed | Passed |
| Lean | `developer` | `changed=4` | `changed=0` | Passed | Passed |
| Official | `web` | `changed=6`, after ShellCheck provider fix | `changed=0` | Passed | Passed |
| Lean | `web` | `changed=9` | `changed=0` | Passed | Passed |
| Official | `python` | `changed=7` | `changed=0` | Passed | Passed |
| Lean | `python` | `changed=7` | `changed=0` | Passed | Passed |

Common tools were exercised through version/execution checks for ripgrep, fd,
fzf, jq, tree, Git, LFS, delta, lazygit, Neovim, curl, HTTPie and OpenSSL. Neovim
ran headlessly with user configuration disabled for the probe; the feature did
not replace settings, install extensions, set Git identity or install hooks.

Both web guests passed Node ARM64 execution and standard-library checks, npm,
pnpm, PostgreSQL/SQLite client checks and quality-tool execution. Selected Node
was `26.13.0`, pnpm `12.16.1`, PostgreSQL client `18.6`, and ShellCheck `0.11.0`.
Docker reported native ARM64 and passed `hello-world`, container DNS, Compose
execution and a Buildx build/load/run that asserted native guest architecture.
The isolated Compose projects, test containers and built test images were removed.
These functional container tests ran before grant revocation and restart;
package/activation persistence was checked separately after restart. Both web
guests reported `docker.socket` enabled and active after a fresh boot, with
`docker.service` disabled/inactive until a client needs it.

Both Python guests passed execution of the selected mise Python `3.15.2`, uv
`0.13.6`, SSL/SQLite/compression/ctypes imports, Python virtual-environment creation
and execution, uv virtual-environment creation, native C compilation/execution,
CMake, Ninja, GDB and pkg-config checks. System `/usr/bin/python3` remained
independent. ShellCheck's installed executable was inspected as a native ARM64
ELF, in addition to executing it. Quality checks did not install project hooks.

The final selected-runtime probes explicitly used `mise exec`; ordinary
noninteractive SSH resolves plain `python` to system Python `3.14.8`. Separate
interactive Bash probes proved that normal developer shells select the mise
Python and Node installations. Initial plain-SSH Python probes were insufficient
to establish selected-runtime acceptance and were replaced by these checks.
No repository-owned PATH or shell controller was added.

## Hardware and persistence

All six guests passed the repository workstation check after a manager-owned
restart, including `aarch64`, Foot configuration, native clipboard-channel
presence, host-owned idle policy, the suspend-lock mask and native Retina scale 2.
Changed boot IDs established actual restarts. Final system and user service
managers reported zero failed units.

The actual Hyprland compositor logs and temporarily instrumented native
Quickshell configuration reported hardware-backed VirGL on the Apple M5 Max.
The native shell used Qt QRhi/OpenGL; process environments contained no forced
software renderer. The native shell launcher was restored after diagnostics.
Neither `llvmpipe`, `softpipe` nor another software renderer was accepted.

Normal Wayland Chromium WebGL2, using an isolated temporary profile and
`--disable-software-rasterizer`, reported ANGLE/Mesa/VirGL on both web guests and
all official guests. Chromium was not added merely to test lean developer or
Python profiles, which do not select a browser. Temporary browser resources
were removed; a diagnostic cleanup race was corrected to terminate its complete
isolated process group before deleting its profile.

Native Mac window zoom was exercised on official developer, lean developer and
official web. Guest resolution changed from `4960×2790` to `6720×3656` while
Retina scale stayed at 2; the windows were restored. Native UI automation
repeatedly stalled, including despite its requested timeout. The remaining
resize cases (lean web, official Python and lean Python) were subsequently
skipped at the user's request on 1 November 2026. Their renderer and Retina
checks still passed through native guest diagnostics. No monitor/display
controller or software-rendering override was installed.

Installed package lists persisted on all six guests. Captured configuration
bytes also persisted except on official web, where the native shell materialized
the previously absent `bar.layout.tray` as `[]`. Reconstructing the original
post-apply file from the repository's pre-idle backup reproduced its exact
recorded SHA-256. Removing only that new empty array from the observed JSON
reproduced all original setting values, proving that no prior preference was
lost. The native addition was retained rather than overwritten.

## Issues found and fixed

1. **Unavailable ARM64 ShellCheck package.** Official web preflight stopped with
   `changed=0` because `shellcheck` was absent from its configured ARM64 package
   repositories. The quality baseline now selects ShellCheck through its native
   mise registry short name, while yamllint and pre-commit remain guest packages.
   Real installation and ARM64 execution passed on both factories. Fixtures now
   model the missing package and explicitly cover this provider choice.
2. **Stale official-factory package metadata.** The first developer application
   installed two feature groups before a `git-lfs` archive download returned 404.
   Omarchy's native update completed, then profile installation and reapplication
   passed. Official web/Python were natively updated before their successful
   applications; lean used the selected factory directly. The feature helper now
   reports an actionable native-update hint for archive 404s, without refreshing
   databases, performing a partial upgrade or replacing Omarchy's update path.
3. **Native authorization during updates.** The settings upgrade revoked the
   first temporary grant. Authorization was renewed through native guest prompts;
   expired prompts were reopened rather than bypassed or supplied a stored
   password. The guide now documents preparation and grant renewal.

Validation probes were also corrected for the empty `hyprctl configerrors -j`
representation `[""]`, the isolated Chromium cleanup race, and selected-runtime
execution described above. The compositor's GLES 3.2 context negotiation retry
to GLES 3.0 was followed by the verified hardware VirGL renderer; it was not
treated as a software-rendering result.

ShellCheck provider references: [mise registry entry](https://github.com/jdx/mise/blob/main/registry/shellcheck.toml)
and [upstream Linux ARM64 releases](https://github.com/koalaman/shellcheck/releases).

## Evidence, isolation and limits

Private manager replies, the disposable UUID allowlist, source hashes, native
update/probe logs, Ansible recaps, package/configuration snapshots and shutdown
proofs are retained under ignored `.artifacts/profile-validation/20261101/`.
Temporary connection inventories were removed after use. Generated identities,
account details, credentials and network addresses are not committed here.

Exactly six new allowlisted guests were added. All six are stopped and retained,
with inactive grants, no matching runtime processes and no open disk/firmware
handles. Trash deletion was not performed. Pre-existing configuration and the
captured stopped-root inode/size/modification-time inventories match baseline.
One pre-existing guest was running at baseline and later stopped in a separate
layout-validation run: its matching stop receipt is retained there, dated
18:49:59 AEDT. Consequently the global lifecycle comparison is not unchanged;
this profile matrix issued lifecycle/configuration commands only for its six
new allowlisted UUIDs.

Repository verification passed all **162 tests**, `make syntax-check`, the
documented Bash checks, Python compilation and `git diff --check`. These results
apply to the exact builds and selections above, not future moving selectors or
all catalogue alternatives.

Clipboard-channel presence does not establish bidirectional contents or focus
routing. At the user's request on 1 November 2026, the remaining resize cases,
clipboard round-trip checks and movement between physical displays were skipped;
they are not pending acceptance work for this run and are not claimed as passed.
Completed resize coverage remains recorded above. Sleep/wake, audio/camera,
crash recovery and authentication to external services were outside this run's
acceptance scope. No image metadata was relabelled as universally hardware/owner
validated.
