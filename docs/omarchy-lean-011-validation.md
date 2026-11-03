# Lean factory admission and bootstrap on VM Manager 0.11.0 — 4 November 2026

The documented lean build imports into the installed manager and passes full
default bootstrap in one new disposable ARM64 VM. Unattended owner setup,
authenticated managed SSH, native update/restart and hardware VirGL passed on
0.11.0. The disposable VM is stopped and retained; the pre-existing VM was left
unchanged. Broader desktop acceptance remains listed below.

## Reproduce the flow

Use the existing Apple Silicon/ARM64 Docker environment, Python 3.10+ and manager
0.11.0 in `/Applications`. Run from the repository root:

```bash
make build-omarchy-image
make bootstrap-omarchy-vm VM_NAME="Dev Omarchy" \
  OMARCHY_VM_MANAGER_APP="/Applications/Omarchy VM Manager.app" \
  OMARCHY_VM_FACTORY=.artifacts/omarchy-image/latest
```

Review the proposal, confirm it and follow the native guest authentication
prompt. Bootstrap automatically snapshots the build, prepares format 2, imports
through the manager and checks the returned manifest identity before creation.
There is no manual package copying, bundle preparation, descriptor editing or
manifest-hash transfer. Use an unused VM name and saved Guest Defaults for a new
workstation.

For admission alone, without creating or starting a VM:

```bash
make import-omarchy-factory \
  OMARCHY_VM_MANAGER_APP="/Applications/Omarchy VM Manager.app" \
  OMARCHY_VM_FACTORY=.artifacts/omarchy-image/latest
```

This optional command shows an import proposal and uses bootstrap's preparation
and native import functions. `OMARCHY_VM_YES=yes` accepts that proposal for an
already reviewed automated run. Normal bootstrap includes the import itself.

## Confirmed failure and admission policy

Before changing the build, a separate format-2 bundle was prepared from the
original `942e8f6e89867c2a-adf6043c0378a1b4` build, then selected by `latest`.
It retained its own image, evidence and original integration archive with SHA-256
`628dda72597c9361ba0d4eae5769b7ebed2c592852712b67d54554aeda72403a`.
The real installed 0.11.0 importer returned `factory-verification-failed` and
identified the unreviewed package SHA-256. This confirms the refusal at the
package-policy boundary, independently of the repository's earlier preparation
failures. The initial sandboxed CLI attempt could not open the manager; the
outside-sandbox retry reached its native verification and produced this refusal.

The reviewed complete archive is
`try-omarchy-0.1.0-43.1-aarch64.pkg.tar.zst`, SHA-256
`9fc986521b67cfa9e891fd826453553f1e2e4a319e6edb1302c760f1e22a2211`.
It was retained by build `af93b5f10d206637-7816326733d14d53`, source
`80156396a5daa795487c0f4a8308eee53f6ea68b`. Rebuilding/repacking integration
produced different archive identities even with the same package version.
Matching source or version alone cannot admit a new archive.

The repository now retains that reviewed archive under
`omarchy/image/reviewed-packages/`. The lock pins its checksum, origin and the
complete transformed recipe identity, including the license, file modes and
link targets. Host staging and the container check that identity before reuse.
The normal dependency resolver and pacstrap installation consume the retained
archive; package dependency checks remain enabled. Build provenance records the
reuse and the actual archive is retained in each output's `packages/` and
`SHA256SUMS`.

`guest-integration-compatibility.json` mirrors the existing manager policy:
guest integration contract 1, the reviewed lean/runtime archives and lean owner
contract. Bootstrap includes the original complete archive in its private flat
bundle and emits format 2. Source commits remain checked provenance without
requiring equality to the manager's host patch commit. The installed app's
resource layout, runtime package, owner contract and capabilities are checked;
native manager verification remains authoritative.

No manager policy, installed app or runtime was changed. A changed source recipe
or package hash stops the flow and requires package review and a manager policy
decision. No new hash was admitted. An old unsupported disk cannot be repaired
by substituting the reviewed archive in its evidence; build a new disk with the
reviewed package installed through the normal builder.

