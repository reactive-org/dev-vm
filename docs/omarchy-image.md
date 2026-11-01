# Minimal Omarchy factory

`make build-omarchy-image` builds an opt-in ARM64 desktop foundation for Apple Silicon and Omarchy VM Manager. It never invokes the manager, launches QEMU, accesses a guest disk, replaces a factory cache or installs host software. Bootstrap accepts its path in `OMARCHY_VM_FACTORY` and coordinates preparation/import through VM Manager; omission keeps the official default for new guests.

## Standard Omarchy, prepared for your Mac

The **Lean, mean coding image** starts with standard ARM64 Omarchy and uses
Try Omarchy’s factory approach to prepare a bootable disk for QEMU on Apple
Silicon. It uses Omarchy’s kernel, official package repositories and normal
update commands, with a smaller app selection that keeps Git, Python and the
standard build tools. ARM64 packages come from Omarchy’s `edge` channel.

Docker is the build environment: Try’s recipe uses Omarchy’s `pacstrap-docker`
tooling and Arch Linux ARM mirror, then installs the system onto a disk with
the usual ARM64 UEFI boot layout, Btrfs subvolumes and factory snapshot.
Owner setup runs on first boot. Omarchy VM Manager runs the resulting disk
in QEMU and supplies its native Mac integration for graphics, Retina scaling,
dynamic resolution, clipboard, networking and SSH.

