# Choose an application layout

No application layout is installed by default. The tracked example
`omarchy/examples/layouts/claude-two-terminals-browser.lua` describes Claude
Desktop on the right, two Foot terminals stacked on the left, and a floating
Chromium window. The `omarchy/examples/layouts/terminal-browser.lua` example
places one Foot terminal on the left (40%) and Chromium on the right (60%).
The `omarchy/examples/layouts/vscode-browser.lua` example places VS Code on
the left (60%) and Chromium on the right (40%).
The `omarchy/examples/layouts/four-terminals.lua` example arranges four Foot
windows in an equal 2×2 grid on workspace 1, using a dedicated app ID for each
corner and the same floating placement rules as the other presets.
The `omarchy/examples/layouts/multi-workspace.lua` example spans three
workspaces: VS Code and Chromium on 1, four terminals on 2, and Claude with
two terminals on 3. Each terminal uses a dedicated app ID, and each window
rule assigns its destination workspace without switching the current view.
The `omarchy/examples/layouts/claude-browser-code-terminals.lua` alternative
places Claude Desktop and Chromium on workspace 1, VS Code alone on 2,
and four terminals in a 2×2 grid on 3.
For a smaller single display, `omarchy/examples/layouts/small-screen.lua`
gives Claude Desktop workspace 1, Chromium workspace 2 and VS Code workspace 3,
each filling the usable area. Two equal-width, full-height terminals share
workspace 4.
Install the desired applications before selecting a layout.

Choose the official Try image or a BYO custom image path in the same
bootstrap runbook: [four terminals](omarchy-layout-four-terminals.md),
[terminal and browser](omarchy-layout-terminal-browser.md),
[VS Code and browser](omarchy-layout-vscode-browser.md),
[Claude, two terminals and browser](omarchy-layout-claude-two-terminals-browser.md),
the [multi-workspace workstation](omarchy-layout-multi-workspace.md),
[Claude and browser, VS Code, and four terminals](omarchy-layout-claude-browser-code-terminals.md),
or the [small-screen workstation](omarchy-layout-small-screen.md).
Bootstrap installs their apps and applies the layout in the selected VM.
All seven layout runbooks include actual guest screenshots; see the
[capture notes](images/layouts/README.md) for preparation and provenance.
For your own base image, [build your lean, mean coding image](omarchy-layout-factory.md).
That optional image build contains no selected apps or app layout.

Copy the example into the ignored `omarchy/local/` directory for a
workstation-specific variant. Omit `OMARCHY_VM_LAYOUT_FILE` to preserve the
current choice, or pass `OMARCHY_VM_LAYOUT_FILE=off` to remove the managed
layout. Layout changes take effect on the next Hyprland login.
The playbook equivalents are `omarchy_layout_file` and `omarchy_remove_layout`
in the explicitly selected feature variables file.

## Lean layout validation — 1 November 2026

