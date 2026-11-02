# Documentation

[Project home](../README.md)

## Setup runbooks

Run the copy-and-paste commands in a Mac terminal at the repository root.
Every runbook supports the official Try Omarchy image or a BYO compatible
custom factory path. Bootstrap handles native import and installs selected apps
and layouts. Optionally [build your lean, mean coding image once](omarchy-layout-factory.md).

- [Standard workstation](omarchy-vm-manager-runbook.md)
- [Trimmed workstation](omarchy-official-trimmed-runbook.md)
- [Four tiled Foot terminals](omarchy-layout-four-terminals.md)
- [Terminal and browser](omarchy-layout-terminal-browser.md)
- [VS Code and browser](omarchy-layout-vscode-browser.md)
- [Claude, terminals and browser](omarchy-layout-claude-two-terminals-browser.md)

## Reference

- [Prerequisites, bootstrap and resource settings](omarchy-bootstrap.md)
- [Developer feature selection](omarchy-features.md) and [playbook contract](omarchy-playbooks.md)
- [External setup repositories, dotfiles and trusted custom tasks](omarchy-setup-repositories.md)
- [Themes](omarchy-themes.md) and [application layouts](omarchy-layouts.md)
- [Removal profile and restoration](omarchy-lean-developer.md)
- [Scope and factory choices](omarchy-overview.md)
- [Custom factory overview](omarchy-layout-factory.md), [build reference](omarchy-layout-factory-reference.md) and [artifact contract](omarchy-image.md)
- [Workstation checks and recovery](omarchy-validation.md)
- [Repository checks](development.md)

## Validation records

- [External setup repositories, official and lean acceptance](omarchy-setup-validation.md)
- [Developer, web and Python profile live acceptance](omarchy-profile-validation.md)
- [Official-image trimming](omarchy-official-trimmed-validation.md)
- [Official factory / manager 0.9.2 acceptance](omarchy-official-43-validation.md)
- [Feature playbook acceptance](omarchy-playbook-validation.md)
- [Lean 42.1 acceptance and historical timer failure](omarchy-lean-42-validation.md)
- [Lean 43.1 acceptance and remaining checks](omarchy-lean-43-validation.md)
- [Manager report-timer handoff](omarchy-manager-report-timer-handoff.md)

These records describe the exact builds tested, rather than later rebuilds or updates.

[Shared Swift provisioning](../README.md#swift-provisioning-foundation) provides offline manifest validation, profile resolution and source-snapshotted planning; the Python operational commands remain unchanged.

[Transport/authorization contracts](../README.md#transport-and-authorization-sequencing-fake-adapters-only) add a shared sequencer tested solely with in-memory guest adapters; the concrete command adapter continuation below adds process specifications without enabling operational Swift commands.

[Concrete SSH/Ansible adapters](../README.md#concrete-sshansible-adapters-fake-process-runners-only) cover pinned transport commands, private payload/Ansible files, guest scope control and terminal-stream contracts, tested only with fake process runners. The local runner/PTY continuation below adds an opt-in backend; operational integration stays disabled.

[Local process runner and PTY](../README.md#local-process-runner-and-pty--3-november-2026) records exact local process ownership, bounded terminal streams/input leases and disposable-fixture validation. No real SSH/Ansible or VM acceptance is claimed.

[Manager package integration](../README.md#manager-package-integration--3-november-2026) records consumption of the immutable source/resources, offline helper/launcher packaging, local relocation evidence and remaining operational boundaries.

[Manager coordinator/journal foundation](../README.md#manager-coordinatorjournal-foundation--3-november-2026) records the earlier fake-runtime orchestration, private risk markers and lifecycle leases; the continuation below adds durable cleanup checkpoints while production ownership remains pending.


[Durable frozen inputs and cleanup checkpoints](../README.md#durable-frozen-inputs-and-cleanup-checkpoints--3-november-2026)
records bounded inert archives, conservative original-scope recovery, preallocated
payload identity, exact manager base-plus-patch provenance and fake ownership
reconciliation. Recovery cannot resume apply or rebind a VM; production helper
ownership and all real guest acceptance remain pending.
