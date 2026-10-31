# Omarchy ARM64 developer workstation

This repository implements the
[Reactive developer VM](https://www.reactive.org/dev-vm) as a small, explicit
preference layer over
[**Omarchy VM Manager**](https://github.com/reactive-org/omarchy-vm-manager)
on Apple Silicon. The manager owns the ARM64 VM, factory image, storage, GPU
and Retina integration, display scaling, clipboard, networking, managed SSH,
persistence, and Mac app lifecycle. Omarchy owns Arch, Hyprland, applications,
Docker, mise, language runtimes, and guest updates.

The repository owns only workstation preferences: a readable Foot font,
host-owned idle/locking policy, an optional theme, and an optional per-workstation
app layout.
It does not install host software or replace either project's update path.

The Omarchy/Parallels and Ubuntu/Ansible implementations remain available
temporarily as rollback paths while the managed workstation is evaluated.

## Omarchy VM Manager quick start

Follow the concise [operator runbook](docs/omarchy-vm-manager-runbook.md) to
build and verify the sibling manager checkout and configure its Guest Defaults
once. Then hand the complete VM lifecycle to the manager's
[JSON CLI](https://github.com/reactive-org/omarchy-vm-manager/blob/main/Docs/CLI.md):

```bash
make bootstrap-omarchy-vm \
  VM_NAME="Dev Omarchy" \
  OMARCHY_VM_LAYOUT_FILE="$PWD/omarchy/examples/layouts/claude-two-terminals-browser.lua"
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

The default guest software set is `claude-desktop`, `1password`, and
`1password-cli`. Override the comma-separated set without editing the repository.
For example, a new VM using Omarchy's configured `mise` tool for OpenCode instead
can be bootstrapped with:

```bash
make bootstrap-omarchy-vm \
  VM_NAME="Dev Omarchy" \
  OMARCHY_VM_PACKAGES=opencode
```

`pi` works the same way, and `OMARCHY_VM_PACKAGES=` selects no additional guest
software. An unprefixed name uses `mise` when Omarchy already configures that
tool; all other names use `omarchy-pkg-add`. Prefix an ambiguous entry with
`mise:` or `pkg:` to choose explicitly. Reapplying ensures the selected software
is installed but never removes software left by an earlier selection.

The default CLI path is the sibling checkout at
`../Omarchy VM Manager/bin/omarchy-vm`. Override
`OMARCHY_VM_MANAGER_CLI=/absolute/path/to/omarchy-vm` when the manager lives
elsewhere. Shared folders and general port forwarding are not currently part
of the manager's CLI contract.

### Optional theme

Choose an Omarchy theme with its HTTPS GitHub repository URL (with or without
`.git`), for example one from the [community catalog](https://omarchy.org/themes/):

```bash
make bootstrap-omarchy-vm \
  OMARCHY_VM_THEME=https://github.com/bjarneo/omarchy-ash-theme
```

Omit `OMARCHY_VM_THEME` to preserve the current theme. To choose automatically:

```bash
make bootstrap-omarchy-vm OMARCHY_VM_THEME=random
make bootstrap-omarchy-vm OMARCHY_VM_THEME=most-starred
```

To draw a random theme with at least 10 GitHub stars:

```bash
make bootstrap-omarchy-vm \
  OMARCHY_VM_THEME=random OMARCHY_VM_THEME_MIN_STARS=10
```

`OMARCHY_VM_THEME_MIN_STARS` defaults to `10`; set it to `0` to disable filtering.
The minimum applies only to `random` and is ignored for other theme choices.
A positive minimum requires the same GitHub authentication as `most-starred`
and chooses uniformly among repositories meeting the inclusive minimum. Setup
stops if no themes qualify. The selection reports its star count and the number
of eligible themes. The controller flag is `--theme-min-stars`.

`random` chooses uniformly from the GitHub repositories in the official
[website catalog source](https://github.com/omacom/omarchy-site/blob/master/themes/index.html).
`most-starred` chooses the catalog repository with the highest current GitHub
star count; ties use alphabetical repository URL order. Entries explicitly
reported by GitHub as `NOT_FOUND` are skipped and printed, covering removed
or private repositories. Star ranking prefers an
existing `gh` CLI on the host and uses `gh api` with its GitHub.com login. If you
have already run `gh auth login --hostname github.com`, no token export is
needed. `gh` honors `GH_TOKEN` ahead of `GITHUB_TOKEN`, and either overrides its
stored login. If `gh` is unavailable, the controller uses `GH_TOKEN` or
`GITHUB_TOKEN` directly, with access to public repository metadata. It never
installs `gh` or starts an interactive login during setup.

Both paths query GitHub's GraphQL API in batches; credentials stay on the host
and are never printed, staged, or passed to the guest. Lookup or API failures
stop setup before any VM changes instead of silently choosing another theme.

The selected URL appears in the proposal before confirmation. Each automatic
selection runs once per bootstrap invocation; reuse the printed URL to keep
the same choice on future runs. Omarchy's native `theme install`/`theme set`
commands apply the selection without requiring a live graphical session. An
installed theme from the same repository is reused without pulling or deleting
local changes; an already active selection with generated Foot settings is left
alone. Setup runs in an Omarchy login shell so its native templates are available,
and regenerates missing active theme settings even when no new theme is selected.
A name collision with a local theme or another repository stops with an error.
Omarchy continues to
own theme updates. The normal managed reboot activates the selection.

For guest-side application, `make apply-omarchy-vm-guest OMARCHY_VM_THEME=URL`
also accepts a repository URL; automatic selection is a host bootstrap option.
The controller's equivalent argument is `--theme URL|random|most-starred`.

If Foot reports that its active theme include is missing, regenerate the current
theme from a guest login terminal and validate the result:

```bash
OMARCHY_THEME_HEADLESS=1 omarchy theme set "$(cat "$HOME/.local/state/omarchy/current/theme.name")"
foot --check-config
```

### Optional workstation app layout

No application layout is installed by default. The tracked example in the
bootstrap command above reproduces the evaluated layout: Claude Desktop on the
right, two Foot terminals stacked on the left, and a floating Chromium window.

Copy the example into the ignored `omarchy/local/` directory for a
workstation-specific variant. Omit `OMARCHY_VM_LAYOUT_FILE` to preserve the
current choice, or pass `OMARCHY_VM_LAYOUT_FILE=off` to remove the managed
layout. Layout changes take effect on the next Hyprland login.

### Validation

After the first graphical login, re-run the non-persistent host-side validation
without installing diagnostic packages:

```bash
make check-omarchy-vm VM_NAME="Dev Omarchy"
```

The check requires `aarch64`, rejects `llvmpipe` and `softpipe`, verifies the
Foot configuration and manager-provided clipboard channel, reports the current
Hyprland display and scale, and confirms the explicit idle preferences. Also test one host-to-guest
paste, one guest-to-host paste, a normal restart, and window movement between
the two host displays before accepting the migration.

### Hyprland 0.57 black desktop after updating

Try Omarchy issue [#429](https://github.com/omacom/try-omarchy/issues/429)
tracks a current regression where an Omarchy update leaves the launcher and
tooltips visible but turns the desktop black and hides opened windows. Do not
force `llvmpipe`: that disables required hardware rendering. Bootstrap applies
the conditional repair only when the installed Hyprland/Try Omarchy combination
needs it. For manual guest-side recovery:

```bash
make repair-omarchy-vm-black-screen
sudo reboot
```

The repair backs up both changed user configuration files under
`~/.local/state/dev-workstation/try-omarchy-black-screen/`, is safe to reapply,
and requires a full Hyprland restart rather than only `hyprctl reload`.

Validate repository changes on the Mac with:

```bash
bash -n omarchy/guest/apply-workstation.sh \
  omarchy/guest/apply-theme.sh \
  omarchy/guest/check-workstation.sh \
  omarchy/guest/repair-try-omarchy-black-screen.sh
PYTHONPYCACHEPREFIX=/tmp/dev-ubuntu-pycache \
  python3 -m py_compile scripts/omarchy_vm_manager.py scripts/omarchy_vm.py
make test-omarchy
```

## Legacy Omarchy/Parallels rollback workflow

Install Parallels Desktop, Python 3, xorriso, and OpenSSL 3 on the Mac:

```bash
brew install python xorriso openssl@3
```

Have an SSH key available, normally `~/.ssh/id_ed25519.pub`, then run:

```bash
make bootstrap-omarchy
```

The workflow fetches the current official `edge-aarch64` manifest, downloads
the image, verifies its SHA-256, and shows the complete VM proposal before
making changes. It asks how much of the VM's current host display the window
should occupy, defaulting to 75%. Rectangle Pro applies supported centered
presets automatically; when it is unavailable, the workflow prints the manual
target without failing. Use `OMARCHY_WINDOW_SIZE=50`, `67`, `75`, `100`,
or `off` for unattended runs. It prompts privately for the Omarchy login/sudo
password and uses Omarchy's supported unattended `cidata` interface. The
generated drive contains a password hash and public SSH key, is ignored by Git,
and is deleted after successful guest configuration.

On the first apply, the controller runs `omarchy update -y` in an SSH terminal
before installing integration packages. Omarchy deliberately requires its own
sudo prompt for that update; enter the guest password when asked. This keeps
keyrings, migrations, boot verification, and restart hooks in Omarchy's
supported update path.

Defaults are 4 CPUs, 12 GB RAM, a 64 GB expanding disk, and the highest
advertised mode, `4096x2160@60`, at scale 1.0. This provides a crisp 4096x2160
logical workspace that can be downsampled into a large host window without
magnifying application UI. Omarchy's global text size is set to 16px while Foot
is independently set to 15pt, keeping application UI compact without
sacrificing terminal readability. Override the mode without editing files:

```bash
make bootstrap-omarchy \
  VM_NAME="Dev Omarchy" \
  CPUS=8 MEMORY_MB=16384 DISK_GB=96 \
  OMARCHY_DISPLAY_MODE=4096x2160@60 \
  OMARCHY_WINDOW_SIZE=75
```

### Optional per-VM app layout

The managed workstation configuration does not launch or position applications.
Bootstrap instead asks for an optional Hyprland Lua layout file, so workspace
policy can differ per VM. Leave it blank for native Omarchy behavior.

The repository includes an example reproducing the evaluated layout exactly:
Claude Desktop fills the right 60%, two Foot terminals are stacked on the left,
and Chromium floats above them. Use the tracked example directly:

```bash
make bootstrap-omarchy \
  OMARCHY_LAYOUT_FILE="$PWD/omarchy/examples/layouts/claude-two-terminals-browser.lua"
```

For a VM-specific variant, copy the example into the ignored local directory
and edit that copy:

```bash
mkdir -p omarchy/local
cp omarchy/examples/layouts/claude-two-terminals-browser.lua \
  omarchy/local/dev-omarchy.lua

make bootstrap-omarchy \
  OMARCHY_LAYOUT_FILE="$PWD/omarchy/local/dev-omarchy.lua"
```

`make apply-omarchy` preserves an installed layout when the variable is omitted.
Pass another file to replace it, or `OMARCHY_LAYOUT_FILE=off` to remove it and
return to native Omarchy behavior.

The evaluation VM is deliberately unencrypted: the unattended Omarchy format
would otherwise place the LUKS passphrase in plaintext on `cidata` and still
require it during first boot. Use it only on encrypted host storage. Encryption
can be reconsidered after the workstation is accepted.

The new path uses Omarchy's Chromium, Neovim, Docker, mise, and Claude Code
integration. It additionally installs Omarchy's Claude Desktop and 1Password
packages. Google Chrome and VS Code are not installed initially.

Hyprland and applications use Parallels' hardware-backed virgl renderer. The
Omarchy shell alone uses Qt's software scene graph because Qt/Quickshell loses
alpha on virgl and otherwise turns its full-screen launcher/bar layer opaque.
This does not disable GPU acceleration for Chromium, Claude Desktop, or the
compositor.

If `~/Parallels/Shared` exists, it is exposed as the only host share at
`/mnt/shared`. Parallels Tools provide clipboard and shared-folder integration.
The vendor `prlcc` desktop autostart owns the single clipboard process; `prlcp`
does not exchange clipboard data correctly when launched without that parent.
A user-service drop-in periodically refreshes the complete vendor chain if it
becomes stale.
The guest delegates idle behavior to the host: Omarchy's automatic screensaver
and idle lock are disabled, and its lock-before-suspend user service is masked.
Manual guest locking remains available if explicitly invoked.

After the first graphical login, inspect the fixed monitor mode and renderer:

```bash
make check-omarchy \
  VM_NAME="Dev Omarchy" \
  GUEST_USER="developer"
```

The check fails if the graphical session reports `llvmpipe` or `softpipe`.
Reapply the small guest configuration after changing the display setting or
updating Parallels Tools with:

```bash
make apply-omarchy \
  VM_NAME="Dev Omarchy" \
  GUEST_USER="developer"
```

Validate changes locally with:

```bash
python3 -m py_compile scripts/omarchy_vm.py
bash -n omarchy/guest/configure.sh \
  omarchy/guest/dev-vm-display-init \
  omarchy/guest/dev-vm-session-check
make test-omarchy
```

## Legacy Ubuntu/Ansible workflow

## What it installs

- Base OS tools and Parallels Tools build prerequisites
- zsh, Starship, Neovim, tmux, lazygit, current GitHub CLI, and modern CLI
  utilities
- Firefox from Mozilla's DEB repository (not Snap)
- Google Chrome for Linux ARM64, Visual Studio Code ARM64, 1Password desktop
  and CLI (`op`), mise, Claude Desktop, and Claude Code
- Docker Engine, Buildx, and Compose from Docker's repository
- Hyprland, greetd/agreety, kitty, Waybar, fuzzel, mako, Nautilus, PipeWire,
  portals, clipboard history, locking, and screenshot tools; or a lean i3/Xorg
  session for environments where native Wayland integration is unreliable
- Ubuntu's JetBrains Mono package, applied to kitty, Waybar, fuzzel, mako,
  and GTK 3/4 applications

The project intentionally does **not** install GNOME/KDE, `ubuntu-desktop`,
GDM/SDDM, NetworkManager, a dock, or desktop icons.

## Prerequisites

For an automated VM build, install Parallels Desktop Pro or Business, Ansible,
Python 3, and `xorriso` on the Mac, and have an SSH public key available. For
example:

```bash
brew install ansible python xorriso
```

For a VM installed separately, create a normal user with sudo access, enable
SSH during installation, and make sure the Mac can reach it over SSH.

Only modules included with `ansible-core` are used; no Galaxy collections are
required.

Ubuntu 26.04 uses `sudo-rs` by default. Older Ansible controllers do not
recognise its authentication prompt, so this project sets Ansible's privilege
escalation executable to Ubuntu's supported `/usr/bin/sudo.ws` compatibility
implementation. This affects Ansible only; interactive `sudo` remains
`sudo-rs`.

## Bootstrap a Parallels VM

The Make workflow creates the VM hardware and, by default, performs an Ubuntu
Autoinstall before Ansible takes over. Run:

```bash
make bootstrap
```

The workflow uses a checked-in **Dev Server** configuration profile as its
default. This is a baked-in set of sizing and lean integration settings; it
does not clone, inspect, or otherwise depend on a VM named `Dev Server` being
registered. It recursively searches `~/Downloads` for Ubuntu Server ARM64 ISOs
and offers the most recently modified image. Before changing anything, it
prompts for the VM name, ISO, CPUs, memory, disk size, and whether to start,
displays the complete proposal, and requires explicit confirmation.

The created VM uses a lean Linux integration profile: bidirectional clipboard
and UTC time synchronization are enabled; application sharing, broad home/disk
sharing, shared profile/cloud, printer synchronization, automatic
camera/smart-card/gamepad sharing, host location, Rosetta, and automatic
SSH-key injection are disabled. If `~/Parallels/Shared` already exists on the
Mac, Ansible exposes only that directory to the VM at `/mnt/shared`.

Autoinstall defaults the Ubuntu username to the current macOS account name and
the hostname to a normalized form of the VM name. It selects one SSH public key
(preferring `~/.ssh/id_ed25519.pub`), prompts twice for a local/sudo password,
installs standard Ubuntu Server onto the entire virtual disk, disables SSH
password authentication, and reboots. The normal Linux numeric UID is retained;
only the account name is matched to the Mac.

The local/sudo password is hashed with bcrypt before it is written to CIDATA,
then the plaintext is discarded. Autoinstall creates a temporary, user-scoped
`NOPASSWD` sudoers rule so Ansible can run unattended. After the final reboot,
the playbook removes that rule as its last privileged action, restoring normal
password-protected sudo. If provisioning fails, the controller makes a separate
best-effort cleanup attempt and warns prominently if the VM cannot be reached.

The workflow creates two ignored artifacts under `.artifacts/autoinstall`: a
cached copy of the Ubuntu ISO whose GRUB entry includes the `autoinstall` kernel
argument, and a per-VM CIDATA ISO. The latter contains the password hash and SSH
public key, is mode `0600`, and must never be committed or shared. The existing
host-side confirmation remains the destructive safety boundary before the
installer is allowed to replace the VM disk.

List discovered images or registered VMs with:

```bash
make images
make vms
```

Any prompt default can be supplied up front while retaining the final safety
confirmation:

```bash
make bootstrap \
  VM_NAME="Ubuntu Workstation" \
  IMAGE="$HOME/Downloads/ubuntu-26.04.1-live-server-arm64.iso" \
  CPUS=8 MEMORY_MB=12288 DISK_GB=24 START_VM=yes
```

Override the generated identity or selected public key when needed:

```bash
make bootstrap \
  GUEST_USER="developer" \
  GUEST_HOSTNAME="ubuntu-workstation" \
  SSH_PUBLIC_KEY="$HOME/.ssh/id_ed25519.pub"
```

Set `AUTOINSTALL=no RUN_ANSIBLE=no` to retain the original interactive Ubuntu
installer.

To take only the CPU, memory, and disk defaults from a currently registered VM,
set `SIZING_VM="VM name"`. The Dev Server integration profile remains in force.

If Parallels fails after creating the VM but before finishing its configuration,
fix the reported incompatibility and rerun the same command with `RESUME=yes`.
This explicit switch prevents an existing VM from being modified accidentally;
the recovery path will grow an undersized disk but never shrink an existing one.

The generated installation includes Python, OpenSSH, and Avahi. After starting
the VM, bootstrap waits for key-based SSH authentication at `HOSTNAME.local`,
runs the complete playbook against a private temporary inventory, installs
Parallels Tools unattended, and reboots. It reports SSH progress every 30
seconds; the default timeout is 45 minutes. Temporary inventory and known-hosts
data are removed when the command exits, and the project files
remain free of the generated host and account details.

Override the target or timeout when mDNS is unavailable:

```bash
make bootstrap SSH_HOST=VM_IP_ADDRESS SSH_WAIT_TIMEOUT=3600
```

To stop after creating and starting the installed server, disable both the
provisioning stage and (optionally) the SSH wait:

```bash
make bootstrap RUN_ANSIBLE=no
make bootstrap RUN_ANSIBLE=no WAIT_FOR_SSH=no
```

Interactive installation requires `AUTOINSTALL=no RUN_ANSIBLE=no`.

## Inventory and variables

Replace both placeholders in `inventory.ini`:

```ini
[workstation]
ubuntu-vm ansible_host=YOUR_HOST_OR_IP ansible_user=YOUR_USER
```

Set the same account in `group_vars/all.yml`:

```yaml
workstation_user: YOUR_USER
```

For checkout-specific overrides, copy `local-vars.example.yml` to
`local-vars.yml` and edit it. The playbook loads `local-vars.yml` automatically
when it exists, including through both `make bootstrap` and
`make apply-playbook`; no `PLAYBOOK_ARGS` override is required. The local file
is ignored by Git and should not contain secrets.

For checkout-specific setup that needs full Ansible tasks rather than variable
overrides, copy `developer_extra_tasks.example.yml` to
`developer_extra_tasks.yml`. The playbook loads this ignored task file
automatically after its standard roles. It can configure private package
repositories or install software that should not be part of the shared
workstation definition. Run only these tasks with the `developer_extra_tasks`
tag when needed.

To keep multiple developer profiles, place them in the ignored
`developer_extra_tasks/` directory and select one with the Make variable
`DEVELOPER_EXTRA_TASKS_FILE`. Paths may be absolute or relative to the project
root. The root-level `developer_extra_tasks.yml` remains the default when the
variable is omitted. For example:

```bash
make apply-playbook \
  VM_NAME="Ubuntu Workstation" \
  DEVELOPER_EXTRA_TASKS_FILE="developer_extra_tasks/rails.yml"
```

The same override works during an end-to-end build:

```bash
make bootstrap \
  DEVELOPER_EXTRA_TASKS_FILE="$HOME/.config/dev-ubuntu/java.yml"
```

An explicitly selected file must exist; the Make workflow fails before starting
or modifying the VM if its path is wrong. Direct Ansible runs can set the lower-
case `developer_extra_tasks_file` variable with `--extra-vars`.

The main switches live in `group_vars/all.yml`. Firefox, Chrome, VS Code,
1Password, mise, GitHub CLI, Claude Desktop, Claude Code, Docker, and Snap
removal are enabled by default. Set `remove_snapd: false` if the VM needs any
snaps. `desktop_session` defaults to `hyprland` for the native Wayland desktop.
Set it to `i3-x11` only when an Xorg compatibility fallback is required. Useful
display settings include
`hyprland_scale`, `hyprland_main_modifier`, `keyboard_layout`, `ui_font_family`,
`ui_font_size`, and `kitty_font_size`. The main modifier defaults to
`ALT SUPER`, requiring Option+Command together for desktop shortcuts in
Parallels. Raw checkout-specific Hyprland stanzas can be appended through
`hyprland_extra_config` in ignored `local-vars.yml`; the managed base
configuration remains intact. Kitty is the managed terminal and uses the
selected session's native display backend. Its tabs, panes, and top-level
windows start in the workstation user's home directory.
`kitty_display_server` defaults to `wayland`;
`kitty_force_software_rendering` is available if the Parallels virtual GPU
proves insufficient. Apply only the terminal configuration with:

```bash
make apply-playbook \
  VM_NAME="Ubuntu Workstation" \
  PLAYBOOK_ARGS="--tags kitty"
```

Apply only the rendered Hyprland configuration after changing a local override
with `PLAYBOOK_ARGS="--tags hyprland_config"`.

The desktop role installs Ubuntu's `fonts-jetbrains-mono` package. It is the
primary kitty font and the configured face for Waybar, fuzzel, mako, and GTK
3/4 applications. Synced Powerlevel10k fonts remain managed by the shell role.

Before its first apt operation, the base role compares the VM's UTC clock with
the Ansible controller. If their difference exceeds
`maximum_clock_skew_seconds`, it corrects the guest and restarts chrony. This
prevents apt from rejecting signed repository metadata as not valid yet after
the VM has been suspended or restored.

Set `parallels_vm_name` to the VM's exact name in Parallels Desktop. With
`prepare_parallels_tools_media: true`, the playbook checks inside Ubuntu for
an installed `parallels-tools` package or Tools executable. When Tools is
absent it asks the Mac's `prlctl` to attach the bundled ARM64 ISO, reusing an
already attached or mounted disc. Standalone playbook runs leave an initial
installer available for manual use by default; set
`install_parallels_tools_automatically: true` to use the vendor's unattended
installer. The full bootstrap workflow enables that setting automatically.

Existing installations are compared with the exact version stored in the
host-bundled ISO. With `update_parallels_tools_automatically: true` (the
default), an older guest invokes `prlctl installtools` on the controller, waits
up to five minutes for the new version, and verifies `prltoolsd.service` before
continuing. Equal or newer guest versions are left untouched; the role never
downgrades Tools.

The shell role clones [Oh My Zsh](https://github.com/ohmyzsh/ohmyzsh) and
[Powerlevel10k](https://github.com/romkatv/powerlevel10k) into the workstation
user's standard directories. It keeps `.zshrc` Linux-specific and managed by
Ansible; it does not copy the controller's complete `.zshrc`. When available,
the role copies the controller's `.p10k.zsh` and MesloLGS NF fonts, controlled
by `sync_controller_powerlevel10k_config` and
`sync_controller_powerlevel10k_fonts`. Override the controller paths in
`group_vars/all.yml` when running the playbook from a different machine.

The shell role also conditionally copies the controller's `.gitconfig` without
storing the file in the project. Missing files are skipped. Control this with
`sync_controller_git_config`, `controller_git_config_dir`, and
`controller_git_config_files`. To copy further include files referenced from
`.gitconfig`, override `controller_git_config_files` in `local-vars.yml`; the
override replaces the committed list, so repeat `.gitconfig` there.

The shell role can also copy the controller's `~/.ssh/id_rsa` and matching
public key directly into the workstation user's `~/.ssh`, with `0700`
directory and `0600` private-key permissions. The key is read from the
controller only while Ansible runs and is never stored in this repository.
Control this with `sync_controller_ssh_key`, `controller_ssh_key_dir`, and
`controller_ssh_key_files`. This duplicates a private credential into the VM;
set the switch to `false` when agent forwarding or a dedicated VM key is
preferred.

The developer-apps role also conditionally copies these items from the
controller's `~/.claude`: `hooks/block-commands.sh`,
`statusline-command.sh`, `output-styles`, and `settings.json`.
Missing items are skipped. Files are copied with restrictive permissions and
`output-styles` is merged with its target rather than deleting VM-only content.
The controller home path in the hook is rewritten for the workstation account.
The `~/.claude/plugins` tree is deliberately not synchronized. Control this with
`sync_controller_claude_config` and the `controller_claude_*` variables in
`group_vars/all.yml`. The controller's personal files are never stored in this
project.

The playbook deliberately refuses to run unless the target reports Ubuntu 26.04
(Resolute) on `aarch64` and all placeholders have been replaced.

## Validate and run

From this directory, check connectivity and syntax:

```bash
ansible -i inventory.ini workstation -m ping
ansible-playbook -i inventory.ini site.yml --syntax-check
```

Provision with SSH keys:

```bash
ansible-playbook -i inventory.ini site.yml --ask-become-pass
```

With SSH password authentication:

```bash
ansible-playbook -i inventory.ini site.yml --ask-pass --ask-become-pass
```

Roles are independently taggable. For example:

```bash
ansible-playbook -i inventory.ini site.yml --ask-become-pass --tags shell,developer_apps
```

For a VM created by this project's bootstrap workflow, the Make target can
discover its address and build a private temporary inventory automatically:

```bash
make apply-playbook VM_NAME="Ubuntu Workstation"
```

The target starts the VM when necessary, prefers the IPv4 address reported by
Parallels, falls back to the normalized `.local` hostname, waits for key-based
SSH, and runs `site.yml` with `--ask-become-pass`. It defaults to the current
macOS username and the same preferred SSH-key order as bootstrap. Override
`GUEST_USER`, `SSH_HOST`, or `SSH_PUBLIC_KEY` when the VM was created with
non-default values.

Add playbook options with `PLAYBOOK_ARGS`; the default privilege-escalation
prompt remains in place:

```bash
make apply-playbook \
  VM_NAME="Ubuntu Workstation" \
  PLAYBOOK_ARGS="--tags desktop"
```

Install or update only 1Password on an existing bootstrapped VM:

```bash
make apply-playbook \
  VM_NAME="Ubuntu Workstation" \
  PLAYBOOK_ARGS="--tags onepassword"
```

Install or update only Claude Desktop on an existing bootstrapped VM:

```bash
make apply-playbook \
  VM_NAME="Ubuntu Workstation" \
  PLAYBOOK_ARGS="--tags claude_desktop"
```

Claude Desktop is installed from
[Anthropic's signed Linux apt repository](https://support.claude.com/en/articles/10065433-install-claude-desktop)
and launches as `claude-desktop`. The Linux release is currently a beta.

Install or upgrade only GitHub CLI on an existing bootstrapped VM:

```bash
make apply-playbook \
  VM_NAME="Ubuntu Workstation" \
  PLAYBOOK_ARGS="--tags github_cli"
```

The shell role uses
[GitHub CLI's official signed apt repository](https://github.com/cli/cli/blob/trunk/docs/install_linux.md)
rather than Ubuntu's slower-moving community package. The task requests the
latest repository version so rerunning it also upgrades an existing `gh`.

Set `BECOME_ARGS=` for a non-privileged operation such as `--syntax-check`.

To install or update only Parallels Tools:

```bash
ansible-playbook -i inventory.ini site.yml --ask-become-pass --tags parallels_tools
```

To synchronize only the selected Claude Code configuration:

```bash
ansible-playbook -i inventory.ini site.yml --ask-become-pass --tags claude_config
```

To synchronize only the selected Git configuration:

```bash
ansible-playbook -i inventory.ini site.yml --ask-become-pass --tags git_config
```

To synchronize only the selected SSH key into a bootstrapped VM:

```bash
make apply-playbook \
  VM_NAME="Ubuntu Workstation" \
  PLAYBOOK_ARGS="--tags ssh_keys"
```

A standalone playbook run does not reboot by default. Reboot manually when
convenient, or set `reboot_after_provision: true`. The full bootstrap workflow
enables this setting, waits for the reboot, and returns only after the
workstation is reachable again.

## First-login setup

### 1Password

Ansible installs the native app and CLI, configures their system integration,
and starts 1Password silently in the Waybar system tray. The security-sensitive
account settings must be enabled once from inside the unlocked app:

1. Open 1Password from the Waybar tray and sign in to the account.
2. In **Settings > General**, enable **Keep 1Password in the system tray**.
3. In **Settings > Security**, enable
   **Unlock using system authentication**.
4. Lock 1Password, then enter the 1Password account password once when asked.
5. Unlock the app and, in **Settings > Developer**, enable
   **Integrate with 1Password CLI**.
6. Open a new terminal and verify the integration:

   ```bash
   op vault list
   ```

The CLI should now request the Linux system password through the desktop
authentication prompt. Ansible already starts the app silently with the
managed graphical session, so 1Password's separate **Start at login** option
is not required. See
[system authentication on Linux](https://support.1password.com/system-authentication-linux/)
and [1Password CLI app integration](https://www.1password.dev/cli/app-integration/)
for the upstream behavior and security requirements.

## Parallels Tools

The base role installs `dkms`, `libelf-dev`, `build-essential`, `pkg-config`, and
headers for the running kernel. The `parallels_tools` role conditionally makes
the matching installer media accessible inside the VM. Full bootstrap runs the
bundled unattended installer; standalone playbook runs keep an initial
installation manual by default. Existing Tools installations are upgraded
automatically when their four-part version is older than the version bundled
with the controller's Parallels Desktop installation.

After the role reports the installer path, run its `install` program with sudo.
For example, if the role mounted the image at its default location:

```bash
cd /media/cdrom0
sudo ./install
```

A VM snapshot immediately before this step is sensible.
If the kernel was upgraded by the playbook, reboot before installing the tools
so the running kernel and installed headers agree.

### Host shared folder

The `parallels_shared_folder` role conditionally shares the existing macOS
`~/Parallels/Shared` directory as a read/write Parallels custom share. It does
not create the host directory, share the macOS home directory, or enable
Parallels' all-disk sharing. In the VM, a system service mounts the share at
`/mnt/shared` during boot using the Parallels Tools FUSE driver.

Ubuntu 26.04 confines root-initiated `fusermount3` mounts with AppArmor. The
role avoids broadening that security policy: it enables FUSE's `allow_other`
support and runs the Parallels FUSE client as the workstation user from a
system service. The mount starts automatically, remains visible to other users,
and is verified by listing it before the role completes.

When the host directory is absent, the playbook skips all sharing changes and
prints the command needed to create it. After creating it deliberately, apply
only this integration with:

```bash
make apply-playbook \
  VM_NAME="Ubuntu Workstation" \
  PLAYBOOK_ARGS="--tags parallels_shared_folder"
```

Wayland integration in Parallels can vary by Parallels Tools release. Test
dynamic resolution, shared clipboard, pointer behaviour, audio, and shared
folders before treating the VM as finished.

### Optional i3/Xorg session

The default `desktop_session: hyprland` provides the native Wayland desktop and
Hyprland features. An optional `desktop_session: i3-x11` fallback keeps the same
greetd login, kitty terminal, `ALT+SUPER` modifier, browsers, editor, file
manager, font, and Parallels Tools integration. It deliberately does not start
a clipboard-history manager, so applications and Parallels share one ordinary
X11 clipboard without an extra clipboard owner in the middle.

To try i3/Xorg, set `desktop_session: i3-x11` in ignored `local-vars.yml`, then
apply only the desktop role to a named VM:

```bash
make apply-playbook \
  VM_NAME="Ubuntu Workstation - X11 Test" \
  PLAYBOOK_ARGS="--tags desktop"
```

The graphical session is restarted during the change. Log in at the greetd
prompt and confirm the backend with:

```bash
echo "$XDG_SESSION_TYPE"
```

It should print `x11`. To return to Wayland, remove that override (or set it to
`hyprland`) and reapply the desktop role. The backend should then print
`wayland`.

Use the `i3_extra_config` list in ignored `local-vars.yml` for machine-specific
i3 directives without changing the managed base configuration.

Parallels Tools publishes resized virtio display modes, but its Wayland display
client targets GNOME/Mutter rather than Hyprland. Parallels v27 and Ubuntu's
Hyprland 0.53 currently reject runtime modesets, including ordinary advertised
resolutions. The safe default is therefore a fixed `4096x2160@60` startup
mode, controlled by `parallels_hyprland_fixed_mode`. Parallels publishes the
complete virtio mode list shortly after Hyprland starts, so the workstation
performs one delayed configuration reload. It does not continuously follow
host-window resize events.

With `enable_parallels_hyprland_integration: true`, clipboard and drag-and-drop
helpers remain Wayland-native. The incompatible combined Parallels autostart is
disabled. A narrowly matched Hyprland window rule also keeps the Parallels
shared-clipboard helper from entering the tiled layout when input is released.
Parallels' `prlcp` process can remain alive after its Wayland clipboard
connection has become stale. The managed user service therefore restarts it
after `parallels_clipboard_restart_interval` (four hours by default), and a
changed service definition restarts it immediately when the desktop role is
applied. This preserves host/guest integration without leaving a stale helper
running indefinitely.
Set `parallels_dynamic_resolution_enabled: true` only to experiment with the
XWayland `prlcc` bridge; it is disabled by default because the current virtio
driver rejects the requested mode.

Parallels' virtio GPU currently rejects Aquamarine's atomic test commit when
Hyprland changes the framebuffer size. Although Aquamarine exposes a legacy
DRM path, `hyprland_use_legacy_drm` remains `false`: enabling it makes Ubuntu's
Hyprland 0.53 session exit during startup on Parallels v27. A failed dynamic
resize is preferable to a graphical login loop. Changing this experimental
setting requires a new graphical login (or a reboot).

Verify the fixed mode and the enabled integration helpers inside the guest:

```bash
hyprctl monitors all
systemctl --user status parallels-prlcp-wayland.service
systemctl --user status parallels-prldnd-wayland.service
```

If clipboard operations become unreliable before the scheduled refresh, reset
the bridge without logging out:

```bash
systemctl --user restart parallels-prlcp-wayland.service
```

When experimenting with dynamic resolution, inspect its services with
`systemctl --user status parallels-prlcc-x11.service` and
`systemctl --user status parallels-dynamic-resolution.service`.

## Software ownership boundary

Ubuntu's package manager owns durable workstation software: i3, Hyprland and
their desktop services, browsers, VS Code, Claude Desktop, Docker, shells,
editors, CLI utilities, and mise itself. Claude Desktop remains apt-owned
through Anthropic's signed ARM64 repository, while GitHub CLI is apt-owned
through GitHub's signed ARM64 repository. The ARM64 1Password desktop app and
Claude Code are deliberate exceptions: their vendor-recommended installers own
those applications and their updates. 1Password's signed stable ARM64 archive
is verified against the vendor's published signing-key fingerprint before
installation. The `op` CLI remains apt-owned through 1Password's signed ARM64
repository.

Oh My Zsh and Powerlevel10k are treated as user-shell configuration rather
than workstation software. The shell role manages their Git checkouts and
disables Oh My Zsh's independent updater.

mise owns rapidly changing developer runtimes and toolchains such as Node.js,
Ruby, Python, Go, Terraform/OpenTofu, and project-specific utilities. Do not add
those runtimes to the base or shell roles. Declare them per project in
`mise.toml`, for example:

```toml
[tools]
node = "24"
ruby = "4"
python = "3.14"
```

This keeps the operating system boring and stable while projects select the
toolchain versions they need.

## Default desktop keys

| Keys | Action |
| --- | --- |
| `ALT+SUPER+Enter` | kitty |
| `ALT+SUPER+Space` | Application launcher |
| `ALT+SUPER+B` | Google Chrome |
| `ALT+SUPER+Shift+B` | Firefox |
| `ALT+SUPER+C` | Visual Studio Code |
| `ALT+SUPER+E` | Nautilus |
| `ALT+SUPER+P` | Clipboard history (Hyprland only) |
| `ALT+SUPER+Shift+S` | Area screenshot |
| `ALT+SUPER+L` | Lock session |
| `ALT+SUPER+1..9` | Select workspace |
| `ALT+SUPER+Shift+1..9` | Move window to workspace |

The i3/Xorg session retains the application, workspace, focus, movement,
fullscreen, close, lock, and screenshot chords above. `ALT+SUPER+V` toggles a
window between tiled and floating, and `ALT+SUPER+Shift+R` reloads i3.
