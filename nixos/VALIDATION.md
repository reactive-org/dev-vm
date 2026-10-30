# Workstation validation

Latest validation: 2026-10-31. Unattended installation, transactional apply and
the controlled kernel upgrade/reboot/boot-rollback checks are complete. Earlier
sections retain their phase-specific observations and limitations.

Status: the minimal workstation boots and runs Hyprland. With matching host
and guest Tools 27.1.0, the user confirmed reliable focused Kitty→Kitty,
macOS→Kitty and Kitty→macOS copying, including delayed paste. The stock bridge
is enabled by default again. The user confirmed suspend/resume works and
explicitly accepted long-term reliability as an assumption to proceed to
Phase 2; several-hour reliability was not measured. The user also confirmed
Chrome→Kitty and Claude Desktop→Kitty copying, including delayed paste. All
requested focused copy directions now have user-confirmed passes. A separate
vendor helper shutdown crash remains reproducible.

## Phase 2 application modules

Added Home Manager and numtide/llm-agents inputs with locked revisions and
content hashes, both following the unchanged Nixpkgs input. No extra binary
cache or signing key was enabled. All new packages were installed in the
guest; nothing was installed on the Mac.

| Check | Result |
| --- | --- |
| Full `nix flake check`, generic repository host | Pass |
| Full `nix flake check`, installed host | Pass |
| Activation and Home Manager activation service | Pass |
| Chrome / Firefox / VS Code version checks | 156.0.8078.47 / 158.0.1 / 1.142.0 ARM64 |
| mise / GitHub CLI / Claude Code / 1Password CLI | 2026.10.17 / 2.103.2 / 2.1.311 / 2.41.1 |
| Zsh, Oh My Zsh, Powerlevel10k and shell integration | Starts cleanly with a PTY |
| Docker daemon, Buildx and Compose | 29.9.1 ARM64 / 0.35.0 / 5.6.0 |
| ARM64 Docker `hello-world` container | Pass |
| Waybar / fuzzel | 0.15.0 / 1.15.0; version checks pass |
| Full system and user Hyprland configuration parser | Pass |
| Waybar, mako, cliphist text/images, authentication agent, 1Password background app | Active |
| Stock Parallels clipboard service | Active, zero restarts after activation |
| System and user failed-unit lists | Empty |
| Cowork-specific QEMU, firmware and virtiofsd packages in system closure | Absent |
| Chrome→Kitty, including delayed paste | User-confirmed pass |
| Claude Desktop→Kitty, including delayed paste | User-confirmed pass |

Claude Desktop 4.4212.0 starts and creates a native Wayland window. Chrome
initially opened a keyring prompt; the user subsequently confirmed reliable
copying from both Chrome and Claude Desktop into Kitty, including delayed
paste. The keyring PAM integration is inherited by
greetd through the `login` PAM stack. Credentials remain user-managed.
The non-TTY Zsh probe printed ZLE warnings; a real-terminal startup passed
without warnings. This was a test-context limitation, not a login-shell failure.

The graphical session survived activation. After the user logged out and back
in, Zsh and the desktop services started successfully, but greetd retained its
original in-memory launcher and started the old Hyprland configuration. Normal
logout/login alone was insufficient; the Phase 3 launcher correction below
requires one login-manager restart or reboot.
Account-authenticated workflows remain interactive acceptance tasks; the
Chrome/Claude Desktop clipboard checks passed. Firefox and VS Code GUI workflows have
not yet been exercised. The VM has approximately 6 GiB free after installation;
no old generations were removed.

## Phase 3 host integration and local configuration

Post-login checks confirmed the fixed 2560×1600 display at approximately 60 Hz,
native Wayland Kitty, Zsh as the login shell, active desktop/clipboard services
with zero restarts, active Docker and Home Manager, no failed system/user units
and no Hyprland configuration errors. Guest UTC time agrees with the controller
within a two-second measurement tolerance.

The corrected greetd command now resolves stable `/etc/greetd/workstation-login`
and `workstation-session` files. With user approval after saving work, the login
manager was restarted and its new greeter command now resolves the stable
session path. The subsequent graphical login runs Hyprland with
`--config /etc/xdg/hypr/hyprland.conf`. Live binding inspection confirms
Option+Command+Space launches fuzzel, V toggles floating and L locks.
Kitty reads the managed JetBrains Mono 13/native Wayland configuration.
All desktop services and the clipboard bridge start with zero restarts;
there are no configuration errors or failed units. The user also confirmed
the launcher shortcut works.

