# NixOS VM automation

Run these commands from the repository on an Apple Silicon Mac with Parallels
Desktop Pro/Business, Python 3.9+, OpenSSH, `bsdtar`, `xorriso`, and macOS
`/usr/sbin/htpasswd` already available. The workflow checks/uses host tools; it
does not install host software or require host Nix. The matching SSH key must
be usable noninteractively, including through an unlocked SSH agent.

## Fresh installation

```bash
make nixos-images
make bootstrap-nixos VM_NAME="NixOS Workstation" \
  IMAGE="/path/to/nixos-aarch64-linux.iso"
```

Without `IMAGE`, the newest `*aarch64-linux.iso` under `DOWNLOADS_DIR` (default
`~/Downloads`) is proposed. `IMAGE_SHA256` optionally verifies the source image
against a previously verified digest. Use an upstream ISO, not generated private
installer media. If macOS denies the agent access to Downloads, copy the ISO to
an accessible workspace or `/tmp` from your own terminal and select that copy.

Review the VM name, image, user, hostname, sizing and sharing settings, then type
`create`. Enter and confirm the guest login/sudo password privately in your Mac
terminal. Installation then runs unattended: no graphical installer, live SSH
password, `ssh-copy-id` or guest password command is required.

The controller:

1. Refuses an existing VM with the selected name.
2. Builds a private EFI installer ISO from the upstream image, updating both
   the ISO and FAT EFI copies of GRUB's configuration.
3. Creates ARM64 EFI hardware with shared networking and the lean integration
   settings used by this project.
4. Boots an explicit `kernel-command-line.target` using systemd's existing
   command generator. The live script validates its unique boot token,
   Parallels virtualization and an unmounted, unpartitioned, signature-free
   `/dev/sda` before reusing the manual disk installer.
   It starts the live resolver when present and waits for both the Nix cache
   and Chrome vendor names to resolve before partitioning.
5. Writes selected identity, authorized public key and conditional sharing
   settings only into the installed source. It sets the password through
   `chpasswd -e` outside Nix, locks root, and powers off.
6. Detaches the ISO and boots the installed disk. It obtains the SSH host key
   through the selected VM's Parallels guest channel, then uses strict SSH
   checking and verifies the per-install marker and account lock/password state.
7. Runs the transactional apply workflow and full checks against the captured
   source, verifies services and password-required sudo, then deletes its
   credential-bearing ISO/payload copies.

Transient build/download failures get up to three `nixos-install` attempts on
the same mounted filesystems during unattended installation. Partitioning and
formatting happen once, outside that retry loop. A persistent failure retains
the original VM and private media for explicit recovery.

Finally, log into the graphical workstation with the chosen account/password.
Application sign-ins, browser extensions and protected 1Password integration
settings remain interactive. No private keys or authentication sessions are copied.

| Variable | Default / behavior |
| --- | --- |
| `VM_NAME` | `NixOS Workstation`; must be new for bootstrap |
| `CPUS`, `MEMORY_MB`, `DISK_GB` | 4, 12288, 24; expanding disk |
| `GUEST_USER`, `GUEST_HOSTNAME` | `developer`, normalized VM name |
| `SSH_PUBLIC_KEY` | First existing ed25519/ecdsa/RSA `.pub` under `~/.ssh` |
| `SSH_HOST` | Discover the selected VM's shared-network IPv4 address |
| `SSH_KNOWN_HOSTS_FILE` | Optional existing verified file; mismatch fails |
| `SSH_WAIT_TIMEOUT` | 2700 seconds per wait phase |
| `NIXOS_HOST` | `workstation-test`, currently the unattended host template |
| `LOCAL_FLAKE` | Optional non-secret private flake copied into the VM's local input |
| `ARTIFACTS_DIR` | Ignored `.artifacts/nixos`, outside the `nixos/` source tree |
| `NIXOS_SHARE` | `yes`: only existing `~/Parallels/Shared`; `no`: disable |

When sharing is enabled, the proposal explicitly includes read-write access and
the required guest FUSE `user_allow_other` policy. A missing host folder produces
a hint; it is never created. Broad home/disk sharing remains disabled.

For CI, `NIXOS_PASSWORD_HASH_FILE` accepts a separately supplied bcrypt hash in
a file with mode 0600 or stricter, outside all Nix source/local-input trees. Do
not pass a plaintext password in Make arguments or environment variables. The
workflow removes its copies after success, but does not delete the caller's file.

## Apply to an existing VM

```bash
make check-nixos VM_NAME="NixOS Workstation"   # full build, no switch
make apply-nixos VM_NAME="NixOS Workstation"
make nixos-status VM_NAME="NixOS Workstation"
```

Supply `GUEST_USER`/`SSH_PUBLIC_KEY` when they differ from the defaults. The
target must already be this project's ARM64 NixOS workstation with Parallels
Tools and key-based SSH. A stopped VM is started; Ubuntu targets are refused.
The existing Ubuntu `bootstrap` and `apply-playbook` targets remain unchanged.

The root worker uses Parallels' existing administration channel. It does not
add a passwordless-sudo rule. Builds and switches run in a persistent systemd
job, so closing the controller or restarting Tools does not kill the worker.
The job holds a temporary PAM login session while building, activating or
recovering, so its user's manager cannot shut down after the staging SSH
connection ends. The session is stopped on success or failure; persistent
user lingering and sudo policy are unchanged.
Status and logs live in `/var/lib/nixos-workstation/jobs/DEPLOYMENT_ID`.

