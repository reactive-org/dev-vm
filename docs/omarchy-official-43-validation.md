# Official factory / manager 0.9.2 acceptance — 1 November 2026

Live official-factory acceptance passed on exactly one fresh disposable guest
with the reviewed manager 0.9.2 (15) preview, without installation or app
replacement. Owner setup, completion reporting, hardware rendering and playbook
idempotence passed before and after restart. The guest is stopped and retained.
The broader repository suite has unrelated failures, recorded separately below.

## Identities

| Component | Identity |
| --- | --- |
| Manager fix commit | `b8804fc64ae654f7ae58c2cfbcd226680ff0819f` |
| Integration source | `1ecd8499d271cd761e8b4be0e49747de96e57768` |
| Guest integration package | `try-omarchy 0.1.0-43` |
| Runtime lock SHA-256 | `37aeca15303be1d491b9ed39109e4d0fc273093fe88dc1ac9f0b56fa05822cfb` |
| Kit archive SHA-256 | `3c4a3ac1e7a6efc2200db67c65b8d44da2e65bfe459b49ffb44e1d10f274508f` |
| Reporting capability | `ownerSetupReportVersion = 1` |
| Official contract SHA-256 | `d381667f407b5f82cfb9f9c391eccf2898ba8a064bc6b2f082e28f959e76aef8` |
| Official manifest SHA-256 | `1c202c4d9c4087b87d40138d812835a765ff736ff7cf1b9dc233b4fa8945a8cf` |
| Raw factory SHA-256 | `f587d246981b14f1b0537d75ac1be03219368ac78aaefdb98b8e75a8f9a890c3` |
| Compressed factory SHA-256 | `e91daf6dcd218ac96679444ba461c7562edc5540fd9cdb077e151e6af2212286` |
| Factory Omarchy / kernel | `4.0.0.r7235.g967bbdd-1` / `7.2.8-23` |

The actual serving preview, signatures, embedded runtime lock, all 43 runtime
inventory entries and kit archive digest were verified. The new guest's immutable
20 GiB factory cache was independently hashed against the official raw digest;
no existing guest disk was opened. Factory selection was explicitly `official`,
with 4 CPUs, 4 GiB RAM, a 64 GiB disk, saved defaults and managed SSH.

## Live checks

- First boot completed unattended owner setup without a manual wizard or an
  extra provisioning restart. Redacted account, name, Git, hostname, timezone
  and keyboard/input comparisons passed. Host completion identity matched and
  the seed, full manifest and launch marker were removed.
- Three subsequent natural timer activations completed with success and exit 0
  while the timer stayed active. Manager readiness and authenticated pinned SSH
  passed before and after them. A journal summary found 12 successful service
  finishes and no failed-service, missing-manifest or traceback messages.
- The root-private mode-0600 receipt contained only the expected public binding
  and boot ID, matching the helper-authorized launch and durable owner identity.
  Native strict verification selected the official adapter and all three pinned
  owner programs.
- Hyprland's actual compositor log and native Quickshell QRhi reported hardware
  VirGL on the Apple GPU. Their process environments contained no forced software
  renderer. The shell, application content and exposed wallpaper were visible;
  no missing-command notices appeared. The stock image lacks `glxinfo`; native
  renderer logs supplied the evidence without installing a diagnostic package.
- Normal `site.yml` with `omarchy/examples/features.yml` returned `changed=5`
  initially: preferences, Firefox, selected runtimes, agents and credentials.
  Docker already matched. The identical second run returned `changed=0`, with
  zero unreachable/failed tasks. Each of six independent tags also returned
  `changed=0`; package/config/firewall/activation snapshots remained identical
  during reapplication. Docker ARM64 execution, DNS, Compose and Buildx
  build/load/run passed. Foot, host idle policy and Retina scale 2 passed.
- Node/Python ARM64 execution, selected agent/credential CLI versions without
  authentication and normal Wayland Chromium WebGL2 passed. Chromium reported
  ANGLE/Mesa/VirGL with software rasterization disabled.

- Graceful shutdown released all guest disk/firmware handles before cold start.
  The new kernel/runtime session authenticated with stable SSH pins, no setup
  seed was observed during launch, and the report boot credential and seeded
  timer stayed absent/inactive. The report service never executed and its
  volatile receipt was absent. Owner settings still matched after restart.
- Full post-restart reapplication returned `changed=0`, `unreachable=0`,
  `failed=0`. Owner identity and provisioning-log inode/size/modification-time,
  package/preference snapshots, SSH pins and all four firewall hashes stayed
  unchanged. Docker execution/DNS/Compose/Buildx and graphics/runtime checks
  passed again. Final system and user failed-unit counts were zero.

## Repository checks and limits

All 42 focused feature, Ansible-contract and guest-preference tests pass, as do
Ansible and documented Python/Bash syntax checks. The full `make test-omarchy`
run currently fails: 120 tests, 11 errors in unfinished layout-builder interfaces
and the controller's missing `factory` test argument. These unrelated working-tree
changes were preserved, not repaired by this validation session. Live results do
not turn that full-suite failure into a pass.

Detailed redacted evidence and the disposable UUID are under the ignored
`.artifacts/playbook-validation/official-43-20261101/` directory. Existing seven
guest profiles/root inventories, saved defaults and fourteen retained artifact
directories match their baselines. All temporary grants were revoked. Final
graceful shutdown completed with matching exit, no runtime/helper processes and
no guest disk/firmware handles. All eight manager guests are stopped. The new
root is retained for inspection; Trash cleanup was not performed. No host tools
were installed and no macOS permissions granted. The manager checkout and
unrelated working-tree changes were preserved.

Native graphics logs show GLES context negotiation retrying 3.0 after a 3.2
request, then selecting hardware VirGL. The Chromium diagnostic logged a
background SSL handshake failure; the local WebGL test passed. General browser
HTTPS behavior was not an acceptance check.

Crash/interruption, sleep/wake, hibernation, clipboard focus routing and dynamic
display movement remain outside this run. Clipboard-channel presence alone does
not establish functional clipboard behavior. The matching lean result is in the
[43.1 acceptance record](omarchy-lean-43-validation.md).
