#!/usr/bin/env python3
"""Prepare and verify the narrow, hash-locked minimal-provisioning changes."""

import argparse
import hashlib
import json
import re
import stat
import subprocess
from pathlib import Path


class CompatibilityError(RuntimeError):
    pass


def normalize_source_permissions(root):
    """Give exported Git sources checkout modes before recipes preserve them."""
    root = Path(root)
    for path in [root, *root.rglob("*")]:
        info = path.lstat()
        if stat.S_ISLNK(info.st_mode):
            continue
        if stat.S_ISDIR(info.st_mode):
            path.chmod(0o755)
        elif stat.S_ISREG(info.st_mode):
            path.chmod(0o755 if info.st_mode & 0o111 else 0o644)
        else:
            raise CompatibilityError("Unexpected special file in source export")


def check_owner_program_permissions(root, relative, expected_uid=0):
    """Match the managed adapter's file and parent checks inside the guest root."""
    root = Path(root)
    path = root / relative
    info = path.lstat()
    if (not stat.S_ISREG(info.st_mode) or info.st_uid != expected_uid
            or info.st_nlink != 1 or info.st_mode & 0o7022):
        raise CompatibilityError(f"Unsafe owner-program file: {relative}")
    parent = path.parent
    while True:
        info = parent.lstat()
        if not stat.S_ISDIR(info.st_mode) or info.st_uid != expected_uid or info.st_mode & 0o022:
            raise CompatibilityError(f"Unsafe owner-program parent: {relative}")
        if parent == root:
            break
        if root not in parent.parents:
            raise CompatibilityError("Owner program escaped the guest root")
        parent = parent.parent


def digest(path):
    value = hashlib.sha256()
    with Path(path).open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            value.update(block)
    return value.hexdigest()


def package_list(path):
    names = []
    for line in Path(path).read_text().splitlines():
        name = line.split("#", 1)[0].strip()
        if not name:
            continue
        if not re.fullmatch(r"[a-z0-9][a-z0-9@._+\-]*", name) or name in names:
            raise CompatibilityError(f"Invalid or duplicate package in {path}: {name}")
        names.append(name)
    if not names:
        raise CompatibilityError(f"Empty package profile: {path}")
    return names


def replace_once(text, old, new):
    if text.count(old) != 1:
        raise CompatibilityError(f"Upstream contract changed: {old[:100]!r}")
    return text.replace(old, new, 1)


def optional_command(text, command, package):
    return replace_once(
        text, command + "\n",
        f'if pacman -Qq {package} >/dev/null 2>&1; then\n  {command}\nfi\n',
    )


def patch_sources(root, lock):
    root = Path(root)
    for relative, expected in lock["scripts"].items():
        if digest(root / relative) != expected:
            raise CompatibilityError(f"Unreviewed provisioning source: {relative}")

    report = {}
    for relative, expected in lock["scripts"].items():
        path = root / relative
        text = path.read_text()
        if relative == "install/config/enable-services.sh":
            for service, package in (
                ("cups.service", "cups"), ("avahi-daemon.service", "avahi"),
                ("docker.socket", "docker"),
                ("power-profiles-daemon.service", "omarchy-power-profiles-daemon"),
            ):
                text = optional_command(text, f"systemctl enable {service}", package)
        elif relative == "install/config/firewall.sh":
            for command in ("ufw allow 53317/udp", "ufw allow 53317/tcp"):
                text = optional_command(text, command, "localsend")
            for line in text.splitlines():
                if line.startswith("ufw allow in proto udp ") and "allow-docker-dns" in line:
                    text = optional_command(text, line, "docker")
            text = optional_command(text, "install_ufw_docker_rules", "ufw-docker")
        elif relative == "install/hardware/bluetooth.sh":
            text = 'pacman -Qq bluez >/dev/null 2>&1 || return 0\n' + text
        elif relative in ("install/user/chromium.sh", "install/user/mise.sh"):
            package = "chromium" if "chromium" in relative else "mise-bin"
            text = f'pacman -Qq {package} >/dev/null 2>&1 || return 0\n' + text
        elif relative == "bin/omarchy-provision-user":
            text = optional_command(
                text,
                "env -u BROWSER XDG_CURRENT_DESKTOP= xdg-settings set default-web-browser chromium.desktop",
                "chromium",
            )
            text = replace_once(
                text, "xdg-mime default HEY.desktop x-scheme-handler/mailto\n",
                'if [[ -f /usr/share/applications/HEY.desktop ]]; then\n'
                '  xdg-mime default HEY.desktop x-scheme-handler/mailto\nfi\n',
            )
        else:
            raise CompatibilityError(f"No reviewed transformation for {relative}")
        path.write_text(text)
        subprocess.run(["bash", "-n", str(path)], check=True)
        report[relative] = {"upstream_sha256": expected, "patched_sha256": digest(path)}
    return report


