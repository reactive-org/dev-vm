# Omarchy feature playbooks

The playbook targets the non-root owner of an Omarchy `aarch64` guest with native Try Omarchy integration. Both the official factory and the repository's lean factory use the same roles and Omarchy/mise commands. No Ubuntu package sources, roles, desktop templates, personal-key synchronization or Parallels controllers remain.

## Selection

```bash
make apply-playbook VM_NAME="Dev Omarchy" OMARCHY_FEATURES=browsers,docker
make apply-playbook VM_NAME="Dev Omarchy" OMARCHY_FEATURES=languages,agents \
  OMARCHY_VARS_FILE="$PWD/omarchy/local/features.yml"
```

`OMARCHY_FEATURES` selects independent features. With no selection the default is `workstation`. The original six names remain supported; `cli`, `vcs`, `editors`, `build`, `databases`, `api` and `quality` are also available. `OMARCHY_PROFILES=developer`, `web` or `python` selects a workflow, with explicit features added to it. Every built-in role and namespaced data extension has its own tag. Direct Ansible runs can select built-in tags using their own inventory based on VM Manager's managed SSH connection. Profiles and extension registration resolve through the supported launcher, which generates the private inventory and passes the resolved tags and variables.

```bash
make plan-omarchy-features OMARCHY_PROFILES=web
make apply-playbook VM_NAME="Dev Omarchy" OMARCHY_PROFILES=python
make apply-playbook VM_NAME="Dev Omarchy" OMARCHY_SETUP_FILE="$PWD/omarchy/local/setup.yml"
```

See [profiles and extensions](omarchy-features.md) for the feature catalogue, example selection/catalogue files, inheritance and merge rules, schemas and preflight limits. `plan-omarchy-features` resolves local data without contacting a VM. The existing `OMARCHY_PLAYBOOK_PLAN=yes` also checks the manager connection. Both show source hashes and resolved requirements. Built-in definitions come from `omarchy/features/catalogue.json`; the controller, playbook defaults and guest validator share that contract.

Configure legacy lists and version mappings using `omarchy/examples/features.yml`, or use the new `omarchy/examples/setup.yml` selection format via `OMARCHY_SETUP_FILE`. Copy local files to ignored `omarchy/local/` and pass them explicitly. Options do not enable roles. Empty lists/maps select no tools for that field. Legacy option variables override profile options. Plain YAML/JSON parsing rejects duplicate keys, templates, lookups, tags and aliases before connecting. Connection overrides and internal payload variables are refused. Extension catalogues accept only package/mise operations and feature dependencies; they cannot register executable hooks or roles. Old ignored root-level variable/task files remain on disk but are never loaded.

| Role | Official factory | Lean factory |
| --- | --- | --- |
| Workstation | Reapply the explicit preferences using existing helpers | Reuse/reapply the same first-login defaults |
| Browsers | Leave installed browsers and user flags alone | Run the native browser installer for missing Chromium/Firefox |
| Docker | Reuse packages, firewall rules and existing daemon/socket activation | Install missing Docker/Buildx/Compose/UFW integration, then activate the socket |
| Languages | Reuse installed active versions and Omarchy's declarations | Install mise and selected runtime prerequisites before selecting tools |
| Agents | Install only selected lazy tools that are missing | Install mise and only selected coding agents |
| Credentials | Reuse installed tools without changing login state | Add selected packages without importing credentials |
| CLI/VCS/build/API/quality | Reuse selected packages/tools without replacing personal configuration | Add only the selected guest packages/mise tools; no project hooks or services |
| Editors/database clients | Preserve settings, installed alternatives and database contents | Install selected editor/client packages; no extensions, database initialization or server activation |

Roles ensure presence; deselecting one never removes existing software. Image identity is not inferred from package count or an image filename. The guest must satisfy the same OS, architecture, native command and integration checks. A custom factory must separately pass VM Manager's admission and owner-provisioning contract before it can be used.

