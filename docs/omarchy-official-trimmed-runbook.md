# Trim optional desktop apps

Keep development tools and remove optional office, entertainment and hardware
utilities. The lean, mean coding image may already have nothing to remove.

Open VM Manager on your Apple Silicon Mac and save **Guest Defaults**. Run
one of these commands from the repository root with an unused VM name.

**Official Try Omarchy:** Get running quickly with Omarchy’s standard apps already installed and no image build required.

```bash
make bootstrap-omarchy-vm VM_NAME="Dev Omarchy Trimmed" \
  OMARCHY_VM_FACTORY=official \
  OMARCHY_VM_LEAN_DEVELOPER=yes
```

**Lean, mean coding image:** Start with a smaller, reusable base and add only the apps and developer tools you need.

[Build your lean, mean coding image](omarchy-layout-factory.md), then use its
path below. Bootstrap handles preparation and import.

```bash
make bootstrap-omarchy-vm VM_NAME="Dev Omarchy Trimmed" \
  OMARCHY_VM_FACTORY=.artifacts/omarchy-image/latest \
  OMARCHY_VM_LEAN_DEVELOPER=yes
```

Review the proposed removals and password prompt. Setup updates, trims and
configures the guest, then restarts and checks it.

Optional check later, using the same VM name:

```bash
make check-omarchy-vm VM_NAME="Dev Omarchy Trimmed"
```

[Prerequisites and settings](omarchy-bootstrap.md) · [Checks and recovery](omarchy-validation.md)