The repository selects the lean package list and adds workstation preferences,
small package-managed provisioning guards for omitted optional apps, and
hardware-rendering settings. The pinned Omarchy runtime and settings are rebuilt
from upstream source to include those guards; the details are recorded below.
Omarchy continues to own the guest’s software and updates, and VM Manager
continues to own the VM and Mac integration. See the
[acceptance checks](#acceptance-and-updates) and recorded VM validation below
for the tested behaviour.

## Commands

Build the shared minimal foundation once, then let bootstrap install each VM's
selected applications, theme and layout. No optional apps or app layout are
selected by the image builder.

```bash
make build-omarchy-image
```

Then create/configure the VM without copying a manifest hash:

```bash
make bootstrap-omarchy-vm VM_NAME="Dev Omarchy" \
  OMARCHY_VM_FACTORY=.artifacts/omarchy-image/latest
```

The repository-owned `latest` symlink changes atomically only after a successful
full build. Earlier artifacts remain intact; package-only checks, previews and
failures do not change it. A specific build directory, its `.img.zst` path with
companion metadata, or an existing prepared bundle may also be passed. Bootstrap
checks a private snapshot, prepares its descriptor from installed app metadata
when needed, and imports through the native CLI only after proposal confirmation.

Optional preview and package-only checks:

```bash
make build-omarchy-image OMARCHY_IMAGE_PLAN=yes
make check-omarchy-image
```

The default source is the bundled guest-only archive
`omarchy/image/try-guest-source.tar.gz`. Its SHA-256, guest tree identity and
integration commit are pinned in `inputs.lock.json`. No manager checkout or
source preparation is required. Use the [short build guide](omarchy-layout-factory.md)
and [import/bootstrap handoff](omarchy-layout-factory-reference.md) for the complete flow.

The preview validates the pinned guest archive (or an explicit clean Try checkout) and prints the proposal without creating artifacts, running Docker or downloading anything. The compatibility check builds the versioned guest packages, executes the patched optional provisioning leaves with controlled commands, and checks the dependency closure against the live repositories. It runs without privileged Docker access or a disk. The image build repeats these checks and then runs the adapted upstream builder in a privileged ARM64 container for loop devices and mounts. Successful artifacts are published atomically into a new directory. Failed stages remain under `.artifacts/omarchy-image/.building-*` for inspection; they are never a successful factory.

Docker must already be installed and running with an ARM64 Linux engine. The first build downloads checksum-pinned guest source archives and an offline ARM64 Node payload, then creates a guest build container. Subsequent runs reuse verified source downloads, Docker's build cache and guest package archives under `.artifacts/omarchy-image/package-cache/`; pacman still verifies signatures. Each run uses a uniquely named, repository-labeled work volume, removed after its own container exits. No other Docker volume or container is removed. Builds in this repository are serialized.

The new sparse raw disk and filesystem work live in the unique host artifact stage mounted at `/factory-work`; source/package scratch uses the isolated Docker volume. This avoids filling Docker Desktop's virtual disk during Btrfs balance. The host artifact volume must have the requested disk size plus 4 GiB free, and Docker needs at least 3 GiB for source/package scratch. The workflow never prunes unrelated Docker data or changes Docker Desktop's settings.

Advanced users can replace the bundled guest source with an explicit reviewed checkout:

```bash
make build-omarchy-image \
  OMARCHY_IMAGE_TRY_SOURCE=/absolute/path/to/try-omarchy \
  OMARCHY_IMAGE_TRY_COMMIT=EXACT_REVIEWED_40_CHARACTER_COMMIT \
  OMARCHY_IMAGE_SIZE_GIB=20
```

An alternate integration checkout must be clean, descend from the pinned v1.3.0 commit and retain the exact reviewed factory builder. This supports the manager's separately reviewed integration sources without modifying that checkout. The chosen integration commit is recorded. The workflow changes only an isolated exported copy. It bumps the integration package release, removes the Ghostty/Kitty software-rendering launch paths and rejects remaining forced software settings. VM Manager 0.9.3 supplies package 43; its reviewed guest source produces the newer hardware-policy variant 43.1, which the native package installer preserves. A later integration update still requires revalidation.

Git source exports and downloaded archives are normalized to checkout permissions before packaging: directories and executable files use 0755, other files use 0644, and symlink targets are left alone. Git archives can contain group-writable modes; recipes using `cp -a` would otherwise preserve them into the guest. The image audit rejects writable, foreign-owned or linked canonical owner programs, and writable/non-directory parents. Manager integration adapters and contract files receive the same checks when present. Program bytes and their reviewed hashes remain unchanged.

## Foundation and provisioning

`omarchy/image/base.packages` declares required roots. `excluded.packages` rejects optional applications even when dependencies would bring them back. The preflight creates a temporary local repository for the four built packages and asks pacman to resolve the profile, those packages and their optional integration dependencies against an empty installation database. Builder-installed tools cannot conceal missing runtime dependencies, and local package versions/provides are checked normally. A missing root, excluded transitive package or repository error fails the build. Pacman's installed dependency and repository-signature checks remain enabled. As in Try's packaging-only build, `makepkg --nodeps` packages the source without installing the runtime into the builder; the separate resolver and actual image installation check those runtime dependencies. Kernel headers, DKMS and native integration input methods remain even though some host features are not enabled in VM Manager.

The disk preserves Try Omarchy's default 20 GiB sparse GPT layout, 2 GiB FAT32 ESP, ARM64 UEFI fallback, Limine/UKI, Btrfs subvolumes and read-only `@factory` snapshot. Image-target hardware/keyring initialization and owner creation remain deferred to first boot. The upstream builder removes machine identity, random seed, SSH host keys, pacman keyring and package cache before compression.

The pinned Omarchy runtime and settings are rebuilt together from source as package release `1.1`. Six source-hash checked compatibility changes make optional printing, discovery, Docker, power-profile, Chromium, mise, Bluetooth and firewall setup conditional on the corresponding installed package. The deferred Bluetooth leaf returns successfully when BlueZ is absent and preserves native enable/start behaviour when installed. Missing mandatory desktop services still fail. No installed Omarchy-owned file is edited outside package installation. The upstream default package list is retained: an explicit full package reinstall can restore it.

`dev-workstation-preferences` applies Foot size 16, host-owned idle/locking and the existing GPU-preserving Hyprland repair once for a new graphical owner. Nano is retained as a recovery editor and selected through Omarchy's editor state only when that state is absent. It runs as that owner after Try Omarchy's session setup. A failed application does not write the completion marker. Theme and app layout remain explicit per-workstation choices. No hostname, credential, personal configuration, SSH identity or regular user is embedded.

The foundation includes the native desktop's Herdr/Udiskie autostart commands,
socat shell IPC, ImageMagick background inspection and inotify-tools watchers.
They are desktop runtime dependencies rather than optional developer features.
The developer foundation includes Git, Python and Arch's standard `base-devel`
toolchain (including GCC, make and the linker), plus `yay` for native AUR updates.
The locally built image packages can trigger that path even before any optional
apps are selected. Dependency resolution checks these roots, and the isolated
owner check runs `yay`, `makepkg`, `gcc`, `make` and `fakeroot` with `--version`,
then compiles, links and runs a small C program as the synthetic owner. These
checks run without a network update or AUR build. Additional language runtimes
remain independently selected through the developer playbooks.
The native VirGL integration includes the hash-guarded Hyprland 0.57 alpha-format
setting before the first compositor starts. Preferences package 1-2 explicitly
orders first-login work after the graphical target and native session, avoiding
the earlier cycle that caused systemd to skip it.

The Node tarball is staged for upstream offline owner finalization; it is not installed as a selected developer runtime. Other packages may contain static assets or support binaries: the exclusion policy addresses installed packages, rather than claiming the filesystem contains no language-related code.

## Artifact contract for VM Manager

Each successful build produces:

| Artifact | Purpose |
| --- | --- |
| `omarchy-workstation-aarch64-edge.img.zst` | Compressed factory disk |
| `factory.json` | Existing format 1, `upstream-shell-factory`, `aarch64`, `uefi-limine`; compressed/raw disk digests and size |
| `packages.txt` | Actual installed package versions |
| `base.packages`, `excluded.packages` | Effective required roots and exclusions for this build |
| `packages/*.pkg.tar.zst` | Matched Omarchy runtime/settings, integration and workstation preferences |
| `compatibility.json` | Installed owner script hashes, package closure and explicit validation status |
| `source-compatibility.json` | Original/patched provisioning script hashes |
| `provisioning-check.json` | Controlled optional-source behavior checks |
| `user-provisioning-check.json` | Actual per-user finalization, preferences and Foot checks in an isolated snapshot |
| `user-provisioning.log` | Synthetic account's isolated chroot test log |
| `package-resolution.json` | Pre-disk dependency closure result |
| `resolved-repository-packages.txt` | Pre-disk version resolution, including the four local packages |
| `repositories/*.db` | Repository metadata used for pre-disk resolution |
| `image-build.json` | Source/input identities, minimal package profile, builder image digest and unproven compatibility flags |
| `SHA256SUMS` | Checksums for the complete output bundle |

The package-only check produces the package/report subset and no `factory.json` or disk. Input-derived directory names are separated from the disk's actual digest. Rebuilding can produce another disk identity because filesystem IDs, keys and timestamps are generated. Omarchy source, recipes and offline Node are locked; Arch repositories and kernel/graphics packages remain live. Exact reconstruction additionally requires archiving all resolved binary packages. The recorded metadata does not promise a frozen repository or byte-identical builds.

VM Manager owns factory import/admission and creation-time selection. The current pinned integration commit is `85f5e561e5a277ccec08d7725c8714cb090c9011`, compatible with the installed 0.9.3 manager and its reviewed `lean-e4fffc6` owner contract. Path-based bootstrap reads the installed app's runtime lock and lean contract to describe a verified private snapshot, then invokes native `factory-import` only after proposal confirmation. A source/package/owner-program mismatch stops preparation; imported manifests remain subject to the manager's full runtime and admission checks. Older artifacts are preserved and may require rebuilding for the installed runtime. The [43.1 acceptance record](omarchy-lean-43-validation.md) covers the earlier 0.9.2 source pin; the current pinned image's installed-app validation is recorded below. Never substitute these bytes in the official cache or bypass kit verification with environment variables.

The bundled archive exports only `guest/` and `LICENSE` from the recorded integration commit, under the included MIT license. Its guest tree (`aa461dab54d5d6625537ef506259d4e5155c83ba`) is identical to the earlier `1ecd8499d271cd761e8b4be0e49747de96e57768` input. Maintainers updating it must review the guest changes, export those paths with `git archive --format=tar.gz COMMIT guest LICENSE`, and update the commit, archive SHA-256 and guest tree in `inputs.lock.json`. Host runtime sources and binaries are excluded. Normal users need neither that checkout nor Git to consume the bundled build source.

## Acceptance and updates

For an older lean image that stops at `omarchy-update-aur-pkgs` with
`yay: command not found`, follow the [existing-VM recovery steps](omarchy-bootstrap.md#recover-an-older-lean-image-missing-yay).
Rebuild the foundation with `make build-omarchy-image` before creating new VMs.
Rebuilding changes `latest`; it does not repair an existing VM.

The builder checks the installed package closure and graphics policy, actual patched scripts, boot/provisioning markers and absence of regular users. It runs upstream system setup in the image chroot. It then creates a separate writable Btrfs snapshot, creates a synthetic account only there, runs the actual upstream user finalizer and first-owner preferences, and checks Foot's configuration. It deletes that test snapshot before sealing; the factory never contains the account. These checks do not prove the owner wizard/unattended adapter, a successful graphical boot or real GPU rendering. A chroot test is not a full first-boot test. Output manifests explicitly retain these distinctions.

Before admitting this image, use separately authorized disposable manager guests to verify manual/unattended owner setup, independent identities, authenticated SSH, Foot preferences, hardware rendering in Hyprland and Quickshell, clipboard, Retina resizing, restart and factory reset. Reject `llvmpipe`, `softpipe` and forced software backends. Do not reuse existing VM disks for acceptance.

Omarchy retains its normal update channel. A future upstream runtime package can replace the temporary provisioning guards, and a future integration package can restore renderer policies. This initial build milestone does not promise that those changes remain minimal across future updates. Revalidate the package closure, provisioning, rendering and integration after updates; refresh the explicit source lock/patches together until upstream supports optional setup directly. No package holds, background removals or replacement updater are installed.

## Repository validation

```bash
make test-omarchy
PYTHONPYCACHEPREFIX=/tmp/dev-vm-image-pycache python3 -m py_compile \
  scripts/omarchy_image.py omarchy/image/compatibility.py omarchy/image/check-provisioning.py
bash -n omarchy/image/build-container.sh omarchy/image/preferences/first-login.sh \
  omarchy/image/preferences/preferences.install omarchy/image/preferences/PKGBUILD \
  omarchy/image/check-user.sh
```

The source fixtures in `tests/fixtures/omarchy-image/` come from the exact upstream revisions in `inputs.lock.json` (Try's builder, its pinned Hyprland integration policy and Omarchy's six provisioning files). Their MIT licenses are reproduced at `omarchy/image/UPSTREAM-LICENSE` and `omarchy/image/OMARCHY-LICENSE`.

Build-only validation on 1 November 2026 on Apple Silicon: 134 repository tests, the documented shell/Python syntax checks, the package-only compatibility target and a complete host-backed factory build passed. The build contains 568 installed packages and compresses to approximately 1.61 GiB. System provisioning, strict user-finalization log checks, preference reapplication, Foot configuration, AUR tool availability, a non-root C compile/link/run check, exclusions and identity sealing passed. A PCI hardware probe reports the expected missing Docker-kernel module resources in the chroot; hardware validation remains a real-VM requirement. That build launched no VM and changed no VM Manager state.

## Installed-app image acceptance — 1 November 2026

The full build completed in 132 seconds with reads from the VM Manager checkout
and prepared runtime-source directories denied by a sandbox. All 24 published
checksums passed, as did independent decompression, byte-count and SHA-256
verification of the 20 GiB disk. The artifact is
`.artifacts/omarchy-image/3ca761375f6db785-20cac2aa99021d9c`.

| Identity | SHA-256 |
| --- | --- |
| Raw disk | `20cac2aa99021d9cdb2bf5b6f85692334e03f70662569ff783287be5e3f66ac7` |
| Compressed image | `da31a3b8a737cab7f9aa84b195bd46e90259be5b1f6f4f3e0f6e890806b9dc9b` |
| Imported manifest | `714ea1cdb9d0321f52fcbc6c26ec1b5807b6d07e35d86f11f43a498a83e02dfc` |

The installed 0.9.3 (16) app/CLI admitted the factory and booted exactly one new
disposable guest with saved owner defaults, 4 CPUs, 4 GiB RAM and a 64 GiB disk.
Unattended owner setup, pinned SSH, root growth, native first-boot services and
the repository workstation check passed without guest updates or optional app
installation. GLX reported accelerated `virgl (Apple M5 Max)`; Hyprland and
Quickshell had no forced software-rendering environment. System and user
failed-unit counts were zero.

Native macOS window zoom changed the guest resolution from 2688×1512 to
3600×2196 while retaining scale 2. The operator manually verified clipboard
copy/paste in both directions after automated clipboard probes were
inconclusive. DNS and HTTPS passed. A manager-owned restart produced new
kernel/runtime sessions and retained SSH pins, package inventory and preference
hashes; renderer, Retina, networking and service checks passed again.

The disposable guest was gracefully stopped and moved to the manager's
recoverable Trash. Its runtime processes were gone, and all five pre-existing
VMs retained their configurations and active states. The imported factory
remains available. Evidence is under the ignored
`.artifacts/omarchy-image/checkout-free-50m9w4ij/live-vm/` directory, with
`acceptance.json` recording scope and limits. Original build manifests and
checksums remain unchanged; live acceptance is recorded separately.

Audio/camera bridge services and devices were present, but playback/capture,
an independent Quickshell QRhi trace, movement between host displays, factory
reset, manual owner setup, sleep/wake and forced-interruption tests were not
performed.

## Live developer bootstrap — 1 November 2026

A separately authorized test used VM Manager 0.9.3 (16), exactly one new
disposable ARM64 guest and the rebuilt foundation with `base-devel` and `yay`.
The factory's complete published checksum inventory passed before bootstrap.

| Identity | SHA-256 |
| --- | --- |
| Raw factory disk | `877a32ceec343b22ce64e1cc5e0785d48789c008209bf8ae88f19387e4a59de6` |
| Compressed factory | `fee5cb5805757e549015faeb02d03a0690f79551ebeaefc8abbdc75afe29e4c5` |
| Imported manifest | `89e75163dc5447fd8c2d31f571316fbce7573bc83eaeee74c62bfed816c83103` |

Bootstrap used 8 CPUs, 20 GiB RAM, a 64 GiB disk, saved owner defaults,
`pkg:visual-studio-code-bin,pkg:chromium`, `vscode-browser.lua` and
`most-starred`. The selector chose Aetheria (122 stars), at theme commit
`dcf698e2a16226b8ec8b5a70fe8b1fd153daf0d7`.

Native unattended owner setup and authenticated pinned SSH passed. The test
was paused for the operator to authorize native temporary sudo inside the
guest. Omarchy's settings upgrade revoked that grant, requiring a second
native authorization before app installation. No saved password was read or
logged. The resumed `make bootstrap-omarchy-vm` exited successfully, including
the native AUR update, selected app installation, theme/preferences, manager
restart and workstation checks. Runtime/settings updated normally to
`4.0.0.r7519.gd367a56-1`; integration remained `0.1.0-43.1`.

An additional live window check found VS Code 1.144.0 uses native Wayland class
`com.microsoft.VSCode`, which the original `code` rule missed. The example now
matches both native Wayland and XWayland classes for its rule and launch/focus
command. The corrected layout was reapplied through the existing customization
controller, followed by another native restart; update/install were already
complete and no additional sudo grant was needed.

After that restart, both windows were floating on workspace 1: VS Code at
`(12,38)` with size `1470×1345`, Chromium 156.0.8078.79 at `(1494,38)` with size
`974×1345`. This matches the 60/40 expressions on a `4960×2790` display at native
scale 2. Hyprland reported no config errors; accelerated GLX reported
`virgl (Apple M5 Max)`. Foot, host idle policy, clipboard-channel presence,
non-root C compile/link/run, changed boot identity, zero failed system/user
units and inactive temporary sudo all passed. All 134 repository tests and
the documented shell/Python syntax checks passed after the layout fix.

Evidence and the screenshot are in the ignored
`.artifacts/bootstrap-validation/disposable-lean-code-20261101-5b26f6/` directory.
Both pre-existing guest inventories matched their baseline. The disposable VM
was gracefully stopped and retained. Artifact manifests were not relabelled as
validated. Functional clipboard routing, dynamic resizing, browser WebGL and
broader manager acceptance remain separate checks.
