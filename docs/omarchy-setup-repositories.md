# External workstation setup repositories

Keep VM resources, developer features, layouts, dotfiles and custom guest tasks
in a separate repository. dev-vm supplies the execution engine; no fork or edits
to its tracked files are required. Existing bootstrap commands, selection files,
data-only catalogues and `apply-playbook` remain supported.

This workflow uses the existing Omarchy VM Manager Mac app and its Omarchy
`aarch64` guest on Apple Silicon. Application requires the existing host
prerequisites including Ansible. The runner installs no host tools and never
clones or pulls your setup repository.

## Start with the example

Copy the complete [example setup repository](../omarchy/examples/setup-repo/README.md)
into a directory you control, optionally maintained in your own Git repository.
Review its selections, dotfiles and task files. Run from the dev-vm checkout:

```bash
# Local resolution only: no VM connection, task evaluation or sudo.
make plan-omarchy-setup OMARCHY_SETUP_REPO="$HOME/my-workstation"

# Create/configure, update, apply, restart and validate.
make bootstrap-omarchy-vm VM_NAME="Dev Omarchy" \
  OMARCHY_SETUP_REPO="$HOME/my-workstation" OMARCHY_SETUP_TRUST_TASKS=yes

# Reapply to a running guest without updating or restarting it.
make apply-omarchy-setup VM_NAME="Dev Omarchy" \
  OMARCHY_SETUP_REPO="$HOME/my-workstation" OMARCHY_SETUP_TRUST_TASKS=yes
```

`bootstrap-omarchy-setup` is an explicit alias for the external bootstrap path.
Omitting `OMARCHY_SETUP_REPO` from `bootstrap-omarchy-vm` retains the original
workflow. Bootstrap retains native factory admission, exact-name checks,
proposal confirmation, update, sudo cleanup, restart and hardware checks. It
never replaces an existing VM or its factory disk. Apply never creates, starts,
resizes, updates or restarts a VM.

Use `OMARCHY_SETUP_MANIFEST=subdirectory/vm.yml` for a different manifest path.
All source paths resolve against the setup repository root, including when the
manifest is nested. There is no automatic discovery or remote fetching.

## Manifest version 1

Only documented fields are accepted. YAML aliases, tags and templates are
rejected in plain YAML/JSON manifests and catalogues. Ansible tasks/templates
are executable inputs and follow Ansible's own format.

```yaml
schema_version: 1
id: personal
vm:
  name: Dev Omarchy
  # Omit factory to preserve an existing guest's factory; new guests use official.
  cpus: 8
  memory_gib: 20
  disk_gib: 64
  packages: [pkg:chromium]
setup:
  profiles: [project-managed]
  features:
    enable: [agents]
  options:
    workstation:
      shell: zsh
      oh_my_zsh_plugins: [git, docker, docker-compose]
      layout: layouts/coding.lua
    agents:
      tools:
        claude: ""
dotfiles:
  - source: dotfiles/git/config
    target: ~/.config/git/dev-vm-preferences.conf
    mode: "0644"
tasks:
  - name: projects
    file: tasks/projects.yml
  - name: git
    file: tasks/git.yml
assets: [templates]
vars:
  projects_directory: Development/Projects
```

`id` is a stable lowercase ownership/provenance name. Keep it stable when moving
the repository. All sections except `schema_version` and `id` are optional.
Without a feature selection the existing `workstation` default applies. To
select no built-in features, explicitly disable it with
`setup.features.disable: [workstation]`.

`setup` accepts the existing [profile/selection fields](omarchy-features.md),
including `catalogues`, with its nested `schema_version` defaulting to 1. Options
configure selected features; they do not enable them. Profile merging,
dependency/conflict checks and deselection semantics are unchanged.
`project-managed` prepares mise/native build tools without global runtimes.
Projects retain ownership of dependencies, service stacks and runtime versions.

