# External setup repository acceptance — 2 November 2026

This record covers the version-1 external setup workflow as tested, using the
installed, signature-verified Omarchy VM Manager 0.10.0 (23).
The dev-vm base revision was `1d1b50dd589e9a1f1319552a2d55fecb354dc3ea`;
the external-setup implementation and live corrections were uncommitted.
Exact runner source hashes and selected input hashes are recorded in each
successful guest's setup provenance and the ignored evidence directory.
The later built-in keyring feature and profile default have local fixture
coverage only. No VM was contacted to validate that change or Claude's keyring
startup warning.

## Status

| Factory | Result |
| --- | --- |
| Official Try Omarchy | Passed corrected external setup, negative checks, cold start, full zero-change reapplication and functional checks; initial native update required the recovery described below. |
| Lean | Passed normal bootstrap, negative checks, cold start, full zero-change reapplication and functional checks. Native per-setup Keychain authentication completed before first launch. |

Both disposable VMs were stopped and retained for inspection. This acceptance
preceded Higeia's configuration-only migration; no Higeia VM was changed.

## Scope and isolation

Exactly two newly named disposable profiles were created through the installed
manager, with 4 CPUs, 8 GiB RAM and independent 64 GiB disks. Saved owner defaults
supplied the password through the manager; native owner overrides selected a
generic test identity. Personal SSH-key inheritance and shared folders were
explicitly disabled. No password or personal credentials were read by the test
controller, supplied through chat, or copied from the Mac into the guest.
Native sudo and Docker consent were completed by the operator in Terminal.

The controller rejects every UUID present in the original inventory before
performing guest/lifecycle operations. The two pre-existing VMs retained their
original configuration, resources, factory, sharing settings, running/stopped
state and active session identity. The existing stopped VM's complete recorded
file-stat inventory and saved Guest Defaults matched baseline after both runs.
The existing running VM continued its own workload; its disk contents were not
treated as immutable or claimed to be byte-identical. The final isolation check
passed after both disposable VMs were stopped.

No host software was downloaded, built or installed; the installed manager was
not replaced or modified. Native factory admission, SSH pins and graphics paths
were kept enabled. Old incompatible factory entries were left alone.

## Factory identities

| Component | SHA-256 |
| --- | --- |
| Official manifest | `1c202c4d9c4087b87d40138d812835a765ff736ff7cf1b9dc233b4fa8945a8cf` |
| Official raw disk | `f587d246981b14f1b0537d75ac1be03219368ac78aaefdb98b8e75a8f9a890c3` |
| Lean admitted manifest | `714ea1cdb9d0321f52fcbc6c26ec1b5807b6d07e35d86f11f43a498a83e02dfc` |
| Lean raw disk | `20cac2aa99021d9cdb2bf5b6f85692334e03f70662569ff783287be5e3f66ac7` |
| Lean compressed disk | `da31a3b8a737cab7f9aa84b195bd46e90259be5b1f6f4f3e0f6e890806b9dc9b` |

All 24 published files in the current lean artifact's checksum inventory passed
independent verification. Both guests' immutable 20 GiB factory copies also
passed full raw-disk hashing. No image was rebuilt or retained disk patched.

## External repository exercised

Two standalone Git repositories outside dev-vm were prepared from the shipped
example. Their manifests select `project-managed`, Ruby prerequisites, Claude
CLI/Desktop, Chromium, 1Password tools, keyring packages and the Claude/two-Foot/
floating-browser layout. There are no project-owned global runtime selections.

The fixture extends the example with a controlled dotfile, an unrelated file
that must survive reapplication, and explicit `become: true` tasks creating a
root-owned configuration file. Tasks exercise directory creation, templates,
Git includes, explicit privilege escalation and expected failure. An additional
manifest selects a deliberately failing task for negative checks.

Only declared sources/assets are snapshotted. The repositories' Git metadata and
unselected files are not part of the applied input set. Source/engine hashes,
selected task names and requested VM settings match the guest provenance.

## Results on both factories

- Normal bootstrap completed the corrected software, preferences, dotfiles and
  custom tasks, revoked setup sudo, restarted through VM Manager and passed the
  repository workstation checker.
- Fresh graphical checks passed hardware `virgl (Apple M5 Max)`, no forced
  software renderer, a valid Hyprland configuration, native `4960×2790` display
  at scale 2, Foot configuration, host-owned idle policy and clipboard-channel
  presence. The exact layout hash and all four expected floating workspace-1
  windows were present, with geometry within two logical pixels of the selected
  layout at native display scale.
