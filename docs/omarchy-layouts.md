# Choose an application layout

No application layout is installed by default. The tracked example
`omarchy/examples/layouts/claude-two-terminals-browser.lua` describes Claude
Desktop on the right, two Foot terminals stacked on the left, and a floating
Chromium window. The `omarchy/examples/layouts/terminal-browser.lua` example
places one Foot terminal on the left (40%) and Chromium on the right (60%).
The `omarchy/examples/layouts/vscode-browser.lua` example places VS Code on
the left (60%) and Chromium on the right (40%).
Install the desired applications before selecting a layout.

Choose the official Try image or a BYO custom image path in the same
bootstrap runbook: [terminal and browser](omarchy-layout-terminal-browser.md),
[VS Code and browser](omarchy-layout-vscode-browser.md), or
[Claude, two terminals and browser](omarchy-layout-claude-two-terminals-browser.md).
Bootstrap installs their apps and applies the layout in the selected VM.
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
