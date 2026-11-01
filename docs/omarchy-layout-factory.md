# Build your lean, mean coding image

Start with a smaller, reusable base and add only the apps and developer tools you need.

Use an existing ARM64 Docker engine and the matching VM Manager checkout's
prepared runtime source. From the repository root:

```bash
make build-omarchy-image
make bootstrap-omarchy-vm VM_NAME="Dev Omarchy" \
  OMARCHY_VM_FACTORY=.artifacts/omarchy-image/latest
```

The build contains the shared Omarchy desktop, Foot, native Mac integration and
required system/recovery tools. Optional apps and layouts are added by bootstrap.
The `latest` shortcut points to the last successful full build; previews, failed
builds and package-only checks do not change it.

Bootstrap verifies/prepares a private copy, shows the proposal, imports through
VM Manager after confirmation, then creates and configures the VM. No manifest
hash needs copying. You can also pass a specific build directory, its `.img.zst`
file with companion metadata, or a prepared factory bundle.

Choose [terminal and browser](omarchy-layout-terminal-browser.md),
[VS Code and browser](omarchy-layout-vscode-browser.md), or
[Claude and terminals](omarchy-layout-claude-two-terminals-browser.md) for app/layout
options.

**Official Try Omarchy:** Get running quickly with Omarchy’s standard apps already installed and no image build required.
Skip building and use `OMARCHY_VM_FACTORY=official`.

[Build/import details](omarchy-layout-factory-reference.md) · [Image contract](omarchy-image.md)
