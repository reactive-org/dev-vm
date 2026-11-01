# Minimal Omarchy factory

`make build-omarchy-image` builds an opt-in ARM64 desktop foundation for Apple Silicon and Omarchy VM Manager. It never invokes the manager, launches QEMU, accesses a guest disk, replaces a factory cache or installs host software. Bootstrap accepts its path in `OMARCHY_VM_FACTORY` and coordinates preparation/import through VM Manager; omission keeps the official default for new guests.

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
checks a private snapshot, prepares the bundle with the manager's helper when
needed, and imports through the native CLI only after proposal confirmation.

Optional preview and package-only checks:

```bash
make build-omarchy-image OMARCHY_IMAGE_PLAN=yes
make check-omarchy-image
```

The default is the matching existing manager checkout's prepared
`.build/runtime-source`, resolved to a real path, at `managed_try_commit` in
`inputs.lock.json`. The builder verifies the clean checkout, exact commit,
reviewed builder hash and baseline ancestry. It never prepares/downloads manager
source automatically. Set `OMARCHY_VM_MANAGER_DIR` for another existing manager
checkout. Use the [short build guide](omarchy-layout-factory.md) and
[import/bootstrap handoff](omarchy-layout-factory-reference.md) for the complete flow.

The preview validates a clean local Try checkout and prints the proposal without creating artifacts, running Docker or downloading anything. The compatibility check builds the versioned guest packages, executes the patched optional provisioning leaves with controlled commands, and checks the dependency closure against the live repositories. It runs without privileged Docker access or a disk. The image build repeats these checks and then runs the adapted upstream builder in a privileged ARM64 container for loop devices and mounts. Successful artifacts are published atomically into a new directory. Failed stages remain under `.artifacts/omarchy-image/.building-*` for inspection; they are never a successful factory.

Docker must already be installed and running with an ARM64 Linux engine. The first build downloads checksum-pinned guest source archives and an offline ARM64 Node payload, then creates a guest build container. Subsequent runs reuse verified source downloads, Docker's build cache and guest package archives under `.artifacts/omarchy-image/package-cache/`; pacman still verifies signatures. Each run uses a uniquely named, repository-labeled work volume, removed after its own container exits. No other Docker volume or container is removed. Builds in this repository are serialized.

The new sparse raw disk and filesystem work live in the unique host artifact stage mounted at `/factory-work`; source/package scratch uses the isolated Docker volume. This avoids filling Docker Desktop's virtual disk during Btrfs balance. The host artifact volume must have the requested disk size plus 4 GiB free, and Docker needs at least 3 GiB for source/package scratch. The workflow never prunes unrelated Docker data or changes Docker Desktop's settings.

The default source is the manager's prepared runtime checkout at the reviewed managed commit. Explicit source overrides:

```bash
make build-omarchy-image \
  OMARCHY_IMAGE_TRY_SOURCE=/absolute/path/to/try-omarchy \
  OMARCHY_IMAGE_TRY_COMMIT=EXACT_REVIEWED_40_CHARACTER_COMMIT \
  OMARCHY_IMAGE_SIZE_GIB=20
```

An alternate integration checkout must be clean, descend from the pinned v1.3.0 commit and retain the exact reviewed factory builder. This supports the manager's separately reviewed integration sources without modifying that checkout. The chosen integration commit is recorded. The workflow changes only an isolated exported copy. It bumps the integration package release, removes the Ghostty/Kitty software-rendering launch paths and rejects remaining forced software settings. VM Manager 0.9.2 supplies package 43; its reviewed source produces the newer hardware-policy variant 43.1, which the native package installer preserves. A later integration update still requires revalidation.

Git source exports and downloaded archives are normalized to checkout permissions before packaging: directories and executable files use 0755, other files use 0644, and symlink targets are left alone. Git archives can contain group-writable modes; recipes using `cp -a` would otherwise preserve them into the guest. The image audit rejects writable, foreign-owned or linked canonical owner programs, and writable/non-directory parents. Manager integration adapters and contract files receive the same checks when present. Program bytes and their reviewed hashes remain unchanged.

