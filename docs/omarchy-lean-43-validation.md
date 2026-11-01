# Lean 43.1 acceptance — 1 November 2026

The rebuilt lean factory passed unattended owner setup, completion reporting
after host cleanup, hardware rendering and playbook idempotence before and
after restart. Validation used the reviewed 0.9.2 (15) manager preview without
installation and exactly one new disposable guest, now stopped and retained.

## Reviewed identities

| Component | Identity |
| --- | --- |
| Manager fix commit | `b8804fc64ae654f7ae58c2cfbcd226680ff0819f` |
| Integration source | `1ecd8499d271cd761e8b4be0e49747de96e57768` |
| Manager / kit / lean package | `0.9.2 (15)` / `0.1.0-43` / `0.1.0-43.1` |
| Runtime lock SHA-256 | `37aeca15303be1d491b9ed39109e4d0fc273093fe88dc1ac9f0b56fa05822cfb` |
| Kit archive SHA-256 | `3c4a3ac1e7a6efc2200db67c65b8d44da2e65bfe459b49ffb44e1d10f274508f` |
| Reporting capability | `ownerSetupReportVersion = 1` |
| Selected contract | `lean-e4fffc6`, `1347cb16b831eb2c3a67344a5bbb68c9da776a55221ecab5ba90ce385078d310` |
| Raw disk SHA-256 | `8e6dd480085c6a4ce76a5e84aa34977744e84e7e2ec05e029c0e136c0d7cc9eb` |
| Compressed SHA-256 | `e2a6cb7fde6bd98b91f1b0eb4cb4d8f74fd77c26099d86ea9db9f00c8fedc3e1` |
| Imported manifest SHA-256 | `f5144d0addfeaca64774bff04b9474aa897bc7f0d5d8fc8ad8e2b807e6441569` |

The new artifact is `.artifacts/omarchy-image/8709642159651033-8e6dd480085c6a4c`,
with its separate `.Manager.factory` bundle. Its compressed size is
1,700,951,234 bytes; the raw disk is 21,474,836,480 bytes. All published
checksums and the full decompressed digest passed independent verification.
The five owner programs and reviewed owner/SSH adapter and contract bytes match
their sources. Native contract verification passed inside a read-only image
copy, including permissions and links. Both reviewed contract digests remain
unchanged; fresh official-image live validation is separate work.

The builder retained its checked hardware-policy transformation, native VirGL
quirk, source-permission normalization, optional provisioning guards, desktop
helpers and preferences 1-2. No retained disk was patched or relabelled.

## Live observations

Exactly one new disposable UUID was created with the imported factory explicitly
selected, saved owner defaults, managed SSH, 4 CPUs, 4 GiB RAM and a 64 GiB disk.
The matching preview's signature, embedded lock and all 43 runtime inventory
entries passed verification; the serving process was that preview.

- Owner provisioning completed without a manual wizard. Redacted comparisons
  passed for account, full name, Git name/email, hostname suffix, timezone and
  keyboard/input selection. Host completion identity matched and all three
  temporary host setup files disappeared.
- After cleanup, three strictly later natural timer invocations returned
  `Result=success`, `ExecMainStatus=0`. The timer remained active. Manager
  readiness and authenticated pinned SSH passed before and after this interval.
- The deferred hardware queue emptied, keyring work completed, and the hardware
  unit succeeded and disabled itself. The first-login marker was present and
  there were zero failed system units.
- The actual desktop screenshot showed wallpaper and shell without missing
  helper notices. Hyprland/GLX and actual native Quickshell QRhi reported
  hardware VirGL on the Apple GPU, with no forced software renderer. The native
  VirGL quirk was set, Foot passed, and native Retina scale was 2.
- The receipt was root-owned, mode 0600, regular with one link, under a private
  root-owned directory. Its exact public-only schema, current boot, VM/session,
  fingerprint, owner and contract matched the helper credential and durable
  identity. The seeded-boot service journal contained 18 successful finishes
  and no failed-service, missing-manifest or traceback messages.
- A graceful stop completed with no guest processes or disk handles, followed by
  a cold start with a new kernel/runtime session and authenticated pinned SSH.
  No setup seed was observed during launch. The managed-setup flag and report
  credential were absent, the timer stayed inactive, the report service never
  executed, and the volatile receipt was absent. Owner identity and provisioning
  log inode/size/modification-time values were unchanged.
- The normal `site.yml` workflow used `omarchy/examples/features.yml` through
  private manager-pinned SSH inventory. First application returned `changed=5`
  for the five optional feature groups; workstation preferences already matched.
  The identical second application and each of six independent tags returned
  `changed=0`, with no unreachable/failed tasks. Package, config, firewall and
  activation snapshots were identical during those reapplications.
- Docker ARM64 hello-world, container DNS, Compose and Buildx build/load/run
  passed. Node/Python ARM64 execution and libraries passed; Claude, Codex,
  OpenCode and 1Password CLI version commands passed without authentication.
  Normal Wayland Chromium WebGL2 reported ANGLE/Mesa/VirGL with its software
  rasterizer disabled. Temporary browser, Docker and diagnostic-shell resources
  were cleaned up and the native shell launcher restored.
- A subsequent manager-owned graceful restart produced another authenticated
  kernel/runtime session with stable SSH pins and no new setup seed. Full
  reapplication returned `changed=0`, `unreachable=0`, `failed=0`. Owner-file
  metadata, packages and preferences stayed unchanged. Native SSH refresh
  reordered its firewall allow block; an exact permutation of the same three
  native rule blocks reconstructed the original hash, proving unchanged content.
  Docker, selected tools, Hyprland/GLX, native Quickshell and Chromium WebGL2
  passed again. Final system and user failed-unit counts were zero.

## Evidence and remaining checks

Detailed redacted evidence and the exact disposable UUID are under the ignored
`.artifacts/playbook-validation/lean-43-20261101/` directory. All 114 repository
tests, Ansible syntax, documented Python/Bash checks and `git diff --check`
passed. Two local Ansible tests initially could not open their sandboxed RPC
socket; the complete rerun with local socket access passed.

All six existing profile/root inventories, saved Guest Defaults and all twelve
recorded retained artifact directories match their baselines. The new guest
was gracefully stopped; its matching exit was observed, no runtime/helper
processes or guest disk/firmware handles remain, and all seven manager guests
are stopped. All operator-enabled temporary grants were revoked. The new root
is retained for inspection; moving it to Trash is optional and was not performed.
No host software was installed, no app replaced, and no macOS permission granted.

The serial console emitted a nonfatal encryption-mapping warning on this
unencrypted factory; boot and all acceptance checks completed. Its underlying
initramfs cause was not investigated. A brief manager SSH `connecting` transition
was also observed between probes; subsequent checks waited for manager-owned
authenticated readiness. Neither was hidden by changing guest services or reports.

Fresh official-factory acceptance, forced interruption/crash, sleep/wake,
clipboard focus routing and dynamic display movement are outside this run.
Clipboard-channel presence alone does not establish functional clipboard support.
