# Project guidance

This repository customizes an official Try Omarchy ARM64 developer workstation on Apple Silicon. The Omarchy/Parallels and Ubuntu 26.04/Ansible paths remain temporarily as rollback options until the Try Omarchy workstation is accepted.

- Target the official Try Omarchy Mac app and its `aarch64` guest; do not silently broaden host, hypervisor, or architecture support.
- Let Try Omarchy own virtualization, graphics, display scaling, clipboard, host sharing, networking, SSH integration, persistence, and Mac app updates.
- Let Omarchy own Arch, Hyprland, applications, Docker, mise, language runtimes, and guest updates. Keep repository-owned guest changes limited to explicit workstation preferences.
- Never download or install host software without the user's explicit permission. The normal repository workflow may verify and open an already-installed Try Omarchy app.
- Keep host controllers conservative: show the proposal before changing a VM, refuse to replace existing VMs, checksum downloaded images, and identify the exact guest disk before an unattended wipe.
- Keep guest configuration small, idempotent, and safe to reapply.
- Hardware rendering is required. Do not accept `llvmpipe`, `softpipe`, or forced software rendering.
- Use Try Omarchy's native Retina and dynamic-resolution integration. Do not install repository-owned monitor or host-window controllers.
- Never commit real hostnames, IP addresses, usernames, passwords, tokens, private keys, or generated `cidata` media.
- Run `make test-omarchy` and the relevant shell/Python syntax checks documented in `README.md` after changing an Omarchy workflow.
- While the legacy path remains, keep its roles independently taggable, use `ansible.builtin` modules, and run the documented Ansible syntax check after changing YAML or Jinja templates.