The empty local flake input, configurable projects directory, extra packages,
Git include paths, Hyprland overrides and mise runtime declarations are
implemented. Rails and Java profile overrides evaluate successfully. The Rails
example's appended Chrome floating rule passes the Hyprland parser. The projects
directory was created by Home Manager. Optional language runtimes were not
installed. Both the exact generic host and installed host passed full flake
checks and the installed configuration activated successfully, without moving
the Nixpkgs pin.

The shared-folder module passed a full build and activation with its option
enabled. The user explicitly approved read-write access to the existing host
folder and the guest-wide FUSE `user_allow_other` setting, after automatic
approval review required these permissions. A service-only namespace approach
could not publish the mount and was removed. The final module uses the standard
unprivileged Parallels FUSE helper and privileged NixOS fusermount wrapper.
`/mnt/shared` is visible to normal guest processes with `nosuid,nodev`,
`default_permissions` and the workstation UID/GID. A host-created synthetic
file was read and modified by the guest; a guest-created file was read by the
host. All test files were removed. A mount-service restart passed and no failed
units remain. The missing-folder workflow was tested with a nonexistent fixture
and invoked no Parallels command.

Personal-state handling uses explicit one-file SSH provisioning into the mutable
home. A synthetic binary payload passed an actual transfer with mode 0600.
Existing-file, existing-directory, traversal and symlinked-parent refusal checks
passed, and the fixtures were removed. The Make target also passed with spaces
and quotes in the selected filename, preserving mode 0600. No private keys, authentication state or
personal dotfiles were copied. Bash syntax, ShellCheck, Python syntax and
`git diff --check` passed.

Suspend/resume and focused clipboard checks are user-confirmed as recorded above;
long-term reliability is an accepted assumption. Authenticated application
workflows remain open. The corrected launcher login and automatic service
startup passed. Unattended installation and controlled kernel compatibility
with the matching Tools release are validated below.

## Phase 4 unattended installation and apply automation

The Make workflow now creates private EFI media from the official ARM64 ISO,
installs onto only a new blank Parallels disk, sets the selected account password
outside Nix, powers off, detaches the ISO, boots the disk, verifies SSH/account
security and runs the same transactional apply used for subsequent updates.
No host software was installed. Disposable tests disabled host folder sharing.

| Check | Result |
| --- | --- |
| Fresh `make bootstrap-nixos`, from creation through final apply | Pass, without installer interaction or manual recovery |
| Private external and FAT EFI GRUB configuration, unchanged EFI executable | Pass |
| Source ISO SHA-256 against the user-supplied digest | Pass |
| Automatic disk boot, strict SSH host-key verification, installed marker | Pass |
| Developer account password present, root locked, passwordless sudo denied | Pass |
| Full flake build and exact pinned Hyprland Lua parser | Pass |
| Existing-instance hardware, SSH keys, installation, identity and sharing data retained | Pass, all five files unchanged |
| Explicit private local input replacement and subsequent preservation | Pass |
| Invalid Nix candidate rejected before activation | Pass; active generation and source unchanged |
| Invalid Lua rejected by the parser build check | Pass; active generation, boot profile and source unchanged |
| Intentional activation failure | Pass; previous running system, boot profile and source restored |
| Resume after an interrupted post-install account check | Pass; same VM completed without repartitioning |
| Host controller terminated during a build-only apply | Pass; guest systemd job completed and active system/source stayed unchanged |
| Read-only blank-disk guard against an installed disk | Refused existing partitions as intended |
| Credential-bearing generated ISO/payload cleanup after success | Pass |
| Final `make check-nixos` against repository source | Pass |
| System failed-unit lists and SSH/Tools/login services on all test VMs | Empty failed lists; required services active |
| Nine controller/media safety tests, Bash syntax, guest ShellCheck and diff checks | Pass |

Early test boots exposed a conflict between the ISO's default target and the
systemd command generator; explicitly selecting `kernel-command-line.target`
fixed unattended startup. A transient Parallels SDK failure during a read-only
account check exposed a recovery gap; bounded guest-channel retries and recorded
VM/marker-based resume were validated. These failures are distinct from the
successful final fresh run.

Apply jobs run independently under systemd, preserve password-required sudo,
check the candidate before switching, and publish source only after activation
and service checks succeed. A failed activation attempts automatic recovery and
retains its log/source for diagnosis. This does not establish rollback for every
possible kernel, power-loss or vendor Tools failure. Kernel boot compatibility
and rollback are validated below; interactive application acceptance remains open.

## Controlled kernel upgrade and boot rollback — 2026-10-31

