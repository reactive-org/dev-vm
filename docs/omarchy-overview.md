# Scope and factory choices

This repository implements the
[Reactive developer VM](https://www.reactive.org/dev-vm) as a small, explicit
preference layer over
[**Omarchy VM Manager**](https://github.com/reactive-org/omarchy-vm-manager)
on Apple Silicon. The manager owns the ARM64 VM, factory image, storage, GPU
and Retina integration, display scaling, clipboard, networking, managed SSH,
persistence, and Mac app lifecycle. Omarchy owns Arch, Hyprland, applications,
Docker, mise, language runtimes, and guest updates.

For the default managed workflow, this repository applies workstation preferences: a readable Foot font,
host-owned idle/locking policy, an optional theme, an optional per-workstation
app layout, and an opt-in lean developer application selection.
It does not install host software or replace either project's update path.

The repository targets Omarchy ARM64 through VM Manager. Use either the official
Try Omarchy factory or an admitted compatible custom factory, then apply selected
features. The repository's opt-in lean factory is one BYO option.
Host tool installation remains a separate operator action.

## Minimal factory image build

Build an opt-in desktop-foundation factory from the pinned Try Omarchy builder:

```bash
make build-omarchy-image OMARCHY_IMAGE_PLAN=yes
make check-omarchy-image
make build-omarchy-image
```

The preview checks local source inputs without Docker or downloads. The check
target builds guest packages, exercises the optional-provisioning guards and
resolves their dependencies without creating a disk. The build target creates
a sealed ARM64 UEFI/Btrfs factory under `.artifacts/omarchy-image/`. Both require
an existing ARM64 Docker engine; neither installs host tools, operates a VM,
changes VM Manager, or replaces its factory/cache.

The foundation includes the Omarchy desktop, native Mac integration, Foot,
Git, Python, graphics, audio, input methods and recovery tools. Browser,
Docker, language runtimes, coding agents and credential apps are excluded,
including when pulled in transitively. The [feature playbooks](omarchy-features.md) support both
images. VM Manager owns custom-factory admission and selection; the image builder
does not replace its official cache or existing disks.

See the [image build contract and validation limits](omarchy-image.md)
before importing an artifact. A successful build proves static policy and
system setup; hardware rendering and owner setup require a disposable-VM test.
The [live acceptance record](omarchy-playbook-validation.md) distinguishes
official and lean image results and their remaining validation limits.