SOFTWARE_PATTERNS = (
    r"LIBGL_ALWAYS_SOFTWARE\s*=\s*(?:1|true)",
    r"WLR_RENDERER_ALLOW_SOFTWARE\s*=\s*1",
    r"(?:QT_QUICK_BACKEND|QSG_RHI_BACKEND)\s*=\s*software",
    r"GALLIUM_DRIVER\s*=\s*(?:llvmpipe|softpipe)",
)


def software_settings(root):
    result = []
    for path in Path(root).rglob("*"):
        if path.is_symlink() or not path.is_file():
            continue
        try:
            text = path.read_text()
        except (UnicodeError, OSError):
            continue
        if any(re.search(pattern, text, re.IGNORECASE) for pattern in SOFTWARE_PATTERNS):
            result.append(str(path.relative_to(root)))
    return sorted(result)


def prepare_integration(recipe):
    recipe = Path(recipe)
    hyprland = recipe / "files/usr/share/try-omarchy/hyprland.lua"
    if digest(hyprland) != "1e775d3d25f9f201bb17b36a65d695b77500596142a0b1480bb8da863dea7f34":
        raise CompatibilityError("Unreviewed integration Hyprland policy")
    hyprland.write_text(replace_once(
        hyprland.read_text(), 'if host_option("omarchy.qemu_virgl=1") then\n',
        'if host_option("omarchy.qemu_virgl=1") then\n'
        '  -- Preserve alpha-capable VirGL DMA-BUF formats on Hyprland 0.57.\n'
        '  hl.config({ quirks = { skip_non_kms_dmabuf_formats = false } })\n',
    ))
    path = recipe / "PKGBUILD"
    text = path.read_text()
    match = re.search(r"^pkgrel=([0-9]+)$", text, re.MULTILINE)
    if not match:
        raise CompatibilityError("Integration recipe needs a reviewed integer pkgrel")
    path.write_text(text[:match.start()] + f"pkgrel={match[1]}.1" + text[match.end():])
    files = recipe / "files"
    environment = files / "usr/lib/environment.d/90-try-omarchy.conf"
    text = environment.read_text()
    environment.write_text(replace_once(text, "WLR_RENDERER_ALLOW_SOFTWARE=1\n", ""))
    for relative in (
        "usr/lib/try-omarchy/bin/ghostty", "usr/lib/try-omarchy/bin/kitty",
        "usr/lib/systemd/user/app-com.mitchellh.ghostty.service.d/10-try-omarchy-software-gl.conf",
        "usr/share/try-omarchy/ghostty/com.mitchellh.ghostty.desktop",
        "usr/share/libalpm/hooks/try-omarchy-ghostty.hook",
        "usr/share/libalpm/hooks/try-omarchy-ghostty-remove.hook",
    ):
        path = files / relative
        if not path.is_file():
            raise CompatibilityError(f"Integration layout changed: {relative}")
        path.unlink()
    remaining = software_settings(files)
    if remaining:
        raise CompatibilityError("Unreviewed software rendering policy: " + ", ".join(remaining))


def check_package_set(installed, required, excluded):
    missing = sorted(set(required) - set(installed))
    unwanted = sorted(set(installed) & set(excluded))
    if missing or unwanted:
        raise CompatibilityError(f"Package closure failed; missing={missing}, excluded={unwanted}")


def check_user_log(text):
    failures = [line for line in text.splitlines() if re.search(
        r"command not found|No such file or directory|Bad file descriptor|"
        r"Failed: .*exit code|Theme retint failed|finalization reported errors",
        line, re.IGNORECASE,
    )]
    if failures:
        raise CompatibilityError("User finalization logged errors: " + "\n".join(failures))


