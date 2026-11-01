# Validate and recover a workstation

After the first graphical login, re-run the non-persistent host-side validation
without installing diagnostic packages:

```bash
make check-omarchy-vm VM_NAME="Dev Omarchy"
```

The check requires `aarch64`, rejects `llvmpipe` and `softpipe`, verifies the
Foot configuration and manager-provided clipboard channel, reports the current
Hyprland display and scale, and confirms the explicit idle preferences. Also test one host-to-guest
paste, one guest-to-host paste, a normal restart, and window movement between
the two host displays before accepting the migration.

## Hyprland 0.57 black desktop after updating

Try Omarchy issue [#429](https://github.com/omacom/try-omarchy/issues/429)
tracks a current regression where an Omarchy update leaves the launcher and
tooltips visible but turns the desktop black and hides opened windows. Do not
force `llvmpipe`: that disables required hardware rendering. Bootstrap applies
the conditional repair only when the installed Hyprland/Try Omarchy combination
needs it. For manual guest-side recovery:

```bash
make repair-omarchy-vm-black-screen
sudo reboot
```

The repair backs up both changed user configuration files under
`~/.local/state/dev-workstation/try-omarchy-black-screen/`, is safe to reapply,
and requires a full Hyprland restart rather than only `hyprctl reload`.