- Managed dotfile contents/modes, template output, project directory, root-owned
  fixture and provenance matched the external repository. Native Git content
  and permissions were preserved while its preferences include was added.
  Zsh/Bash mise activation, native compile/link/run, SQL clients, Claude CLI and
  1Password CLI worked without application sign-in. User runtime selections
  matched the pre-application baseline.
- Built-in and trusted check modes completed without enabling a setup grant.
  Workstation and Docker each reported their documented conservative planned
  work; the custom stage reported `changed=0`. Explicit task selection skipped
  unselected custom tasks. The original feature-only toolchain check separately
  reported `changed=0`, `unreachable=0`, `failed=0`.
- A guest edit triggered default dotfile conflict refusal and remained intact.
  Explicit owner-level helper backup preserved that edit, source updates were
  idempotent, and the canonical source was restored. The unrelated file remained
  intact. An expected task failure was surfaced correctly, and sudo stayed
  inactive. These helper-level backup/update exercises supplement the actual
  launcher/bootstrap and check-mode runs; they are not additional full apply
  invocations.
- After a manager-owned graceful stop and cold start, the kernel boot ID changed.
  Normal full reapplication returned `changed=0`, `unreachable=0`, `failed=0` in
  both the built-in and custom plays. Selected file fingerprints, package list,
  root task output and provenance matched the pre-cold-start snapshot. Native
  sudo was inactive and system/user failed-unit counts were zero.
- Before and after that cold start, owner access to the local Docker daemon,
  ARM64 containers, DNS, Compose and Buildx build/load/run passed without sudo.
  Chromium WebGL2 reported hardware VirGL with software rasterization disabled.
  Temporary containers, build image and browser profile were cleaned up.

Both disposables were gracefully stopped and retained for inspection. The lean
bootstrap completed on its first invocation after the operator authorized the
manager's native Keychain prompt; it required no compositor recovery.

## Findings corrected during acceptance

1. The first example selected Omarchy's existing Git config as a whole-file
   dotfile. Conflict refusal correctly stopped application. The example now
   deploys a separate preferences snippet and adds a managed Git include,
   retaining the native configuration, identity and permissions. The local real
   Ansible regression also checks an existing mode-0600 Git config.
2. A failed dotfile helper emitted no JSON, and the role's unconditional
   `changed_when` parser obscured its useful error with a secondary parse error.
   Parsing is now conditional on successful helper exit. Conflict errors remain
   clear and temporary payload cleanup still runs.
3. The first custom-task inventory inherited `ansible_become=false`, overriding
   a task's explicit `become: true`. Custom tasks now receive a separate private
   inventory with the same pinned connection and owner-default play, allowing
   explicit task-level escalation. The regression failed before the correction,
   passed afterward, and the live root-owned fixture proved the corrected path.

Native setup grants were verified revoked after the real task failure and after
an actual controller interruption, as well as on successful completion.

## Native official-update recovery

The official factory started with Hyprland `0.56.2-7`. Its native Omarchy update
installed `0.57.0-2` and new default Lua files while the old deleted compositor
binary was still running. The UI reported:

```text
/usr/share/omarchy/default/hypr/looknfeel.lua:94:
unknown config key 'misc.bell_sound'
```

The native shell-restart helper then waited on a Hyprland IPC client. External
layout application had not begun. Omarchy's native boot verification completed
successfully. The disposable controller was interrupted, its native sudo grant
was verified revoked, and the manager restarted that same guest. The new
compositor cleared the error and IPC recovered. A normal bootstrap retry
completed. Stock Omarchy Lua was not edited to hide the error. This means the
official result includes a documented native-update recovery, not a claim of an
uninterrupted first invocation on that older factory.

## Validation limits and evidence

After the live corrections, `make test-omarchy` completed successfully: 230 tests,
with one existing skip for the missing host Lua interpreter. Ansible, Python
and documented shell syntax checks passed. The actual guest layout startup is
covered above; the skipped standalone Lua recovery fixture is not represented
as executed locally.

Raw evidence, generic disposable identities, external-repository paths, source
hashes, logs, probes and isolation checks are under the ignored
`.artifacts/setup-acceptance/20261102-external-repo/` directory. Do not publish its
unredacted native inventory/logs as repository documentation.

Clipboard focus routing, moving the VM between physical displays, sleep/wake,
authentication to installed applications, every catalogue alternative, and
application-specific Claude graphics behavior are outside this run. Clipboard
channel presence alone does not prove end-to-end clipboard routing. Moving
selectors/rolling packages are not a reproducibility guarantee.
