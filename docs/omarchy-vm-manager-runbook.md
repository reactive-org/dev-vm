# Standard Omarchy workstation

Keep your chosen image's installed apps and apply the workstation preferences.

Open VM Manager on your Apple Silicon Mac and save **Guest Defaults**. Run
one of these commands from the repository root with an unused VM name.

**Official Try Omarchy:** Get running quickly with Omarchy’s standard apps already installed and no image build required.

```bash
make bootstrap-omarchy-vm VM_NAME="Dev Omarchy" \
  OMARCHY_VM_FACTORY=official
```

**Lean, mean coding image:** Start with a smaller, reusable base and add only the apps and developer tools you need.

[Build your lean, mean coding image](omarchy-layout-factory.md), then use its
path below. Bootstrap handles preparation and import.

```bash
make bootstrap-omarchy-vm VM_NAME="Dev Omarchy" \
  OMARCHY_VM_FACTORY=.artifacts/omarchy-image/latest
```

Setup updates the guest, applies preferences, restarts and checks rendering
and managed SSH. Open the desktop in VM Manager and start working.

Review the proposal and follow the guest-password prompt.

Optional check later, using the same VM name:

```bash
make check-omarchy-vm VM_NAME="Dev Omarchy"
```

[Prerequisites and settings](omarchy-bootstrap.md) · [Checks and recovery](omarchy-validation.md)
