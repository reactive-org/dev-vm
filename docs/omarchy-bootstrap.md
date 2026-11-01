# Bootstrap reference

The [quick starts](README.md#setup-runbooks) assume an existing manager app/CLI,
Git, Python 3 and make on an Apple Silicon Mac. Ansible is required for the
optional feature playbooks. Host tools are installed separately.

If preparing an existing sibling manager source checkout, build and verify it
without installing it globally:

```bash
cd "../Omarchy VM Manager"
make app verify-app
```

Open `dist/Omarchy VM Manager.app` and save **Guest Defaults** for the owner
account, password, keyboard, timezone and hostname prefix. The password remains
in the Mac login Keychain. Return to the dev-vm repository root before running
the setup commands. The default CLI is the sibling checkout's
`bin/omarchy-vm`; its path can be overridden as described below.

## Choose a starting image

Use either the official Try Omarchy factory or a compatible custom Omarchy
ARM64 factory admitted by VM Manager. Choose one command for a new VM:

```bash
make bootstrap-omarchy-vm VM_NAME="Dev Omarchy" OMARCHY_VM_FACTORY=official
```

For BYO, pass a successful build directory, its compressed image with companion
metadata, or a prepared factory bundle. Bootstrap handles preparation and import:

```bash
make build-omarchy-image
make bootstrap-omarchy-vm VM_NAME="Dev Omarchy" \
  OMARCHY_VM_FACTORY=.artifacts/omarchy-image/latest
```

For another compatible image, set `OMARCHY_VM_FACTORY=/path/to/factory.img.zst`
(or a prepared bundle directory). A standalone disk without its factory metadata
and provisioning evidence is insufficient. Keep the image and companion files
together. Existing prepared bundles retain their exact descriptor and hashes.

Bootstrap verifies a private snapshot and uses the manager checkout's existing
`Scripts/prepare_factory_bundle.py` for repository build outputs. After showing
the source/identity in the proposal and receiving confirmation, it invokes native
`factory-import`, checks the returned identity, then creates the VM. No hash
copying or manual import is required. `OMARCHY_VM_MANAGER_DIR` selects the existing
manager checkout containing the preparation helper when it lives elsewhere.

Already-imported manifest SHA-256 selectors are still accepted. Add the same app,
theme and layout options to either image choice; those are per-VM selections.

## Bootstrap behaviour

The controller hands the VM lifecycle to the manager's
[JSON CLI](https://github.com/reactive-org/omarchy-vm-manager/blob/main/docs/CLI.md):

```bash
make bootstrap-omarchy-vm VM_NAME="Dev Omarchy"
```

Before changing anything, the controller verifies Omarchy VM Manager 0.6.0 or
newer with command protocol 1, inventories the exact named profile, rejects
protected or incompatible guests, and prints the complete proposal for
confirmation. The manager creates or starts the guest and waits for its own
authenticated, pinned SSH connection. The controller then enables Omarchy's
native 60-minute passwordless-sudo grant over that connection, asking you to
confirm Omarchy's prompt and enter the guest sudo password. It uses the grant
to update Omarchy and the guest system through `omarchy update -y`, install the
selected guest software through Omarchy and mise, and apply the small idempotent
preference layer. It disables the grant before rebooting the guest through the
manager, waits for managed SSH to return, validates hardware VirGL and integration,
and removes its temporary payload. It never installs host software, handles guest passwords, scans personal
SSH files, or replaces or resets an existing VM.
New guests request a 64 GiB sparse disk by default; an existing stopped guest
can grow to that capacity but is never shrunk. Override with
`OMARCHY_VM_DISK_GIB=128` when more space is needed.

## Resource and preference overrides

Pass these make variables to bootstrap and use the same resource values for
`make check-omarchy-vm`:

| Variable | Default | Purpose |
| --- | --- | --- |
| `VM_NAME` | `Dev Omarchy` | Exact managed guest name |
| `OMARCHY_VM_FACTORY` | Omitted | Official for new VMs; preserve an existing VM's factory |
| `OMARCHY_VM_CPUS` | `8` | Guest CPU count |
| `OMARCHY_VM_MEMORY_GIB` | `20` | Guest RAM in GiB |
| `OMARCHY_VM_DISK_GIB` | `64` | Guest disk capacity in GiB; grow only |
| `OMARCHY_VM_WAIT_TIMEOUT` | `3600` | Bootstrap readiness timeout in seconds |
| `OMARCHY_VM_FOOT_FONT_SIZE` | `16` | Foot font size |
| `OMARCHY_VM_IDLE_MODE` | `host` | `host`, `guest` or `keep` idle policy |

For example, when the Mac's guest budget calls for a smaller allocation:

```bash
make bootstrap-omarchy-vm VM_NAME="Dev Omarchy" \
  OMARCHY_VM_CPUS=4 OMARCHY_VM_MEMORY_GIB=8
make check-omarchy-vm VM_NAME="Dev Omarchy" \
  OMARCHY_VM_CPUS=4 OMARCHY_VM_MEMORY_GIB=8
```

The controller accepts at least 4 CPUs and 4 GiB RAM; the manager also checks
host capacity. Active guests with mismatched resources must be stopped through
the manager before bootstrap can update them. For a custom factory, pass its
build/image/bundle path or an already-imported manifest SHA-256 in
`OMARCHY_VM_FACTORY`. Native VM Manager import and creation own admission and
factory selection. A mismatch on an existing VM is refused before import or VM
mutation; choose a new name instead. Import/preparation failures never fall back
to another image. Omission uses official for a new VM and preserves an existing
VM's factory.

See the [removal profile](omarchy-lean-developer.md),
[themes](omarchy-themes.md) and [layouts](omarchy-layouts.md) for their optional
overrides. Bootstrap selects no additional software unless
`OMARCHY_VM_PACKAGES` is supplied.

## Privilege and cleanup

Bootstrap also attempts to disable the grant on setup errors, Ctrl+C, SIGTERM,
and SIGHUP, including a partially completed enable operation. A cleanup failure
is reported, and prevents a successful setup from continuing to reboot. If the
host process is killed outright or managed SSH is unavailable, Omarchy's native
60-minute expiry and reboot cleanup provide the fallback. To revoke manually,
run `omarchy sudo passwordless --disable` in a guest terminal. The controller
never captures the password or writes its own sudoers rules.
`OMARCHY_VM_YES=yes` skips the host proposal confirmation; Omarchy's native grant
confirmation and initial password prompt remain interactive.

An Omarchy settings-package upgrade can revoke temporary sudo grants early;
subsequent privileged steps may then ask for authentication again. Bootstrap
respects that native revocation and does not renew or extend the 60-minute grant.

Bootstrap adds no optional software by default. After the guest is ready, use
`make apply-playbook` to select browsers, Docker, languages, coding agents and
credential applications independently. This keeps creation of a lean workstation
separate from its developer-specific software selection.

The default CLI path is the sibling checkout at
`../Omarchy VM Manager/bin/omarchy-vm`. Override
`OMARCHY_VM_MANAGER_CLI=/absolute/path/to/omarchy-vm` when the manager lives
elsewhere. Shared folders and general port forwarding are not currently part
of the manager's CLI contract.
