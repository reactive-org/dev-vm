# Try Omarchy operator runbook

These are the only manual steps. The repository takes over once SSH is
reachable.

1. Install the reviewed [Try Omarchy 1.2.0 release][release] from its official
   DMG. Its SHA-256 must be
   `403e7695c824dc67448d9f273bd105c6a17db2e89fd120d9fc7df1d647af30ba`.
   The repository does not install host software.
2. Launch Try Omarchy, create the normal Omarchy account, and wait for the
   desktop. Do not run an Omarchy system update during initial setup.
3. Open **Setup → Try Omarchy Settings** and set:
   - Resources: **8 CPUs, 20 GiB RAM, 64 GiB sparse disk**.
   - Networking: **NAT**.
   - Shared folder: **`~/Shared`**, enabled read/write.
   - Under **Port forwarding**, choose **Add SSH** and keep the prefilled TCP
     mapping **`127.0.0.1:2222` → guest port `22`**. This also requests `sshd`
     for the next boot; no separate guest SSH setup is needed.
4. Save the settings and choose **Restart Try Omarchy…**. A guest-only reboot
   does not apply port forwarding.
5. From a Mac terminal in this repository, run:

   ```bash
   make bootstrap-try-omarchy \
     GUEST_USER="<omarchy-user>" \
     TRY_OMARCHY_LAYOUT_FILE="$PWD/omarchy/examples/layouts/claude-two-terminals-browser.lua"
   ```

Replace `<omarchy-user>` with the account created inside Omarchy; it is not
necessarily the Mac username. Review the printed proposal and confirm it. On a
new VM, enter the guest password once to authorize the existing Mac SSH public
key, then enter it for Omarchy's own Claude Desktop and 1Password installers.
Passwords are never stored by the repository.

When the command finishes, restart Try Omarchy only if it says the compatibility
repair changed the Hyprland configuration. Otherwise, log out and back in once
to activate a selected application layout.

[release]: https://github.com/omacom/try-omarchy/releases/tag/v1.2.0