For project-owned mise versions, select `OMARCHY_PROFILES=project-managed` or
the independently tagged `toolchain` feature. Its composite variable is
`omarchy_toolchain: {prerequisites: [ruby]}`; supported prerequisites are Ruby
and Python native build libraries. It verifies existing native Bash activation
and zsh mise hooks when zsh is the login shell, and makes no global runtime
selections or project changes. See the
[project-managed workflow](omarchy-features.md#let-projects-manage-their-toolchains).

## Native ownership

Packages go through `omarchy-pkg-add`; browsers use `omarchy-install-browser`. The supported browser names are Chromium and Firefox, available through the ARM64 repositories. The playbook does not add third-party repositories, run AUR builders or silently substitute another architecture.

Runtime and agent selections use mise registry short names. An empty version keeps Omarchy's existing declaration and installs it only if absent. Explicit selectors use `mise use --global` when the desired version is absent or differs from the current default. Other tools and config entries are preserved. A new mise installation builds Omarchy's lazy shims without eagerly installing all declared tools. Ruby/Python selections install their native build/library prerequisites. The Ansible interpreter remains system Python, independent of mise.

Supported coding-agent short names are `claude`, `codex`, `opencode`, `pi`, `copilot`, `amp` and `crush`. Credential-package selections are `1password`, `1password-cli` and `github-cli`; the last reuses an installed package or an existing Omarchy `gh` mise declaration when available. Installing these tools does not sign in, open an authentication UI, copy SSH keys or transfer host tokens. Use the tools' own authentication flow in the guest afterward. Browser extensions and optional desktop/CLI authentication switches remain native, explicit choices.

Docker retains Omarchy's sudo/polkit policy. No account is added to the docker group. The role requires an active existing UFW policy, uses packaged `ufw-docker install`, and adds Omarchy's two standard container-to-host DNS exceptions through UFW. Those exceptions are deferred on the lean factory until Docker is selected. It reloads UFW only when integration/rule files change and enables socket activation when neither an active daemon nor the desired socket already exists. It preserves existing rules, including manager SSH access, and never resets the firewall or opens a host forward. A customized inactive UFW policy stops Docker configuration before a new socket is started. Docker daemon and resolved configuration remain owned by Omarchy's settings package.

Workstation preferences reuse the existing Foot, idle, theme, layout and GPU-preserving compatibility helpers. They ensure Herdr/Udiskie autostart, socat shell IPC, ImageMagick background inspection and inotify-tools watching are available when repairing an older lean guest. A known old repository first-login unit receives a hash-guarded ordering drop-in; customized overrides are preserved. They do not install monitor, clipboard, SSH, shared-folder or host-window controllers. Existing hardware-rendering validation remains required after a graphical login.

The workstation login shell defaults to zsh. Set `options.workstation.shell` in a
selection file, or `omarchy_shell` in legacy variables/direct Ansible, to `zsh`,
`bash` or `keep`. Zsh uses small additive startup blocks for Omarchy's environment
and mise activation; native Bash configuration stays intact. Shell changes use
`chsh` for the owner, require a registered executable shell, and take effect in new
login sessions. Check mode reports planned shell/package/file changes without
writing files or changing the account. See [login shell](omarchy-features.md#login-shell).

## Connection and privilege lifecycle

The guest must already be running with authenticated managed SSH. The launcher checks VM Manager's protocol/version, guest UUID, protected status, NAT policy and exact pinned SSH command, then generates a mode-0600 inventory and parameters in a private temporary directory. It uses the manager-owned identity and known-host pin, disables shared SSH multiplexing and cleans its temporary files on exit. It never scans personal SSH files or changes VM resource/lifecycle settings.

Normal application clears any older native grant and cached sudo authorization, then asks for Omarchy's native consent and the guest sudo password once near the start. It uses `omarchy sudo passwordless permanent` for the setup window so long runs and settings updates do not revoke access midway; even theme application can need its privileged browser-policy writer. The launcher attempts revocation and cached-authorization clearing (`sudo -K`) on success, failure, Ctrl+C, SIGTERM, SIGHUP and even a partially completed grant operation, and verifies that passwordless sudo is inactive. This mode has no automatic expiry and survives reboot: after an uncatchable termination or unavailable SSH, run `omarchy sudo passwordless --disable && sudo -K` in the guest. Check-mode runs do not request a grant. No password is stored in Ansible inventory, variables, arguments or logs. A direct Ansible run needs a native grant enabled in the guest before application and manually revoked afterward.

```bash
make apply-playbook VM_NAME="Dev Omarchy" OMARCHY_FEATURES=agents OMARCHY_PLAYBOOK_PLAN=yes
make apply-playbook VM_NAME="Dev Omarchy" OMARCHY_FEATURES=agents OMARCHY_PLAYBOOK_CHECK=yes
```

Plan mode reads manager metadata and validates local options without staging a guest payload or changing privileges. Check mode reads guest state and stages/removes a temporary owner-owned helper payload; it never invokes installation/configuration commands or enables a sudo grant. Workstation and Docker firewall checks conservatively report planned work rather than executing native mutating tools. Root facts/platform checks and payload cleanup are tagged `always`. The temporary guest payload is also removed when a role fails. Resolved runs preflight all missing repository packages before applying roles; registry names are checked when mise is available. Lean guests without mise defer registry checks until after its native installation. Actual release/build availability is established by mise, so preflight does not guarantee an atomic installation.

No automatic full update or reboot runs as part of feature application. Omarchy retains updates; VM Manager retains restart. Newly installed runtimes or applications can require a new login. The existing bootstrap controller still owns its separately requested update/restart workflow and defaults to no additional software.

## Validation

The [three-profile live acceptance record](omarchy-profile-validation.md) covers
installation, zero-change reapplication, selected-runtime execution, restart
persistence and hardware rendering on six fresh official/lean guests. It records
the ARM64 ShellCheck provider correction and native update/authorization limits;
its scope does not imply acceptance of every catalogue alternative.

```bash
make syntax-check
make test-omarchy
PYTHONPYCACHEPREFIX=/tmp/dev-omarchy-pycache python3 -m py_compile \
  scripts/omarchy_playbook.py scripts/omarchy_vm_manager.py omarchy/guest/apply-features.py
```

Tests cover both initial package sets, complete profile reapplication, profile composition/conflicts, local extension/schema rejection, version selection, selective prerequisites, check-mode mutation refusal, firewall/activation policy, pinned-connection inventory, variable-override refusal and privilege cleanup. Actual Ansible tests verify built-in/extension tag isolation, preflight cleanup and that check mode reaches a controlled helper, with zero changes reported. These tests do not install real features into a VM. Live manual/unattended owner, browser/GPU, agent authentication, Docker containers and clipboard/display acceptance remain separate disposable-guest checks.

The earlier 1 November 2026 baseline passed all 114 tests and documented syntax checks. Fresh manager 0.9.2 official-image results, including current repository-test limitations, are recorded in the [official acceptance record](omarchy-official-43-validation.md). Disposable official-image testing found and fixed a mise metadata parsing issue that caused repeated language/agent selection. Later lean-image testing corrected archive permissions, desktop dependencies, first-login ordering and the first-frame VirGL setting. See the [live acceptance results](omarchy-playbook-validation.md) and [lean 43.1 acceptance record](omarchy-lean-43-validation.md) for observed checks and limits. The VM Manager checkout remains unchanged.

Sources for the native interfaces: [Omarchy browser installer](https://github.com/omacom/omarchy/blob/quattro/bin/omarchy-install-browser), [Omarchy mise declarations](https://github.com/omacom/omarchy/blob/quattro/etc/mise/conf.d/omarchy-tools.toml), [mise use](https://mise.jdx.dev/cli/use.html), [packaged UFW/Docker integration interface](https://github.com/chaifeng/ufw-docker).