A disposable ARM64 VM was installed through the unattended workflow with
four CPUs, 12 GiB RAM
and a 48 GiB expanding disk to retain both kernel closures. Host folder sharing
was disabled. No host software was installed. A cold Parallels snapshot was
created before the upgrade.

A private local input selected `pkgs.linuxPackages_latest`, changing the test
kernel from **6.18.59 to 7.3.0**. The repository's kernel default and complete
flake lock stayed unchanged. The actual Parallels Tools and Hyprland package
store paths were identical before and after the change: Tools **27.1.0-58756**
and Hyprland **0.56.2**. This is a kernel compatibility rehearsal, not a default
kernel-policy change or a simultaneous vendor Tools upgrade.

| Check | Result |
| --- | --- |
| Full candidate flake checks, system build and activation | Pass |
| Reboot from 6.18.59 into 7.3.0 | Pass; boot ID changed and running/booted/profile systems matched |
| SSH, networkd, Parallels Tools, greetd and Docker services | Active on both kernels and after rollback |
| Virtio GPU, native Wayland Kitty and fixed 2560×1600 display | Pass on both kernels and after rollback |
| UWSM desktop, stock clipboard controller, Waybar, notifications, audio services and portals | Active; system/user failed-unit lists empty |
| Exact Hyprland configuration and two-second synthetic guest clipboard retention | Pass on both kernels and after rollback |
| ARM64 Docker `hello-world`, container networking disabled | Pass on 7.3.0 and after rollback |
| Password-required sudo and persistent user lingering disabled | Retained |
| Older boot entry selected with `bootctl set-oneshot` | Pass; 6.18.59 booted while the persistent profile still selected 7.3.0 |
| `nixos-rebuild boot --rollback --no-reexec` | Pass; baseline profile and default boot entry restored |
| Recorded baseline source pointer restored, followed by another reboot | Pass; kernel, running system, booted system, profile and source all matched the baseline |

The upgraded kernel reported no error-level kernel log messages. A PCI
device-tree warning was present on 6.18.59 before and after rollback. Existing
duplicate D-Bus service-name diagnostics were also observed; empty failed-unit
lists do not imply an entirely warning-free journal.

The rehearsal exposed a real deployment race before the kernel change: the
staging SSH login could end while system activation was reloading the user's
manager, producing a failed activation. Apply now holds a temporary PAM login
session under systemd through build, activation and recovery, and releases it
on success or failure. It does not enable persistent lingering or change sudo.
A deployment from an explicitly inactive user manager passed. An invalid
candidate was refused without changing the active system/profile/source and
its temporary login session was cleaned up. SDK diagnostics now use a separate
descriptor so controller error reporting is isolated from terminal handling.
The final repository build-only check, nine controller/media safety tests,
Bash syntax, changed-worker ShellCheck and whitespace checks passed.

Recovery documentation was corrected in two places discovered by the test:
rollback needs `--no-reexec` to avoid an absent legacy `nixpkgs/nixos` lookup,
and manual flake commands must resolve the managed source symlink first to
retain pure evaluation. The Make workflow already uses resolved release paths.

This test does not establish focused macOS/application clipboard acceptance
on the new kernel, audible playback, shared-folder I/O with the new kernel,
or multi-day reliability. Those are separate from the measured service,
graphics, native guest clipboard, container and boot-recovery checks above.

## Installation and desktop validation — 2026-10-31

An installation encountered a live-image DNS failure fetching Chrome after
access to the Nix cache succeeded. The installer now starts the available
resolver explicitly, checks cache/vendor DNS before partitioning and retries
only the mounted build/install stage up to three times. Recovery verified VM
identity, existing partition labels/types, configured account and authorized
key before continuing on the original filesystems. Installation completed
without repartitioning and passed account, SSH and apply verification. Bash
syntax, ShellCheck and the controller/media safety suite passed for the fix.

Graphical login, Kitty and the launcher passed. Desktop, clipboard, audio and
portal services were active with empty system/user failed-unit lists, an empty
Hyprland error report, fixed 2560×1600 output and native Wayland Kitty.
Installed application version checks passed. Docker's `hello-world` container
passed as the normal workstation user. The authentication agent and 1Password
background app were active, and guest/host clock agreement was within a
three-second measurement tolerance.

The explicit shared folder passed host-to-guest read/modify and guest-to-host
create/read checks; synthetic fixtures were removed afterward. Focused
Kitty-tab, macOS-to-Kitty and Kitty-to-macOS copying passed, including delayed
paste. Audible playback, end-to-end application/runtime workflows and
multi-day reliability remain acceptance work. Issue #1 remains open and the
Ubuntu implementation remains available.

