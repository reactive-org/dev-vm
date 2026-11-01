# Omarchy developer workstation

[![CI](https://github.com/reactive-org/dev-vm/actions/workflows/ci.yml/badge.svg?branch=main)](https://github.com/reactive-org/dev-vm/actions/workflows/ci.yml)

Get a ready-to-code ARM64 workstation on your Apple Silicon Mac with
[Omarchy VM Manager](https://github.com/reactive-org/omarchy-vm-manager).

## Prerequisites

Use an **Apple Silicon Mac** with the following host tools already available.
Install missing host tools separately; this repository does not install them.

| Dependency | When required |
| --- | --- |
| Git | Cloning this repository; also required for advanced image builds using an explicit source checkout. Default image builds use bundled guest sources. |
| Python 3.10+ (`python3`) and make | Running the repository's bootstrap, image-build, feature and validation targets. CI uses Python 3.14. |
| macOS Bash and OpenSSH (`ssh`, `scp`, `sftp`) | Shell scripts and guest access through VM Manager's managed SSH connection. |
| Omarchy VM Manager app and CLI | Creating, configuring and checking VMs from either factory. Save **Guest Defaults** in the app first. The CLI is discovered on `PATH`, then in `~/Applications` or `/Applications`. Lean image import also reads the installed app’s compatibility metadata. See [manager setup and CLI paths](docs/omarchy-bootstrap.md). |
| Docker CLI and a running ARM64 Linux engine | `make build-omarchy-image` and `make check-omarchy-image`. Full image builds require privileged containers. The official factory and image previews (`OMARCHY_IMAGE_PLAN=yes`) do not require host Docker. |
| Ansible (`ansible-playbook`, `ansible-inventory`) | Optional feature playbooks (`make apply-playbook`), `make syntax-check` and the complete `make test-omarchy` suite. CI pins `ansible-core` 2.21.5. Standard bootstrap does not require Ansible. |
| PyYAML | Reading YAML setup, catalogue or variables files. The loader can reuse the existing Ansible Python runtime; JSON files do not need PyYAML. |
| Authenticated GitHub CLI (`gh`) or `GH_TOKEN`/`GITHUB_TOKEN` | Optional theme selection by GitHub stars. See [theme selection](docs/omarchy-themes.md). |

Guest applications, Docker, mise and language runtimes are managed inside the VM
through Omarchy and the selected [features](docs/omarchy-features.md).
See [image build requirements](docs/omarchy-image.md) for disk-space allowances
and [repository checks](docs/development.md) for validation details.

## Quick start

Open the existing manager app and save **Guest Defaults**. Run from this
repository's root with an unused VM name.

**Official Try Omarchy:** Get running quickly with Omarchy’s standard apps already installed and no image build required.

```bash
make bootstrap-omarchy-vm VM_NAME="Dev Omarchy" OMARCHY_VM_FACTORY=official
```

**Lean, mean coding image:** Standard ARM64 Omarchy with a smaller app selection,
Git, Python and build tools, prepared for QEMU on your Mac using Try Omarchy’s
factory approach and Omarchy VM Manager’s native integration
([image details](docs/omarchy-image.md)).

```bash
make build-omarchy-image
make bootstrap-omarchy-vm VM_NAME="Dev Omarchy" \
  OMARCHY_VM_FACTORY=.artifacts/omarchy-image/latest
```

Bootstrap prepares/imports the image through VM Manager, creates the VM, then
updates it, applies preferences, restarts and checks it. Review the proposal
and confirm Omarchy's prompt, then enter the guest sudo password once near the
start. Bootstrap keeps sudo passwordless during setup and restores default sudo
authentication before restarting. Apps and layouts are selected during bootstrap.
An existing [custom image or factory bundle path](docs/omarchy-bootstrap.md#choose-a-starting-image)
works too; no manual import or manifest hash is needed.

## Pick your setup

Every runbook shows both image choices with copy-and-paste commands.

- [Standard workstation](docs/omarchy-vm-manager-runbook.md)
- [Trim optional desktop apps](docs/omarchy-official-trimmed-runbook.md)
- [Four tiled Foot terminals](docs/omarchy-layout-four-terminals.md)
- [Terminal left 40%, browser right 60%](docs/omarchy-layout-terminal-browser.md)
- [VS Code left 60%, browser right 40%](docs/omarchy-layout-vscode-browser.md)
- [Claude, two terminals and a floating browser](docs/omarchy-layout-claude-two-terminals-browser.md)

Next: [add developer tools](docs/omarchy-features.md) or [choose a theme](docs/omarchy-themes.md).

If projects own their tools through `mise.toml`, choose the
[`project-managed` profile](docs/omarchy-features.md#let-projects-manage-their-toolchains)
for the workstation, mise and native build prerequisites without selecting
global runtimes. Feature playbooks default the login shell to zsh; select `bash`
or `keep` through the [workstation shell setting](docs/omarchy-features.md#login-shell).

[All documentation](docs/README.md) · [Prerequisites and settings](docs/omarchy-bootstrap.md) · [Repository checks](docs/development.md)
