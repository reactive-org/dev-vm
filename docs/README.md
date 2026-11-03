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


[Manager authenticated helper ownership](../README.md#manager-authenticated-helper-ownership--3-november-2026)
records inherited HMAC control, exact original-worker fencing, conservative missing
helper state and local packaged-helper fixtures. This is a manager-only handoff;
shared engine/pins are unchanged and operational job/terminal integration remains
pending.


[Manager admitted helper launch and registration](../README.md#manager-admitted-helper-launch-and-registration--3-november-2026)
records signed-package/owned-child admission, journal-before-spawn original-owner
pins and authenticated inert worker reservation. Shared source/pins are unchanged;
operational job dispatch, full manager restart and live terminal integration remain
pending.


[Manager helper-side engine dispatch](../README.md#manager-helper-side-engine-dispatch--3-november-2026)
records one-shot activation, shared-sequencer helper tasks, authenticated status/
cancellation, durable no-replay markers and fake/signed-process fixture coverage.
Shared sources/pins are unchanged; production contexts/backends, full restart and
live terminal integration remain pending.

[Manager frozen-input delivery and context validation](../README.md#manager-frozen-input-delivery-and-context-validation--3-november-2026)
records private authenticated delivery binding, independent helper replan/review
checks, frozen-copy ownership and local signed-helper fixtures. The shared plan's
reviewed manifest path is now public read-only and its inventory/pin is updated;
product backends, session authority, restart and terminal integration remain pending.

[Manager helper backend and session authority](../README.md#manager-helper-backend-and-session-authority--3-november-2026)
records concrete shared-adapter/fenced-runner construction, independent authenticated
manager checks and fake/signed-helper coverage. Shared explicit connection/tool
verification and fixed-purpose metadata APIs update the engine pin; product resource
handoff, operational runner/terminal wiring and restart acceptance remain pending.

[Manager transport-resource admission and private handoff](../README.md#manager-transport-resource-admission-and-private-handoff--3-november-2026)
records managed-SSH/Homebrew admission, original private reference proofs, inherited
resource delivery and local signed-helper validation. The shared private-reference
API and link-count proofs update the engine/export pin; product acquisition/wiring,
operational runner/terminal integration and restart acceptance remain pending.

[Manager milestone 3 completion](../README.md#manager-milestone-3-completion--3-november-2026)
records manager service composition, strict workflow journaling, SSH wait/review,
matching-exit restart and explicit new-session check review, authenticated cleanup,
bounded retention and separate-process lost-owner refusal. Milestone 3 is complete
for fake/local acceptance; public execution stays disabled. Terminal/input,
UI/CLI, real guest and distribution acceptance remain milestones 4–7. This consumer
completion does not change the shared source/export pin from the handoff slice.

[Manager milestone 4 terminal transport](../README.md#manager-milestone-4-terminal-transport--3-november-2026)
records the separate authenticated stream, explicit input owner, detach/expiry,
resize, bounded output and visible gap/reset contract, local TTY restoration and
fake/local acceptance. Shared input scope reservation/suspension and canonical
workspace paths update the engine/export inventory. Native rendering and public
app/CLI attach are milestone 5; product execution remains disabled.

[Manager milestone 5 terminal/observation slice](../README.md#manager-milestone-5-terminalobservation-slice--3-november-2026)
records the consumer's renderer/CLI fixtures and remaining gated workflow actions.

[Manager frozen review and task-trust slice](../README.md#manager-milestone-5-frozen-review-and-task-trust-slice--3-november-2026)
records the shared planner/request consumer contract and fake-only validation.