The two layouts below passed live testing in separate new disposable ARM64
guests with VM Manager 0.9.3 (16), 8 CPUs, 20 GiB RAM and 64 GiB disks.
The factory's complete checksum inventory passed before testing. The image
was the same rebuilt developer foundation recorded in the
[image validation](omarchy-image.md#live-developer-bootstrap--1-november-2026).

| Layout | Observed result |
| --- | --- |
| Terminal and browser | One Foot window at `(12,38)`, size `974×1345`; Chromium at `(998,38)`, size `1470×1345`: the expected 40/60 split. |
| Claude, terminals and browser | Claude at `(998,38)`, size `1470×1345`; Foot windows at `(12,38)` / `(12,704)`, sizes `974×667` / `974×666`; Chromium at `(670,251)`, size `1140×865`: the expected base split, stacked terminals and overlapping browser. |

All layout windows were floating on workspace 1. Geometry matched the native
`4960×2790` display at scale 2 within two logical pixels. Window classes matched
the tracked rules, including `com.anthropic.Claude` and the dedicated Foot IDs.
Stacking follows ordinary focus changes; startup does not force Chromium above
Claude. No focus override or window-event callback is installed.

The resumed native bootstrap commands exited successfully after update,
installation, customization and restart. Omarchy's settings upgrades revoked
the first temporary sudo grants; the operator reauthorized each guest natively
before installation. AUR updates passed without the earlier missing-`yay`
failure. Both guests retained `tokyo-night`, reported accelerated
`virgl (Apple M5 Max)`, passed Foot/idle/clipboard-channel checks, and had zero
failed system/user units and inactive sudo grants. Non-root C compile/link/run
checks passed. Installed applications were Foot `1.28.0-2`, Chromium
`156.0.8078.79-1` and, in the Claude case, Claude Desktop `4.4212.0-1`.
Claude opened at its welcome screen; no account sign-in was performed.

Path-based preparation stopped before VM creation because the sibling manager
checkout's runtime lock had moved from the image's integration source
`1ecd8499d271cd761e8b4be0e49747de96e57768` to
`80156396a5daa795487c0f4a8308eee53f6ea68b`. These layout tests used the manager's
already verified manifest selector
`89e75163dc5447fd8c2d31f571316fbce7573bc83eaeee74c62bfed816c83103` for the same
disk. Native admission checks stayed enabled; the sibling checkout and its
preparation guard were unchanged. The manager also deferred the second first
cold start until the first guest was ready; retry used the same new profile.

Evidence and screenshots are under the ignored
`.artifacts/runbook-validation/20261101-931e79/` directory. Both disposable guests
were stopped and retained; the three pre-existing guests matched their baseline.
The final repository suite passed 134 tests, with the documented shell/Python
syntax checks and `git diff --check`. Official-factory variants and the Standard
and Trim runbooks were outside this test's selected scope.

## Four-terminal validation — 1 November 2026

The four-terminal preset passed live testing in one new disposable ARM64
guest with VM Manager 0.9.3 (16), 8 CPUs, 20 GiB RAM and a 64 GiB disk.
The current lean factory's complete published checksum inventory passed
before creation. Native factory admission, unattended owner setup and pinned
SSH remained enabled. The selected factory had disk SHA-256
`7816326733d14d5367df810c684d1c540794240ff39d1086439a1c319c443494`
and imported manifest SHA-256
`6b49ae727ec1865e15c90bc990bb13d46b2747012d7ac5f4ceb93b2fe245e5bf`.

The repository controller applied the exact tracked preset and restarted the
guest. Reapplying it and restarting again produced exactly four Foot windows,
each floating on workspace 1 with its dedicated app ID. The installed layout
hash matched the source after both applications. On the native `4960×2790`
display at scale 2, the observed logical geometry was:

| Terminal | Position | Size |
| --- | --- | --- |
| Top left | `(12,38)` | `1222×667` |
| Top right | `(1246,38)` | `1222×667` |
| Bottom left | `(12,717)` | `1222×666` |
| Bottom right | `(1246,717)` | `1222×666` |

This gives 12-pixel inner gaps, 12-pixel side/bottom margins and clearance
for the native panel. The one-pixel height difference is compositor rounding.
Both restart checks passed accelerated `virgl (Apple M5 Max)`, preserved the
default theme, reported no Hyprland configuration errors or failed system/user
units, and had no active temporary sudo grant. Foot configuration, host idle
preferences, clipboard-channel presence and a non-root C compile/link/run
check also passed.

This validation covered layout selection, reapplication and restart on the
lean factory's installed packages. Full update/bootstrap, the official-factory
variant, functional clipboard routing and moving between host displays remain
separate checks. Factory build manifests were left unchanged.

Raw checks, window geometry and screenshots are in the ignored
`.artifacts/layout-validation/20261101-four-terminals/` directory.
All four layout runbooks include screenshots captured from this same guest.
After the four-terminal test, Chromium `156.0.8078.79-1`, VS Code `1.144.0-1`
and Claude Desktop `4.4212.0-1` were installed through Omarchy's native commands
using an operator-authorized temporary sudo grant, which was revoked after
installation. Each preset's installed source hash, window classes and geometry
were verified before capture. No application account was signed in.
The four prepared WebP files total 130,266 bytes; their hashes, dimensions and
display scales are recorded in the [capture notes and manifest](images/layouts/README.md).

The manager refused an initial attempt to reopen an older disposable
terminal/browser guest because its factory record belongs to a different
runtime. Its native `factory-verification-failed` status remains visible and
it is inactive; its disk was not changed. All captures continued in the new
guest with factory admission checks intact. A concurrent guest's first boot
also temporarily deferred one restart; work resumed after native SSH readiness.

The new guest was restored to the four-terminal preset, passed final geometry,
renderer and workstation checks, and was gracefully stopped and retained.
All five pre-existing VM disk trees matched their complete file-stat baseline.
Repository verification passed 160 tests, the documented Bash/Python checks,
Ansible syntax, screenshot decoding/metadata checks and documentation links.

## Claude, browser, code and terminals validation — 5 November 2026

The `claude-browser-code-terminals.lua` preset passed live validation in one
new disposable lean `aarch64` guest using installed VM Manager **0.11.0 (27)**,
8 CPUs, 20 GiB RAM and a 64 GiB disk. All 24 published factory checksums passed
before creation. The admitted lean factory manifest was
`dd76d38cab9343cbd68989cfef5f45a53d3bb2352a53ed05929e06859f4c9dcc`.
Native Guest Defaults, owner setup and pinned managed SSH were used; shared
folders, personal-key inheritance and guest Touch ID were disabled for this guest.

Omarchy's native update and app installation ran through the repository controller
helpers, followed by preference/layout application, native setup-sudo revocation
and a manager-owned restart. The installed layout matched the tracked source
hash before and after screenshot preparation. No layout source changes were needed.

All seven windows were floating, with exactly two windows on workspace 1,
one on workspace 2 and four on workspace 3. Measured logical-pixel geometry at
native `2080×1170`, scale 1, matched the preset exactly:

| Workspace | Window | Position | Size |
| --- | --- | --- | --- |
| 1 | Claude Desktop | `(12,38)` | `1230×1120` |
| 1 | Chromium | `(1254,38)` | `814×1120` |
| 2 | VS Code | `(12,38)` | `2056×1120` |
| 3 | Top-left Foot | `(12,38)` | `1022×554` |
| 3 | Top-right Foot | `(1046,38)` | `1022×554` |
| 3 | Bottom-left Foot | `(12,604)` | `1022×554` |
| 3 | Bottom-right Foot | `(1046,604)` | `1022×554` |

Workspace switching through Hyprland's native Lua dispatch API was checked
before each capture. The guest reported `Accelerated: yes` and
`virgl (Apple M5 Max)`, with no software-rendering overrides in the desktop
processes, no Hyprland configuration errors and zero failed system/user units.
Foot configuration, the native clipboard channel and host-owned idle/locking
preferences passed the repository workstation check. The boot ID changed after
restart; the native sudo grant was inactive and noninteractive sudo required
authentication again.

Installed app versions were Foot `1.28.0-2`, Chromium `156.0.8078.79-1`,
VS Code `1.145.0-1` and Claude Desktop `4.16336.0-1`; Omarchy was
`4.0.0.r7594.g84b3f28-1`. Claude remained at its welcome screen, Chromium at
a new tab and VS Code at Welcome. No application accounts were signed in.

The [runbook](omarchy-layout-claude-browser-code-terminals.md) includes one
actual screenshot per workspace. Before capture, empty Foot windows were
relaunched with their original app IDs and neutral labeled Bash prompts;
native notification banners and VS Code's first-run sign-in overlay were
dismissed. No window geometry was adjusted. The complete geometry, renderer,
service-health and sudo checks passed again after preparation.

All 36 live assertions passed. Repository validation also passed: 239 tests ran
(238 passed, one host-Lua availability skip), with the documented Bash/Python
syntax checks, `git diff --check`, screenshot decoding/metadata checks, capture
hashes and documentation links verified.

Private inventories, logs, JSON checks, geometry and raw PNGs are retained in
ignored `.artifacts/layout-validation/20261105-claude-code/`. Public capture
hashes and provenance are in the [screenshot manifest](images/layouts/claude-browser-code-terminals-manifest.json).
The disposable guest was gracefully stopped and retained. All three existing
guests retained their inventory settings, stopped state and complete disk-tree
file-stat baselines; exactly one new guest was created.

This validates the lean factory at the observed display size. The official
factory, Retina/dynamic-resolution transitions and functional clipboard paste
were not exercised in this run.

## Original multi-workspace validation — 5 November 2026

The `multi-workspace.lua` preset passed live validation in a separate new
disposable lean `aarch64` guest with installed VM Manager **0.11.0 (27)**,
8 CPUs, 20 GiB RAM and a 64 GiB disk. All 24 published factory checksums passed
before creation. The admitted factory manifest was
`dd76d38cab9343cbd68989cfef5f45a53d3bb2352a53ed05929e06859f4c9dcc`.
Native Guest Defaults, owner setup and pinned managed SSH were used, with
shared folders, personal-key inheritance and guest Touch ID disabled.

The repository controller helpers ran Omarchy's native update, installed the
three apps, applied preferences and the exact preset, revoked setup sudo and
restarted the guest through VM Manager. A transient SSH `connecting` state
was resolved with the manager's native readiness wait on the same guest and
pinned connection.

The first live run passed 46 of 47 assertions and found a one-logical-pixel
overlap between the two workspace 3 terminals. Their size and upper position
were correct, but the lower terminal's vertical offset was `monitor_h*0.50+6`.
Changing only that offset to `monitor_h*0.50+19` restored the intended 12-pixel
gap. The corrected source was reapplied through the controller without a new
sudo grant, and the guest was restarted again before validation and capture.

All 47 assertions then passed. Exactly nine floating windows were present,
with workspace counts of two, four and three; no windows overlapped. At native
`2080×1170`, scale 1, all measured logical-pixel geometry matched exactly:

| Workspace | Window | Position | Size |
| --- | --- | --- | --- |
| 1 | VS Code | `(12,38)` | `1230×1120` |
| 1 | Chromium | `(1254,38)` | `814×1120` |
| 2 | Top-left Foot | `(12,38)` | `1022×554` |
| 2 | Top-right Foot | `(1046,38)` | `1022×554` |
| 2 | Bottom-left Foot | `(12,604)` | `1022×554` |
| 2 | Bottom-right Foot | `(1046,604)` | `1022×554` |
| 3 | Claude Desktop | `(838,38)` | `1230×1120` |
| 3 | Top Foot | `(12,38)` | `814×554` |
| 3 | Bottom Foot | `(12,604)` | `814×554` |

Hardware rendering reported `Accelerated: yes` and `virgl (Apple M5 Max)`.
Hyprland and Quickshell were running without software-rendering overrides;
there were no Hyprland configuration errors or failed system/user units.
The repository workstation check passed, including Foot configuration,
the native clipboard channel and host-owned idle/locking preferences.
The boot ID changed after restart, the native sudo grant was inactive and
noninteractive sudo required authentication again.

Installed app versions were Foot `1.28.0-2`, Chromium `156.0.8078.79-1`,
VS Code `1.145.0-1` and Claude Desktop `4.16336.0-1`; Omarchy was
`4.0.0.r7594.g84b3f28-1`. No application accounts were signed in.

The [runbook](omarchy-layout-multi-workspace.md) includes one actual screenshot
per workspace. The six empty Foot windows were relaunched with their original
app IDs and neutral labeled Bash prompts, and native notifications and VS Code's
first-run sign-in overlay were dismissed. The corrected layout-source hash and
all 47 live checks passed again after this preparation. Workspace switching was
confirmed through the native Hyprland Lua API before each `grim` capture.
No window geometry was adjusted for screenshots.

Repository validation passed: 239 tests ran (238 passed, one host-Lua availability
skip), along with the documented Bash/Python syntax checks, `git diff --check`,
screenshot decoding/metadata checks, source/output hashes and documentation links.

Private inventories, logs, initial overlap evidence, corrected geometry,
checks and raw PNGs are retained in ignored
`.artifacts/layout-validation/20261105-multi-workspace/`. Public capture hashes
and provenance are in the [screenshot manifest](images/layouts/multi-workspace-manifest.json).
The disposable guest was gracefully stopped and retained. All four existing
guests retained their inventory settings, stopped state and complete disk-tree
file-stat baselines; exactly one new guest was created.

This validates the corrected lean-factory preset at the observed display size.
The official factory, Retina/dynamic-resolution transitions and functional
clipboard paste were not exercised in this run.

## Small-screen validation — 5 November 2026

The `small-screen.lua` preset passed live validation in a new disposable lean
`aarch64` guest with installed VM Manager **0.11.0 (27)**, 8 CPUs, 20 GiB RAM
and a 64 GiB disk. All 24 published factory checksums passed before creation.
The admitted lean factory manifest was
`dd76d38cab9343cbd68989cfef5f45a53d3bb2352a53ed05929e06859f4c9dcc`.
Native Guest Defaults, owner setup and pinned managed SSH were used; shared
folders, personal-key inheritance and guest Touch ID were disabled.

Omarchy's native update and app installation ran through the repository
controller helpers, followed by preference/layout application, native sudo
revocation and a manager-owned VM restart. The operator then resized the
native guest window to a laptop-sized viewport. VM Manager's native display
integration reported **1794×1089 logical pixels**, from **3588×2178 backing
pixels at scale 2**. No guest monitor rule or host display controller was added.
The test uses this measured viewport, rather than claiming a specific MacBook
Pro model's factory resolution.

The resize exposed a limit of the floating preset: already-open windows kept
their original `2080×1170`, scale-1 geometry. The five fresh app windows were
closed and reopened with their original classes/app IDs so the saved rules
could apply at the smaller logical size. No window positions or sizes were
manually adjusted, and no layout source change was needed. VS Code was reopened
through native `uwsm-app` after a short-lived fixture service terminated its
first relaunch. The successful test validates newly opened windows at the
measured viewport; it does not establish automatic refitting after display
changes or a cold VM boot directly into that exact window size.

All 43 assertions passed before and after capture preparation. Exactly five
floating windows were present, with workspace counts of one, one, one and two.
Every window stayed inside the usable display area, with no overlap or clipping,
and logical-pixel geometry matched the preset exactly:

| Workspace | Window | Position | Size |
| --- | --- | --- | --- |
| 1 | Claude Desktop | `(12,38)` | `1770×1039` |
| 2 | Chromium | `(12,38)` | `1770×1039` |
| 3 | VS Code | `(12,38)` | `1770×1039` |
| 4 | Left Foot | `(12,38)` | `879×1039` |
| 4 | Right Foot | `(903,38)` | `879×1039` |

The terminal gap and outer gaps were 12 logical pixels; the top clearance
preserved Omarchy's panel. Hyprland and Quickshell ran without software-rendering
overrides. GLX reported `Accelerated: yes` and `virgl (Apple M5 Max)`; there
were no Hyprland configuration errors or failed system/user units. Foot
configuration, the native clipboard channel and host-owned idle/locking
preferences passed. The boot ID changed after the manager restart, the native
sudo grant was inactive and noninteractive sudo required authentication again.

Installed app versions were Foot `1.28.0-2`, Chromium `156.0.8078.79-1`,
VS Code `1.145.0-1` and Claude Desktop `4.16336.0-1`; Omarchy was
`4.0.0.r7594.g84b3f28-1`. No application accounts were signed in.

The [runbook](omarchy-layout-small-screen.md) contains one actual screenshot per
workspace. For capture, the two empty Foot windows were relaunched with the
same app IDs and neutral labeled Bash prompts. Native notification banners and
VS Code's first-run sign-in overlay were dismissed. Source hashes, geometry,
rendering, service health and sudo cleanup were checked again. Each workspace
was selected and confirmed through the native Hyprland Lua API before `grim`
captured the complete frame over pinned managed SSH.

Repository validation passed: 239 tests ran (238 passed, one host-Lua availability
skip), with the documented Bash/Python syntax checks, `git diff --check`, image
decoding/metadata checks, source/output hashes and documentation links verified.

Private inventories, logs, initial resize failures, app relaunch evidence,
geometry, checks and raw PNGs are retained in ignored
`.artifacts/layout-validation/20261105-small-screen/`. Public capture hashes
and provenance are in the [screenshot manifest](images/layouts/small-screen-manifest.json).
The disposable guest was gracefully stopped and retained. All five existing
managed guests retained their inventory settings, stopped state and complete
disk-tree file-stat baselines; exactly one new guest was created.

The official factory, functional clipboard paste, physical MacBook hardware and
automatic resizing of already-open floating app windows remain outside the
passing scope of this run.
