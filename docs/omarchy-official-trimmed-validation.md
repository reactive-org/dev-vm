# Official-image lean validation — 1 November 2026

Validated the opt-in profile on the existing managed aarch64 workstation using
Omarchy VM Manager 0.6.1 and `try-omarchy` 0.1.0-40. The normal Omarchy
update/snapshot path ran first. Its settings-package upgrade revoked the
temporary sudo grant; the operator renewed it, and application resumed without
repeating the update. The grant was revoked before the manager-owned reboot.

- Installed packages fell from 883 to 805: 78 removals, with no new system
  packages. The removed versions account for 1,330.44 MiB (about 1.30 GiB) of
  installed files, calculated from repository metadata matched to their exact
  pre-removal versions. Retained snapshots and caches mean this is not a claim
  about reclaimed host disk space.
- All installed removal candidates were removed except `superwhisper-bin`.
  Its native recursive transaction would also remove protected
  `pipewire-audio` and `pipewire-pulse`, so it was retained.
- Hardware-backed VirGL, Foot configuration, native display state, pinned SSH,
  clipboard channel, host-owned idle policy and lock masking passed after reboot
  and again after a graceful shutdown/relaunch. Package database checks found
  no errors; system and user managers reported no failed units.
- Clipboard text transfer in both directions was confirmed manually by the
  operator after relaunch. Automated transfer probes failed even though the
  native clipboard service was active; no automated end-to-end clipboard pass
  is claimed. The manager routes clipboard traffic only to the focused guest.
- Functional checks passed for C compilation/execution, Python standard
  libraries, Git commit/read, Neovim edit/write, tmux sessions and mise.
  Chromium rendered a local HTTP page using an isolated temporary profile.
  Docker ran an ARM64 `hello-world` container after removal, before reboot.
  Docker/Compose/Buildx commands and native Docker socket activation passed
  after reboot; ordinary Docker use still requires Omarchy's normal sudo policy.
- Reapplying the lean helper without a sudo grant left the installed package
  set unchanged. Existing Claude Desktop and 1Password CLI packages were
  retained; no additional lazy mise toolchains were installed for these checks.

Live testing found that pacman rejects combining `--nosave` with `--print`.
The profile now previews with `-Rs --print`, while Omarchy's actual removal
continues to use `-Rns`. Unexpected preview errors stop application instead of
being mistaken for dependency-protected packages. The focused suite passes all
82 tests, including this regression; documented shell/Python syntax checks pass.
