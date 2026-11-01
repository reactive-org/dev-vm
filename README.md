# Omarchy ARM64 developer workstation

This repository implements the
[Reactive developer VM](https://www.reactive.org/dev-vm) as a small, explicit
preference layer over
[**Omarchy VM Manager**](https://github.com/reactive-org/omarchy-vm-manager)
on Apple Silicon. The manager owns the ARM64 VM, factory image, storage, GPU
and Retina integration, display scaling, clipboard, networking, managed SSH,
persistence, and Mac app lifecycle. Omarchy owns Arch, Hyprland, applications,
Docker, mise, language runtimes, and guest updates.

For the default managed workflow, this repository applies workstation preferences: a readable Foot font,
host-owned idle/locking policy, an optional theme, an optional per-workstation
app layout, and an opt-in lean developer application selection.
It does not install host software or replace either project's update path.

The repository targets Omarchy ARM64 through VM Manager. Use either the official
Try Omarchy factory or the opt-in lean factory, then apply selected features.
Host tool installation remains a separate operator action.

## Minimal factory image build

Build an opt-in desktop-foundation factory from the pinned Try Omarchy builder:

```bash
make build-omarchy-image OMARCHY_IMAGE_PLAN=yes
make check-omarchy-image
make build-omarchy-image
```

The preview checks local source inputs without Docker or downloads. The check
target builds guest packages, exercises the optional-provisioning guards and
resolves their dependencies without creating a disk. The build target creates
a sealed ARM64 UEFI/Btrfs factory under `.artifacts/omarchy-image/`. Both require
an existing ARM64 Docker engine; neither installs host tools, operates a VM,
changes VM Manager, or replaces its factory/cache.

The foundation includes the Omarchy desktop, native Mac integration, Foot,
Git, Python, graphics, audio, input methods and recovery tools. Browser,
Docker, language runtimes, coding agents and credential apps are excluded,
including when pulled in transitively. The feature playbooks below support both
images. VM Manager owns custom-factory admission and selection; the image builder
does not replace its official cache or existing disks.

See the [image build contract and validation limits](docs/omarchy-image.md)
before importing an artifact. A successful build proves static policy and
system setup; hardware rendering and owner setup require a disposable-VM test.
The [live acceptance record](docs/omarchy-playbook-validation.md) distinguishes
official and lean image results and their remaining validation limits.

## Select developer features

With the chosen guest already running and managed SSH ready:

```bash
make apply-playbook VM_NAME="Dev Omarchy" \
  OMARCHY_FEATURES=workstation,browsers,docker,languages,agents,credentials
```

Select only what you need. The default is `workstation`; omitted features leave
existing software and settings alone. An existing browser/runtime/application is
reused on the official image. A lean image receives the prerequisites for the
selected feature through native Omarchy commands and mise.

| Feature / Ansible tag | Default selection when enabled |
| --- | --- |
| `workstation` | Foot size 16, host-owned idle policy and the GPU compatibility repair |
| `browsers` | Chromium; Firefox can also be selected |
| `docker` | Docker, Buildx, Compose, native UFW integration and socket activation |
| `languages` | Node using Omarchy's configured mise version |
| `agents` | Claude CLI using Omarchy's configured mise version |
| `credentials` | 1Password app and CLI, without signing in or copying credentials |

Copy [the example configuration](omarchy/examples/features.yml) into the ignored
`omarchy/local/features.yml`, edit its selections, and pass it explicitly:

```bash
make apply-playbook VM_NAME="Dev Omarchy" OMARCHY_FEATURES=languages,agents \
  OMARCHY_VARS_FILE="$PWD/omarchy/local/features.yml"
```

Values configure a feature; they do not enable it. Each role has its own Ansible
tag. Empty lists/maps select no tools for that feature. An empty mise version
uses Omarchy's existing declaration; a string such as `"3"`, `"lts"` or an exact
version creates/selects a user-level mise setting without replacing other tools.
System Python remains `/usr/bin/python3` for Ansible.

Preview the manager connection/proposal, or inspect planned changes:

```bash
make apply-playbook VM_NAME="Dev Omarchy" OMARCHY_FEATURES=docker OMARCHY_PLAYBOOK_PLAN=yes
make apply-playbook VM_NAME="Dev Omarchy" OMARCHY_FEATURES=browsers,languages OMARCHY_PLAYBOOK_CHECK=yes
```

Check mode stages and removes a temporary payload but does not install packages,
write workstation preferences, start services or enable a sudo grant. Workstation
and Docker firewall predictions are conservative when they cannot be evaluated
without applying native tools. Normal privileged runs use Omarchy's interactive
60-minute sudo grant and revoke it on completion, failure or interruption.

The launcher generates a private temporary inventory from VM Manager's pinned
SSH command. It never creates, starts, resizes or reboots a VM. Docker retains
Omarchy's normal sudo/polkit access policy; no docker-group membership is added.
Use VM Manager for a new login/restart when needed, then validate hardware and
integration with `make check-omarchy-vm`.

See [the playbook contract](docs/omarchy-playbooks.md) for selection, image
compatibility and validation limits. Existing ignored `local-vars.yml` and
`developer_extra_tasks.yml` files are no longer loaded; personal files are left
in place and are not copied into a guest.

## Omarchy VM Manager quick start

Follow the concise [operator runbook](docs/omarchy-vm-manager-runbook.md) to
build and verify the sibling manager checkout and configure its Guest Defaults
once. Then hand the complete VM lifecycle to the manager's
[JSON CLI](https://github.com/reactive-org/omarchy-vm-manager/blob/main/Docs/CLI.md):

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

### Optional lean developer profile

This removal profile is for existing full-image guests. The lean factory starts
with a smaller package set and receives additions through the feature playbooks.

Use macOS for day-to-day activity and keep the guest focused on coding:

```bash
make bootstrap-omarchy-vm OMARCHY_VM_LEAN_DEVELOPER=yes
```

This option defaults to `no`. The controller flag is `--lean-developer`.
It works for new and existing managed guests and prints the candidate removals
in the host proposal before confirmation. After the normal `omarchy update -y`
and selected software installation, it uses `omarchy-pkg-drop` to remove the
installed, removable entries in
[`lean-developer.packages`](omarchy/guest/lean-developer.packages): office,
notes, presentation, signing, creative, entertainment, dictation, theme-creation
and LAN-sharing apps; printing UI/server packages; Bluetooth, physical display,
Thunderbolt and power-profile tools. Other applications are not removal targets.

Foot, Chromium for localhost testing, Neovim, Git, tmux, mise, build tools,
Docker/Buildx/Compose, coding agents and credentials remain available.
Explicit entries in `OMARCHY_VM_PACKAGES` take precedence over the removal list;
for example, retain Obsidian with:

```bash
make bootstrap-omarchy-vm OMARCHY_VM_LEAN_DEVELOPER=yes \
  OMARCHY_VM_PACKAGES=claude-desktop,1password,1password-cli,pkg:obsidian
```

Every removal first previews pacman's dependency-checked transaction. Packages
required by retained software are skipped and reported. Transactions that would
remove protected desktop, graphics, networking, audio, boot, recovery or VM
integration components are also skipped. Omarchy's native removal may clean up
unused dependencies of removed apps. It never forces broken dependencies or
performs a general orphan cleanup. UPower, battery integration, kernel headers,
DKMS and required input methods remain; installed SQL client libraries and
cross-architecture container emulation are not removal targets.

The existing `OMARCHY_VM_IDLE_MODE=host` default delegates automatic locking and
idle policy to macOS. The profile does not replace desktop configuration or
rewrite Omarchy's menus and shortcuts; shortcuts for removed apps may remain.
Omarchy continues to own updates, migrations and all VM integration. The normal
bootstrap reboot and hardware/clipboard checks still run.

Reapplying with the flag is safe and checks the current package graph again.
Omitting it on a later run preserves the current selection; it does not reinstall
removed apps. Restore individual apps with `omarchy pkg add PACKAGE` and omit
the flag or add them to `OMARCHY_VM_PACKAGES` on future lean runs. Omarchy
migrations or reinstall/reset may restore defaults; this is a per-invocation
preference, not a background enforcement service. Disk savings depend on shared
dependencies, caches and retained snapshots; this does not lower VM RAM allocation.

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

No application layout is installed by default. The tracked example
`omarchy/examples/layouts/claude-two-terminals-browser.lua` describes Claude
Desktop on the right, two Foot terminals stacked on the left, and a floating
Chromium window. Install the desired applications before selecting that layout.

Copy the example into the ignored `omarchy/local/` directory for a
workstation-specific variant. Omit `OMARCHY_VM_LAYOUT_FILE` to preserve the
current choice, or pass `OMARCHY_VM_LAYOUT_FILE=off` to remove the managed
layout. Layout changes take effect on the next Hyprland login.
The playbook equivalents are `omarchy_layout_file` and `omarchy_remove_layout`
in the explicitly selected feature variables file.

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
PYTHONPYCACHEPREFIX=/tmp/dev-omarchy-pycache \
  python3 -m py_compile scripts/omarchy_vm_manager.py scripts/omarchy_playbook.py \
  scripts/omarchy_image.py omarchy/guest/apply-lean-developer.py omarchy/guest/apply-features.py \
  omarchy/image/compatibility.py omarchy/image/check-provisioning.py
bash -n omarchy/image/build-container.sh omarchy/image/preferences/first-login.sh \
  omarchy/image/preferences/preferences.install omarchy/image/preferences/PKGBUILD \
  omarchy/image/check-user.sh
make syntax-check
make test-omarchy
```
