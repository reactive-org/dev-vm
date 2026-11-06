# Repository validation

Run these checks from the repository root after changing an Omarchy workflow.
Use existing host tools; install any missing tools separately. Run
`make syntax-check` after YAML changes.

The project `mise.toml` pins Python, Lua, Ansible Core, uv, ShellCheck and
yamllint. To opt into installing these host tools, run `mise trust` and
`mise install`. Then use `mise run test`, `mise run syntax-check`, or
`mise run check` for both. Lua enables the layout regression tests that otherwise
skip when no interpreter is installed. VM Manager and Docker remain separate
prerequisites; no mise task installs host software or operates a VM.

Validate repository changes on the Mac with:

```bash
bash -n omarchy/guest/apply-workstation.sh \
  omarchy/guest/apply-theme.sh \
  omarchy/guest/check-workstation.sh \
  omarchy/guest/repair-try-omarchy-black-screen.sh
PYTHONPYCACHEPREFIX=/tmp/dev-omarchy-pycache \
  python3 -m py_compile scripts/omarchy_vm_manager.py scripts/omarchy_playbook.py \
  scripts/omarchy_image.py omarchy/guest/apply-lean-developer.py omarchy/guest/apply-features.py \
  scripts/omarchy_profiles.py scripts/omarchy_data.py omarchy/guest/feature_contract.py \
  scripts/omarchy_setup.py omarchy/guest/apply-dotfiles.py \
  omarchy/image/compatibility.py omarchy/image/check-provisioning.py
bash -n omarchy/image/build-container.sh omarchy/image/preferences/first-login.sh \
  omarchy/image/preferences/preferences.install omarchy/image/preferences/PKGBUILD \
  omarchy/image/check-user.sh
make syntax-check
make test-omarchy
```

Feature definitions live in `omarchy/features/catalogue.json`. After changing
them, regenerate editor schemas with
`python3 scripts/omarchy_profiles.py --write-schemas`; tests detect schema drift.
Use `make plan-omarchy-features OMARCHY_PROFILES=web` or
`OMARCHY_SETUP_FILE="$PWD/omarchy/examples/team/setup.yml"` to exercise profile
and extension resolution locally without contacting a VM. The resolver uses
plain YAML/JSON; YAML can reuse the already installed Ansible Python runtime.

Preview an external setup with
`make plan-omarchy-setup OMARCHY_SETUP_REPO=omarchy/examples/setup-repo`.
The local setup tests exercise dotfile conflicts, frozen source changes, task
trust/check boundaries and real Ansible templates plus zero-change reapplication.
They do not create a VM or validate hardware. `make syntax-check` validates both
the feature and external-setup playbooks.

When using Codex, run `make test-omarchy` outside the Codex sandbox so the
Ansible tests can create their local Unix socket for controller RPC. The
sandbox blocks socket creation with `Operation not permitted`, which Ansible
reports as `Local RPC server did not start`. Run from a normal Mac terminal
or use Codex’s approved execution outside the sandbox. These tests use local
fixtures and do not connect to a VM.

## Continuous integration

[GitHub Actions](https://github.com/reactive-org/dev-vm/actions/workflows/ci.yml)
runs the shell, Python and Ansible syntax checks and `make test-omarchy` for
pull requests and pushes to `main`. It can also be started manually from the
Actions tab. The workflow uses an Apple Silicon macOS runner with Python 3.14
and pinned `ansible-core` 2.21.5, including the local Ansible fixture tests.
Action versions are pinned to reviewed commit hashes in
`.github/workflows/ci.yml`; update those pins and the Ansible version there
when upgrading CI dependencies.

CI validates repository code and local fixtures. Factory builds and real-VM
acceptance remain separate checks requiring the documented build environment
and an explicitly selected disposable guest.

## Factory branch test-only publication

`codex/swift-factory-builder` uses the dedicated Factory Swift and offline recipe
checks job for push/PR selection (feature-branch pushes create no run until a PR
is opened under the existing trigger policy). It uses preinstalled Swift 6.2+ and
Python 3.11+, verifies the pinned Linux staging export and runs shared Swift tests
with fake Docker adapters and disposable local processes. It installs no software
and performs no factory download/build, signing or VM operation. Repository and
pinned source-dependency checkout remain normal hosted CI inputs.

The ordinary Ansible installation/legacy validation job is skipped for this
branch. That broader validation remains separately scoped. The initial publication kept the manager's source pin at `df5e2c8`. The later
shared resource-lookup fix advances only the active public package source pin;
private candidate pins and archived resource bytes stay frozen.

The first hosted factory run refused regenerated resource bytes under its newer
Python toolchain. The read-only oracle check now compares the canonical
uncompressed tar against the maintained staging output, then verifies that the
committed compressed bytes still match recipe.json and the compiled Swift pin.
It never recompresses or rewrites a check input. Three local tests verify no-write
behavior, refusal of changed archive contents, and refusal of an equivalent gzip
re-encoding without matching recipe/pin changes. Existing resources and all source
pins remain unchanged; the fresh hosted result is reported separately.

The next hosted pass reached the Swift suite, then failed factory resource lookup
because resourceURL already included a Resources component. Named bundle lookup
now handles both supported SwiftPM layouts and still rejects missing or damaged
pinned resources. The local shared suite passes 93 tests. The updated hosted
result is recorded separately; real factory/guest acceptance stays TO PROVE.

## Docker executable admission — 6 November 2026

The first local read-only factory readiness pass rejected the installed
43,052,752-byte Docker CLI because the shared executable pin capped tools at
32 MiB. Factory Docker admission and its local host process runner now use a
separate 128 MiB policy. Guest SSH/Ansible keep the 32 MiB policy. Hashing reads
1 MiB chunks, with unchanged symlink, file stamp, owner, executable-permission
and replacement checks. This changes neither engine admission nor execution
authorization: readiness still rejects remote/non-ARM64 Linux engines and never
builds, downloads, starts Docker or creates containers/volumes.

Fake Docker runners and disposable files cover both size boundaries, the observed
CLI size, complete hashes, content changes, unsafe permissions and symlink
retargeting. A padded disposable shell script exercises the host runner's larger
policy without invoking Docker. The manager records the exact source change as a
checksum-pinned integration patch over the same immutable package base; existing
private artifacts and frozen candidate pins remain unchanged. Fresh local test
and read-only host results are recorded separately from real factory/guest
acceptance, which remains TO PROVE.

**VERIFIED — repair validation:** the complete shared Swift suite passes 97 test
functions, including the four new size/integrity functions and their parameter
cases. The manager passes 542 Dev Swift and 340 script tests. An initial sandbox
run timed out two existing PTY fixtures; the unchanged suite passes outside the
sandbox with unchanged deadlines. Fresh read-only host inspection admits the
installed Docker CLI, requires a local Unix socket and ARM64 Linux engine, and
revalidates the engine identity. No real build/download/container mutation,
credential access, installation or VM operation occurs. Engine-internal scratch
free space and real factory/import/guest acceptance remain unmeasured/unperformed.
