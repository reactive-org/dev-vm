# NixOS ARM64 Parallels workstation prototype

This prototype implements issue #1's minimal workstation and application modules. It uses upstream Nix,
an explicitly locked `nixos-unstable` input, the stock NixOS Parallels guest
module, systemd-networkd, greetd/agreety, Hyprland with UWSM, Kitty, PipeWire,
matching Hyprland portals and JetBrains Mono. The Ubuntu Make targets continue
to provision Ubuntu. See [automation](AUTOMATION.md) for unattended installation,
`make apply-nixos`, checks, private local inputs and recovery.

See [the validation record](VALIDATION.md) for measured results and outstanding
acceptance tests. The user passed the focused clipboard and suspend/resume
checks on Parallels 27.1.0, and accepted long-term reliability as an assumption
to proceed to Phase 2. Several-hour reliability is not recorded as a measured pass.
Chrome→Kitty and Claude Desktop→Kitty subsequently passed the user's focused
copying checks, including delayed paste.

## Workstation applications and user configuration

The host imports small modules for durable applications, Docker and Home
Manager. They provide Firefox, official ARM64 Google Chrome, VS Code, mise,
GitHub CLI, Claude Code, Claude Desktop, 1Password desktop/CLI, and developer
utilities. Nix owns these packages; mise owns project language runtimes. Docker
includes Buildx and Compose. Docker group membership gives administrative
control over the guest and takes effect in a new login session.

Home Manager manages Zsh with Oh My Zsh and Powerlevel10k, direnv, fzf, zoxide,
mise shell activation, Git/LFS, Kitty, Waybar, fuzzel, mako, GTK fonts and
clipboard history. JetBrains Mono is used throughout; MesloLGS NF is available
for the prompt. An existing mutable `~/.p10k.zsh` is sourced when present.
Conflicting unmanaged dotfiles are backed up with `.before-home-manager`;
existing backups are not silently overwritten.

