# Lean 42.1 rebuild and acceptance — 1 November 2026

For the matching 43.1 rebuild and completion-report fix validation, see the
[newer acceptance record](omarchy-lean-43-validation.md). This record describes
the retained 42.1 artifact and its observed blocker.

**Acceptance is blocked on VM Manager's completion-report timer.** The latest
factory boots unattended, completes native deferred hardware setup, applies
first-login preferences, authenticates over pinned SSH and renders through
hardware VirGL. After the host removes its completed setup manifest, the
manager-owned report timer repeatedly fails. No failed unit was masked and this
session made no manager code/app changes. See the [manager handoff](omarchy-manager-report-timer-handoff.md).

## Latest artifact

The artifact is `.artifacts/omarchy-image/d356175ff1e79499-5eef06671f7bbc0d`;
its sibling `.Manager.factory` directory is the normally imported flat bundle.
Use this identity when continuing the investigation; earlier trials are retained.

| Identity | Value |
| --- | --- |
| Installed manager | 0.9.1 (14), reviewed build following `4f09aad` |
| Integration source | `aab6bd82b279cc81c2627be73f7b206ae6dadfc0` |
| Integration package | `try-omarchy 0.1.0-42.1` |
| Preferences package | `dev-workstation-preferences 1-2` |
| Omarchy | `4.0.0.r7481.ge4fffc6-1.1` |
| Sealed package count | 552 |
| Compressed size | 1,700,513,392 bytes |
| Raw disk size | 21,474,836,480 bytes |
| Compressed SHA-256 | `c1df76a11e237e1a0ce0bebb5c12bfc96dc07aca1cb88128df230fe701b11037` |
| Raw disk SHA-256 | `5eef06671f7bbc0d354587e5096b6a43ff4d015258fcaf9d033eeffe2218f91c` |
| Factory manifest SHA-256 | `d7862e36446c8a251dd48aeb85ef5b8f8f4d9f07bf42ef07d711754dd92a0d5b` |
| Selected owner contract | `lean-e4fffc6`, SHA-256 `1347cb16b831eb2c3a67344a5bbb68c9da776a55221ecab5ba90ce385078d310` |

All 22 published checksums and the full decompressed disk digest were
independently verified. The installed manager's signature and all 43 runtime
inventory entries match its reviewed pins. The official contract is unchanged.
All five owner-program hashes and the preserved owner/SSH adapters match the
reviewed source. The unchanged adapter's contract/program checks also passed
inside a read-only copy of the image. These static checks are distinct from
the live observations below.

## Builder and playbook fixes

- Git archives carried 0664 files and 0775 directories, which recipes preserved.
  The first trial correctly failed the adapter's `program-parent` check.
  Exported sources now receive checkout modes before packaging, and installed
  owner files/contracts/adapters and parents receive ownership, mode and link
  audits. Program bytes and manager verification policy remain unchanged.
- The lean desktop omitted Herdr/Udiskie autostart, socat IPC, ImageMagick
  background inspection and inotify-tools watching. These five native helpers
  are now in the foundation; the workstation role repairs their absence on older
  guests through `omarchy-pkg-add`.
- The known Hyprland 0.57/VirGL alpha-format issue produced a black background.
  The user had also seen it with the official image. The native VirGL integration
  now includes the existing GPU-preserving quirk before the first compositor
  starts, guarded by the integration source hash. No software renderer is used.
- The first-login unit had an ordering cycle with the graphical target and native
  session. Preferences 1-2 explicitly follows both. A hash-guarded workstation
  drop-in repairs only the exact old repository unit and preserves custom overrides.
- Deferred hardware setup unconditionally enabled Bluetooth while BlueZ was
  deliberately absent. A sixth source-hash-checked optional-provisioning guard
  skips this leaf only when BlueZ is absent. Controlled tests preserve native
  enable/start behaviour when present. The remaining native queue is retained.

## Observed live results

Four new disposable guests were used, with explicit authorization for additional
trials after the initial failure. Every lifecycle operation used its recorded
UUID. All four are stopped and retained. Five original guest profiles and their
root-file inode/size/modification-time inventories match the initial baseline.
All eight guests existing before the last trial also match that phase's baseline.
No runtime/helper processes or open test-disk handles remain.

On the latest artifact:

| Check | Result |
| --- | --- |
| Unattended owner setup; no manual wizard | Passed |
| Saved username, full name, Git name/email, hostname suffix, timezone, keyboard/input selection | All redacted comparisons passed |
| Matching host completion identity and temporary seed removal | Passed |
| Authenticated managed SSH for the current VM/session | Passed |
| Deferred hardware queue and keyring initialization | Completed; queue empty, unit succeeded and disabled itself |
| Automatic first-login preferences | Completion marker present; Foot, idle policy and lock mask passed |
| Hyprland and actual native Quickshell configuration | Hardware VirGL; no forced software rendering |
| Optional browsers, Docker, mise, Node and credential apps before provisioning | Absent |
| Manager completion-report timer after seed cleanup | Failed repeatedly; blocker |
| Full feature/restart acceptance on this exact disk | Not continued after the manager blocker |

Earlier desktop-corrected trials passed all six feature groups with the same
example selections, an identical second application, every independent tag,
and full reapplication after restart (`changed=0`, no unreachable/failed tasks).
Package and preference hashes, owner completion/log metadata and SSH pins were
stable. Native SSH refresh reordered its firewall allow rule: matching the exact
pre-restart hash by permuting the same three rule blocks proved that rule content
was unchanged. The initial byte-for-byte firewall assertion was too strict; the
evidence retains that failure and its resolution.

Docker ARM64 execution, DNS, Compose and Buildx build/load/run passed on those
trials. Node/Python execution and Claude/Codex/OpenCode/1Password CLI version
checks passed without authentication. Normal Wayland Chromium WebGL2 reported
ANGLE/Mesa/VirGL with software rasterization disabled. The operator confirmed
the desktop-corrected factory displayed its wallpaper/UI without missing-command
notifications. These results are not substituted for full acceptance of the
latest disk while its manager timer remains failed.

## Verification and evidence

Commands included the documented `make prepare-source`, resolved-source
`make build-omarchy-image` with the exact integration commit and 20 GiB size,
flat-bundle preparation with `--owner-contract lean-e4fffc6`, installed-CLI
factory import/UUID-only lifecycle commands, and the normal `site.yml` playbook
through private manager-pinned SSH inventory. Native temporary sudo grants were
operator-enabled and revoked on cleanup. Personal settings were compared in
memory/stdin; only boolean results were retained. No password seed or personal
key/credential was inspected or exported.

All 114 repository tests, Ansible syntax, documented Python/Bash syntax checks
and `git diff --check` pass. Source fixtures and reports include the optional
Bluetooth presence/deferred matrix and the permission/desktop/ordering regressions.

Detailed local evidence is under `.artifacts/playbook-validation/lean-42-*/`.
The latest directory is `lean-42-complete-20261101`; trial UUIDs and exact local
paths are in its ignored acceptance report. No manager app was replaced, no
host tool installed, no macOS permission granted and no existing VM operated on.

Interruption/retry, forced crashes, host sleep/wake, end-to-end clipboard focus
routing, moving between host displays and factory reset were not exercised.
Native display state and clipboard-channel presence do not establish those behaviours.
