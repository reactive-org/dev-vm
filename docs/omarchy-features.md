# Developer profiles and feature extensions

Select a complete workflow with a profile, or select individual features. Both
use the official Omarchy VM Manager's pinned SSH connection to an existing,
running Omarchy `aarch64` guest. The official Try Omarchy and repository lean
factories use the same native Omarchy/mise operations.

## Start with a profile

Start from the normal [bootstrap workflow](omarchy-bootstrap.md), which updates
the guest through Omarchy. For an older or directly created factory guest, run
`omarchy update` inside it before adding features: stale package databases can
reference archives that the mirror has already removed. Feature application
deliberately does not refresh databases or upgrade the guest. The launcher asks
for the guest sudo password once before applying features, uses Omarchy's native
persistent grant during setup, and restores default sudo authentication afterward.

Resolve a profile locally before connecting to a guest:

```bash
make plan-omarchy-features OMARCHY_PROFILES=web
```

Apply it to an already running workstation:

```bash
make apply-playbook VM_NAME="Dev Omarchy" OMARCHY_PROFILES=web
```

| Profile | Features | Included selections |
| --- | --- | --- |
| `developer` | `workstation,cli,vcs,editors,api` | zsh, Foot/idle preferences, code search/navigation, Git/LFS/diff tools, Neovim and HTTP/TLS diagnostics |
| `web` | `developer` + `browsers,languages,docker,databases,quality` | Chromium, Node `lts`, pnpm, Docker/Buildx/Compose, PostgreSQL client, SQLite, shell/YAML checks and pre-commit |
| `python` | `developer` + `languages,build,databases,quality` | Python `3`, uv, native extension build prerequisites, CMake/Ninja/GDB, SQLite, shell/YAML checks and pre-commit |
| `project-managed` | `developer` + `toolchain,browsers,build,docker,databases` | mise with Bash/zsh activation, Chromium, build tools, Docker/Compose, PostgreSQL and SQLite clients; no global runtime selections |

Profiles supply selections and options; installation logic stays in independently
tagged features. Agents and credentials are optional additions to every profile.
Project frameworks, linters, tests, virtual environments and service stacks remain
in the project's dependency declarations, mise configuration and Compose files.
No profile creates a project, installs Git hooks or starts application services.

With no profile, selection file or explicit feature selection, the default is
still `workstation`. Enabling a profile does not implicitly install the old Node
or Claude defaults: Python selects Python/uv, and agents run only when selected.

## Select individual features

Existing commands and the explicit legacy variable file remain supported:

```bash
make apply-playbook VM_NAME="Dev Omarchy" \
  OMARCHY_FEATURES=workstation,browsers,docker,languages,agents,credentials

make apply-playbook VM_NAME="Dev Omarchy" OMARCHY_FEATURES=languages,agents \
  OMARCHY_VARS_FILE="$PWD/omarchy/local/features.yml"
```

Copy [the legacy variable example](../omarchy/examples/features.yml) to the ignored
`omarchy/local/features.yml`. Its values configure features; they do not enable
them. `OMARCHY_FEATURES` adds features to any selected profiles. Omitted features
leave existing software and settings alone; deselection never uninstalls tools.

| Feature / Ansible tag | Baseline when selected | Configuration |
| --- | --- | --- |
| `workstation` | zsh with Oh My Zsh and Starship, Foot size 12, host-owned idle policy and GPU compatibility repair | `shell`: `zsh`, `bash` or `keep`; `oh_my_zsh`, `oh_my_zsh_plugins`, `oh_my_zsh_update_mode`, `starship`, `starship_config`; `font_size`, `idle_mode`, `theme`, `layout`, `remove_layout` |
| `cli` | ripgrep, fd, fzf, jq and tree | `packages` list and `tools` mise map |
| `vcs` | Git, git-lfs, git-delta and lazygit | `packages` and `tools`; no identity, signing or hook configuration |
| `editors` | Neovim | `editors`: `neovim`, `vscode`, both or neither; settings/extensions remain untouched |
| `browsers` | Chromium through the native installer | `browsers`: `chromium`, `firefox`, both or neither |
| `languages` | Node using Omarchy's declaration when selected alone | `tools`: mise short-name/version map; Python and Ruby prerequisites are explicit |
| `toolchain` | mise, lazy shims when newly installed, and verification of Bash activation plus zsh hooks when zsh is the login shell | `prerequisites`: `ruby`, `python`, both or neither; native build libraries only, no runtime selection |
| `build` | base-devel, pkgconf, CMake, Ninja and GDB | `packages` and `tools` |
| `docker` | Docker, Buildx, Compose, native UFW integration and socket activation | `access`: `native` (standalone default) or `sudoless` (developer-profile default); requires active UFW |
| `databases` | SQLite CLI | `clients`: `sqlite`, `postgresql` or `mysql`; PostgreSQL uses `postgresql-libs`, MySQL uses `mariadb-clients`; no server initialization/activation |
| `api` | curl, OpenSSL and HTTPie | `packages` and `tools` |
| `quality` | ShellCheck through mise; yamllint and pre-commit guest packages | `packages` and `tools`; no changes to existing repositories |
| `agents` | Claude CLI using its native declaration | `tools`: `claude`, `codex`, `opencode`, `pi`, `copilot`, `amp`, `crush` |
| `credentials` | 1Password desktop app and CLI | `packages`: `1password`, `1password-cli`, `github-cli`; no sign-in or credential copying |