## Observed results

Installed app: **0.11.0 (27)**, release tag `v0.11.0-dev.3`. Its embedded runtime
lock identifies artifact `v0.11.0-dev.2`, host patch source
`37c635f8992a9e19cc99696542bf061baff804c0`; the image source remains
`85f5e561e5a277ccec08d7725c8714cb090c9011`.

| Check | Result |
| --- | --- |
| Original unreviewed `latest` archive, native format-2 import | Refused with the explicit unreviewed SHA-256 error |
| Original reviewed `af93b5f1…` build, new import command | Imported as `9501a7aa2ca6cc29d1734eff704c81687b37e2ff16ce5a921443c5cb2a1bd37f` |
| Fresh `make build-omarchy-image` | Passed; published `0b57e134bf7307a5-af02e24f6254de96` and updated repository `latest` |
| Required/excluded dependency resolution | Passed; 571 resolved packages |
| Optional provisioning, owner-program/permission and identity-sealing checks | Passed |
| Isolated user finalization, preferences, Foot and development tools | Passed in chroot, including C compile/link/run |
| Independent complete output checksum verification | All 24 entries passed |
| Fresh factory, documented native import command | Imported successfully; identity below |
| Manager factory catalog after import | Fresh identity remained listed after native revalidation |
| Initial admission-only bootstrap with each reviewed build and real 0.11 CLI | Reached proposal with the matching identity; deliberately declined before import/create |
| Initial admission-only guest inventory | Unchanged; no VM operations during that phase |
| `make test-omarchy` | 239 tests passed; one Lua availability skip |
| Documented shell/Python syntax checks; `git diff --check` | Passed |

Fresh artifact identities:

| Component | SHA-256 |
| --- | --- |
| Raw disk, 20 GiB | `af02e24f6254de969029ec98464218c15c15cc1027acd6d78bdd5f504a40f9ed` |
| Compressed disk | `dbdf847b2d8ad41d590b807491596fb26f1c8684968ade9dc1f0e54842626168` |
| Imported format-2 manifest | `dd76d38cab9343cbd68989cfef5f45a53d3bb2352a53ed05929e06859f4c9dcc` |
| Integration archive installed by the build | `9fc986521b67cfa9e891fd826453553f1e2e4a319e6edb1302c760f1e22a2211` |

The first full test invocation used macOS Python 3.9.6 and failed tests requiring
`tomllib`. The passing invocation used the existing Homebrew Python 3.14 on
`PATH`: `PATH=/opt/homebrew/bin:$PATH make test-omarchy`, outside the sandbox for
the local Ansible socket fixtures. No host software was installed. Regression
coverage includes changed archive bytes with recomputed checksums, missing or
linked archives, changed complete recipes, malformed source evidence,
unsupported runtime/owner identities and capabilities, differing host/source
provenance, and confirmation/import/create ordering.

Logs, negative-control bundle, build/checksum evidence and private inventories
are retained under ignored `.artifacts/omarchy-011-validation/`. The manager
retains the two new native imports; existing bundles, receipts and guest disks
were not rewritten. Build metadata still correctly says `manager_admitted:
false` and `guest_boot_tested: false`; later admission is recorded here rather
than changing sealed artifact evidence.

## Full live bootstrap — 4 November 2026

The subsequent authorized live run used the same fresh factory and installed
0.11.0 (27) app. All 24 artifact checksums passed again before creation. Exactly
one new disposable VM was created, with the explicit factory path, saved Guest
Defaults, managed SSH, 8 CPUs, 20 GiB RAM and a 64 GiB disk. Optional apps,
feature playbooks, themes and layouts were not selected. Bootstrap used Foot
size 12 and host-owned idle/locking, as in the documented default flow.

The initial create/wait client was interrupted to move authentication into an
attachable terminal. The manager continued the same guest's launch. A native
`get` pinned its UUID and confirmed that owner setup and SSH had completed; the
resumed normal bootstrap adopted that exact guest. No second VM was created.
The operator confirmed Omarchy's native sudo prompt and entered the guest
password directly in the terminal. No password or Keychain secret was read,
logged or supplied by repository code.

