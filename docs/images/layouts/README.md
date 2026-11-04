# Layout screenshots

The four single-workspace images are actual guest desktop captures taken on 1 November 2026 with
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

## Three-workspace captures — 5 November 2026

These three images show `claude-browser-code-terminals.lua` running in one new
disposable lean ARM64 guest with Omarchy VM Manager **0.11.0 (27)**. Each frame
was captured with the guest's native `grim`, over pinned managed SSH, after
switching to and checking the requested workspace through Hyprland's Lua API.

| Screenshot | Workspace |
| --- | --- |
| [Claude Desktop and Chromium](claude-browser-code-terminals-workspace-1.webp) | 1 |
| [VS Code](claude-browser-code-terminals-workspace-2.webp) | 2 |
| [Four Foot terminals](claude-browser-code-terminals-workspace-3.webp) | 3 |

The native display was `2080×1170` at scale 1. Before capture, the four empty
Foot windows were relaunched with their original app IDs and neutral labeled
Bash prompts. Native notification banners and VS Code's first-run sign-in
overlay were dismissed. No application accounts were signed in and no window
positions or sizes were changed. Layout-source hashes, all seven window
placements, workspace counts, rendering and service health passed before
capture preparation and again afterward.

The complete frames were resized to `1920×1080` with the existing `cwebp` tool
and encoded at quality 86, method 6, without cropping or overlays. All three
WebP outputs decoded successfully and contain no EXIF, XMP or ICC metadata;
they total 93,264 bytes. The separate
[manifest](claude-browser-code-terminals-manifest.json) records raw/output
hashes, dimensions, display scale and the corresponding layout source hash.
The original 1 November manifest remains specific to its four captures.

Raw PNGs and private validation evidence are under ignored
`.artifacts/layout-validation/20261105-claude-code/`. See the
[live validation record](../../omarchy-layouts.md#claude-browser-code-and-terminals-validation--5-november-2026)
and the [layout runbook](../../omarchy-layout-claude-browser-code-terminals.md).
