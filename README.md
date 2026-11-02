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
| Ansible (`ansible-playbook`, `ansible-inventory`) | Optional feature playbooks, external setup application/bootstrap, `make syntax-check` and the complete `make test-omarchy` suite. CI pins `ansible-core` 2.21.5. Standard bootstrap does not require Ansible. |
| PyYAML | Reading YAML setup, catalogue or variables files. The loader can reuse the existing Ansible Python runtime; JSON files do not need PyYAML. |
| Python 3.11+ | Developer-profile compact prompts or custom `starship_config` TOML; validation uses the standard-library TOML parser. |
| Authenticated GitHub CLI (`gh`) or `GH_TOKEN`/`GITHUB_TOKEN` | Optional theme selection by GitHub stars. See [theme selection](docs/omarchy-themes.md). |

Guest applications, Docker, mise and language runtimes are managed inside the VM
through Omarchy and the selected [features](docs/omarchy-features.md).
See [image build requirements](docs/omarchy-image.md) for disk-space allowances
and [repository checks](docs/development.md) for validation details.

## Quick start

For the in-progress shared Swift controller, see [Swift provisioning foundation](#swift-provisioning-foundation).
The commands below still use the existing Python controller.

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

Keep a complete setup in a separate repository with
[external setup repositories](docs/omarchy-setup-repositories.md): VM resources,
features, layouts, dotfiles and explicitly trusted custom Ansible tasks. Start
from the [standalone example](omarchy/examples/setup-repo/README.md):

```bash
make plan-omarchy-setup OMARCHY_SETUP_REPO="$HOME/my-workstation"
make bootstrap-omarchy-vm VM_NAME="Dev Omarchy" \
  OMARCHY_SETUP_REPO="$HOME/my-workstation" OMARCHY_SETUP_TRUST_TASKS=yes
```

If projects own their tools through `mise.toml`, choose the
[`project-managed` profile](docs/omarchy-features.md#let-projects-manage-their-toolchains)
for the workstation, mise and native build prerequisites without selecting
global runtimes. Feature playbooks default to zsh with optional Oh My Zsh and
Starship enabled; select `bash`
or `keep` through the [workstation shell setting](docs/omarchy-features.md#login-shell).

## Swift provisioning foundation

The root SwiftPM package targets Swift 6 and macOS 15+. It exports
`DevVMProvisioningCore` and the migration-stage `dev-vm` executable. This first
milestone-2 slice validates setup manifest structure only. It has no process,
Ansible, SSH, manager, VM or installation interface. The legacy Python commands
above remain the operational entry points until an explicit cutover.

```sh
make build-provisioning test-provisioning
swift run --skip-build dev-vm validate-manifest omarchy/examples/setup-repo/vm.yml
make test-provisioning-oracle  # development-only, requires existing Python/PyYAML
```

`validate-manifest` accepts one explicit `.json`, `.yml` or `.yaml` file and
returns a JSON count summary with `structure_valid: true`, `resolved: false`
and `execution_available: false`. Invalid input exits 1; invalid commands exit 2.
Diagnostics use fixed codes and optional numeric locations, never source text,
paths or variable values. Source assets, dotfiles and custom task entry points
are declarations: they are not opened, captured or executed. No host dependency
checks occur. The compiled CLI/parser works with Python and Ansible absent from
`PATH`; the Swift toolchain is needed only to build it.

The data readers enforce UTF-8, 256 KiB input, at most 30 container levels,
string-only unique keys, finite numbers and no template markers. YAML aliases,
anchors, explicit tags, version/tag directives and merge keys are rejected before composing
a tree. JSON uses a bounded grammar and Foundation string decoding; malformed
JSON never falls back to YAML. File reads reject leaf symlinks, directories,
FIFOs, oversized inputs and detectable changes during the read. This is not a
repository snapshot or protection against later path/asset replacement.

The YAML event parser is compiled from the unmodified parser subset of Yams
6.2.2's CYaml/LibYAML at `a27b21e0c81c5bf42049b897a62aaf387e80f279`, behind a
small C event bridge and Swift validation. It needs no host YAML library. See
[the SHA-256 inventory](ThirdParty/ParserInventory.json) and the bundled
[Yams](Sources/DevVMProvisioningCore/Resources/Yams-LICENSE.txt) and
[LibYAML](Sources/DevVMProvisioningCore/Resources/LibYAML-LICENSE.txt) MIT notices.
Selection schema/catalogue resources are copied from this repository's
`ed36bbec92943c10f9a0b1b2d4887a4f4a190bff` baseline; tests require exact hashes
and equality with their maintained originals. Changes require reviewed inventory
and fixture updates. SwiftPM supplies the resource bundle through the library.
Only catalogue/schema resources are packaged in this slice; playbooks, roles,
presets and guest helpers remain in their existing locations for the later port.

Manifest validation covers schema version, IDs, VM field types/ranges,
selection fields/options against the bundled schema, known builtin references,
duplicate aliases, relative source declarations, reserved/overlapping dotfile
targets, quoted modes and unique task names. Namespaced references are lexical
declarations until their catalogues are resolved. `starship_config` is bounded
schema text here; TOML parsing, effective option validation, profile merging,
source traversal/symlink checks, factory admission, snapshots and plan generation
are still pending. A `SetupManifest` is not an approved executable plan.

Compatibility changes are deliberate and limited: signed 64-bit integers;
decimal finite floating point (including exponent notation); YAML 1.1 boolean
spellings retained; unquoted timestamps and legacy octal/hex/binary,
underscored or sexagesimal numbers rejected. Quote such values when they are
intended as strings. Unlike PyYAML, numeric exponent notation in YAML mappings
is consistently numeric. DEL characters in bounded names/paths, any `.git`
path segment and canonically equivalent duplicate Unicode keys are also refused.
Bare and `pkg:` selectors for the same package are treated as duplicate
declarations. These are not claims of complete Python-controller parity.

**VERIFIED — local no-VM checks, 2 November 2026:** build and 12 Swift test
functions pass, including 94 parameterized cases and 18 shared plain-data
fixtures. The unchanged Python loader agrees on all 18 oracle fixtures with
subprocess fallback disabled. The Swift tests and CLI also pass with
`PATH=/nonexistent` (test runner invoked by absolute toolchain path). Existing
`make test-omarchy` passes 235 tests with one Lua fixture skipped because Lua is absent, using the
already-installed Homebrew Python and local socket access. The initial system
Python 3.9 run lacked `tomllib`; the restricted run could not start Ansible's
local RPC server. Neither required an installation or a code workaround.
`make syntax-check` passes both unchanged playbooks, with expected empty-host
inventory warnings. No real guest or VM operation was performed.

**TO PROVE:** complete controller/selection/TOML parity, planning and snapshots,
full resources, immutable manager dependency pin, app/helper integration,
read-only app relocation, transport/authorization, the live terminal and all
real-guest behavior. The manager's execution gates remain disabled.

[All documentation](docs/README.md) · [Prerequisites and settings](docs/omarchy-bootstrap.md) · [Repository checks](docs/development.md)
