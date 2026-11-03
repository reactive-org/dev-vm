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
`DevVMProvisioningCore` and the migration-stage `dev-vm` executable. The package now provides
strict manifests, feature/profile resolution, immutable source snapshots and
offline proposals. A concrete SSH/Ansible command adapter is available behind an
injected process runner. An opt-in local runner and PTY backend now have
disposable-fixture coverage; no operational Swift setup or VM backend is enabled.
The transport continuations below describe the implemented boundaries. The legacy Python commands
above remain the operational entry points until an explicit cutover.

```sh
make build-provisioning test-provisioning
swift run --skip-build dev-vm validate-manifest omarchy/examples/setup-repo/vm.yml
swift run --skip-build dev-vm plan omarchy/examples/setup-repo
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
targets, quoted modes and unique task names. `validate-manifest` checks namespaced references lexically; `plan` resolves
the explicitly declared catalogues. `SetupManifest` remains a structure-only
value, and a `SetupPlan` remains an offline proposal without execution approval.

Compatibility changes are deliberate and limited: signed 64-bit integers;
decimal finite floating point (including exponent notation); YAML 1.1 boolean
spellings retained; unquoted timestamps and legacy octal/hex/binary,
underscored or sexagesimal numbers rejected. Quote such values when they are
intended as strings. Unlike PyYAML, numeric exponent notation in YAML mappings
is consistently numeric. DEL characters in bounded names/paths, any `.git`
path segment and canonically equivalent duplicate Unicode keys are also refused.
Bare and `pkg:` selectors for the same package are treated as duplicate
declarations. These are not claims of complete Python-controller parity.

**VERIFIED — original foundation `e86550e`, 2 November 2026:** build and 12 Swift test
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

**TO PROVE at the foundation commit:** complete controller/selection/TOML parity,
planning and snapshots, full resources, immutable manager dependency pin, app/helper integration,
read-only app relocation, transport/authorization, the live terminal and all
real-guest behavior. The manager's execution gates remain disabled.

## Offline planning continuation

`FeaturePlanner.resolve` implements builtin/extension feature prerequisites,
profile inheritance, sibling conflicts, explicit overrides, empty-map/list
clearing, null tool tombstones, provider conflicts and exact effective options.
Catalogue declaration order is preserved by both JSON and YAML readers. All
feature and profile graphs are checked, including unselected definitions.
Limits are 32 catalogues, 512 features/profiles and 30 graph levels.

Selected Starship TOML uses Swift-native TOMLDecoder 0.4.5 at
`a2bbd2796fe3064e107de18cb56031052c4fa899`, pinned in `Package.swift` and
`Package.resolved`, with its MIT notice bundled. The parser supports TOML 1.1;
a compatibility preflight rejects its new escapes, optional time seconds,
multiline inline tables and inline-table trailing commas to retain the Python
oracle's TOML 1.0 contract. Text is bounded to 64 KiB and bracket/key depth to
30. Invalid unselected profile prompt text may be repaired by an override;
selected, enabled zsh/Starship configuration must validate. No external TOML
parser, Python or Ansible is invoked by the library or CLI.

`SetupPlanner.plan` captures explicit manifest/catalogue/layout/dotfile/task/asset
inputs below a selected repository descriptor. Traversal uses `openat` with
no-follow flags, refuses symlinks, `.git`, nonregular files and unsafe paths,
and detects changes during reading. The immutable in-memory `SourceSnapshot`
retains bytes and permissions, expands dotfile trees, includes empty-directory
membership and never captures unrelated files. Limits are 4,096 files, 32 MiB
total, 4,096 directories, 8,192 entries per directory and 64 path levels.
`plan.verify(in:)` rewalks the declarations to detect additions, removals,
content/mode changes, root replacement and engine/resource changes. Frozen bytes
remain available when their originals change. This is a reviewed byte snapshot;
it does not claim a filesystem transaction against an adversarial concurrent
writer. Private job-directory materialization belongs to the execution port.

The versioned JSON proposal includes effective configuration, package/mise
requirements and provenance, predicted effects, expanded dotfiles, opaque task
metadata, selected input hashes, an engine inventory and deterministic input/plan
digests. It records required application tools, task trust, expected Docker
restart policy, update ownership and pending guest conflict/factory checks.
Variable values and opaque file/task contents are excluded from serialized plans.
`execution_available` stays false. Factory references remain declarations for
manager admission; local paths are neither opened nor converted into admitted
factory images. Guest state, installed versions, actual additions/removals and
existing dotfile conflicts cannot be determined offline.

`make` regenerates the checked-in engine inventory from Swift/C sources, package
pins and bundled resources before building/testing. This uses the existing
Python development tool only; the compiled library/CLI does not use Python.
Direct SwiftPM builders must run `make provisioning-inventory` after source
changes. Tests reject stale inventories. This inventory binds build inputs; final
signed app/helper provenance and immutable manager packaging remain pending.

```sh
make build-provisioning test-provisioning test-provisioning-oracle
make test-provisioning-planning-oracle ORACLE_PYTHON=/path/to/existing/python
```

The full planning oracle needs an existing Python 3.11+ with PyYAML. It compares
all legacy proposal fields except the intentionally different engine identity,
normalizing only the bundled catalogue's path to `builtin/catalogue.json`.
It forbids Python subprocesses, manager calls and interpreter fallback. Swift
children run with `PATH=/nonexistent`. No host dependency is installed or probed.
The Python operational controllers remain unchanged.

**VERIFIED — continuation, 2 November 2026:** build, 20 Swift test functions,
18 plain-data fixtures and 66 complete proposal/error cases (41 accepted, 25
rejected) pass. Snapshot tests cover limits, edits/additions/removals/modes,
empty directories, symlink/special-file rejection, root replacement, opaque
inputs, engine hashes and equal plan digests across equivalent roots. Existing
`make test-omarchy` passes 235 tests with the existing Lua fixture skipped, and
both playbooks pass syntax checks. The complete oracle used the existing
Ansible-managed Python 3.14 as a development test interpreter only. All 20
Swift tests also pass with `PATH=/nonexistent` using the absolute toolchain
runner. An isolated CLI/bundle copy plans successfully; altering its bundled
catalogue produces only `manifest.resource` and exit 1. This is not full app
relocation acceptance. No tools were installed, guest contacted, VM launched
or app opened.

**TO PROVE:** complete TOML/parser parity outside this fixture matrix, frozen
job materialization, full resource distribution, manager dependency/helper/UI
integration, signed provenance and relocation, operational standalone cutover,
transport/authorization, live terminal and all real-guest behavior. Existing
manager execution gates remain disabled. Concrete transports and production execution remain deferred.

## Transport and authorization sequencing (fake adapters only)

**Historical boundary at `f807104`:** `ProvisioningGuestAdapter` was a typed
async port implemented only by the in-memory `FakeGuest` in tests. Concrete
command construction and payload materialization are added in the continuation
below. The later local-runner section adds pipe/PTY execution; guest discovery,
operational integration and lifecycle control remain deferred.
`ProvisioningSequencer` is a single-use actor for reviewed apply/check attempts
and cleanup-only recovery. The CLI still exposes offline validation/planning
only, and proposals still report `execution_available: false`.

A request binds a frozen plan and current source/engine identity, job ID, exact
VM/runtime-session ID, non-root owner name/UID, pinned host-key digest,
dependency digest, mode, task subset/check policy, dotfile conflict policy and
interactive input lease into a review digest. Approval separately acknowledges
custom task code, the persistent setup grant and Docker's root-equivalent opt-in.
Absent/stale approval, untrusted selected tasks or missing required input stop
before any adapter call. Check mode skips tasks unless explicitly requested and
trusted; it never resets/enables/revokes grants, clears sudo authentication,
installs manifest packages, changes Docker access or requests restart. Check mode
is not a sandbox for trusted custom tasks.

Every operation is preceded by an identity check; every reply must match command,
job, VM/session/owner/UID/host-key/dependency pins, protocol version and expected
structured proof. Future adapters must perform actual authentication and enforce
these pins at operation time. The current fake replies establish sequencing only,
not cryptographic identity or a working guest command. A mismatch stops all
further actions on that channel. No endpoint discovery or silent rebinding occurs.

Apply sequencing is: stage frozen inputs; reset any stale native grant and clear
cached authentication; request the native persistent grant interactively; verify
active policy without cached authentication; apply selected packages/features;
request any explicit native Docker consent; apply repository work; quiesce owned
work; revoke, clear cached authentication and verify inactive policy; check Docker
owner access again after revocation; quiesce that check and remove the job-owned
payload. Interactive commands receive an input lease ID, never passwords or
keystrokes. Docker success returns `appliedRestartRequired`; no restart is run.

**PRIVATE COUPLING:** `NativeAuthorizationContract` version 1 describes fixed
`bash -lc` guest argv from `scripts/omarchy_vm_manager.py` and
`scripts/omarchy_playbook.py` at `56dba82`. It includes native grant enable/reset,
cache clearing, compound revocation verification, native Docker confirmation
with `OMARCHY_DEFER_REBOOT=1` and local-socket Docker checks. It interpolates no
user values and accepts no nonterminal secret input. This code constructs argv
only; tests never execute these scripts. Native CLI meanings are private guest
couplings, not public Try Omarchy kit capabilities.

Cleanup coverage is armed before staging or grant/reset attempts, since failure
or a lost acknowledgement can leave side effects. Cancellation interrupts only
the exact active command and retains it until its async call ends; cleanup uses
an independent cancellation scope with no prompts, fresh grant or source-file
dependency. A local command ending does not prove remote work stopped: a separate
job-scoped quiescence proof is mandatory. Payload removal is withheld while work
is uncertain. An inactive-policy observation while work still runs does not
clear grant risk. A later compound inactive/cache-cleared proof can reconcile a
lost revoke/cache-clear reply once work is stopped.

Results preserve primary failure separately from cleanup failures. Unresolved
work/grant/payload state returns `cleanupRequired` and an opaque in-memory ticket
bound to the original target, dependency pin and job-owned payload ID. A fresh
driver may recover only that context, without input, grant, apply/check work or
restart—even if the original source repository has changed or disappeared.
Recovery refuses changed guests/sessions or dependencies. It reports cleanup
confirmation, never successful setup. Cross-restart rebinding and private
persistent recovery journals remain manager work.

Schema-1 result/event records contain fixed codes and command/job/VM/session IDs,
with correlated started/completed/failed events. They exclude owner/key material,
paths, frozen data, terminal input/output and arbitrary adapter diagnostics.
Bindings, requests, commands and recovery tickets have redacted descriptions.
Attempt completion is never a VM `.exited` boundary; consumers must retain VM
clients/reservations under the manager's existing lifecycle rules.

Commands carry adapter deadlines: identity checks 10 seconds; grant/cache probes
and cleanup 30 seconds; interactive commands 120 seconds; setup operations 3,600
seconds. Actual deadline enforcement/local-process exit belongs to a concrete
transport. Fake timeout replies test state transitions; they do not prove hard
wall-clock bounds, uncooperative-adapter termination or descendant cleanup.

**VERIFIED — fake-adapter slice, 2 November 2026:** build and all 38 Swift test
functions pass (18 added for sequencing/native contracts), including partial
staging/grants, body failures, cancellation during authorization/cleanup,
concurrent/replayed driver rejection, stale review/source checks, 10 reply/pin
mismatch cases, nonprivileged check mode, post-revoke Docker checks, uncertainty
and same-target recovery without original inputs, and sanitized reports. All 38
also pass with `PATH=/nonexistent`. The 18 plain-data and 66 proposal/error oracle
fixtures remain passing. Seven targeted existing Python tests with mocked guest,
Ansible and lifecycle calls preserve the grant/revoke/check ordering reference.
The full Ansible-running legacy suite was not rerun for this fake-only slice;
its prior `56dba82` evidence remains historical. No host tool was installed or
probed, SSH/Ansible script run, credential read, app opened or VM operated.

**TO PROVE:** real SSH pins/receipt authenticity, native command/TTY/password echo
behavior and SSH quoting, adapter deadlines/cancellation/process ownership,
remote quiescence, private payload materialization, persistent recovery and
explicit restart rebinding, helper/CLI/UI integration, package/signature admission,
terminal streams and every real-guest scenario. Manager execution gates stay
disabled.

[All documentation](docs/README.md) · [Prerequisites and settings](docs/omarchy-bootstrap.md) · [Repository checks](docs/development.md)


## Concrete SSH/Ansible adapters (fake process runners only)

**IMPLEMENTED — milestone 2 continuation, 2 November 2026:**
`SSHAnsibleGuestAdapter` constructs exact SSH/SCP/Ansible invocations, materializes
frozen inputs and interprets bounded results. `ProvisioningProcessRunner` is an
injected port. At `9ebaf17`, only an in-memory fake was supplied; the local
runner continuation below adds a process/PTY backend. There is still no operational
Swift apply/check command. CLI proposals still declare
execution unavailable; manager integration and execution gates are unchanged.

The connection accepts an explicit loopback endpoint, manager VM/session/owner
binding, ed25519 host key and private-key reference. Key admission reads metadata
only. A manager-owned authority revalidates session/dependency admission before
each process; private SSH config/known_hosts enforce the host key and explicit
credential, with forwarding, agent access, proxy commands and connection sharing
disabled. Executables are pinned by resolved identity/hash, revalidated on every
invocation and invoked through their original launcher path to retain Ansible
symlink dispatch. No tool discovery or version probe occurs here.

Private UUID job storage contains immutable repository bytes, bundled playbooks,
roles, catalogue and guest helpers, fixed inventory, JSON variables and isolated
Ansible config/home/temp/plugin paths. Build-time resource copies and hashes are
checked against maintained sources. Nested manifest variables use the exact
snapshot manifest path. Ansible receives the admitted launcher, fixed transport
variables and explicit tags/check mode; user variables never enter shell argv.
Native manifest packages use Omarchy commands and mise, preserving upstream
installation paths. Check mode never installs those packages or changes grants.

Interactive native grant, Docker consent and package installers receive only an
input-lease ID and request an SSH TTY/terminal stream. Ansible requests live output
with closed stdin. A future runner must enforce deadlines, output bounds, PTY
ownership/echo rules and matching local descendant exit before returning. Raw
terminal bytes never enter structured events/results. Cancellation tracks the
command even between subprocesses, prevents the next launch and never interrupts
cleanup. Fake outcomes establish these contracts, not real terminal behavior.

**PRIVATE COUPLING:** `omarchy/guest/provisioning-job.py` is a guest-only Python
helper, not a host Python runtime. It binds one exclusive non-root UUID payload
and lease to recorded systemd user scopes. Preparation requires Linux/aarch64,
Python 3, cgroup v2, a user manager/bus and `systemd-run --scope
--expand-environment=no` support, checked before granting sudo. This flag requires
systemd 254+ ([systemd-run reference](https://www.freedesktop.org/software/systemd/man/latest/systemd-run.html)).
The Ansible shell wrapper scopes module commands. Quiescence seals new body work,
stops recorded scopes and requires inactive/empty cgroups before a structured
receipt. Pending/uncertain launch registration fails closed; payload removal
requires that proof and the exact owned lease. There is no process-name killing
or unverified removal fallback. Cleanup commands may run after sealing to revoke
authorization. This is not a sandbox for trusted custom tasks, which may escape
scopes or create independent services. Uncertain startup can require manual
recovery; persistent recovery and reboot/session rebinding remain deferred.

**VERIFIED — fake-process checks:** make build and all 50 Swift test functions
pass, including 12 new transport tests with parameterized faults, malformed or
mismatched receipts, launcher retargeting, source/workspace tampering, partial
staging, check mode and cancellation before/between/during process calls. All 50
also pass with `PATH=/nonexistent`. The 18 parser and 66 complete planning oracle
fixtures and seven existing mocked Python sequencing tests pass. Both new Python
files pass syntax compilation; 21 bundled YAML resources pass static parsing.
The full legacy suite and real Ansible syntax commands were not rerun because
this slice uses fake process runners only. No SSH/SCP/SFTP/Ansible executable,
credential contents, host installation, UI action or VM operation was used.

**TO PROVE:** actual SSH authentication/quoting, Ansible execution/parity, guest
helper/systemd/cgroup operation and privileged descendants, real deadlines and
cancellation, PTY/password echo and terminal delivery, persistent recovery,
standalone cutover, manager/helper integration and signed relocation. Earlier
fake-adapter evidence remains historical; concrete command generation and local
materialization now exist, without real-guest acceptance.


## Local process runner and PTY — 3 November 2026

**IMPLEMENTED — milestone 2 continuation:** `LocalProvisioningProcessRunner` is
an explicitly injected local backend. It executes an exact absolute program/argv,
working directory and supplied environment, with no shell expansion, tool lookup
or inherited credentials/environment. Pipe mode keeps stdout/stderr separate,
closes unused stdin, limits supplied stdin to 64 KiB and combines captured output
under 32 KiB. Overflow and I/O errors are failures even if the child exits zero.
Streaming mode publishes actual bytes and leaves structured stdout/stderr empty.
The standalone CLI remains offline only; no real SSH/Ansible transport is wired
up, and manager execution gates are unchanged.

`CDevVMProcess` is a small Darwin syscall bridge around `posix_spawn`, PTY,
wait and process-group queries. It creates a new session with inherited file
descriptors closed by default and explicit signal state. For PTYs, supply an
explicit `ProvisioningExecutablePin` for the compiled `dev-vm-process-host`
launcher. Darwin establishes the session after spawn file actions; the launcher
claims its controlling terminal then `execve`s the target, retaining the same
owned PID. It does no tool discovery, shell parsing or credential retrieval.
It needs to be admitted/packaged with the future manager helper, not installed
from Homebrew. No fork runs inside the Swift runtime. The separate C executable
under `tests/ProcessFixture` is test-only and is never an installed runtime asset.
The ordering is checked against [Apple's spawn implementation](https://github.com/apple-oss-distributions/xnu/blob/main/bsd/kern/kern_exec.c)
and exercised by the controlling-terminal fixture.

Ownership is registered before spawn. Cancellation targets only the matching
invocation; deadlines/cancellation send TERM then KILL after 150 ms. The waitable
leader reserves its PID/group until no live group members remain and output
reaches EOF; then the runner reaps that exact child. Normal parent exit with live
children is a failure requiring group cleanup. A 250 ms post-exit drain grace and
2-second cleanup window prevent an inherited pipe from silently hanging success.
Unconfirmed cleanup returns `cleanupUnconfirmed`, retains ownership/descriptors
and blocks the same VM/session across fresh runner instances in this process.
Exact-ID `reconcileLocalCleanup` can retry without launching commands. If a caller
drops an uncertain runner, a retained local reaper keeps that ownership; lost
wait ownership stays blocked rather than risking PID reuse. This registry is
in-memory, not cross-process or crash recovery.

**LOCAL TERMINAL CONTRACT:** `ProvisioningTerminal` provides pull-based raw byte
frames tagged by invocation/channel/sequence, with redacted descriptions. Storage
is bounded to a configured 8 KiB–1 MiB and at most 1,024 frames; snapshots are at
most 64 KiB and report gaps. No viewer callback can stall the drain loop. It does
not reconstruct an arbitrary terminal screen after a gap; the future renderer
must indicate/reset/resynchronize it. ANSI, carriage returns and split UTF-8 bytes
are preserved, not interpreted. There is no UI emulator or IPC attach endpoint.

Input is explicitly granted from a reviewed request (or exact job context), bound
to job/VM/session/dependencies/mode and one lease. Input/resize messages require
an active invocation, exact owner, monotonic sequence and bounds (4 KiB per input,
64 KiB queued, 1–500 rows and 1–1,000 columns). PTYs start raw/no-echo; each input
flush preserves those local settings. Writes and revocation are serialized, so
pending input cannot survive revocation. Detach/revoke does not cancel the job;
an unanswered prompt reaches its deadline. Leases cannot be reused, and a live
command does not permit silent ownership transfer. Input is never published or
persisted. Programs can deliberately print secrets; this is not automatic output
redaction. Remote SSH/sudo echo remains unverified.

**VERIFIED — disposable local fixtures only:** make build and all 64 Swift test
functions pass (14 new local runner functions), plus 18 parser and 66 complete
planning oracle fixtures. All 64 also pass with `PATH=/nonexistent` using the
absolute Swift toolchain and already-built fixtures. Tests copy compiled fixture
and launcher binaries into private UUID temp directories; they cover literal
argv/environment, stdin/EOF, separate capture, floods/gaps, split UTF-8/ANSI,
controlling terminal/foreground group, SIGWINCH sizing, synthetic no-echo input,
lease revocation/replay, descriptor inheritance, stale/early/concurrent
cancellation, TERM-resistant descendants, parent exit, missing/changed launchers
and uncertain-pipe reconciliation/admission. Tests assert no live fixture
children after cleanup (orphan zombies are reaped by launchd). PTY checks need
`/dev/tty` outside the workspace filesystem sandbox: restricted runs failed that
fixture access; the full local suite passes outside that restriction. A one-off
direct Swift invocation without the repository's module-cache environment also
failed its sandboxed cache write; make-based checks use the local cache normally.
No real SSH/SCP/SFTP/Ansible executable, host tool install, credential access, UI
or VM operation is used. Legacy tests that execute Ansible are not rerun.

**TO PROVE:** real SSH/Ansible and nested PTY/remote password behavior, guest
scope/quiescence/auth cleanup, hostile deliberate session/group escape, opaque
kernel stalls and foreign SIGCHLD reapers, cross-process/crash/persistent recovery,
helper launcher signature/admission/relocation, terminal renderer/escape policy,
IPC/viewer resynchronization and operational CLI/manager integration. Process
groups are not a sandbox: deliberately detached code can outlive its parent,
especially if it closes inherited pipes. Local exit proves only the owned group
and descriptors; it never proves guest quiescence or a VM `.exited` boundary.


## Manager package integration — 3 November 2026

Manager integration is committed as `6dbda68111005b657fc358609d058dee676789f4`
on `codex/dev-vm-provisioning-plan`. This worktree adds documentation only; the
manager deliberately keeps its engine/source pin at `bb3fae2`.

Omarchy VM Manager's `codex/dev-vm-provisioning-plan` worktree now consumes an
unmodified 79-file source export from `bb3fae22be45b38035fac52aefa0eb270a9d0fea`.
The manager's `Config/DevVMProvisioning.lock.json` records exact source/resource
hashes, and its make preparation verifies the export before generating a compiled
pin. Root `Package.resolved` exactly resolves the same TOMLDecoder revision. The
engine source, parsers, resources, standalone CLI and engine identity in this
worktree are unchanged; this note records the consumer handoff only.

Manager core and an offline-only `OmarchyVMProvisioningHelper` link the library.
The helper admits embedded resources and supports package verification, manifest
validation and offline plans. Apply/check/recover/exec are refused; it never
creates a runner, reads a registry/Keychain, probes tools or reaches a VM. Its
product UI/CLI setup gates remain disabled. Distribution includes this library's
resource bundle/licenses, helper, exact-source PTY launcher, source lock and a
manifest of final signed child hashes sealed by the outer app signature.

The launcher is built unchanged in a generated standalone SwiftPM package,
without needing this checkout or a new host Python runtime. A fresh developer
build may still need ordinary source/cache access for exactly pinned TOMLDecoder;
runtime planning needs neither a checkout/toolchain nor Homebrew/Ansible.

**VERIFIED — manager local fixtures:** build, 227 manager Swift tests/38 suites,
48 script tests and relocated/read-only offline-helper checks pass. A private
ad-hoc sealed fixture app contains no VM runtime; its actual helper plans with
empty PATH and private empty HOME/TMPDIR, rejects execution/overrides/tampering,
and omits synthetic variable values. Deep strict signature verification passes
before resource damage and rejects it afterward. Manager code is sealed but never
opened/executed by that fixture. Existing socket/mock-authentication fixtures
required running outside the workspace sandbox; no actual Keychain or auth UI was
used. An initial network update was unavailable, so validation reused existing
exact Git objects and private caches with update checks disabled. No real SSH/
SCP/SFTP/Ansible, host installs, UI action or VM operation occurred.

**TO PROVE:** complete runtime-kit app assembly, Developer ID/notarization,
other-Mac relocation, authenticated helper IPC, job/session/journal integration,
terminal rendering/attachment, operational CLI/app setup and all real guest/
authorization/echo/quiescence behavior. Existing 64 package-test and oracle
results above remain evidence for the pinned engine, not new remote acceptance.


## Manager coordinator/journal foundation — 3 November 2026

The manager foundation is committed as `f752331b4158f464b4fcef71d8a8c289df1d2e61`
on `codex/dev-vm-provisioning-plan`. This companion change is documentation only;
the manager keeps its shared engine/source pin at `bb3fae2`.

The manager's `codex/dev-vm-provisioning-plan` worktree now has an internal
`ProvisioningCoordinator` over this package's pinned `ProvisioningSequencer`,
plus a private versioned job journal and VMManager lifecycle leases. It retains
the unchanged `bb3fae2` source/resource pin. No engine API, parser, resource or
standalone command changes are required in this worktree; these docs record the
consumer's next step.

The coordinator deduplicates accepted job/review identities, reserves one active
job, revalidates package/source/session/dependencies, journals before adapter work
and separates viewer lifetime from explicit job cancellation. The private bounded
journal stores digests/manager-owned IDs and structured status, not credentials,
source contents/paths, terminal data or helper PIDs. Bad/changed journals fail
closed. Disk failure stops body work while known-target cleanup remains possible.

Manager leases defer ordinary shutdown for cleanup, block incompatible lifecycle
or storage edits and preserve `.exited` ownership. Force stop and unexpected
session/execution/readiness changes retain cleanup uncertainty. A cleanup deadline
records risk while retaining the worker; pending Quit then uses normal VM shutdown
policy. Restart-required remains metadata. No VM lifecycle is added to this library.

Explicit same-process recovery uses the original opaque engine ticket, without
sources or input. After restart, interrupted/cleanup-required records never resume
apply or reconstruct a ticket from a PID. The pinned ticket API is intentionally
in-memory: authenticated helper reattachment, persistent recovery, frozen-input
capsules and reviewed session rebinding remain future integration work.

**VERIFIED — manager fakes/local fixtures:** 248 Swift test functions/40 suites
(21 new coordinator/journal functions), 48 script tests and existing relocated
package checks pass. Coverage includes deduplication/stale admission, private
write-ahead/corrupt storage, cancellation/viewer detach, shutdown/force stop,
sleep/exit/SSH loss, unresponsive-worker deadlines, disk failure with attempted
revoke, live cleanup after source removal and conservative reopen. New coordinator
paths execute no subprocess. Existing socket/mock-context fixtures require the
workspace sandbox exception, without actual Keychain or authentication UI.
No real SSH/SCP/SFTP/Ansible, host installs, manager UI or VM operations occur.

**TO PROVE:** production coordinator construction/helper IPC, durable source and
recovery formats, SSH waits/restart rebinding, job/terminal UI and CLI, retention/
migration and real guest/helper crash/authorization/echo/quiescence behavior. The
manager execution surfaces remain disabled. This is the start of milestone 3,
not full job integration or real-guest acceptance.


## Durable frozen inputs and cleanup checkpoints — 3 November 2026

This continuation adds shared-engine APIs required by the manager's next
milestone-3 slice. The historical manager handoffs above describe the earlier
unchanged `bb3fae2` consumer; they do not describe this extension. Python
operational commands and disabled Swift execution entry points are unchanged.

`SourceSnapshot.privateArchive()` emits the private `DVMSNAP1` binary format:
versioned strict JSON metadata followed by selected raw file bytes. The reader
checks exact schema, duplicate keys, safe paths, hashes, lengths, tree references,
snapshot identity and EOF. It preserves binary bytes, modes and empty directories,
without host absolute paths/root inode identities. Bounds are 8 MiB metadata,
32 MiB file bytes, 4096 files/directories, 8192 directory children, 150000 JSON
values and path depth 64. `FrozenInputsArchive` exposes inert data with redacted
descriptions; it cannot become a SourceSnapshot/SetupPlan, extract into a user
tree or resume apply. Selected config may be sensitive: never put archive bytes
in plan/status/events/terminal output. File privacy/quota belong to the manager.

`CleanupRecoveryIdentity` takes an independently authenticated original
job/payload/guest/dependency/engine/mode expectation. Its private version-1
checkpoint includes original guest identity metadata, without credentials,
private keys, source data or terminal bytes. Restore compares the exact document
and conservatively re-proves work/payload risk and apply-only grant/cache
inactivity; disk flags cannot assert cleanliness. It authorizes no transport
by itself. The sequencer accepts a preallocated payload UUID, and retains its
control payload until grant/cache inactivity and work quiescence are proved.

The manager now fsyncs UUID-named 0600 input/checkpoint files in a 0700 directory
before its schema-2 index and worker. It binds hashes/token/payload to the original
review/session/dependencies, uses a bounded quota counting orphan files, and never
automatically imports/replays/deletes artifacts. Reopened cleanup requires a fresh
challenge proof from an injected authority that the previous worker is stopped
AND fenced from further launch. The authority is fake-only in this slice; no PID
or disk observation is sufficient. Cleanup needs neither original sources nor an
input archive, and never stages/grants/applies/prompts/restarts/rebinds. The fixture
boundary is coordinator/helper reopen with the original surviving VMManager
session, not full manager/VM restart adoption. Legacy journal risk remains held
when no genuine ticket/checkpoint exists.

**PRIVATE COUPLING — manager export:** manager `codex/dev-vm-provisioning-plan`
uses the immutable `bb3fae22be45b38035fac52aefa0eb270a9d0fea` base plus
`Patches/dev-vm-durable-state.patch`. Its lock binds base and resulting 82-file
inventories, patch hash, resulting snapshot digest and updated engine identity;
preparation verifies the result and reverse patch against the base inventory.
This is not an unchanged-base engine claim or a mutable external path dependency.
Parser, guest resource and C launcher bytes are unchanged. This worktree contains
the matching shared source/tests; the manager export retains baseline README bytes
and documents current integration in its own plan/vendor notice.

**VERIFIED — shared fake/local fixtures:**
`make build-provisioning test-provisioning test-provisioning-oracle test-provisioning-planning-oracle ORACLE_PYTHON=/opt/homebrew/opt/ansible/libexec/bin/python`
passes 68 Swift test functions, 18 strict-parser oracle fixtures and 66 complete
planning/error oracle fixtures. The Python path uses an already available runtime
only for development-time comparisons, never Ansible or a runtime fallback.
Four new test functions cover binary/mode/empty-directory archive round trips,
source removal, malformed/traversal/hash/version damage, conservative apply/check
cleanup restore, wrong original identity, preallocated payloads and helper retention
when inactive proof fails. Existing PTY tests need the workspace sandbox exception
for `/dev/tty`; all process fixtures are disposable local programs. No real
SSH/SCP/SFTP/Ansible, installs, UI actions or VM operations occurred.

**VERIFIED — manager fake/local fixtures:** `make test` passes 260 Swift test
functions/40 suites, 49 script tests and relocated/read-only offline-helper
packaging. Twelve new coordinator/journal functions exercise close/reopen and
interrupted markers, fresh original-worker fencing, wrong-session/dependency and
proof rejection, source/input removal, damaged/unsafe/swapped checkpoints,
quota/orphans, private inert archives and schema-1 risk preservation. A graceful
shutdown race now classifies body cancellation separately from original guest
identity so cleanup is not suppressed. Production entry points stay disabled.

**TO PROVE:** production authenticated helper IPC/fencing and manager construction,
full manager/VM restart with reviewed session rebinding, SSH waits, real missing
control-helper reconciliation/crash/quiescence, power-loss durability, artifact
retention/removal, live terminal/job UI and CLI, and all real guest authorization/
echo/transport acceptance. A helper that cannot prove absence leaves cleanup
required. This slice does not enable Swift operational execution.


## Manager authenticated helper ownership — 3 November 2026

The manager's milestone-3 continuation implements capability-authenticated
inherited helper IPC and original-worker fencing. This section supersedes the
older pending-IPC statements above; this worktree's shared engine, resources,
Python commands and immutable manager source pin are unchanged.

The manager/helper control channel uses an inherited same-user Unix stream and
per-launch 256-bit capability passed only through an anonymous bootstrap pipe.
HMAC-SHA256 frames bind helper instance/executable/package identity, direction,
channel, sequence and payload. Strict bounded schema/request/challenge checks
reject replay, reflection, wrong pins/keys, truncation and unexpected commands.
Capabilities never enter arguments, environment, disk, journal or diagnostics.
Only one request may be outstanding and a failed channel is never auto-retried.
This authenticates the private launch capability, not a distribution signing
identity; production launch admission remains a distinct required step.

A helper-local registry retains immutable original job/VM/session/payload/worker,
review, engine/dependency/binding/checkpoint scope. Registration is a trusted local
owner operation, never an IPC/disk-import command. Missing state and a new/empty
helper return unknown. The manager wrapper over this package's process-runner
protocol closes an original worker's launch gate permanently, interrupts only its
owned invocation, and waits for matching local exit/not-started or exact retained
cleanup. Uncertain or mismatched receipts retain ownership. Local proof never
claims guest work/grants are clean: the shared sequencer still quiesces/revokes/
verifies/removes against the original revalidated guest. Disconnect fences local
work without inventing remote proof or reading a PID from disk.

The coordinator now has a concrete authenticated recovery authority, tested with
fake runtimes/process runners and local sockets after coordinator reopen. The
actual relocated/ad-hoc sealed helper also supports an inherited ownership-only
mode. Its empty registry authenticates unknown responses but creates no runner,
tool probes, journal, Keychain access or VM. Existing operational setup gates and
apply/check/recover/exec entry points remain disabled. Shared code/resources and
the manager's base-plus-durable-patch source inventory do not change in this slice.

The user-supplied Setup-tab screenshot is the reference for the future large dark
live terminal/stage strip, follow/expand, cancellation and job details. Raw terminal
and input bytes are deliberately absent from the structured ownership protocol;
rendering, stream/input-lease transport and UI/CLI attachment remain later work.
No screenshot with personal sidebar identifiers is copied into this repository.

**VERIFIED — manager local fixtures:** `make test` passes 275 manager Swift test
functions/41 suites (15 new IPC/coordinator functions), 49 script tests and the
expanded relocated/read-only helper fixture. New Swift IPC tests use only fake
process runners. A separate actual ad-hoc sealed helper is tested through private
inherited socket/pipe descriptors, empty PATH and private empty HOME/TMPDIR; its
empty registry returns authenticated unknown, rejects replay/wrong MAC/bad binary
pins, and produces no secrets or host state. Existing package signature/tamper
checks still pass. Full regression uses the existing exception for local sockets/
synthetic LAContext, with no actual Keychain or auth UI. No real SSH/SCP/SFTP/
Ansible, installs, manager UI or VM operations occur. Shared code is unchanged;
prior 68 package tests/oracles remain historical evidence, not a new run here.

**TO PROVE:** automatic admitted manager/helper launch and exclusive backend/job
registration, operational sequencer/IPC delegation, full manager-process restart
and reviewed session rebinding, signer/audit policy as required by release,
real helper/guest crashes, remote cleanup and hard kernel-stall behavior, plus
terminal/CLI integration and real guest acceptance. A private capability/live
registry supports coordinator reopen, not adoption of a VM after manager restart.
The missing-helper case remains cleanup-required rather than assumed safe.


## Manager admitted helper launch and registration — 3 November 2026

The next manager milestone-3 slice adds an admitted helper launch factory and
inert worker registration. This supersedes the earlier pending launch/registration
status. This worktree has a documentation-only handoff: shared code/resources,
Python commands and the manager's base-plus-durable-patch source pin are unchanged.

The manager admits its exact package/helper, strict outer/nested signatures and
retained executable identity. Default policy requires non-ad-hoc matching app/
helper Team IDs; an explicit internal ad-hoc fixture policy is separate. Before
handing over the private launch capability, Security.framework verifies the owned
running child's admitted cdhash. Transient PID lookup is never saved/adopted or a
substitute for the authenticated inherited connection. Spawn uses fixed argv,
private cwd/HOME/TMPDIR, empty tool PATH, null diagnostics, bootstrap pipe and one
control fd with CLOEXEC-default handling. A waitable owned child is retained until
matching exit; there is no arbitrary PID kill or automatic helper replacement.

Bootstrap 2 reserves one metadata-only worker and sends an authenticated receipt
for the exact registration digest before reconciliation. The reservation contains
plan/input/mode and original job/VM/session/payload/worker/review/engine/dependency/
binding/checkpoint/helper identities, never source contents, guest credentials,
process invocations or terminal bytes. It has no operational runner/activation
API. Fencing permanently retires the not-started reservation. Bootstrap 1 still
has an empty registry and reports unknown for lost workers.

The coordinator now persists schema-3 owner pins and a pending registration marker
before launch, checks fresh admission around the receipt, and leaves a queued job
with no engine task and a conservative cleanup hold. Duplicate submissions cannot
automatically dispatch it. Schemas 1/2 preserve risk without inventing owners;
unknown/partial owner fields fail closed. Errors after owner publication retain
that exact owner, close only its channel and keep cleanup required. Recovery
requires the same surviving service/channel plus fresh original-scope proof.
Confirmed shared-engine remote cleanup releases that helper channel while its
owned child observer waits for exit. Matching VM `.exited` still controls guest
resources; no VM storage or lifecycle is added to this package.

The manager adds a debug-only Swift launch-fixture product, excluded from app
staging and disabled in release. It exercises the real factory with an ad-hoc
sealed/read-only disposable app. Fake-runtime tests cover ordering and failure;
no host software is installed and no real SSH/Ansible or guest is executed.
The Setup-tab screenshot remains the later terminal UI reference.

**VERIFIED — manager local fixtures:** `make test` passes 284 manager Swift test
functions/42 suites (9 new registration/coordinator/journal functions), 49 script
tests and expanded relocated/read-only signed package fixtures. Fakes cover
journal-before-spawn and owner retention, receipt/admission/session failures,
duplicates, schema migration and same-service recovery after coordinator reopen.
The real factory's debug-only fixture rejects ad-hoc code under production policy,
rejects resource tampering and same-byte executable replacement, then admits an
explicit ad-hoc fixture, verifies its owned child's loaded code, registers/fences
its inert worker and observes matching reaped exit. Control directories stay empty;
capabilities never enter output/files. Existing protocol/signature/tamper checks
pass. Local sockets/mock-auth fixtures use the existing sandbox exception, without
real signing credentials, auth UI, host installs, SSH/Ansible or VM operations.
Shared code/pins are unchanged and were not retested by this docs-only handoff.

**TO PROVE:** product wiring, operational engine/job/backend dispatch, positive
release signer/Team policy, full manager restart/reconnect and reviewed session
rebinding, real helper/guest crashes and remote grant cleanup, hard kernel stalls,
retention, SSH waits, terminal streams/input leases and UI/CLI. Existing setup
execution gates stay disabled; this slice does not start an operational Swift
provisioning job or complete milestone 3.


## Manager helper-side engine dispatch — 3 November 2026

The manager continuation activates a registered helper worker and invokes this
package's shared sequencer with injected fake adapters. This supersedes the earlier
no-dispatch status. This worktree changes documentation only: shared code/resources,
Python commands and the manager's immutable engine/source pin remain unchanged.

Authenticated activate/status/cancel messages name an exact original registration,
activation ID/digest and owner/review/plan/input/engine/dependency/session scope.
They carry acknowledgement booleans, never executable plans, arbitrary paths,
credentials or terminal bytes. The helper ANDs acknowledgements with its locally
prepared approval. One activation owns one task/sequencer, and duplicates return
status without preparing or running again. Changed activation conflicts; fencing
never reopens. A local context factory must prepare without guest/process work and
provide the matching reviewed request/approval, authority, exclusive runner and
adapter. The product helper has no such factory and refuses activation.

The helper task survives viewer/RPC detach. It revalidates command/binding/mode,
package/body and session/dependency authority, stops body on known disconnect or
cancellation, and permits original-target shared-sequencer cleanup without input.
Typed bounded status contains operation/result/failure metadata, not terminal,
source values or raw errors. Final local runner uncertainty overrides a clean guest
result. Disconnect retains owned tasks/cleanup instead of treating EOF as exit or
grant revocation. No guest authorization or Ansible rules are reimplemented.

Manager schema 4 persists activation identity and cleanup risk before dispatch,
checks authenticated monotonic results and retains lifecycle holds on lost replies,
disk/status failure or VM/session/dependency change. Accepted activations are never
automatically replayed after coordinator reopen. Explicit original-owner cleanup
still requires fresh authority; helper-child exit and matching VM `.exited` remain
separate. Ordinary shutdown preserves cancellation/cleanup ordering.

A separate temporary ad-hoc-signed fixture app replaces only its helper slot with
the excluded debug fixture binary. That binary hosts the synthetic factory and
fixed local manifest, so actual admitted helper-process dispatch/cancellation can
be tested without putting a fake backend in the normal helper. No runtime flag,
environment override or RPC can enable a product backend. No real SSH/SCP/SFTP/
Ansible, host install, manager UI or VM operation is performed. The Setup screenshot
stays the future terminal UI reference; raw streams/input remain later work.

**VERIFIED — manager fake/local fixtures:** `make test` passes 297 manager Swift
functions/43 suites (13 new engine/coordinator/journal functions), 49 script tests
and expanded signed package checks. Tests cover one-shot apply/check, activation
consent/context/source checks, cancellation/fencing/disconnect, physical uncertainty,
journal-before-RPC, viewer detach, shutdown, malformed/lost replies, no replay after
reopen, runtime/dependency invalidation and strict schema preservation. The regular
helper refuses activation without a factory. A distinct temporary ad-hoc-signed
helper fixture runs the actual shared sequencer with synthetic adapters, completes
and cancels/cleans correctly, and exits through the admitted owned launcher.
Existing identity/protocol/signature/tamper checks pass. No fake backend is put in
the normal helper/app, and no real signing credential, authentication UI, transport,
installation or VM is used. Existing socket/mock-auth sandbox exceptions apply.
Shared sources/pins are unchanged; their prior tests/oracles are not rerun here.

**TO PROVE:** production frozen-context/consent delivery, exclusive real backend
construction and manager-aware per-command session authority, product wiring,
full manager/helper restart/reconnect and reviewed rebinding, release signatures,
real guest/auth/echo/remote cleanup/crash/kernel behavior, terminal/PTY/input/UI/CLI.
Current fixture acceptance does not establish guest behavior or enable operational
setup. No shared package/oracle rerun is claimed for this docs-only handoff.

## Manager frozen-input delivery and context validation — 3 November 2026

The manager's next milestone-3 continuation delivers selected frozen inputs and
reviewed request metadata to its admitted helper. This supersedes the pending
context transfer above. This worktree exposes `SetupPlan.manifestPath` as public
read-only metadata so a consumer can preserve the reviewed relative manifest path;
engine inventory is regenerated. No planner/parser/guest/C-launcher behavior or
Python operational command changes. The manager's immutable base-plus-patch export
is updated with that exact API/inventory change; it is not an unchanged engine pin.

The manager fsyncs a private immutable `DVMCNTX1` blob (strict request JSON plus
`DVMSNAP1` selected archive). Registration/schema-5 journal bind its exact length
and total/metadata/archive hashes to the original owner/review. A retained private
read-only source descriptor is checked before transfer. The child inherits an
empty separate socket at fd 4; only after owned-live-child image admission receive
bootstrap 3 and the frozen bytes. Capability/source data do not enter arguments,
environment, status or terminal. Data is chunked/bounded and requires exact size,
hash and EOF; no arbitrary host source path is sent to the helper.

The helper verifies metadata/target/session/dependencies, writes only into a new
private UUID tree using descriptor-relative no-follow/exclusive traversal, and
preserves modes, binary bytes and empty directories. Existing archive bounds plus
implicit-directory/depth bounds apply. It independently replans with this package
inside that tree, compares plan/input/engine hashes, reconstructs the full request
and compares review identity before acknowledging delivery. `FrozenInputsArchive`
remains inert data; it does not deserialize an executable plan or grant apply.

A backend receives the validated context only; delivered, backend and explicit
activation acknowledgements combine by AND. The product helper has no backend,
rejects activation and keeps execution gates disabled. Only an excluded Debug
fixture constructs synthetic adapters. Once an accepted frozen job exists, its
selected private copy defines the reviewed inputs; original-checkout edits/removal
cannot replace them. Source checks still precede publication, activation validates
persisted/private copies, cleanup remains independent of inputs, and reopen never
replays apply. Schemas 1–4 preserve risk/ownership without invented receipts.
Partial private artifacts are retained; automatic import/removal is not introduced.

**VERIFIED — shared fake/local checks:**
`make build-provisioning test-provisioning test-provisioning-oracle test-provisioning-planning-oracle ORACLE_PYTHON=/opt/homebrew/opt/ansible/libexec/bin/python`
passes 68 Swift functions, 18 parser oracle fixtures and 66 complete planning/error
fixtures. The already available Python runtime is used solely for development
oracle comparisons; no Ansible or product Python fallback runs. Existing PTY
fixtures need the local `/dev/tty` sandbox exception.

**VERIFIED — manager fake/local checks:** `make test` passes 308 Swift functions/
44 suites, 49 script tests and expanded relocated/read-only signed-helper fixtures.
Coverage includes independent replan after source deletion, custom manifest/
catalogue/tasks, binary/mode/empty-directory preservation, metadata/hash/scope/
framing damage, unsafe/changed private descriptors, root substitution and directory
bounds, strict bootstrap/receipt/journal handling and consent constraints. The
actual product helper validates but denies activation. A separate ad-hoc-signed
fixture helper receives/validates a multi-frame payload, then completes/cancels
using fake adapters after the parent's source is removed. Changed delivery is
refused and the owned child reaped. No real SSH/SCP/SFTP/Ansible, credentials,
auth UI, host installs, installed-app changes or VM operations occur.

**TO PROVE:** exclusive real backend construction and trusted manager-aware session/
dependency authority, product wiring, full restart/reconnect/rebinding, real release
signatures, power-loss durability/retention UX and terminal/PTY/input/UI/CLI work.
Real guest authorization, echo, cleanup/quiescence and crash/kernel behavior remain
unproved. This is a foundation continuation, not completion of milestone 3.

## Manager helper backend and session authority — 3 November 2026

The next manager milestone-3 continuation constructs this package's concrete
`SSHAnsibleGuestAdapter` with an original-worker fenced runner and a manager-backed
session authority. This supersedes the pending construction/authority foundation
above. The product helper has no transport-resource provider, rejects activation
and leaves setup execution gates disabled. All exercised providers supply inert
fixture files and fake process runners; no SSH/Ansible command is executed.

Shared changes are narrow: `ProvisioningSSHConnection.verify()` exposes stat-only
identity reference revalidation without reading key bytes;
`ProvisioningTransportTools.verify()` is public; `ProvisioningProcessPurpose` gains
Codable for fixed private metadata. Inventory and the manager's exact immutable
base-plus-patch export/engine pin are updated together (82 resulting files). Guest
resources, parser dependencies and C launcher remain unchanged. No Python
operational workflow or runtime fallback changes.

A single-use helper-local builder checks the frozen request/package and fresh
manager permission before asking a trusted provider for the explicit connection,
tools, dependency digest and idle process-runner factory. Recheck exact bindings
and pins around awaits, then construct the shared adapter and fenced runner with
the same authority. There is no manifest/RPC-selected executable, host path or
credential-discovery default. Production managed-SSH/Homebrew admission and private
resource handoff remain consumer wiring, not an implicit capability of the builder.

Bootstrap 4 binds a separate inherited fd-5 reverse authority channel. A derived
HMAC key domain and separate counters prevent control frames from granting session
permission. The manager binds one original registration/activation after durable
activation/lease publication. Fresh challenge-correlated checks cover preparation,
commands, invocations and completion; responses are never cached. A dedicated
reverse loop keeps control/status/cancel available while the coordinator awaits
VMManager/dependency checks. Typed bounded metadata contains no owner names,
credentials, paths/argv, source or terminal bytes. Wrong/replayed/lost frames fail
closed. Schema 6 preserves the authority version without inventing it for legacy
rows or resuming apply after restart.

VM/session/readiness/lifecycle ownership remains with the manager. It checks the
current lease/generation/activation and original target/dependencies around awaits.
The fenced runner records ownership before permission and rechecks cancellation
before backend launch. Original-target cleanup remains possible after ordinary
cancellation or package/source loss. Failed journal writes stop body work while
retaining the live lease for cleanup and an unresolved hold. Lost or invalid
authority cannot assert remote cleanliness; uncertain local ownership retains the
original runner until explicit matching proof. No VM implementation is duplicated.

**VERIFIED — shared fake/local checks:**
`make build-provisioning test-provisioning test-provisioning-oracle test-provisioning-planning-oracle ORACLE_PYTHON=/opt/homebrew/opt/ansible/libexec/bin/python`
passes 68 Swift functions, 18 parser oracle fixtures and 66 complete planning/error
fixtures. The existing Python runtime is development-only; PTY fixtures use the
existing local `/dev/tty` sandbox exception. No real Ansible or guest runs.

**VERIFIED — manager fake/local checks:** `make test` passes 319 Swift functions/
45 suites, 49 script tests and expanded relocated/read-only signed-helper fixtures.
New coverage includes concrete adapter apply/check without execution, construction
ordering/resource changes, fresh manager permission before every fake invocation,
cancel/shutdown/session/readiness/dependency/package/channel changes, cancellation
during dependency validation, failed-journal cleanup, strict MAC/challenge/schema
and binding handling, local-authority bypass refusal and uncertainty recovery
without constructing another backend. A separately sealed/ad-hoc-signed Debug
helper exercises actual backend construction and inherited session RPC with fake
process replies, completion and deterministic interruption/cleanup. The normal
helper refuses activation without a provider and matching child exit is reaped.
No real credentials/auth UI, host installs, SSH/SCP/SFTP/Ansible, installed-app
change or VM operation occurs.

**TO PROVE:** consumer resource admission/handoff and product construction, real
runner/terminal/input leases, UI/CLI, full restart/reconnect/rebinding, release
signatures, power-loss/retention UX and all real guest/auth/echo/transport/remote
cleanup/quiescence/crash/kernel behavior. Fresh manager RPC is not atomic remote
execution or proof of guest liveness after its reply. Milestone 3 remains incomplete.

## Manager transport-resource admission and private handoff — 3 November 2026

The next milestone-3 continuation admits the manager's original transport resources
and hands them privately to its helper. This supersedes the pending admission/
handoff foundation above. Product setup gates stay disabled; the normal helper
has no process-runner factory and still refuses activation. No VM implementation
or Python operational workflow is changed.

The shared package adds `ProvisioningTransportReference`, an explicitly private
metadata format for original connection/executable proofs. It contains the public
host key and identity-file path/stat proof, never private-key bytes. Import checks
strict schemas, expected binding/identity/tool paths and original inode/mode/link/
time/hash/target proofs rather than blessing replacement files. Identity references
now require one link. Descriptions are redacted; default report/event encoding is
not added. Export/import do not run a process or authorize execution by themselves.
The manager's exact base-plus-patch export/engine pin is updated with 83 resulting
files. Guest resources, parser dependencies and C launcher remain unchanged.

The manager admits only its current running/ready session/profile/root and managed
SSH port. It verifies public managed manifests/known-hosts metadata, root identity
and stat-only key reference without calling credential generation or key-reading
storage validation. It consumes an already checked dependency report, validates
fixed system entries, Homebrew Ansible pair/version/installation and fingerprints,
and captures original full tool pins. Dependency identity is derived from that
selection and must match the reviewed request. Report fingerprints are change
detectors, not new binary-signing or complete runtime provenance claims.

An ephemeral bounded descriptor binds resources to the original job/VM/session/
worker/payload/review/checkpoint/plan/engine/mode. Bootstrap 5 binds its SHA/size/
dependency receipt and inherited fd 6. Only after owned-child admission transfer
it on the private one-shot channel, with exact framing/hash/EOF. No descriptor file
is written; no private paths/data enter arguments, environment, control/status/
terminal frames or the journal. The helper independently checks its host policy
and original references before acknowledging the resource digest. Fixture policy
is injected only by excluded test code, never selected by the document or a flag.

Manager and helper recheck current resources before publication/activation and
command/invocation boundaries. Changed keys/tools/wrappers/installation/public
metadata require new review, not automatic recapture or cleanup retargeting.
Schema 7 stores receipts only; legacy risk/pins survive without invented resources.
Live admission/launch state remains separate, and coordinator reopen never imports
credentials or replays apply. Product resource acquisition/coordinator wiring,
operational runner and terminal/input leases remain later consumer work.

**VERIFIED — shared fake/local checks:**
`make build-provisioning test-provisioning test-provisioning-oracle test-provisioning-planning-oracle ORACLE_PYTHON=/opt/homebrew/opt/ansible/libexec/bin/python`
passes 70 Swift functions, 18 parser fixtures and 66 complete planning/error oracle
fixtures. New shared tests round-trip original proofs with an unreadable synthetic
identity file and reject changed/retargeted/unknown proofs. Python is used only for
development comparisons; existing PTY tests use the local `/dev/tty` exception.

**VERIFIED — manager fake/local checks:** `make test` passes 328 Swift functions/
46 suites, 49 script tests and expanded relocated/read-only signed-helper fixtures.
New coverage includes manager-owned metadata/report admission, private round trip,
key/tool/alias/installation/metadata/root changes, cross-job/mode/review/format/hash
damage, acknowledgement refusal, independent policy, migration and no replay.
Concrete apply/check use fake process runners. A separate sealed/ad-hoc-signed
Debug helper imports the actual inherited descriptor and uses original resources
with fake process replies for completion/cancellation; matching exit is reaped.
The normal helper rejects fixture paths under host policy and gets no fake runner.
No real credentials/auth UI, host installs, SSH/SCP/SFTP/Ansible, installed-app
changes or VM operations occur.

**TO PROVE:** genuine resource admission across supported installations, product
acquisition/coordinator wiring and report provenance/lifetime, operational runner/
terminal/input/UI/CLI, full restart/reconnect/rebinding, release signing, retention/
power-loss UX and real guest identity/auth/echo/transport/remote cleanup/quiescence/
crash/kernel behavior. Stat/hash/RPC checks do not make remote execution atomic or
prove guest liveness after a reply. Milestone 3 remains incomplete.

## Manager milestone 3 completion — 3 November 2026

**DESIGN DECISION:** manager milestone 3 is complete for fake/local acceptance. Its
new manager-owned service installs once with product execution disabled; opening it
admits the pinned package and seeds persisted lifecycle risk before exposing work,
without probing tools, starting helpers or operating VMs. A strict private workflow
index complements schema-7 child journals and receipt-bound frozen inputs. Owned
preparation waits for the exact SSH session, requires review, persists acceptance
before suspending and deduplicates concurrent/duplicate requests. Original-helper
exit observation is required even after a clean engine result.

Planned restart requires separate approval and the matching old `.exited` before
the manager may create the replacement session. Fresh resources, the same VM/owner/
UID/expected key and a distinct explicit rebind review authorize a new check-only
job over frozen inputs, excluding custom tasks and password input. Cancellation,
timeout and `.error` never substitute for exit or silently reapply.

Reopen never resumes activation or imports sources/credentials. Cleanup requires
current manager-session authority, original resource admission and independent
stopped-and-fenced proof from the original authenticated helper. A surviving
launcher can support service/coordinator reopen; a genuinely fresh manager process
cannot recreate that capability from disk. It retains cleanup-required holds and
refuses worker/VM adoption and replay. The separate-process debug fixture exercises
owner exit during fake work, EOF fencing and fresh-process refusal; its marker is
only a test diagnostic, never a production ownership proof.

Retention preserves private inputs/checkpoints/deliveries and orphan/partial files.
Count/byte-only reports reveal no private contents or paths. Quotas refuse work
instead of evicting recovery data; retained rebind trees also have count/entry/byte
bounds. Manual recovery/retention UX remains later acceptance work.

**VERIFIED — consumer no-VM checks:** `make test` passes 347 Swift test functions in 48 suites, 49 script tests, and relocated/read-only ad-hoc-signed helper fixtures. The final `make test-provisioning-tools` run passes 141 functions in 13 suites after the last cancellation/recovery guard changes. Package/export validation and companion/vendor source/engine matching pass.
No shared source or export-pin changes were needed for this completion above the
transport-resource handoff slice. The previously recorded 70 shared Swift, 18 parser
and 66 planning/error oracle checks remain its evidence. New manager checks cover
service composition, local runner construction/output with no input grant, SSH and
restart/rebind lifecycle, concurrency, failures/corruption, retention, surviving-
capability recovery and full-process lost-capability refusal. No actual SSH/SCP/
SFTP/Ansible, credential/auth UI, host install, installed-app change or VM operation
is performed.

**TO PROVE / NEXT:** milestone 4 live terminal/stream/input/resize delivery and
rendering; milestone 5 Setup UI/CLI; milestone 6 approved real guest authentication,
restart/check, revocation, remote cleanup/quiescence and crash/sleep/wake behavior;
milestone 7 release signing/distribution. Product helper execution remains disabled
without an operational runner factory. Positive remote recovery/adoption after
full process loss is not established by the safe refusal tests. The Setup screenshot
remains a later UI target.

### Manager milestone 4 terminal transport — 3 November 2026

The manager consumer now connects the shared memory-only terminal to a dedicated
inherited, separately authenticated helper stream. Viewers start read-only; one
explicit owner generation controls input and PTY size. Detach/expiry/channel loss,
completion/cancel/fence and observed output gaps revoke input. Queued keystrokes
are discarded on suspension; a new live attachment must deliberately reclaim the
reviewed scope. Output stays bounded, in memory and separate from structured
status/results and journals. Eviction requires a visible decoder/emulator reset,
an explicit jump to the live tail and a fresh claim, never invented old screen
state. The scoped local TTY helper restores settings after success/error/cooperative
cancellation; hard process termination is not covered.

The shared package adds reserved-versus-enabled input scope, atomic suspension and
explicit resumption, plus a read-only tail sequence for the consumer's reset
contract. Permanent revocation remains final. Transport workspaces normalize their
own generated paths before local runner admission. Sources, engine inventory,
manager export and reviewed patch are synchronized; the immutable base revision
remains unchanged. No guest resources/playbooks or third-party dependencies change.

**VERIFIED:** `make build-provisioning test-provisioning test-provisioning-oracle
test-provisioning-planning-oracle
ORACLE_PYTHON=/opt/homebrew/opt/ansible/libexec/bin/python` passes 72 Swift test
functions, 18 parser oracle fixtures and 66 complete planning/error oracle fixtures.
Python is an existing development oracle only. The manager's final `make test` passes 362 Swift functions in 49 suites,
49 script tests and the relocated/read-only/ad-hoc-signed helper fixtures. Package
export verification, exact comparison of all seven changed source/engine/test
files and both worktree diff checks pass.
Local fixtures prove ANSI/carriage-return/split-UTF-8 byte delivery, real local PTY
prompts/hidden input/resize, view detach/reclaim, expiry, stale capability refusal,
bounded floods, cancellation, gap/reset handling and TTY restoration. An excluded
ad-hoc-signed debug helper runs a fixed local printf/sleep feature fixture through
the admitted frozen/resource/session/engine/terminal path; it never executes the
original SSH/Ansible command. The shipped helper still has no operational runner
factory and product execution remains disabled.

**TO PROVE / NEXT:** native emulator/rendering and host-action escape policy,
Setup UI and external CLI stream endpoint are manager milestone 5. Real nested
SSH/native guest authentication/echo, resize, revocation, restart/check, remote
cleanup and crash/sleep/wake acceptance remain approval-gated milestone 6; release
distribution/signatures remain 7. Full-process loss cannot recreate terminal or
worker capabilities from disk. No real transports, host installs/downloads, VM or
user UI operation occurred. The Setup screenshot remains the milestone-5 target.

### Manager milestone 5 terminal/observation slice — 3 November 2026

The manager consumer now has a native Setup terminal and separate same-user
streaming CLI endpoint backed by the existing job service. Both use the shared
terminal/input contract; no shared engine/resource source changes are required.
The manager pins SwiftTerm 1.99.0 as a renderer-only dependency (Swift 6.2+), filters
host-action escapes, validates split UTF-8, bounds scrollback/input, displays gaps,
and requires explicit ownership. Offline manager presets select the existing
`developer`, `web`, `python` and `project-managed` profiles through the same planner.
UI/CLI default to view-only; detach is distinct from cleanup-aware cancellation.

The manager's `make test-provisioning-ui-cli` covers renderer, strict protocol,
same-user sockets, cross-view ownership and disposable CLI TTY restoration.
`make test` passed 376 manager Swift test functions in 50 suites, 52 script tests, and the relocated/read-only/ad-hoc-signed helper fixtures (including original owner-loss/reopen and terminal streaming). The focused UI/CLI coverage contains 13 functions plus the four-case bundled-preset test: split Unicode/ANSI, cursor/colour/CR rendering, blocked host actions, oversized/malformed streams, storage bounds across cursor/style changes, native viewer ownership/search/reset, strict correlated protocol refusal, cross-view input ownership, EOF/gap/reclaim, distinct cancellation and disposable PTY termios/signal/open-file-flag restoration on detach, connection loss and task cancellation. Vendor inventory, the reviewed two-line source patch, exact upstream export comparison, unchanged shared-package export checks and `git diff --check` passed. No user window was opened or real transport executed.
These are fake/local checks. Product execution, New VM setup coupling,
frozen preview-to-apply/custom-task trust and reviewed restart/check/recovery
surfaces remain gated follow-up work. No real SSH/Ansible, host installs or VM
operations occurred. Shared package sources/resources remain at committed
`3d616f0`; its previous 72 tests and oracle checks remain the unchanged baseline.

### Manager milestone 5 frozen review and task-trust slice — 3 November 2026

The manager now exposes frozen preview capture/lookup, explicit bounded task-source
inspection and prepare/apply consent through the same native/CLI service. It uses
this package's existing SetupPlanner, immutable source archives and request review
identity; no shared library/resource/pin changes are needed. Capture replans inside
a retained private UUID tree and compares plan/input/engine hashes. Later edits to
the original folder cannot change the approved inputs. A separate task-trust digest
binds the exact request, complete frozen snapshot and task selection. General Apply,
persistent sudo and Docker root-access acknowledgements do not imply task trust.

Final submission rechecks frozen sources, package, original resources/session and
fresh dependencies before the existing helper path. One preparation/submission is
owned per UUID; duplicate consent retrieves its acceptance, while failed operations
are not automatically replayed. Explicit source reads use 4096-byte chunks and never
enter background status/terminal output. Memory-only previews/consent cannot be
reconstructed from retained files after manager restart. Product execution and its
real owner/UID/key resolver stay disabled; fake tests supply synthetic bindings.
`make test` passed 390 manager Swift test functions in 52 suites, 52 script tests and the relocated/read-only/ad-hoc-signed helper fixture suite (including original-owner loss/reopen and terminal streaming). `make test-provisioning-review` passed 28 functions in three suites: frozen previews, original-source edits, explicit task-source chunking, preview quotas, no authority after reopen, separate task/sudo/Docker consent, exact duplicate submission, changed source/tool/session admission, cancellation during a gated final recheck, stale task trust, strict nested protocol cases and CLI/native service interoperability. Tests call the native service API and actual private CLI socket, without opening the form or claiming visual acceptance. Package/export and both diff checks pass; shared package sources/resources/pins are unchanged.
Native feature editing/New VM handoff and reviewed restart/check/recovery surfaces
remain follow-up work. No actual SSH/Ansible, host installs, factory images, VM
operations or user UI takeover occurred. Shared sources/resources remain unchanged
at `3d616f0`; the docs-only terminal consumer commit is `f5d495c`. The manager's
preceding terminal/UI/CLI slice is committed at `18feed5`.

### Manager milestone 5 reviewed workflow actions — 3 November 2026

The manager now exposes reviewed restart, post-restart check and cleanup recovery
through the same native/CLI service. Exact action UUID/digest and acknowledgement
bind workflow, VM/session/job, sequence and frozen-input/dependency hashes. It
reuses the established manager coordinator and this package’s sequencing contracts.
Restart waits for matching VM exit before replacement; check requires fresh-session
admission, excludes custom tasks and grants no authorization input. Recovery uses
only original identity/quiescence/revocation/cache/inactive/payload cleanup, with a
lazy adapter factory behind authenticated original-worker and checkpoint admission.
Saved metadata/PID cannot recover lost capabilities; failed revocation retains risk.
No Apply/task trust is reused as action consent and no failed operation is replayed.
`make test` passed 403 manager Swift test functions in 54 suites, 52 script tests and the relocated/read-only/ad-hoc-signed helper fixtures, including original-owner loss/reopen and terminal streaming. `make test-provisioning-actions` passed 13 functions in two suites (including ten malformed-wire variants and three final-check admission/cancellation variants). Fake fixtures cover explicit consent, shared CLI/native action lookup, duplicate restart/check, diagnostic-vs-exit boundaries, fresh-session frozen checks with custom tasks excluded and no authorization input, active-risk recovery refusal, lazy factory ordering, missing original capability after reopen, source-free cleanup, failed revocation/retained holds, stale sibling recovery reviews, failed-operation non-replay and lost in-memory consent. Product endpoint tests prove disabled refusal before probes/factories. UI controls compile; complete interactive/visual acceptance was not performed. Package/export checks and both diff checks pass. Shared package sources/resources/pins are unchanged.
Product execution, real target resolution and recovery factories stay disabled.
Native feature editing/New VM setup handoff and all real guest/visual/distribution
acceptance remain separate. No actual SSH/Ansible, installs, factory images, VM or
user UI operations occurred. Shared library/resources/pins remain unchanged; the
manager’s preceding frozen-review slice is `d6d9c64` (companion docs `09a099c`).