VM defaults are 8 CPUs, 20 GiB RAM and a grow-only 64 GiB disk. `vm.name` defaults
to `Dev Omarchy`. `vm.lean_developer` defaults to false and enables the existing
opt-in removal profile during bootstrap when true; apply does not run that
removal profile. `vm.packages` uses bootstrap selectors
(`pkg:NAME`, `mise:NAME` or existing native auto-selection). Apps are ensured
before features/layouts on both bootstrap and apply. Check mode reports these
selectors but does not inspect/install them; use features/catalogues when package
check-mode inspection is needed.

`vm.factory` accepts `official`, an admitted manifest hash or a compatible local
factory path. Manifest factory paths resolve relative to the setup repository
and may reference an independently built artifact outside it. Disks are never
copied into the setup snapshot; native checksum/admission checks remain
responsible for them. Runtime source/assets must stay inside the setup repository.

For bootstrap, explicit `VM_NAME`, `OMARCHY_VM_CPUS`, `OMARCHY_VM_MEMORY_GIB`,
`OMARCHY_VM_DISK_GIB` and `OMARCHY_VM_FACTORY` override manifest values. A CLI
factory path resolves against the calling directory. Other software/preferences
belong in the manifest; explicitly supplied legacy feature/preference flags are
refused rather than silently ignored. Existing installed manager app/CLI overrides work as
before. Configure owner account, password, keyboard, timezone, SSH-key policy
and supported host sharing through VM Manager. Keep credentials out of the repo.

## Dotfiles and conflicts

Each entry selects a file or directory. Directories expand into individual files;
empty directories are not deployed. Targets are relative to the guest owner's
home, optionally prefixed with `~/`. Permissions default to `"0644"`; quote octal
modes explicitly. Symlink sources/destination ancestors and overlapping targets
are refused. Credential directories such as `.ssh`, `.gnupg` and `.aws`, and
runner state, are refused as targets. Do not select credentials elsewhere either.

Ownership, content hashes and modes are recorded in
`~/.local/state/dev-vm/dotfiles.json`. Reapplication updates files that match the
last deployed version. Identical unmanaged files can be adopted. Conflicts and
guest edits stop deployment before any selected dotfile is written. Files owned
by another setup are refused.

After reviewing conflicts, explicitly retain backups and replace them with
`OMARCHY_SETUP_DOTFILES_CONFLICT=backup`. Adjacent backups are named
`NAME.dev-vm-backup-UNIQUE_ID`; their paths are reported. This cannot transfer
ownership from another setup. Removing an entry never deletes its guest file or
ownership record. Unrelated files remain intact.

Prefer snippets over replacing Omarchy-owned files. Use workstation shell/prompt
options where possible. If managing complete shell startup files, select
`shell: keep` and preserve Omarchy's environment and mise activation. Symlinks
created by another dotfile manager need deliberate reconciliation first.
The example's Git task adds an include for its preferences snippet, preserving
Omarchy's existing Git configuration and owner identity.

## Trusted custom tasks

Tasks run in manifest order after software, features, native Docker consent and
dotfiles. Use `ansible.builtin` modules and idempotent tasks. The default user is
the guest owner; a task can request `become: true` during the native setup grant.
Use Omarchy/mise for installations and preserve their update paths. Do not build
replacement VM, SSH, networking or display controllers.

| Variable | Meaning |
| --- | --- |
| `workstation_user` | Manager-authenticated non-root guest owner |
| `workstation_group` | Owner's primary numeric group ID |
| `workstation_home` | Guest home directory |
| `workstation_architecture` | Validated `aarch64` guest architecture |
| `workstation_setup_dir` | Controller-side frozen selected inputs |
| `workstation_vars` | Plain values from manifest `vars` |

`workstation_setup_dir` is for controller-side copy/template sources, not a
shared guest directory. The snapshot contains only manifest, catalogues, layout,
dotfile sources, task entry points and explicit `assets`. Declare templates,
included task files, scripts or local roles under `assets` and resolve them from
the snapshot. No blanket repository copy is made. Symlinks, `.git` trees and
special files are refused; inputs are limited to 4096 files and 32 MiB.

For example, `tasks/projects.yml` can contain:

