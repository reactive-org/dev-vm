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
