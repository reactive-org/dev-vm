# VM Manager handoff: report timer after completed seed cleanup

The matching 43.1 rebuild has since passed the authorized lean live checks; see
[the acceptance record](omarchy-lean-43-validation.md). The reproduction below
applies to the retained 42.1 image.

Fix the reviewed owner adapter's completion-report path while preserving both
the official and `lean-e4fffc6` contracts and all existing guests. Preserve
unrelated work already present in the manager checkout.

Observed with installed VM Manager 0.9.1 (14), the reviewed build following
`4f09aad`, integration source `aab6bd82b279cc81c2627be73f7b206ae6dadfc0`
and guest package 42.1. The exact factory and checksums are in
[the acceptance record](omarchy-lean-42-validation.md).

## Reproduction and evidence

1. Create a fresh guest with the imported lean factory, saved owner defaults and
   managed SSH. Owner setup completes without the wizard; its result is success.
2. The guest reports `configured`; the manager records completion and removes
   the temporary password seed, setup manifest and launch marker.
3. The current boot retains `tryomarchy.managed_setup=1`, and
   `try-omarchy-managed-setup.timer` remains active.
4. Subsequent `try-omarchy-managed-setup.service` invocations exit 1 repeatedly.
   Owner settings, completion identity and authenticated SSH remain valid.
   The latest hardware queue is empty and its unit succeeded; this is a
   separate manager integration failure.

In the pinned guest source,
`guest/package/try-omarchy/files/usr/lib/try-omarchy/managed-owner-setup`,
`acknowledge()` requires `SHARE / 'manifest.json'` after confirming completed
local state. The host's `ManagedOwnerStorage.finish()`/`clearSeed()` in
`Sources/OmarchyVMManagerCore/ManagedOwnerSetup.swift` removes that file.
The `--report` exception path exits 1. A synthetic isolated-container
reproduction confirms `FileNotFoundError: manifest.json` after this cleanup,
with committed identity present and pending/warning markers absent.

Evidence, including redacted journal output, state comparisons and the synthetic
reproduction, is under the ignored
`.artifacts/playbook-validation/lean-42-complete-20261101/` directory in dev-vm.
All test guests are stopped and retained; do not restart or alter them implicitly.

## Required fix and checks

Make reporting after legitimate completed-seed cleanup well-defined. Preserve
durable completion ordering, contract verification, VM/session/config/owner
binding and current-session SSH gating. Keep password removal prompt and secret
transport private. Do not solve this by masking/resetting the failed unit,
keeping password seeds, accepting unknown contracts or trusting stale reports.
Review any change to manifest lifetime or the reporter's trusted inputs together.

Add tests for official and lean completion followed by host seed/manifest
removal and repeated timer invocations. Retain negative coverage for wrong
VM/session/owner/fingerprint/contract, damaged identity, incomplete cleanup,
finalization warnings and interrupted durable commits. Record the intended
timer lifetime and verify that success cannot acknowledge another session.

Use the normal reviewed complete-kit build/inventory/signature pipeline.
Provide the new exact integration commit/package version, runtime pins and
matching dev-vm hardware-policy build instructions. A changed adapter requires
a reviewed matching rebuild; do not patch or relabel an existing factory disk.
Respect this session's applicable authorization boundaries for app installation,
permissions and live guests; this handoff requests the code fix and no-VM checks.
