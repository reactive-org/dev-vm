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
