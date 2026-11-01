# Prepare your lean, mean coding image

One lean, mean coding image serves every workstation layout. The builder creates the
sealed base; bootstrap coordinates native factory import and VM creation, then
installs the selected apps, theme and layout.

## Build and bootstrap

Use an Apple Silicon Mac with existing Git, Python 3.10+, make, an ARM64 Linux
Docker engine and the matching VM Manager app/CLI checkout. Allow the requested
factory capacity plus 4 GiB on the artifact volume and at least 3 GiB of Docker
scratch. Bootstrap's private snapshot also needs room for the compressed payload.

```bash
make build-omarchy-image
make bootstrap-omarchy-vm VM_NAME="Dev Omarchy" \
  OMARCHY_VM_FACTORY=.artifacts/omarchy-image/latest
```

The builder reads the manager checkout's prepared `.build/runtime-source`,
resolves its real path and checks `managed_try_commit` in
`omarchy/image/inputs.lock.json`. The reviewed source is
`1ecd8499d271cd761e8b4be0e49747de96e57768`, producing package 43.1 for the
matching 0.9.2 manager and `lean-e4fffc6` owner contract. See the manager's
`docs/LeanOwnerSetup.md` if source preparation is needed. Host tools and manager
sources are never downloaded/prepared automatically.

`OMARCHY_VM_MANAGER_DIR` selects another existing manager checkout. Advanced
`OMARCHY_IMAGE_TRY_SOURCE` and `OMARCHY_IMAGE_TRY_COMMIT` overrides retain the
clean-source, exact-commit, ancestry and builder-hash checks. Disk size defaults
to 20 GiB via `OMARCHY_IMAGE_SIZE_GIB`.

Optional preview and package-only checks:

```bash
make build-omarchy-image OMARCHY_IMAGE_PLAN=yes
make check-omarchy-image
```

Only successful full builds atomically update the repository-owned `latest`
symlink. Original artifact directories remain intact. Unrelated files/directories
at that shortcut are preserved and cause a clear error. Previews, failures and
package-only checks leave the shortcut unchanged. Building performs no VM or
manager-cache operations.

## Accepted factory paths

`OMARCHY_VM_FACTORY` accepts:

- A successful repository build directory, including the `latest` shortcut.
- The build's `.img.zst` file, with `factory.json`, `SHA256SUMS` and provisioning
  evidence alongside it.
- A flat prepared bundle containing `reviewed-factory.json` and its declared files.
- `official`, or an already-imported manifest SHA-256 for advanced use.

An isolated raw/compressed disk without companion metadata is refused. Bootstrap
never invents missing evidence, changes contract hashes, patches an old disk or
relabels an unbooted image as validated.

For repository outputs, bootstrap checks the selected payloads against
`SHA256SUMS`, copies the image and required evidence to a private temporary bundle,
and runs the matching manager checkout's existing `prepare_factory_bundle.py`
with `lean-e4fffc6`. That native helper checks owner programs, integration version,
source and runtime compatibility. Existing prepared bundles are copied verbatim;
their descriptor is preserved. Payloads must be regular files with matching hashes;
undeclared files, links and unsafe names are refused in prepared bundles.

The source path and prepared identity appear in the proposal. The path is resolved
once, so another build changing `latest` during confirmation cannot change the
reviewed snapshot. After confirmation, bootstrap calls VM Manager's native
`factory-import` and requires the returned custom-factory identity to match the
prepared descriptor before creating a VM. The manager owns admission, its private
library, runtime checks and storage. Original source artifacts are not modified.

Temporary preparation files are removed afterward. Cancellation, failed
preparation, failed import or an unexpected returned identity prevents VM
creation. Native mutations are not retried automatically; after an uncertain
CLI outcome, inspect manager state before retrying. No fallback to official or
replacement of an existing VM occurs. A different factory on an existing name
is refused before import; choose an unused name for a new image.

## Applications and validation

The foundation includes required desktop/provisioning tools such as Foot and
system Python. No optional browsers, editors, agents, developer runtimes,
credential apps or app layouts are selected during building. Bootstrap adds
those through its existing explicit options; see the layout runbooks.

Build checks are static/chroot checks, not live owner or GPU acceptance. Complete
the [workstation checks](omarchy-validation.md), including normal restart,
hardware rendering, Retina/dynamic resizing and clipboard text in both directions.
Reject `llvmpipe`, `softpipe` and forced software backends.

Keep the full artifact and checksums. The [image contract](omarchy-image.md) and
[43.1 acceptance record](omarchy-lean-43-validation.md) describe recorded evidence
and remaining limits. Live Arch repositories mean rebuilds are not guaranteed
byte-identical. Never commit owner credentials or real guest identities.
