# Disposable playbook acceptance — 1 November 2026

For fresh official-factory testing with manager 0.9.2, see the
[official acceptance record](omarchy-official-43-validation.md).

The latest lean rebuild is recorded in the [43.1 acceptance record](omarchy-lean-43-validation.md).

For the later manager 0.9.1 / integration 42.1 rebuild, see the
[lean factory acceptance record](omarchy-lean-42-validation.md). The manager
contract blocker described below is historical; the later run also found and
corrected factory permissions, desktop dependencies and first-login ordering.

The official-image acceptance checks passed on a new disposable ARM64 guest
through VM Manager 0.8.0, after correcting a mise idempotence bug. The lean image remains
blocked on a matching, reviewed manager owner-provisioning contract. No existing
guest was started or provisioned for these checks.

The disposable official guest was gracefully stopped through VM Manager after
acceptance. Its state is stopped, no runtime/helper processes or open guest-disk
handles remain, and its root is retained for inspection. All four pre-existing
profiles compare unchanged; their root-file inode, size and modification-time
inventories also match the baseline. No existing VM was started, restarted or
provisioned. Moving the stopped disposable root to Trash remains an optional
manager-owned cleanup action.

## Official factory

The factory disk SHA-256 is
`f587d246981b14f1b0537d75ac1be03219368ac78aaefdb98b8e75a8f9a890c3`.
The new guest uses 4 CPUs, 4 GiB RAM, a 64 GiB disk, NAT, saved Guest Defaults
and manager-owned, pinned SSH. Initial boot installed `try-omarchy 0.1.0-40`
but remained at `waiting-owner`; a manager-owned restart completed unattended
owner setup and authenticated SSH. This is an observed first-boot limitation;
its underlying cause has not been established.

| Check | Observed result |
| --- | --- |
| All six roles in check mode | Completed; temporary payload cleaned up |
| All six roles applied with the example selections | Passed, `changed=4`, `failed=0` |
| Workstation role reapplied | Passed, `changed=0`, `failed=0` |
| All roles reapplied after the mise fix | Passed, `changed=0`, `failed=0` |
| Each of the six feature tags run independently | Passed, each `changed=0`, `failed=0`; no other role executed |
| Hyprland | Hardware-backed VirGL on the Apple GPU |
| Quickshell, actual native shell configuration | Qt QRhi OpenGL with Mesa/VirGL on the Apple GPU |
| Normal Wayland Chromium, isolated temporary profile | WebGL2 through ANGLE/Mesa/VirGL; software rasterizer disabled |
| Foot, native display, clipboard channel, host idle policy, lock mask | Passed after workstation application |
| Docker ARM64 `hello-world` | Passed |
| Compose, Buildx and container DNS | Passed, including a native ARM64 image build and execution |
| Restart persistence | Passed: package and preference hashes unchanged, pinned SSH ready, graphics rechecked, Docker socket enabled/active |

The first complete application installed Firefox, selected Node and Python,
selected Claude/Codex/OpenCode, and installed the 1Password app and CLI. Docker
reused its existing packages, firewall rules and activation policy without
changes. Runtime execution and standard-library probes passed for Node
26.13.0 and Python 3.15.2. Version commands passed for Claude 2.1.316, Codex
0.166.0, OpenCode 2.2.5 and 1Password CLI 2.41.1. No agent or credential tool
was signed in, and no host credentials were copied.

The initial headless Chromium probe returned no WebGL context. The normal
Wayland window passed; the headless result is not treated as a desktop-rendering
failure. Quickshell diagnostics were enabled only for a temporary run of its
native configuration, then its normal launcher was restored with
`omarchy-restart-shell`. No permanent diagnostic settings were installed.

## Lean admission blocker

The built lean disk SHA-256 is
`5d8e93f8c02fea92d534fce2d31bccfe8587c5a52eab3ed5dfcb695bced72d18`.
The current manager owner contract has SHA-256
`d381667f407b5f82cfb9f9c391eccf2898ba8a064bc6b2f082e28f959e76aef8`.

