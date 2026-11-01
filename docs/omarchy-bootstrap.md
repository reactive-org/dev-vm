# Bootstrap reference

The [quick starts](../README.md#quick-start) assume an existing manager app/CLI,
Git, Python 3 and make on an Apple Silicon Mac. Ansible is required for the
optional feature playbooks. Host tools are installed separately.

Open the installed **Omarchy VM Manager.app** and save **Guest Defaults** for
the owner account, password, keyboard, timezone and hostname prefix. The password
remains in the Mac login Keychain. Run setup commands from the dev-vm repository
root. No VM Manager source checkout or local app build is required.

The controller finds `omarchy-vm` on `PATH`, then the bundled CLI in
`~/Applications/Omarchy VM Manager.app` or `/Applications/Omarchy VM Manager.app`.
Set `OMARCHY_VM_MANAGER_APP=/absolute/path/Omarchy VM Manager.app` for another
installed location, or `OMARCHY_VM_MANAGER_CLI=/absolute/path/to/omarchy-vm` for
an explicit CLI. When that CLI is a wrapper rather than the bundled executable
or a symlink to it, also set `OMARCHY_VM_MANAGER_APP` for lean factory preparation.

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

Bootstrap verifies a private snapshot and describes repository build outputs
using the installed app's runtime inventory and reviewed lean owner contract.
The image's integration source, package and owner-program hashes must match that
app. After showing the source/identity in the proposal and receiving
confirmation, bootstrap invokes native `factory-import`, checks the returned
identity, then creates the VM. No hash copying or manual import is required.
The manager remains responsible for factory admission and runtime verification.

After bootstrap's restart, the manager can briefly report
`ssh-connection-unavailable` during its final pinned identity probe even though
the new session is running. Bootstrap retries only the manager's read-only
`wait --for ssh` for that same VM/session, with up to five delayed retries
within the original timeout. It never repeats the restart or relaxes SSH pins.
Other errors, a changed session or exhausted retries still stop setup and leave
the VM available for inspection. For a retained running guest, use
`make check-omarchy-vm VM_NAME="your VM name"` once managed SSH is ready; then
apply any features that bootstrap did not reach.

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
authenticated, pinned SSH connection. The controller then clears any older native
grant and cached sudo authorization, asks you to confirm Omarchy's prompt and
enter the guest sudo password once, and enables `omarchy sudo passwordless permanent`.
This native grant survives long runs and settings-package updates. It uses the grant
to update Omarchy and the guest system through `omarchy update -y`, install the
selected guest software through Omarchy and mise, and apply the small idempotent
preference layer. It disables the grant, clears cached sudo authorization and
verifies that passwordless sudo is inactive before rebooting the guest through the
manager, waits for managed SSH to return, validates hardware VirGL and integration,
and removes its temporary payload. It never installs host software, captures guest passwords, scans personal
SSH files, or replaces or resets an existing VM.
New guests request a 64 GiB sparse disk by default; an existing stopped guest
can grow to that capacity but is never shrunk. Override with
`OMARCHY_VM_DISK_GIB=128` when more space is needed.

## Recover an older lean image missing yay

Older lean factories omitted the AUR helper and build prerequisites. Omarchy's
native update can reach its AUR step because the image includes locally built
packages, then stop with `yay: command not found`. Bootstrap attempts to restore
default sudo authentication after that failure; resolve any cleanup warning before retrying.

In a terminal inside the affected guest, install the missing tools through
Omarchy (enter the guest sudo password when prompted):

```bash
omarchy-pkg-add yay base-devel
```

Then rerun bootstrap from this repository on the Mac, using the existing VM's
exact name and the same software, theme, layout and resource selections. Omit
`OMARCHY_VM_FACTORY` to preserve its admitted factory, especially if `latest`
has since been rebuilt. For example:

```bash
make bootstrap-omarchy-vm VM_NAME="Dev Omarchy" \
  OMARCHY_VM_PACKAGES=pkg:visual-studio-code-bin,pkg:chromium \
  OMARCHY_VM_LAYOUT_FILE=omarchy/examples/layouts/vscode-browser.lua \
  OMARCHY_VM_THEME=most-starred
```

Bootstrap retries the native update before applying the selected setup and
restarting/checking the VM. A rebuilt image is used only for new VMs; it does
not replace the existing VM or its disk.

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

Bootstrap also attempts to restore default sudo authentication on setup errors,
Ctrl+C, SIGTERM and SIGHUP, including a partially completed enable operation.
Cleanup uses the native `--disable`, clears cached sudo authentication with
`sudo -K`, and requires the native policy probe to report inactive. A cleanup
failure is reported and prevents a successful setup from continuing to reboot.
The grant uses Omarchy's `permanent` mode only for the setup window: it has no
automatic expiry and survives reboots. If the host process is killed outright
or managed SSH is unavailable, revoke it in a guest terminal:

```bash
omarchy sudo passwordless --disable && sudo -K
```

The controller never captures the password or writes its own sudoers rules.
`OMARCHY_VM_YES=yes` skips the host proposal confirmation; the one native grant
confirmation and initial password prompt remain interactive. Guests must support
Omarchy's native `permanent` mode; unsupported or declined authorization stops
setup before the update or customization steps. Bootstrap does not fall back to
an expiring grant.

Bootstrap adds no optional software by default. After the guest is ready, use
`make apply-playbook` to select browsers, Docker, languages, coding agents and
credential applications independently. This keeps creation of a lean workstation
separate from its developer-specific software selection.

CLI discovery and explicit installed-app/CLI paths are described above.
Shared folders and general port forwarding are not currently part of the
manager's CLI contract.