The source of built-in definitions is [catalogue.json](../omarchy/features/catalogue.json).
The launcher, Ansible defaults and guest validator use that same catalogue.
Built-in roles remain directly taggable. For the new composite variables, a
legacy file can set, for example, `omarchy_cli: {packages: [jq], tools: {}}` or
`omarchy_databases: {clients: [sqlite]}`. Existing variable names are unchanged.

An empty mise selector reuses an existing declaration, installing its tool if
needed. With no declaration, it selects `latest` at user level. Explicit selectors
such as `"3"`, `"lts"` or an exact version use a user mise selection while preserving
other tools. Moving selectors are not reproducibility guarantees, and an exact
runtime pin does not freeze rolling guest packages. System Python remains
`/usr/bin/python3` for Ansible.

Missing packages must exist in the guest's configured ARM64 repositories. No
third-party repositories, AUR builds, emulation or host installations are used.
ShellCheck uses its mise registry entry because the tested ARM64 repositories
do not provide the `shellcheck` package; mise selects its native Linux ARM64 release.
The `github-cli` compatibility choice reuses an existing package, or Omarchy's
existing `gh` mise declaration when present. Competing selected package/mise
providers are refused rather than resolved by changing PATH precedence.

## Login shell

The `workstation` feature defaults the owner's login shell to `zsh`. Override it
in a selection file:

```yaml
options:
  workstation:
    shell: zsh # zsh (default), bash, or keep the current shell
    oh_my_zsh: true # Default enabled; completion/plugins
    oh_my_zsh_plugins: [git, docker, docker-compose]
    oh_my_zsh_update_mode: reminder
    starship: true # Default enabled; prompt
    starship_config: |
      add_newline = false
      format = '$directory$git_branch$git_status$cmd_duration$line_break$character'

      [directory]
      truncation_length = 1
      substitutions = [
        { from = '([^/]{20})[^/]+', to = '${1}…', regex = true },
      ]

      [git_branch]
      format = '[$symbol$branch]($style) '
      truncation_length = 24
      truncation_symbol = '…'

      [cmd_duration]
      format = '[$duration]($style) '

      [character]
      success_symbol = '[❯](bold green)'
      error_symbol = '[❯](bold red)'
```

Set either boolean to `false` to opt out independently. Both are ignored for
`bash` and `keep`. Legacy variables and direct Ansible runs use `omarchy_shell`,
`omarchy_oh_my_zsh`, `omarchy_oh_my_zsh_plugins`, `omarchy_oh_my_zsh_update_mode`,
`omarchy_starship` and `omarchy_starship_config`.
`keep` skips shell installation, startup-file edits and login-shell changes.
The setting applies only when `workstation` is selected, including through a profile.

Zsh is installed through `omarchy-pkg-add`. Small additions to `~/.zshenv` and
`~/.zshrc` load Omarchy's native environment and activate mise when installed.
Personal configuration and native Bash startup files are preserved; customized
managed blocks and symlinks stop configuration for review. No global runtimes
are selected. Existing terminals keep their shell; log out and back in to refresh
the desktop session. Bootstrap alone retains its existing shell behavior until
the playbook's workstation feature is applied.

