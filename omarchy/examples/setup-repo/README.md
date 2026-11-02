# Example external setup repository

Copy this whole directory into a repository you own. It is a standalone input
to dev-vm; no source changes or fork are required. Review the choices first:
this example includes developer tools, Claude Desktop/CLI, Chromium, 1Password
applications and desktop keyring packages. It never signs in or copies credentials.

From your dev-vm checkout:

```bash
make plan-omarchy-setup OMARCHY_SETUP_REPO="$HOME/my-workstation"
make bootstrap-omarchy-vm VM_NAME="Dev Omarchy" \
  OMARCHY_SETUP_REPO="$HOME/my-workstation" OMARCHY_SETUP_TRUST_TASKS=yes
```

To preview the committed example directly, use
`OMARCHY_SETUP_REPO=omarchy/examples/setup-repo`. Planning contacts no VM and
executes no tasks. `make apply-omarchy-setup` reapplies to a running guest.

- `vm.yml`: resources, app selections, project-managed profile and file mappings.
- `layouts/coding.lua`: Claude right, two terminals left and a floating browser.
- `dotfiles/`: Git preferences without identity and an optional Neovim module.
- `tasks/projects.yml`: idempotent guest directory creation.
- `tasks/git.yml`: includes the Git preferences snippet without replacing native configuration.
- `tasks/editor.yml` and `templates/`: rendering a separate sample editor snippet.

The Git task preserves Omarchy's existing Git configuration and identity.
The profile includes the built-in `keyring` feature; this example also explicitly
selects the optional Seahorse manager with `setup.options.keyring.seahorse: true`.
The editor snippet leaves installed editor settings alone. Load the Neovim
module from your own configuration when desired. No global language runtimes
are selected. Customize these examples for your applications.

Custom tasks are trusted Ansible code with access to the controller Mac.
`OMARCHY_SETUP_TRUST_TASKS=yes` explicitly enables them; use
`OMARCHY_SETUP_TASKS=` to skip them. The engine checkout's
`docs/omarchy-setup-repositories.md` documents the manifest, conflicts, check mode,
task context and migration guidance. This example stays usable after moving to
another repository.
