# Repository validation

Run these checks from the repository root after changing an Omarchy workflow.
Use existing host tools; install any missing tools separately. Run
`make syntax-check` after YAML changes.

Validate repository changes on the Mac with:

```bash
bash -n omarchy/guest/apply-workstation.sh \
  omarchy/guest/apply-theme.sh \
  omarchy/guest/check-workstation.sh \
  omarchy/guest/repair-try-omarchy-black-screen.sh
PYTHONPYCACHEPREFIX=/tmp/dev-omarchy-pycache \
  python3 -m py_compile scripts/omarchy_vm_manager.py scripts/omarchy_playbook.py \
  scripts/omarchy_image.py omarchy/guest/apply-lean-developer.py omarchy/guest/apply-features.py \
  omarchy/image/compatibility.py omarchy/image/check-provisioning.py
bash -n omarchy/image/build-container.sh omarchy/image/preferences/first-login.sh \
  omarchy/image/preferences/preferences.install omarchy/image/preferences/PKGBUILD \
  omarchy/image/check-user.sh
make syntax-check
make test-omarchy
```

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