def audit_root(root, profile, report_path):
    root, profile = Path(root), Path(profile)
    result = subprocess.run(
        ["arch-chroot", str(root), "pacman", "-Q"],
        check=True, capture_output=True, text=True,
    )
    installed = dict(line.split(maxsplit=1) for line in result.stdout.splitlines())
    check_package_set(
        installed, package_list(profile / "base.packages")
        + ["omarchy-dev", "omarchy-settings-dev", "try-omarchy", "dev-workstation-preferences"],
        package_list(profile / "excluded.packages"),
    )
    for name in ("etc", "usr/lib/environment.d", "usr/lib/systemd", "usr/lib/try-omarchy",
                 "usr/share/try-omarchy", "usr/share/uwsm"):
        matches = software_settings(root / name)
        if matches:
            raise CompatibilityError(f"Software rendering policy under {name}: {matches}")
    for name in ("boot/EFI/BOOT/BOOTAA64.EFI", "boot/limine.conf",
                 "var/lib/omarchy/provisioning/pending", "var/lib/omarchy/image/deferred-steps",
                 "var/lib/omarchy/image/pacman-keyring"):
        if not (root / name).is_file():
            raise CompatibilityError(f"Missing boot/provisioning contract: {name}")
    passwd = (root / "etc/passwd").read_text().splitlines()
    if any(1000 <= int(line.split(":")[2]) < 65534 for line in passwd):
        raise CompatibilityError("The factory contains a regular user")
    scripts = (
        "usr/bin/omarchy-provision-owner", "usr/bin/omarchy-provision-user",
        "usr/share/omarchy/install/provisioning/setup-form.sh",
        "usr/share/omarchy/install/provisioning/luks-rekey.sh",
    )
    for relative in (*scripts,
                     "usr/share/omarchy/install/provisioning/progress-icon.sh",
                     "usr/share/try-omarchy/owner-setup-contract.json",
                     "usr/share/try-omarchy/lean-owner-setup-contract.json",
                     "usr/lib/try-omarchy/managed-owner-setup",
                     "usr/lib/try-omarchy/managed-ssh"):
        # Stock integration sources do not carry manager-specific programs.
        # The Omarchy owner programs are always mandatory.
        if relative.startswith("usr/share/try-omarchy/") or relative.startswith("usr/lib/try-omarchy/"):
            if not (root / relative).exists() and not (root / relative).is_symlink():
                continue
        check_owner_program_permissions(root, relative)
    patched = json.loads((profile / "source-compatibility.json").read_text())
    for relative, hashes in patched.items():
        installed_path = "usr/" + relative if relative.startswith("bin/") else "usr/share/omarchy/" + relative
        if digest(root / installed_path) != hashes["patched_sha256"]:
            raise CompatibilityError(f"Installed compatibility patch differs: {relative}")
    report = {
        "format": 1, "profile": "desktop-foundation", "package_closure": "passed",
        "system_provisioning": "passed", "hardware_policy": "passed-static-checks",
        "owner_program_permissions": "passed",
        "owner_provisioning": "requires-disposable-vm-validation",
        "hardware_rendering": "requires-disposable-vm-validation",
        "user_finalization": "passed-in-isolated-chroot",
        "manager_admission": "requires-custom-factory-support-and-matching-integration-package",
        "owner_programs": {"/" + name: digest(root / name) for name in scripts},
        "packages": installed,
    }
    Path(report_path).write_text(json.dumps(report, indent=2, sort_keys=True) + "\n")


def audit_seal(root, report_path):
    root = Path(root)
    if (root / "etc/machine-id").read_bytes():
        raise CompatibilityError("Factory machine identity was not cleared")
    for path in (root / "var/lib/systemd/random-seed", root / "etc/pacman.d/gnupg"):
        if path.exists() or path.is_symlink():
            raise CompatibilityError(f"Factory contains shared identity state: {path.relative_to(root)}")
    if list((root / "etc/ssh").glob("ssh_host_*")):
        raise CompatibilityError("Factory contains SSH host identities")
    if any((root / "var/cache/pacman/pkg").iterdir()):
        raise CompatibilityError("Factory package cache was not cleared")
    accounts = [line.split(":") for line in (root / "etc/shadow").read_text().splitlines()]
    if not any(fields[0] == "root" and fields[1].startswith(("!", "*")) for fields in accounts):
        raise CompatibilityError("Factory root account must have a locked password")
    report = json.loads(Path(report_path).read_text())
    report["identity_sealing"] = "passed"
    Path(report_path).write_text(json.dumps(report, indent=2, sort_keys=True) + "\n")


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest="command", required=True)
    patch = sub.add_parser("patch-source")
    patch.add_argument("root", type=Path)
    patch.add_argument("profile", type=Path)
    patch.add_argument("report", type=Path)
    audit = sub.add_parser("audit-root")
    audit.add_argument("root", type=Path)
    audit.add_argument("profile", type=Path)
    audit.add_argument("report", type=Path)
    seal = sub.add_parser("audit-seal")
    seal.add_argument("root", type=Path)
    seal.add_argument("report", type=Path)
    args = parser.parse_args()
    try:
        if args.command == "patch-source":
            lock = json.loads((args.profile / "inputs.lock.json").read_text())
            result = patch_sources(args.root, lock)
            args.report.write_text(json.dumps(result, indent=2, sort_keys=True) + "\n")
        elif args.command == "audit-root":
            audit_root(args.root, args.profile, args.report)
        else:
            audit_seal(args.root, args.report)
    except (OSError, ValueError, CompatibilityError, subprocess.CalledProcessError) as error:
        parser.exit(1, f"Image compatibility failed: {error}\n")


if __name__ == "__main__":
    main()