| Program | Manager's accepted SHA-256 | Lean SHA-256 |
| --- | --- | --- |
| `/usr/bin/omarchy-provision-owner` | `2b99154b4f5fa9ddd08b3236043bfdb621d70d57aff03d665d163c874c68930a` | `b81202f7b6f58f4e670c8f3509e1eb952807b92ad24d0c0e87b75bd03004d0ca` |
| `/usr/share/omarchy/install/provisioning/setup-form.sh` | `188a2fe1284ef8a4579dca5be72a2fd83efb5063dc3c61a1442c7f88a5646812` | `b3ae7c22c8c8de91590d3a0e7d037b75734b7d886c8dceb012a3bbdf546045c5` |
| `/usr/share/omarchy/install/provisioning/luks-rekey.sh` | `29ce96e714ad76eda9c42f9d82b3f0e87e7a8f22e3edd17e6fa73074dc2e0189` | Same |

The lean artifact currently carries `try-omarchy 0.1.0-36.1`, derived from the
stock source. The manager injects its own pinned `0.1.0-40` integration package.
Its unattended adapter checks the installed owner programs before invoking
their functions. Preparing a bundle descriptor does not resolve this mismatch.
The new contract and adapter function compatibility need review together; do
not simply replace the accepted hashes or claim capabilities in metadata.

The operator chose to wait for the matching manager contract. No lean guest
has been created, no factory has been imported, and no manager verification has
been bypassed. Once the matching runtime is available, prepare/import a flat
bundle through the manager's documented tool and repeat the same live matrix
on a second new disposable UUID root.

## Idempotence correction

The first full reapplication completed with `changed=2`: languages and agents
were unnecessarily selected again. On the actual guest, mise 2026.10.17 returns
an array from `mise ls --json TOOL`, and its tool-filtered rows omit `tool` and
`name`. The helper incorrectly discarded those rows and treated installed,
configured tools as unconfigured. It now accepts unnamed rows from the filtered
query while retaining support for named rows and the mapping format. Regression
tests cover installed default runtimes, explicit Python selection and agents
using the observed metadata shape. Live check mode for languages and agents
then completed with `changed=0`, `failed=0`.

Normal full reapplication and all six independent tag runs subsequently passed
with zero changes and no failures. Independent snapshots confirmed identical
package lists, UFW rule hashes, Docker activation state and preference/config
file hashes before and after those seven runs. These checks used the documented
direct Ansible path with a private pinned-SSH inventory and one native grant;
the grant was revoked in cleanup. The first Docker functional attempt was
interrupted by the supported launcher's grant revocation; the grouped retry
passed ARM64 `hello-world`, Compose, container DNS, Buildx build/load and the
built image's execution. The uniquely named Compose project and test image
were removed afterward.

A subsequent manager-owned restart preserved the full installed package list
and all captured preference/config hashes. Hyprland, normal Wayland Chromium
and the native Quickshell configuration again reported hardware-backed VirGL;
no forced software renderer was present. Foot, the native Retina display state,
the clipboard channel, idle settings and lock mask passed again. The Docker
socket was enabled and active, the native sudo grant was inactive, and both
system and user service managers reported zero failed units. Clipboard contents,
focus routing, dynamic window resizing and authentication were not manually
exercised; the clipboard result establishes channel presence only.

## Evidence

Local run logs, the existing-guest baseline, an explicit disposable UUID
allowlist, renderer diagnostics and admission comparisons are under the ignored
`.artifacts/playbook-validation/2026-11-01/` directory. Private connection files
use temporary mode-0600 inventory and variables, and are removed after runs.
Generated guest identifiers and private manager metadata are not committed.

Repository verification: all 109 tests, `make syntax-check`, Python compilation,
the documented Bash syntax checks and `git diff --check` passed. These results supplement the live checks; they
do not establish acceptance for the blocked lean image.
