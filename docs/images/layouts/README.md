# Layout screenshots

These are actual guest desktop captures taken on 1 November 2026 with
Omarchy VM Manager 0.9.3 (16). One disposable lean ARM64 guest was used for
all four presets with VM Manager's native display integration. Three captures
used `4960×2790` at Retina scale 2. The VS Code capture used `1920×1080` at
scale 1 after the guest window was brought to the foreground on the host.
Each installed Lua layout matched its tracked source when captured.

| Screenshot | Layout runbook |
| --- | --- |
| [Four terminals](four-terminals.webp) | [Four tiled Foot terminals](../../omarchy-layout-four-terminals.md) |
| [Terminal and browser](terminal-browser.webp) | [Terminal and browser](../../omarchy-layout-terminal-browser.md) |
| [VS Code and browser](vscode-browser.webp) | [VS Code and browser](../../omarchy-layout-vscode-browser.md) |
| [Claude, terminals and browser](claude-two-terminals-browser.webp) | [Claude, terminals and browser](../../omarchy-layout-claude-two-terminals-browser.md) |

For capture, the empty Foot windows were relaunched with the same app IDs and
placement rules, short terminal labels and a neutral Bash prompt that omits
the guest account and hostname. Notification banners were dismissed using
Omarchy's native shell API. In the Claude preset, the compositor's native
focus and stacking actions brought Chromium to the front to illustrate its
overlap. No application accounts were
signed in, and no window positions or sizes were changed for the screenshots.

The guest's installed `grim` captured the desktop over VM Manager's pinned
SSH connection. The full frames were resized to `1920×1080` and encoded as
WebP (quality 86), without cropping or adding overlays. Output files contain
no EXIF, XMP or ICC metadata. [The manifest](manifest.json) records source and
output hashes, dimensions, display scale and the corresponding layout source hash.

Raw PNGs, window-state JSON, geometry checks and the disposable-guest test
results remain in the ignored
`.artifacts/layout-validation/20261101-four-terminals/` directory.
See the [live layout validation record](../../omarchy-layouts.md#four-terminal-validation--1-november-2026)
for the four-terminal test's scope and results.
