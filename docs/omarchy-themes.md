# Choose and repair a theme

Choose an Omarchy theme with its HTTPS GitHub repository URL (with or without
`.git`), for example one from the [community catalog](https://omarchy.org/themes/):

```bash
make bootstrap-omarchy-vm \
  OMARCHY_VM_THEME=https://github.com/bjarneo/omarchy-ash-theme
```

Omit `OMARCHY_VM_THEME` to preserve the current theme. To choose automatically:

```bash
make bootstrap-omarchy-vm OMARCHY_VM_THEME=random
make bootstrap-omarchy-vm OMARCHY_VM_THEME=most-starred
```

To draw a random theme with at least 10 GitHub stars:

```bash
make bootstrap-omarchy-vm \
  OMARCHY_VM_THEME=random OMARCHY_VM_THEME_MIN_STARS=10
```

`OMARCHY_VM_THEME_MIN_STARS` defaults to `10`; set it to `0` to disable filtering.
The minimum applies only to `random` and is ignored for other theme choices.
A positive minimum requires the same GitHub authentication as `most-starred`
and chooses uniformly among repositories meeting the inclusive minimum. Setup
stops if no themes qualify. The selection reports its star count and the number
of eligible themes. The controller flag is `--theme-min-stars`.

`random` chooses uniformly from the GitHub repositories in the official
[website catalog source](https://github.com/omacom/omarchy-site/blob/master/themes/index.html).
`most-starred` chooses the catalog repository with the highest current GitHub
star count; ties use alphabetical repository URL order. Entries explicitly
reported by GitHub as `NOT_FOUND` are skipped and printed, covering removed
or private repositories. Star ranking prefers an
existing `gh` CLI on the host and uses `gh api` with its GitHub.com login. If you
have already run `gh auth login --hostname github.com`, no token export is
needed. `gh` honors `GH_TOKEN` ahead of `GITHUB_TOKEN`, and either overrides its
stored login. If `gh` is unavailable, the controller uses `GH_TOKEN` or
`GITHUB_TOKEN` directly, with access to public repository metadata. It never
installs `gh` or starts an interactive login during setup.

Both paths query GitHub's GraphQL API in batches; credentials stay on the host
and are never printed, staged, or passed to the guest. Lookup or API failures
stop setup before any VM changes instead of silently choosing another theme.

The selected URL appears in the proposal before confirmation. Each automatic
selection runs once per bootstrap invocation; reuse the printed URL to keep
the same choice on future runs. Omarchy's native `theme install`/`theme set`
commands apply the selection without requiring a live graphical session. An
installed theme from the same repository is reused without pulling or deleting
local changes; an already active selection with generated Foot settings is left
alone. Setup runs in an Omarchy login shell so its native templates are available,
and regenerates missing active theme settings even when no new theme is selected.
A name collision with a local theme or another repository stops with an error.
Omarchy continues to
own theme updates. The normal managed reboot activates the selection.

For guest-side application, `make apply-omarchy-vm-guest OMARCHY_VM_THEME=URL`
also accepts a repository URL; automatic selection is a host bootstrap option.
The controller's equivalent argument is `--theme URL|random|most-starred`.

If Foot reports that its active theme include is missing, regenerate the current
theme from a guest login terminal and validate the result:

```bash
OMARCHY_THEME_HEADLESS=1 omarchy theme set "$(cat "$HOME/.local/state/omarchy/current/theme.name")"
foot --check-config
```
