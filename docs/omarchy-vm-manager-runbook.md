# Omarchy VM Manager operator runbook

These are the only manual steps. Omarchy VM Manager owns the VM, image,
storage, graphics, clipboard, networking and SSH connection.

1. In the sibling Omarchy VM Manager checkout, build and verify the existing
   source without installing it globally:

   ```bash
   cd "../Omarchy VM Manager"
   make app verify-app
   ```

   This repository never installs host software.
2. Open `dist/Omarchy VM Manager.app` once. In **Guest Defaults**, configure
   and enable the owner account, password, keyboard, timezone and hostname
   prefix for new guests. The password remains in the Mac login Keychain.
3. From a Mac terminal in this repository, run:

   ```bash
   make bootstrap-omarchy-vm \
     VM_NAME="Dev Omarchy" \
     OMARCHY_VM_LAYOUT_FILE="$PWD/omarchy/examples/layouts/claude-two-terminals-browser.lua"
   ```

For a developer-only application selection, add
`OMARCHY_VM_LEAN_DEVELOPER=yes` to that command. It defaults off and removes
optional desktop apps and hardware tools through Omarchy, retaining required
desktop/VM integration and anything selected in `OMARCHY_VM_PACKAGES`. Review
the candidate removals in the proposal. See the README's lean developer section
for the tracked list, dependency safeguards and restoration instructions.

Review the printed proposal and confirm it. The command asks Omarchy VM Manager
to create or start the named guest, waits for its authenticated managed SSH
connection, and enables Omarchy's native 60-minute passwordless-sudo grant.
Confirm the native prompt and enter the guest sudo password. Bootstrap then
updates Omarchy and the guest system, installs the selected guest
software, and applies the repository-owned workstation preferences. It disables
the grant, reboots through Omarchy VM Manager, waits for SSH to return, and runs the
hardware/integration checks. New guests default to a 64 GiB sparse, grow-only
disk. It does not scan or modify personal SSH files.

Bootstrap attempts to revoke the grant on failure or interruption too. If cleanup
cannot reach the guest, it reports the failure; Omarchy's expiry and reboot cleanup
remain the fallback. A settings-package update can revoke the grant early and
cause later authentication prompts.

The managed reboot activates any compatibility repair or application layout
change; no additional logout or restart is required after a successful run.

Shared folders and general port forwarding are not part of the manager's
current CLI contract. Clone projects inside the guest for now; do not add a
second virtualization or SSH integration layer in this repository.

## Lean developer validation — 1 November 2026

Validated the opt-in profile on the existing managed aarch64 workstation using
Omarchy VM Manager 0.6.1 and `try-omarchy` 0.1.0-40. The normal Omarchy
update/snapshot path ran first. Its settings-package upgrade revoked the
temporary sudo grant; the operator renewed it, and application resumed without
repeating the update. The grant was revoked before the manager-owned reboot.

- Installed packages fell from 883 to 805: 78 removals, with no new system
  packages. The removed versions account for 1,330.44 MiB (about 1.30 GiB) of
  installed files, calculated from repository metadata matched to their exact
  pre-removal versions. Retained snapshots and caches mean this is not a claim
  about reclaimed host disk space.
- All installed removal candidates were removed except `superwhisper-bin`.
  Its native recursive transaction would also remove protected
  `pipewire-audio` and `pipewire-pulse`, so it was retained.
- Hardware-backed VirGL, Foot configuration, native display state, pinned SSH,
  clipboard channel, host-owned idle policy and lock masking passed after reboot
  and again after a graceful shutdown/relaunch. Package database checks found
  no errors; system and user managers reported no failed units.
- Clipboard text transfer in both directions was confirmed manually by the
  operator after relaunch. Automated transfer probes failed even though the
  native clipboard service was active; no automated end-to-end clipboard pass
  is claimed. The manager routes clipboard traffic only to the focused guest.
- Functional checks passed for C compilation/execution, Python standard
  libraries, Git commit/read, Neovim edit/write, tmux sessions and mise.
  Chromium rendered a local HTTP page using an isolated temporary profile.
  Docker ran an ARM64 `hello-world` container after removal, before reboot.
  Docker/Compose/Buildx commands and native Docker socket activation passed
  after reboot; ordinary Docker use still requires Omarchy's normal sudo policy.
- Reapplying the lean helper without a sudo grant left the installed package
  set unchanged. Existing Claude Desktop and 1Password CLI packages were
  retained; no additional lazy mise toolchains were installed for these checks.

Live testing found that pacman rejects combining `--nosave` with `--print`.
The profile now previews with `-Rs --print`, while Omarchy's actual removal
continues to use `-Rns`. Unexpected preview errors stop application instead of
being mistaken for dependency-protected packages. The focused suite passes all
82 tests, including this regression; documented shell/Python syntax checks pass.
