# Lean developer removal profile

Follow the [trimmed official workstation runbook](omarchy-official-trimmed-runbook.md)
for a guided setup. This reference describes the profile's behaviour and limits.

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
[`lean-developer.packages`](../omarchy/guest/lean-developer.packages): office,
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