## Screenshot-identified login warnings

The user's screenshot identifies two Hyprland startup warnings: the legacy
`.conf` format is deprecated and Hyprland was started without `start-hyprland`.
These are startup/deprecation warnings, not parser errors, so the earlier empty
`hyprctl configerrors` result did not establish a warning-free login.
The centre window is Hyprland's informational update dialog.

The readable session entry point now executes the installed `start-hyprland`
with `--path /run/wrappers/bin/Hyprland`, preserving the NixOS capability
wrapper and UWSM integration. The system and Home Manager configurations and
the local Chrome floating example were migrated to Lua. The exact pinned
0.56.2 parser accepts the complete installed configuration and the local
override. Full generic and installed-host builds and activation pass, with
no failed units and the explicit share still active. The user logged out and
back in and confirmed both warnings disappeared and the launcher shortcut
still works. Process inspection confirms `start-hyprland` supervises Hyprland
with `--watchdog-fd` and `/etc/xdg/hypr/hyprland.lua`. The temporary legacy
configuration files were removed after that successful login.

## Parallels 27.1.0 retest

After the host was upgraded to 27.1.0 (58756), the NixOS Tools package was
updated to the matching official vendor release using a fixed download hash.
The nixpkgs lock, Hyprland and other desktop packages were kept unchanged.
The guest system rebuild and full `nix flake check` passed. Host inspection
confirmed Tools 27.1.0-58756, and the existing graphical session remained active.
No software was installed on the Mac by this retest.

With the stock controller running in a temporary user service:

| Test | Result |
| --- | --- |
| Background macOS→Wayland protocol copies | 0/5 pass |
| Background Wayland→macOS protocol copies | 5/5 pass |
| Native selection intact after each guest copy | 5/5 pass |
| Both selections retained after 10 seconds | 2/2 pass |

Payloads contained distinct Unicode and multiline text, with bounded reads and
detached Wayland owners. These are protocol tests without host-window focus
control; they do not establish focused Kitty application behavior.

Stopping the temporary stock controller reproduced a new SIGSEGV in the
**27.1.0** `prlcp` binary, with the same `wl_map_insert_at` → `proxy_destroy` →
`wl_proxy_destroy` stack seen on 27.0.3. The vendor caller offset is now +0xd9b0.
The shutdown cleanup crash is therefore not fixed for this tested configuration.
It remains distinct from the clipboard ownership failures during normal use.

In a separate focused-window test, the user confirmed all three requested
directions worked reliably: Kitty→Kitty, macOS→Kitty and Kitty→macOS, including
delayed paste. This supports normal interactive copying despite the background
macOS→Wayland protocol result. The stock controller is enabled persistently
again, with a two-second retry for early display-startup failures. The user
subsequently confirmed suspend/resume and accepted longer uptime as an
assumption to proceed. Old measurements below refer
to 27.0.3 and describe the earlier disabled-bridge workaround.

The persistent configuration passed a full guest `nix flake check` and system
build, then activated successfully. The regular `prlcc.service` is enabled and
running with its stock clipboard and drag-and-drop helpers; the temporary test
service is inactive. System and user failed-unit lists are empty, and Hyprland
reports no configuration errors. Startup at a subsequent login is not yet
retested.

## Original 27.0.3 environment and results

- Apple Silicon, Parallels Desktop and guest Tools 27.0.3 (58680).
- ARM64, four virtual CPUs, 12 GiB RAM, 24 GiB expanding disk.
- Installer: official NixOS graphical 26.05.13050 ARM64 ISO.
- Installed package set: pinned nixos-unstable, revision
  `31ecbaca1bdefa45dffc409f0250bd8039ea0010` (26.11 development).
- Hyprland 0.56.2, Mesa 26.2.5, UWSM 0.27.1, Kitty 0.49.2.
- Native Wayland Kitty; monitor verified at 2560×1600, approximately 59.99 Hz,
  scale 1. Renderer reports virgl/OpenGL ES 3.0.

## Confirmed checks

| Check | Result |
| --- | --- |
| Full ARM64 `nix flake check` including system build | Pass |
| Installer/bootstrap Bash syntax and ShellCheck | Pass |
| Disk installation, EFI boot, graphical login, Kitty | Pass |
| SSH public-key login; password-required sudo | Pass |
| systemd-networkd, SSH, greetd, Parallels Tools | Active |
| PipeWire, WirePlumber, Hyprland and main portals | Active |
| Hyprland `configerrors` | Empty |
| System and user failed-unit lists after fixes | Empty (clipboard controller intentionally disabled) |
| Suspend/resume: graphical session and service health | Pass |