```yaml
---
- name: Create projects directory
  ansible.builtin.file:
    path: "{{ workstation_home }}/{{ workstation_vars.projects_directory }}"
    state: directory
    mode: "0755"
```

**External Ansible is trusted executable code, including controller-side code.**
Tasks, lookups, delegation and plugins can access the Mac and its environment.
This is not a sandbox or a guarantee of guest-only execution. Review the repo
before setting `OMARCHY_SETUP_TRUST_TASKS=yes`. Proposal confirmation or
`OMARCHY_VM_YES=yes` does not substitute for explicit task trust. The runner
supplies its own inventory and manager-pinned SSH parameters; trusted code must
respect that contract. Never import host keys, tokens or sign-in state.
Authenticate through each application's native guest flow.

Each task has an independent `setup.NAME` tag. Select names with
`OMARCHY_SETUP_TASKS=projects,editor`, or set `OMARCHY_SETUP_TASKS=` to omit all
custom tasks. Software/features and dotfiles are still applied. Tasks should not
depend on unselected tasks having run. Task names are unique lowercase names;
`all` is reserved for the default selection.

## Preview, check and repeatability

Planning parses only data manifests/catalogues. It never evaluates external
task YAML, templates, lookups or plugins. Tasks are shown as opaque operations
with paths/hashes; a plan cannot predict arbitrary task effects.

```bash
make apply-omarchy-setup VM_NAME="Dev Omarchy" \
  OMARCHY_SETUP_REPO="$HOME/my-workstation" OMARCHY_SETUP_CHECK=yes
```

This checks built-in features/dotfiles and omits external tasks. To also run
trusted tasks in Ansible check mode, explicitly set both
`OMARCHY_SETUP_CHECK_TASKS=yes` and `OMARCHY_SETUP_TRUST_TASKS=yes`. External
Ansible can override check mode or execute controller code; check is not a
read-only guarantee for custom tasks. Built-in checks enable no sudo grant,
install no software and leave guest configuration/ownership state unchanged.
Temporary owner-owned helper payloads are staged and removed.
Tasks using `become: true` must account for a check running without a setup
grant, for example by reporting privileged work as deferred in check mode.
The launcher does not authorize elevation merely to run a check.

Selected inputs are frozen before the proposal. Originals and the built-in
catalogue are rechecked after confirmation, before mutation; changed inputs
require a new proposal. Execution uses the frozen copy. Trusted tasks can
deliberately reach outside it, so reproducibility also depends on their code.
Host environment and credentials are not snapshotted.

Guest input inventories at `~/.local/state/dev-vm/setups/ID.json` record input
hashes, runner source hashes/API version, selected features/tasks and requested
VM settings after the dotfile/task
stage. They do not prove installed versions or hardware acceptance. Failures
can leave completed operations; there is no general rollback. Reapply after
fixing the failure. Unselected software is preserved. Bootstrap validates
accelerated rendering after restart; apply leaves restart/login to VM Manager.

Native sudo is revoked on success, failure and catchable interruption. A killed
controller or unavailable SSH can prevent cleanup. In the guest, run:

```bash
omarchy sudo passwordless --disable && sudo -K
```

## Downstream migration and validation

The example mirrors the Higeia developer-VM brief's shape without copying its
identity, proprietary content or credentials: project-managed tools, Ruby
prerequisites, Claude CLI/Desktop, Chromium, the multi-window layout, 1Password
and keyring packages. Move choices into downstream `vm.yml`, then add personal
dotfiles and reviewed tasks incrementally. Keep sharing and owner/SSH defaults
in VM Manager, and runtime versions in project `mise.toml` files. Omit the theme
option to preserve the native theme.

Local tests cover resolution, frozen inputs, ownership/conflicts, privilege
cleanup and real Ansible copy/template/reapplication. The
[live acceptance record](omarchy-setup-validation.md) identifies the tested
factory identities, corrections and validation limits. Setup does not
resolve an application's separate GPU issue. Adding this feature does not
migrate any existing downstream repository or VM.