The fixed monitor and session launcher remain in the system module. User
bindings live in Home Manager's `~/.config/hypr/workstation.lua`. The launcher
uses `start-hyprland` with the NixOS capability wrapper and reads
`/etc/xdg/hypr/hyprland.lua`, so subsequent rebuilds can be followed by
`hyprctl reload`. The first upgrade from the Phase 1 launcher needs one guest
login-manager restart (or reboot): greetd keeps its original command in memory
across normal logouts. Save work before `sudo systemctl restart greetd`, which
closes desktop applications and returns to the login prompt. Future logins
resolve stable `/etc/greetd/workstation-login` and `workstation-session` paths.
Moving from the legacy `.conf` backend to Lua requires one logout/login;
Hyprland selects its configuration backend at startup. Lua avoids the deprecated
format warning, and `start-hyprland` supplies the supported watchdog startup.
See the [upstream configuration documentation](https://wiki.hypr.land/configuring/core/)
and [pinned launcher source](https://github.com/hyprwm/Hyprland/blob/v0.56.2/start/src/main.cpp).

Shortcuts use Option+Command (`ALT SUPER`): Return opens Kitty, Space opens
fuzzel, B opens Chrome, Shift+B opens Firefox, C opens VS Code, E opens Nautilus,
V toggles floating, L locks, P opens clipboard history, and Shift+S selects a
screenshot. Arrow keys focus windows, Shift+arrows move them, and 1–9 select
workspaces. Shift+1–9 move a window to that workspace. Shift+E exits the session.

Claude Code configuration supports Home Manager's non-secret options. Its
authentication state remains mutable. No host dotfiles, private keys, tokens
or application sessions are copied by these modules. Explicit file provisioning
and a local override input are described below.

Sign into applications yourself. In 1Password, enable the protected desktop
and CLI integration settings manually; browser extensions also require setup.
The background app starts with the graphical session. Claude Desktop's OAuth
URI handler is registered, but authentication and account workflows require
interactive validation. Cowork is not configured: the numtide package's
official app and FHS wrapper are retained with its added firmware and
virtiofsd omitted. No KVM, QEMU or nested virtualization is enabled for it.

## Create and install a fresh VM

On the Apple Silicon Mac with Parallels Desktop 27:

```bash
make bootstrap-nixos \
  VM_NAME="NixOS Workstation Test" \
  IMAGE="$HOME/Downloads/nixos-graphical-26.05.13050.08d3a97586f6-aarch64-linux.iso"
```

The proposal requires typing `create`. Defaults are four CPUs, 12288 MB memory,
a 24 GB expanding disk, shared networking, EFI ARM64, virtio graphics,
bidirectional clipboard and UTC time synchronization. Override `CPUS`,
`MEMORY_MB` and `DISK_GB` if needed. Broad sharing, nested virtualization,
Rosetta and automatic vendor Tools updates are disabled. NixOS owns Tools.
An existing VM is refused, including one left by a partially failed creation;
inspect that VM in Parallels rather than rerunning against it blindly.

After confirmation and a private password prompt, the command remasters the
upstream ISO and installs the workstation unattended. It waits for installation
poweroff, detaches the ISO, boots the disk, verifies SSH/account security, and
applies the captured source with full checks. The installed package set comes
from `flake.lock`, independently of the live ISO's package versions.

The target does not create `~/Parallels/Shared`. If it exists, the host workflow
configures that explicit read-write share; otherwise it prints a hint and
leaves sharing disabled. The proposal includes the guest mount/FUSE policy;
`NIXOS_SHARE=no` disables it for the automated installation.

The Tools package is overridden to the hash-pinned official **27.1.0 (58756)**
release to match the current test host, without advancing the nixpkgs lock.
Keep host and guest Tools builds aligned when repeating integration tests.

## Manual installation and recovery

The following live-ISO steps are a separate fallback, not required by
`make bootstrap-nixos`. To create hardware and boot a regular ISO manually,
run `bash scripts/bootstrap-nixos.sh` with its documented positional arguments
or create the disposable hardware in Parallels, then continue below.

### Reach the live system

In a terminal inside the live environment, run:

```bash
uname -m
sudo passwd nixos
sudo systemctl start sshd
ip -4 -brief address
```

Expect `aarch64`. Choose a temporary live-session password yourself. The live
ISO permits SSH password login after this; the installed system disables it.
Use the address of the VM's Ethernet interface, not `127.0.0.1`.

From this checkout on the Mac, transfer only the NixOS source directory:

```bash
scp -r nixos nixos@VM_IP_ADDRESS:/tmp/dev-vm-nixos
ssh -t nixos@VM_IP_ADDRESS
```

No private key or personal configuration is copied. Before installing, optionally
edit `/tmp/dev-vm-nixos/hosts/workstation-test/default.nix` in the guest to set
`workstation.userName`, `networking.hostName` and
`workstation.authorizedKeys = [ "YOUR_SSH_PUBLIC_KEY" ];`. These changes stay in
the guest. Use only a public key; never insert passwords or private keys.
The installer reports the password command for the configured username.
The committed defaults are disposable examples. If you used `ssh-copy-id` to
access the live guest, its authorized public keys are carried into the installed
workstation account through a module generated only in the guest's source copy.

### Install the new virtual disk

Inside the VM:

```bash
lsblk -o NAME,SIZE,TYPE,FSTYPE,MOUNTPOINTS
sudo bash /tmp/dev-vm-nixos/install.sh /dev/sda
```

Use the actual **whole virtual disk** shown by `lsblk`; `/dev/sda` is an example.
The script prints the selected disk and requires typing its full device path
before erasing it. It refuses mounted disks and runs only on an ARM64 live ISO.
It creates a 1 GiB EFI partition and an ext4 root partition, generates this VM's
hardware configuration, and runs `nixos-install --flake` using the existing lock.
The generic virtio hardware profile in source is replaced only in the installed
copy. No swap or disk encryption is configured for this disposable prototype.

The root account stays locked. After installation, run the printed
`sudo nixos-enter --root /mnt -c "passwd developer"` command in the live console
to set the workstation user's password yourself. Passwords remain mutable in
`/etc/shadow` and never enter the flake or Nix store. Sudo requires the user password.
Keep the console accessible if no authorized SSH key was supplied.

When complete, shut down with `sudo poweroff`, disconnect the installation ISO
in Parallels, then boot from the virtual hard disk. Log in at agreety. Hyprland
and Kitty should start. The initial monitor mode is `2560x1600@59.99` at scale 1.
Option+Command+Return opens Kitty; Option+Command+Q closes the focused window;
Option+Command+Shift+E exits the session. Option+Command+V toggles floating.
Configuration is explicitly passed to Hyprland by the login command.

## Validate before adding applications

Inside the installed guest:

```bash
uname -m
sudo systemctl status prltoolsd
systemctl --user status prlcc
systemctl --user status xdg-desktop-portal xdg-desktop-portal-hyprland
hyprctl monitors
hyprctl configerrors
```

Check graphical login, pointer integration, sound, fixed startup resolution,
and authenticated SSH if a key was configured. `prltoolsd` should be active.
The user `prlcc` service should also be active. With matching host and guest
Tools 27.1.0, the user confirmed reliable Kitty→Kitty, macOS→Kitty and
Kitty→macOS copying, including delayed paste. It starts with the graphical
session and retries startup failures while the display environment becomes
available. See [the validation record](VALIDATION.md) for remaining longevity
tests and the separate vendor clipboard-helper crash during shutdown.

### Optional manual clipboard fallback

If the Parallels user bridge is stopped for troubleshooting, transfer **text**
explicitly over SSH from the Mac, using an active Wayland desktop and
authenticated SSH access:

```bash
make clipboard-to-vm SSH_HOST=VM_IP_ADDRESS GUEST_USER=developer
make clipboard-from-vm SSH_HOST=VM_IP_ADDRESS GUEST_USER=developer
```

Copy on the source side, run the corresponding Make target on the Mac, then
paste normally on the destination side. `clipboard-to-vm` reads macOS clipboard
text and replaces the Wayland clipboard once; `clipboard-from-vm` does the reverse.
There is no background synchronizer, clipboard history or periodic restart.
Images, rich text and file transfer are outside this fallback's scope.

The commands require Python 3, macOS `pbcopy`/`pbpaste`, and key-based SSH. They
validate the existing SSH host key; if the new installed guest is not yet known
to your normal SSH configuration, connect using `ssh developer@VM_IP_ADDRESS`
and verify its host key first. `SSH_KNOWN_HOSTS_FILE` can select an existing
separate known-hosts file. No relaxed host-key checks are used. The script
discovers the active Wayland display from the user's systemd environment,
buffers text in memory, and does not log clipboard contents or save them to disk.
A source read failure does not initiate a destination write.

This is an optional manual workaround. Normal automatic copying uses the
stock Parallels user bridge, which passed the focused tests on 27.1.0.

Record pass/fail, exact versions and timestamps for:

| Copy source → destination | Immediate | Delay, clear, paste | Suspend/resume | Several hours |
| --- | --- | --- | --- | --- |
| Kitty → Kitty | | | | |
| macOS → Kitty | | | | |
| Kitty → macOS | | | | |
| Claude Desktop → Kitty | | | | |
| Chrome → Kitty | | | | |

Repeat copies with distinct text. In Kitty, use Ctrl+Shift+C/Ctrl+Shift+V.
Run `clear`, wait, and paste again to test ownership longevity. Do not claim the
full clipboard matrix passes until the application rows have also been tested.
The validation record contains user-confirmed focused passes for every source
above, including delayed paste. The empty table is a template for future runs.
Dynamic resizing is diagnostic only. Shared folders and the guest Tools upgrade
to 27.1.0 were validated. See the validation record for kernel upgrade coverage.

## Explicit host folder

The only intended host share is the existing `~/Parallels/Shared` directory.
Read-write sharing lets the guest read and modify files inside it. Configure
an existing VM deliberately from the Mac:

```bash
make configure-nixos-share VM_NAME="NixOS Workstation Test"
```

The command never creates the host directory, enables broad home/disk sharing
or enables vendor automount. Add `workstation.sharedFolder.enable = true;` to
the installed host's `integration.nix` or private local module and rebuild.
The `workstation-shared-folder` service mounts the share at `/mnt/shared` as
the workstation user, using Parallels' FUSE helper with `nosuid,nodev`.
It starts after `prltoolsd`. Parallels requires `user_allow_other`; enabling this
module also enables NixOS' guest-wide FUSE setting, allowing guest users to opt
their own FUSE mounts into access by other guest users. Approve that setting
alongside the read-write share. Disable the guest option when no host share is
configured; the default module is disabled. The repository's integration file
is empty, allowing bootstrap to record per-VM sharing without a real host path
in shared source. Runtime mount validation is separate from the unit build.

## Private local overrides and profiles

The `local` flake input has a checked-in empty default. Make a private copy of
the example outside the `nixos/` source tree, which is ignored by Git:

```bash
cp -R nixos/examples/local nixos-local
```

Its `nixosModules.default` can select `workstationProfiles.rails` or `.java`
and set `workstation.extraPackages`, `projectsDirectory`, `gitIncludes`,
`hyprlandExtraConfig` (Lua source) and `miseTools`. The example includes Chrome's floating
window rule. The projects directory is relative to the user home and is created
by Home Manager. Git include paths refer to mutable home files; their contents
are not read into the store. Rails supplies native build/database utilities;
both profiles declare runtime versions for mise. They do not install runtimes
during a system rebuild: run `mise install` deliberately in the guest.

Copy the selected non-secret flake to a separate guest directory, for example
`/etc/nixos/workstation-local`, then evaluate and apply with:

```bash
guest_source=$(sudo readlink -f /etc/nixos/workstation)
sudo nix flake check --no-build "path:$guest_source" \
  --override-input local path:/etc/nixos/workstation-local --no-write-lock-file
sudo nixos-rebuild switch --flake "path:$guest_source#workstation-test" \
  --override-input local path:/etc/nixos/workstation-local --no-write-lock-file
```

Retain those flags for subsequent rebuilds using that private configuration.
No impure evaluation is needed and the shared lock stays unchanged. The local
input is source code and enters the world-readable store: put only non-secret
configuration in it. The checked-in default is covered by the parent source;
a separate override is resolved by Nix with its own content hash.

## Explicit personal-file provisioning

The chosen initial mechanism is an explicit post-install SSH copy of each
selected file into the mutable guest home. Nothing personal is auto-discovered
or copied. Authentication/session state stays user-managed; sign into Claude
and 1Password interactively. Do not place keys, tokens, account data or secret
MCP settings in a flake, Home Manager source or Nix path import.

For a selected Git include file, for example:

```bash
make copy-nixos-user-file SSH_HOST=VM_IP_ADDRESS GUEST_USER=developer \
  SOURCE="$HOME/.gitconfig-client" DESTINATION=.gitconfig-client FILE_MODE=600
```

Use an already verified SSH host key; `SSH_KNOWN_HOSTS_FILE` selects an existing
separate known-hosts file if needed. The helper streams only that file over
authenticated SSH, creates new parent directories with mode 0700, and publishes
the file atomically with mode 0600 by default. It refuses existing files,
directories, symlinks and parent traversal. It never writes into the Nix store
or logs contents. Existing files need an explicit operator decision outside
this helper. Modes 0644, 0700 and 0755 are available when deliberately selected
for non-secret configuration or executable hooks.

## Build, update and recover

With Nix on an ARM64 Linux system:

```bash
cd nixos
nix flake check --no-build path:.
nix flake check path:.
```

The first evaluates the host and all assertions; the second also builds its
system closure. Explicit `path:` includes new files before Git tracks them.
On this Mac the same commands can run in the official ARM64 Nix Docker image:

```bash
docker run --rm \
  -v dev-ubuntu-nix-validation:/nix \
  -v "$PWD/nixos:/work" -w /work \
  nixos/nix:latest \
  nix --extra-experimental-features 'nix-command flakes' flake check path:/work
```

The named volume retains downloaded build dependencies. The image is a validation
tool; the installed OS package set is pinned by the committed `flake.lock`.
Remote inputs and transitive inputs are pinned by revision and content hash in
`flake.lock`. The empty local input lives within the parent source. Home Manager
and `numtide/llm-agents.nix` follow the same Nixpkgs
input, preserving the desktop package set. Home Manager supplies user modules;
numtide supplies the Claude Desktop repackaging of Anthropic's official ARM64
binary. These are trusted build/configuration sources, so review their source
and lock changes before updating. The numtide flake labels its vendor packages
unfree but bypasses Nixpkgs' unfree gate in its own package set; only its Claude
Desktop package is consumed here. No additional binary cache or signing key is
enabled. Dependencies use the standard signed NixOS cache, and vendor fetches
are hash verified. The Nixpkgs unfree predicate permits only Parallels Tools,
Chrome, VS Code, Claude Code and 1Password.

Update deliberately with `nix flake update`, review the lock diff and repeat
evaluation, build and guest acceptance. To update just a new input while
preserving the OS pin, use `nix flake update home-manager llm-agents`.

The installed source is `/etc/nixos/workstation`. To reapply it:

```bash
guest_source=$(sudo readlink -f /etc/nixos/workstation)
sudo nixos-rebuild switch --flake "path:$guest_source#workstation-test" --no-update-lock-file
```

If a change breaks the session, switch to a text console and run
`sudo nixos-rebuild switch --rollback --no-reexec`. The flag avoids a legacy
Nix-channel lookup on this flake-only installation. If boot fails, select the previous
generation from systemd-boot (hold Space during startup to show its menu).
Keep the installation ISO for mounting the disk and recovery if necessary.
Do not garbage-collect older generations until acceptance testing is complete.

Unattended installation and the existing-VM apply workflow are documented in
[automation](AUTOMATION.md). The controlled kernel upgrade, reboot and boot
rollback with Tools held at 27.1.0 passed; see [the validation record](VALIDATION.md)
for scope and remaining interactive acceptance. The multi-day cutover remains open.
Do not retire the Ubuntu path until the issue's multi-day cutover criteria pass.