Audio service health is verified; audible playback has not been tested.
Dynamic resizing, shared folders and kernel/Tools upgrades have not been tested.

## Clipboard protocol tests

Tests use distinct plain-text markers, `wl-copy`/`wl-paste` in the running
Wayland session, and macOS `pbcopy`/`pbpaste`. They do not replace application
selection/copy/paste tests. Tests ran without controlling which host window was
focused; focused-window behavior must be tested separately.

Background `wl-copy` owners must redirect stdout and stderr to `/dev/null` when
launched over SSH, or they can hold the SSH channel open and invalidate timing.
Guest reads use `timeout -k 1 5`; host reads have a five-second deadline. Only
marker matches are reported, not unrelated clipboard contents.

| Test | Immediate | Delayed |
| --- | --- | --- |
| Native Wayland, before bridge startup | 3/3 pass | 3/3 pass (2 seconds) |
| Native Wayland, after suspend/resume, bridge running | 3/3 pass | 3/3 pass (3 seconds) |
| macOS → Wayland, corrected post-resume round trips | 0/3 pass | Not separately measured |
| Wayland → macOS, corrected post-resume round trips | 2/3 pass | 2/3 pass (3 seconds) |

Before suspend, a separate macOS→Wayland marker did transfer successfully after
starting the bridge. This shows the direction is available, but not reliable
across the repeated sequence. No clipboard ownership-retention claim is made
across suspension itself; tests were repeated after resume.

Parallels clipboard logs report missing compositor offers, skipped selections
when the bridge believes it owns the clipboard, and keyboard-leave events that
may invalidate selected offers. These are observations, not a proven root cause.

## Isolation and safe fallback

The user reports that copying between Kitty tabs became reliable with the stock
`prlcc` service and its `prlcp`/`prldnd` children stopped. This implicates the
bridge's interaction with the local clipboard; it does not identify a specific
vendor/compositor code defect.

A standalone temporary `prlcp` was tested with `WAYLAND_DISPLAY` unset,
`GDK_BACKEND=x11` and `XDG_SESSION_TYPE=x11`. Its log confirmed fallback to its
X11 platform. Neither direction passed any of three protocol round trips.
This experiment did not establish a viable XWayland workaround and was stopped.

The 27.0.3 prototype disabled the stock user controller across logins while keeping
the system Parallels Tools daemon enabled. This also disables automatic clipboard
sharing and the controller's drag-and-drop helper.

The new `make clipboard-to-vm` and `make clipboard-from-vm` targets transfer text
once over authenticated SSH using native `wl-copy`/`wl-paste` and macOS
`pbcopy`/`pbpaste`, without a persistent clipboard agent. Three exact round trips
passed with Unicode and trailing newlines, plus an independent guest→host marker
passed. These are limited functional checks, not automatic synchronization or
long-term application acceptance. See README for usage and prerequisites.

## Fixes made during validation

- UWSM rejected the execute-only NixOS Hyprland security wrapper as unreadable.
  A readable launcher script invokes that wrapper while preserving its intended
  permissions. Full build and UWSM dry-run validation pass.
- Stock `prlcc` started before the display environment was ready and exited with
  `cannot open display`. Restarting it after session startup launched its stock
  `prlcp`/`prldnd` helpers. A minimal startup retry was tested, but it cannot repair
  the clipboard ownership failures on 27.0.3. Startup retry is retained with the
  validated 27.1.0 controller.
- EFI partition permissions are restricted to root with fmask/dmask 0077.

No periodic clipboard restart policy or replacement synchronizer has been added.
The full application and longevity matrix remains required before cutover.

## Pending acceptance

- Focused Kitty→Kitty: the user confirmed reliability with the 27.1.0 bridge
  running. Repeat over longer uptime.
- Repeat focused Kitty→Kitty with immediate, delayed, `clear` and paste again
  after establishing whether the bridge influences the failure.
- Focused macOS↔Kitty passed the user test on 27.1.0; repeat with different
  markers over longer uptime.
- Suspend/resume on 27.1.0: user-confirmed pass. Several-hour clipboard
  longevity: accepted by the user as an assumption, not an observed test pass.
- Chrome→Kitty and Claude Desktop→Kitty: user-confirmed pass, including delayed
  paste. Application-specific suspend/resume tests have not been reported.
- The screenshot's two Hyprland startup warnings were fixed and confirmed gone
  by the user after a new login; the launcher shortcut still works.

Do not infer that moving from Ubuntu to NixOS fixes clipboard reliability from
these results. Do not deprecate the Ubuntu path or advance cutover acceptance.
