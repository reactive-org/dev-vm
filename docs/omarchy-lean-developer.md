# Lean developer removal profile

Follow the [trimmed official workstation runbook](omarchy-official-trimmed-runbook.md)
for a guided setup. This reference describes the profile's behaviour and limits.

This profile trims existing full-image guests and applies lean shell preferences.
The lean factory starts with a smaller package set, seeds the same shell
preferences for its first owner, and receives additions through feature playbooks.

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
idle policy to macOS. The profile disables Weather (`omarchy.weather`), Elsewhen
world clock (`omarchy.elsewhen`), Bluetooth (`omarchy.bluetooth`), display
brightness (`omarchy.monitor`) and Reminders (`omarchy.reminders`). Notifications
remain enabled by default and their existing settings are preserved, along with
all unrelated plugins and shell settings. The running guest uses
`omarchy plugin disable`; the lean factory's first-owner preferences use Omarchy's native
shell-config commit helper so they also work before graphical IPC is available.
Only the selected widget placements and Reminders enabled state change. Display
resolution and Retina integration remain owned by VM Manager.

The profile does not rewrite Omarchy's menus and shortcuts; shortcuts for
removed apps may remain.
Omarchy continues to own updates, migrations and all VM integration. The normal
bootstrap reboot and hardware/clipboard checks still run.

Reapplying with the flag is safe and checks the current package graph again.
Omitting it on a later run preserves the current selection; it does not reinstall
removed apps. Restore individual apps with `omarchy pkg add PACKAGE` and omit
the flag or add them to `OMARCHY_VM_PACKAGES` on future lean runs. Omarchy
migrations or reinstall/reset may restore defaults; this is a per-invocation
preference, not a background enforcement service. Disk savings depend on shared
dependencies, caches and retained snapshots; this does not lower VM RAM allocation.

Restore a shell component with `omarchy plugin enable ID`, using its ID above.
Reapplying lean mode disables the five components again. Omitting lean mode
does not re-enable them. Existing factory artifacts and running VMs are not
changed by editing these sources; new builds receive the first-owner defaults,
and existing guests receive them on an explicitly selected lean setup run.

## Upstream overlap review — 7 November 2026

The latest published release checked was [Omarchy 4.5.0](https://github.com/omacom/omarchy/releases/tag/v4.5.0).
Its [release notes](https://omarchy.org/news/2026/11/omarchy-4-5/)
introduce Hype, Signed, Disktree, Monologue and Gliff, and describe the new
Superwhisper default. Compare the [4.5.0 package list](https://github.com/omacom/omarchy/blob/v4.5.0/install/omarchy-base.packages)
with the [moving upstream development list](https://github.com/omacom/omarchy/blob/quattro/install/omarchy-base.packages):
the ARM64 guest uses edge, so a release tag alone does not pin its installed
software. The repository's reviewed factory source pins are unchanged by this
review. An actual guest inventory is needed to establish what a particular VM
has after updates and selected feature installation.

The existing removal list already covers LibreOffice, Obsidian, Omawrite, Hype,
Signed, Pinta, CLIamp, Moonlight, Omacut, Monologue, Superwhisper, Aether,
LocalSend, printing and physical-hardware tools. These overlap office, notes,
PDF signing, image/media work, dictation, sharing or host hardware tasks.

Additional candidates below are **review findings only**, not new removals.
They appear in the 4.5.0 defaults and are not currently targeted by the
full-image removal profile. They are also absent from the lean factory's
explicit root package list; dependencies and subsequent updates can differ.

| Candidate | macOS overlap | Reason to retain or assess first |
| --- | --- | --- |
| Omacalc (`omacalc`) | Calculator | Small convenience; low expected savings |
| Document Viewer (`evince`), imv (`imv`) | Preview | Useful for PDFs and images generated inside the guest |
| mpv / MPRIS (`mpv`, `mpv-mpris`) | QuickTime/media playback | Useful for testing generated media; check retained dependencies |
| Disktree (`disktree-bin`) | Storage inspection tools | Guest caches and Linux disk usage are separate from host storage |
| Disks (`gnome-disk-utility`) | Disk Utility | VM disks belong to VM Manager; keep underlying storage libraries |
| Gliff (`gliff`) | Remote desktop tools | Independent Omarchy remote desktop; keep only if deliberately used |
| Night light (`hyprsunset`) | Night Shift | Host can manage screen colour; disable the shell feature before assessing package removal |
| Video backgrounds (`owe`) | Wallpaper features | Rendering/lock-screen integration requires review; prefer a static background first |

Omarchy also ships [web-app launchers](https://omarchy.org/manual/web-apps/)
for services such as HEY, WhatsApp, Google Photos/Maps/Contacts, X, YouTube,
Discord and Zoom. These overlap host/browser activities and are good candidates
for later launcher cleanup, but they are not individual installed packages.
Microsoft 365 web apps are opt-in, not default packages to remove.

Keep guest browsers for localhost testing, terminals/editors, Docker/mise/build
tools, guest credentials, clipboard, notifications, screenshot/recording tools
and graphics/storage integration. Their host equivalents cannot replace their
guest-local development or integration role.