[Oh My Zsh](https://github.com/ohmyzsh/ohmyzsh) supplies completion and plugins
(`git` by default, or your existing `plugins` array).
[Starship](https://starship.rs/guide/) supplies the prompt and initializes last;
Oh My Zsh's theme is disabled when Starship is enabled. The desktop theme and
existing `~/.config/starship.toml` remain untouched. Omarchy's Nerd Font is reused.

`oh_my_zsh_plugins` defaults to `null`: preserve an existing `plugins` array, or
use `[git]` on a fresh shell. An explicit list replaces that array; `[]` enables
none. Selected plugins must already be bundled with Oh My Zsh or installed under
its default `custom/plugins` directory. Availability is checked before startup
files change; when the framework is absent, check mode defers that check until
application clones it. Plugins do not install their corresponding applications
or download third-party plugins. `oh_my_zsh_update_mode` defaults to `reminder`;
other modes are `prompt`, `auto` or `disabled`. An empty string leaves existing
native update policy alone.

`developer`, `web`, `python` and `project-managed` profiles default to the compact
two-line prompt shown above: one directory component with long names shortened
to 20 characters plus `…`, branches shortened to 24 plus `…`, and compact command
duration. Standalone `workstation` defaults to an empty string, leaving personal
settings active. Override `options.workstation.starship_config` with your own TOML,
or `""` to use personal settings; legacy `omarchy_starship_config` overrides take
precedence. `starship: false` disables the prompt integration.

When zsh and Starship are enabled, selected text is validated as TOML before
connecting to the guest, written to `~/.config/dev-vm/starship.toml`, and selected
with `STARSHIP_CONFIG` in the
managed startup block. TOML validation requires an existing Python 3.11+ on the
controller; other workflows still support Python 3.10. Starship owns module and
format semantics. Edit the playbook to update this managed configuration;
personal edits to managed files/blocks stop application for review. An explicit
empty string removes our `STARSHIP_CONFIG` export and retains the unused
managed file. Personal Starship files, aliases and other startup content remain
intact. These settings apply only when their respective zsh add-on is enabled.

Starship and Git use `omarchy-pkg-add`. Oh My Zsh is cloned from its official
repository into the guest owner's `~/.oh-my-zsh` only when absent. Its installer
is not run, and existing installations are reused without pulling or resetting;
updates remain with `omz update`. The resolved proposal includes this source.
Reapplying is idempotent. Disabling an option removes only its untouched managed
startup block and retains the installed software. Existing user-managed Oh My Zsh,
Starship or Powerlevel10k startup stops configuration for review rather than
adding competing initialization; opt out or migrate those startup lines first.

## Let projects manage their toolchains

Choose `project-managed` when each project's `mise.toml` owns its runtime and
external-tool versions. The independently tagged `toolchain` feature installs
mise through Omarchy and checks the owner's native interactive Bash integration.
It also verifies zsh activation when zsh is the login shell; `workstation` owns
the zsh startup additions. The toolchain feature never selects global runtimes,
edits shell startup files, trusts project configuration, clones a repository,
installs project dependencies or starts
application services. Existing Omarchy declarations and installed tools remain
intact. Missing native Bash activation stops application with a diagnostic;
restore it through Omarchy before retrying.

Select optional Ruby or Python native build prerequisites without installing
those runtimes. These complement the generic `build` feature and do not install
database servers. For example:

```yaml
schema_version: 1
profiles: [project-managed]
features:
  enable: [agents]
options:
  toolchain:
    prerequisites: [ruby]
  agents:
    tools:
      claude: ""
```

The generic [project-managed example](../omarchy/examples/project-managed.yml)
contains this selection. Resolve it before applying:

```bash
make plan-omarchy-features OMARCHY_SETUP_FILE=omarchy/examples/project-managed.yml
make apply-playbook VM_NAME="Dev Omarchy" \
  OMARCHY_SETUP_FILE=omarchy/examples/project-managed.yml
```

After independently obtaining a project in the guest, review its configuration
and run `mise install` from that checkout. Keep project tool declarations,
lockfiles, environment and tasks in the project. Check pinned releases and
backends on Linux ARM64, and make host-specific paths conditional in the project.
Mise activation is needed for directory enter/leave hooks; lazy shims alone do
not provide those hooks. Install and authenticate personal agent/credential
clients separately. No proprietary project configuration belongs in this repo.

The existing `web` and `python` profiles retain their global tool defaults.
Combining either with `project-managed` still explicitly selects their tools;
use `project-managed` alone to avoid those selections. An explicit empty
`languages.tools` map alone does not ensure mise or native build prerequisites;
select `toolchain` for that preparation.

## Customise a profile

Copy [the selection example](../omarchy/examples/setup.yml) to
`omarchy/local/setup.yml`, then edit it:

```yaml
schema_version: 1
profiles: [web]
features:
  enable: [agents]
  disable: [editors]
options:
  browsers:
    browsers: [firefox]
  languages:
    tools:
      node: "24"
  agents:
    tools:
      codex: ""
```

```bash
make plan-omarchy-features OMARCHY_SETUP_FILE="$PWD/omarchy/local/setup.yml"
make apply-playbook VM_NAME="Dev Omarchy" \
  OMARCHY_SETUP_FILE="$PWD/omarchy/local/setup.yml"
```

This selects the web workstation with Firefox, Node 24, inherited pnpm and Codex.
It skips editor management without removing an already installed editor. It does
not sign in to an agent. The versioned selection format is separate from
`OMARCHY_VARS_FILE`; passing it as legacy variables is an error.

Composition follows these rules:

- A profile inherits features and options from `extends`, then applies its own
  options. Multiple selected profiles combine their features.
- Conflicting sibling/composed choices require an explicit child or personal
  override. For example, `web,python` needs an explicit `databases.clients` choice;
  profile order never silently chooses between their different client lists.
- Tool maps merge by key across profile/override layers; lists replace. Empty
  lists/maps explicitly clear that selection. `tools: {}` selects no runtimes;
  overriding only `node` preserves inherited `pnpm`. In an override, use
  `tools: {pnpm: null}` to stop managing just that inherited tool. Null is removed
  during resolution and is never passed to mise as a version or uninstall action.
- A supplied option field replaces its feature's baseline field. Thus Python's
  tool map replaces the standalone languages baseline of Node. Baselines fill
  fields left unspecified after profile composition.
- Personal `options` override profile options; an explicit legacy variable file
  is the last override layer. Options never enable a feature.
- Explicit disables remove feature selections. A disabled required feature,
  dependency/inheritance cycle, unknown name/key/type, duplicate alias or
  incompatible tool selector is an error. Conflicts for disabled features do not
  prevent the remaining features from running.

## Add third-party features without a fork

Keep a data-only catalogue in your own versioned repository or under ignored
`omarchy/local/`. Supply its local path explicitly; there is no automatic remote
fetching or directory discovery. Each catalogue has a unique namespace.

```yaml
schema_version: 1
namespace: example
features:
  api-debug:
    description: HTTP and JSON diagnostics for the team's APIs
    requires: [api]
    packages: [curl, jq]
    mise: {}
profiles:
  backend:
    extends: [builtin.web]
    features: [example.api-debug]
    options:
      languages:
        tools:
          node: "24"
```

Register it in a selection file:

```yaml
schema_version: 1
catalogues: [team/catalogue.yml]
profiles: [example.backend]
```

Paths resolve relative to the selection file. The new feature and Ansible tag
are both `example.api-debug`. Built-in names can also use the `builtin.` prefix.
A custom feature's options are `packages` and `tools`; its `mise` catalogue field
supplies the default `tools` map. Prerequisites are feature IDs and run once
before their dependants. Identical package/tool requirements are reused.

Try the complete, committed downstream example without a VM:

```bash
make plan-omarchy-features OMARCHY_SETUP_FILE="$PWD/omarchy/examples/team/setup.yml"
```

For a standalone catalogue, use `OMARCHY_CATALOGUE=/absolute/path/catalogue.yml`
with `OMARCHY_FEATURES=example.api-debug`. The Python launcher also accepts repeated
`--catalogue` arguments. CLI `OMARCHY_PROFILES` adds profiles to those in a selection
file; personal `options` still have final precedence over profile choices.

The [selection schema](../omarchy/features/selection.schema.json) and
[catalogue schema](../omarchy/features/catalogue.schema.json) provide editor
completion and structural validation. Semantic validation, including references
and conflicts, always runs in the resolver. Examples contain relative
`yaml-language-server` schema directives; adjust them when storing files elsewhere.
Regenerate schemas after changing built-ins with:

```bash
python3 scripts/omarchy_profiles.py --write-schemas
```

Catalogues and selection/legacy files are parsed as bounded plain YAML or JSON.
Duplicate keys, explicit YAML tags, anchors/aliases and Jinja/lookups are rejected.
Only guest package names and mise registry short names with string version
selectors are accepted as installation operations. Catalogues cannot register
shell commands, Ansible roles, service actions, repository sources, credentials
or connection variables. Arbitrary role loading remains a future extension;
configuration beyond these data operations needs a reviewed repository change.

## Review, apply and validate

```bash
# Local resolution only: no manager connection, staging or sudo.
make plan-omarchy-features OMARCHY_PROFILES=python

# Also validate the manager's connection/proposal, without staging a payload.
make apply-playbook VM_NAME="Dev Omarchy" OMARCHY_PROFILES=python OMARCHY_PLAYBOOK_PLAN=yes

# Inspect guest state with a temporary payload, without installing/configuring.
make apply-playbook VM_NAME="Dev Omarchy" OMARCHY_PROFILES=python OMARCHY_PLAYBOOK_CHECK=yes
```

The resolved proposal lists selections, options, dependency reasons, package/tool
requirements, affected configuration/services and SHA-256 hashes of source files.
Sources are rechecked after confirmation; a changed file requires a new proposal.
The plan records requested selectors, not observed installed versions. It does
not claim that a package/tool is available on a guest it has not inspected.

Guest preflight checks all missing repository packages before applying any role.
With mise already installed it also checks registry short names; on a lean guest
without mise that check follows native mise installation. Release download/build
availability is ultimately checked by mise during installation. Check mode never
installs mise solely to inspect a registry entry and cannot validate those
releases or predict every native browser/workstation/firewall effect. Installation
failures can leave completed package/tool additions; rerun after fixing the cause.

Normal runs use Omarchy's native `permanent` sudo grant for the setup window and
attempt revocation, cached-authorization clearing and verification on success,
failure and interruption. The grant has no automatic expiry and survives reboot;
if cleanup cannot run, use `omarchy sudo passwordless --disable && sudo -K` in
the guest. Check mode enables no grant, installs no
packages, writes no preferences and starts no services; its temporary payload is
removed even on failure. The launcher does not create, start, resize or reboot a
VM. Docker retains the native firewall and service integration. Developer profiles
request Omarchy's interactive Sudoless Docker opt-in (root-equivalent Docker group)
when Docker is selected; standalone Docker defaults to native sudo access. Override
with `options.docker.access: native`. After opting in, restart through VM Manager
to refresh existing desktop credentials. The launcher verifies direct local API
access plus Compose/Buildx after setup sudo is revoked. Declined consent fails
setup; check mode obtains no consent and changes no membership. Direct Ansible
runs require native enrollment beforehand. No socket permissions are weakened or
host forwards added. See [Docker access](omarchy-playbooks.md#native-ownership).

Local tests cover both factory fixtures, all three complete profiles, reapplication,
selection/conflicts, schema/data rejection, independent tags, check mode, preflight
and cleanup. Separate [live acceptance](omarchy-profile-validation.md) passed all
three profiles on six disposable official/lean guests on 1 November 2026, after
the recorded provider and preparation corrections. That record identifies the
tested builds, actual checks and remaining integration limits. Repeat live
acceptance for changed builds/selections using disposable guests and check:

- `developer`: chosen editor, search/Git/HTTP tools; preserve existing settings.
- `web`: Node/pnpm versions, browser with hardware rendering and a project-owned
  container workflow through native Docker access.
- `python`: Python/uv versions and creation of a temporary virtual environment;
  `/usr/bin/python3` still runs independently.
- Reapplication and deselection preserve unrelated applications and user files;
  `make check-omarchy-vm VM_NAME="Dev Omarchy"` validates hardware/integration.

See the [playbook contract](omarchy-playbooks.md) and
[repository checks](development.md). VM Manager continues to own virtualization,
SSH, networking, clipboard and display integration; Omarchy owns guest updates.
Personal legacy `local-vars.yml` and `developer_extra_tasks.yml` remain ignored
and are not loaded or copied to a guest.

## Further feature sets

The next proposed profiles remain `data`, `rails`, `systems`, `jvm` and `platform`.
Cloud/provider and Kubernetes capabilities still need implementation and ARM64
acceptance. They can build on this framework without changing profile semantics;
services, credentials and infrastructure operations should remain explicit.

Native interfaces: [Omarchy package installation](https://github.com/omacom/omarchy/blob/quattro/bin/omarchy-pkg-add),
[browser installation](https://github.com/omacom/omarchy/blob/quattro/bin/omarchy-install-browser),
[Omarchy's mise declarations](https://github.com/omacom/omarchy/blob/quattro/etc/mise/conf.d/omarchy-tools.toml)
and [mise registry short names](https://mise.jdx.dev/cli/registry.html).