## Foundation and provisioning

`omarchy/image/base.packages` declares required roots. `excluded.packages` rejects optional applications even when dependencies would bring them back. The preflight creates a temporary local repository for the four built packages and asks pacman to resolve the profile, those packages and their optional integration dependencies against an empty installation database. Builder-installed tools cannot conceal missing runtime dependencies, and local package versions/provides are checked normally. A missing root, excluded transitive package or repository error fails the build. Pacman's installed dependency and repository-signature checks remain enabled. As in Try's packaging-only build, `makepkg --nodeps` packages the source without installing the runtime into the builder; the separate resolver and actual image installation check those runtime dependencies. Kernel headers, DKMS and native integration input methods remain even though some host features are not enabled in VM Manager.

The disk preserves Try Omarchy's default 20 GiB sparse GPT layout, 2 GiB FAT32 ESP, ARM64 UEFI fallback, Limine/UKI, Btrfs subvolumes and read-only `@factory` snapshot. Image-target hardware/keyring initialization and owner creation remain deferred to first boot. The upstream builder removes machine identity, random seed, SSH host keys, pacman keyring and package cache before compression.

The pinned Omarchy runtime and settings are rebuilt together from source as package release `1.1`. Six source-hash checked compatibility changes make optional printing, discovery, Docker, power-profile, Chromium, mise, Bluetooth and firewall setup conditional on the corresponding installed package. The deferred Bluetooth leaf returns successfully when BlueZ is absent and preserves native enable/start behaviour when installed. Missing mandatory desktop services still fail. No installed Omarchy-owned file is edited outside package installation. The upstream default package list is retained: an explicit full package reinstall can restore it.

`dev-workstation-preferences` applies Foot size 16, host-owned idle/locking and the existing GPU-preserving Hyprland repair once for a new graphical owner. Nano is retained as a recovery editor and selected through Omarchy's editor state only when that state is absent. It runs as that owner after Try Omarchy's session setup. A failed application does not write the completion marker. Theme and app layout remain explicit per-workstation choices. No hostname, credential, personal configuration, SSH identity or regular user is embedded.

The foundation includes the native desktop's Herdr/Udiskie autostart commands,
socat shell IPC, ImageMagick background inspection and inotify-tools watchers.
They are desktop runtime dependencies rather than optional developer features.
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

VM Manager owns factory import/admission and creation-time selection. Version 0.9.2 retains the reviewed `lean-e4fffc6` owner contract alongside the preserved official contract and fixes completion reporting after host cleanup. Managed lean setup uses integration commit `1ecd8499d271cd761e8b4be0e49747de96e57768`, producing package 43.1. Path-based bootstrap invokes the existing manager preparation helper with `--owner-contract lean-e4fffc6`; the manual equivalent remains in the manager's `docs/LeanOwnerSetup.md`. Use the resolved `.build/runtime-source` checkout, since the builder rejects symlink sources. An explicit stock-source build or older 36.1/41.1 artifact is not a substitute for this managed source. See the [43.1 acceptance record](omarchy-lean-43-validation.md) for observed results and remaining checks. Never substitute these bytes in the existing official cache or bypass kit verification with environment variables.

## Acceptance and updates

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

Validated on 1 November 2026 on Apple Silicon: 99 repository tests, the documented syntax checks, the package-only compatibility target and a complete host-backed factory build passed. The build contains 526 installed packages and compresses to approximately 1.56 GiB. System provisioning, strict user-finalization log checks, preference reapplication, Foot configuration, exclusions and identity sealing passed. A PCI hardware probe reports the expected missing Docker-kernel module resources in the chroot; hardware validation remains a real-VM requirement. No VM was launched and no VM Manager state was changed.