Source is staged in a new private release under
`/var/lib/nixos-workstation/releases/`. Hardware configuration, installation
keys, identity and sharing files are excluded from the incoming archive and
preserved from the VM. Existing local input is also preserved unless
`LOCAL_FLAKE` explicitly supplies a replacement. Existing usernames cannot
be implicitly changed through apply.

Full flake checks include the system build and the installed Hyprland Lua
parser. Builds use the checked-in lock without implicit updates. After a
successful switch and service checks, `/etc/nixos/workstation` is promoted to
the new source snapshot. A pre-existing real directory is retained once as
`pre-managed-source-DEPLOYMENT_ID`; later source-link changes are atomic.
Login sessions are preserved; a changed launcher takes effect on next login.

An invalid candidate never replaces the active source. Activation failure
attempts to restore the previous system profile/generation and source pointer,
and reports recovery failures explicitly. Failed releases and logs remain for
diagnosis; old generations are not garbage-collected automatically.

## Private local configuration

```bash
cp -R nixos/examples/local nixos-local
# Edit the ignored, non-secret local module.
make apply-nixos VM_NAME="NixOS Workstation" LOCAL_FLAKE="$PWD/nixos-local"
```

This replaces the VM's `local` input with a captured copy of that flake. Later
applies preserve it without needing the flag again. To reset deliberately, use
`LOCAL_FLAKE="$PWD/nixos/local"` to select the committed empty default.
When replacing local source, its new dependencies are resolved explicitly;
review any resulting lock changes in the staged release. Keep runtime/toolchain
versions in mise and secrets in mutable home files, as described in README.

If adopting a previously manual `--override-input local ...` deployment, pass
that local flake explicitly on the first automated apply. An out-of-tree manual
override cannot be inferred from an unchanged default `flake.lock`.

## Failure and interruption recovery

Bootstrap retains the new VM and a private artifact directory on failure.
Its ISO/payload contain the password hash; do not commit, publish or share them.
Inspect `serial.log` or the VM console. Once recovery is complete, remove any
retained private media copies you no longer need.

After an interrupted controller, resume the same recorded VM:

```bash
make resume-nixos VM_NAME="NixOS Workstation" \
  NIXOS_RESUME_DIR="/absolute/path/to/.artifacts/nixos/install-ID"
```

Default resume waits for a still-running live installer or finishes boot/apply
for an already installed VM. It verifies the original VM ID and install marker;
it does not rerun partitioning by default. If an early installer failure left
the disk blank, stop that VM and explicitly request the guarded retry:

```bash
make resume-nixos VM_NAME="NixOS Workstation" \
  NIXOS_RESUME_DIR="/absolute/path/to/.artifacts/nixos/install-ID" \
  NIXOS_RETRY_BLANK=yes
```

The live disk guard still refuses existing partitions/signatures. Partially
formatted disks require an operator recovery decision; there is no force-wipe
or bootstrap-over-existing-VM option.

For an interrupted apply, use `nixos-status` before starting another apply.
Inspect the log through the guest console or the Parallels channel:

```bash
prlctl exec "NixOS Workstation" /run/current-system/sw/bin/tail -n 80 \
  /var/lib/nixos-workstation/jobs/DEPLOYMENT_ID/log
```

For manual runtime recovery, `sudo nixos-rebuild switch --rollback --no-reexec` selects the
previous generation, or select it in systemd-boot. This does not revert the managed
source, its local input or the repository; restore/fix those before applying again.
In particular, reverting repository files alone does not remove a preserved
private kernel override. Successful jobs retain
`previous-system` and `previous-source` references for operator-led recovery.
Use `sudo nixos-rebuild boot --rollback --no-reexec` to select the previous
generation for subsequent boots without changing the currently running kernel,
then reboot. `--no-reexec` is needed here because the flake-only installation
does not provide the legacy `nixpkgs/nixos` search-path entry that the command's
default self-rebuild step attempts to use.

For manual flake commands, resolve the managed source symlink as root first:

```bash
guest_source=$(sudo readlink -f /etc/nixos/workstation)
sudo nix flake check --no-update-lock-file "path:$guest_source"
```

Using the resolved directory keeps pure evaluation from following a copied
source symlink outside the Nix store. The Make targets already use resolved
release paths.

Update `flake.lock` deliberately from an ARM64 Linux checkout, review/copy back
the lock diff, run full checks, and then apply. No host Nix installation is needed:
an existing VM can hold a temporary generic source checkout for this operation.
After accepting a deployment, use `sudo nix-collect-garbage --delete-older-than 14d`
only when old rollback generations are no longer needed. Failed source releases
and job logs are separate from Nix garbage collection and should be removed
only after reviewing which source `/etc/nixos/workstation` still points to.

## Validation commands

```bash
python3 -m unittest discover -s tests -v
bash -n scripts/bootstrap-nixos.sh nixos/install.sh nixos/automation/*.sh
make check-nixos VM_NAME="NixOS Workstation"
```

ShellCheck can run inside the existing VM. The unattended implementation uses
the [systemd command generator](https://www.freedesktop.org/software/systemd/man/latest/systemd-run-generator.html).
`nixos-anywhere` was evaluated, but its
[controller Nix and SSH prerequisites](https://nix-community.github.io/nixos-anywhere/quickstart.html)
would add bootstrap dependencies here. The upstream ISO already provides the
installer and Linux runtime used by this workflow.