The resumed `make bootstrap-omarchy-vm` exited **0**, including native
`omarchy update -y`, preference application, setup-sudo revocation, manager-owned
restart, authenticated SSH readiness and the repository workstation checks.
Runtime/settings updated through Omarchy from
`4.0.0.r7481.ge4fffc6-1.1` to `4.0.0.r7576.g5eb922f-1`. Integration remained
`0.1.0-43.1`; workstation preferences remained `1-2`. No guest files were
hand-patched to make the run pass, and no manager policy/runtime was changed.

| Live check | Observed result |
| --- | --- |
| Unattended owner setup | Native owner report reached `configured`; completion record matched its original setup identity |
| Actual owner configuration | Redacted comparisons passed for non-root username, configured full name and Git identity, hostname suffix, timezone and keyboard |
| Temporary setup credentials | Seed, shared setup manifest and launch manifest were absent after completion and remained absent after restart |
| Managed SSH | Authenticated as the configured owner through the manager's exact per-VM client configuration, with `StrictHostKeyChecking yes` and its pinned known-hosts file |
| Native restart | Runtime session identity changed; bootstrap waited for authenticated managed SSH and completed its checks afterward |
| Hardware rendering | GLX reported `Accelerated: yes` and `virgl (Apple M5 Max)`; no `llvmpipe`, `softpipe` or software rasterizer was reported |
| Active desktop processes | Hyprland and Quickshell were running, with no forced software-rendering environment in either process |
| Desktop configuration | No Hyprland config errors; valid Foot/theme configuration; host-owned idle/locking preferences passed |
| Display observed | Native `Virtual-1`, 2080×1170 at scale 1; dynamic resizing and Retina scale transitions were not exercised |
| Service health | Zero failed system units and zero failed user units; native guest-status reporter active |
| Owner reporting after normal restart | Completion remained recorded; setup timer was inactive on the unseeded boot, as expected; recurring seeded-boot timer behavior was not separately exercised |
| Storage growth | Native disk was 64 GiB and root filesystem exceeded 60 GiB |
| Development foundation | Git, Python, base-devel, yay, GCC and make present; non-root C compile/link/run passed |
| Setup sudo cleanup | Native grant probe returned inactive; `sudo -kn true` failed noninteractively, confirming authentication was required again |
| Clipboard | Native channel present; functional paste in both directions was not tested |
| Isolation | Exactly one new UUID; the one pre-existing VM's complete CLI inventory matched its baseline before and after cleanup |
| Final disposable state | Gracefully stopped through manager CLI, inactive and retained for inspection |

Private live evidence is under
`.artifacts/omarchy-011-validation/live-bootstrap/`, including both bootstrap
logs, exit status, owner and rendering observations, manager inventories and
`acceptance.json` with 35 passing checks. Real account details, hostnames,
addresses and guest UUIDs remain outside committed documentation. The original
sealed factory metadata and checksums remain unchanged; these live results are
recorded separately.

## Remaining limits on 0.11.0

Native import verifies the compressed payload and retained package/build
evidence. The manager expanded the factory for the live VM, but this run did not
perform a separate independent raw-filesystem measurement or decompression/hash
audit. The evidence is not a signed builder attestation.

This was full default bootstrap of the lean foundation. Optional developer
profiles/apps, theme/layout selections, manual owner setup, factory reset,
Retina/dynamic resizing, functional clipboard routing, browser WebGL, an
independent Quickshell QRhi trace, audio/camera, dedicated network tests,
sleep/wake and crash recovery were not exercised. Native repository downloads
and guest updates succeeded, but that does not establish broader network
acceptance. The [earlier 0.9.2 acceptance](omarchy-lean-43-validation.md) and
historical 0.9.3 records in the [image guide](omarchy-image.md) retain their own
scope. Live Arch repositories and disk generation remain variable; only the
reviewed integration archive is reused byte for byte.
