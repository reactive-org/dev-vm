#!/usr/bin/env python3
"""Configure an existing Try Omarchy VM through its localhost SSH forward."""

from __future__ import annotations

import argparse
import json
import os
import plistlib
import re
import shlex
import socket
import subprocess
import sys
from pathlib import Path
from typing import Optional


PROJECT_DIR = Path(__file__).resolve().parents[1]
DEFAULT_APP = Path("/Applications/Try Omarchy.app")
DEFAULT_LOCK = PROJECT_DIR / "omarchy" / "try-omarchy.lock.json"
DEFAULT_PRIVATE_KEY = Path.home() / ".ssh" / "id_rsa"
DEFAULT_SHARE = Path.home() / "Shared"
PREFERENCES = Path.home() / "Library" / "Preferences" / "dev.tryomarchy.native.plist"
GUEST_PAYLOADS = (
    PROJECT_DIR / "omarchy" / "guest" / "repair-try-omarchy-black-screen.sh",
    PROJECT_DIR / "omarchy" / "guest" / "apply-workstation.sh",
    PROJECT_DIR / "omarchy" / "guest" / "check-workstation.sh",
)
REMOTE_PREFIX = "/tmp/dev-ubuntu-workstation."


class TryOmarchyError(RuntimeError):
    pass


def note(message: str) -> None:
    print(f"==> {message}", flush=True)


def run(argv, *, check=True, capture=False, stdin=None):
    options = {"check": check, "text": True, "stdin": stdin}
    if capture:
        options["stdout"] = subprocess.PIPE
        options["stderr"] = subprocess.PIPE
    return subprocess.run([str(value) for value in argv], **options)


def require_file(path: Path, description: str) -> Path:
    path = path.expanduser().resolve()
    if not path.is_file():
        raise TryOmarchyError(f"{description} is unavailable: {path}")
    return path


def load_lock(path: Path) -> dict:
    path = require_file(path, "Try Omarchy lock file")
    try:
        lock = json.loads(path.read_text(encoding="utf-8"))
        app = lock["app"]
        for key in ("bundle_id", "dmg_sha256", "release_url", "team_id", "version"):
            if not isinstance(app[key], str) or not app[key]:
                raise ValueError(key)
    except (KeyError, ValueError, json.JSONDecodeError) as error:
        raise TryOmarchyError(f"Invalid Try Omarchy lock file: {path}") from error
    return lock


def plist_value(plist: dict, key: str) -> dict:
    try:
        value = plist[key]
        if not isinstance(value, bytes):
            raise TypeError(key)
        decoded = json.loads(value.decode("utf-8"))
        if not isinstance(decoded, dict):
            raise TypeError(key)
        return decoded
    except (KeyError, TypeError, UnicodeDecodeError, json.JSONDecodeError) as error:
        raise TryOmarchyError(
            f"Try Omarchy has no readable {key}; configure and save it in the launcher"
        ) from error


def read_launcher_preferences(path: Path = PREFERENCES) -> dict:
    path = require_file(path, "Try Omarchy launcher preferences")
    try:
        return plistlib.loads(path.read_bytes())
    except (plistlib.InvalidFileException, OSError) as error:
        raise TryOmarchyError(
            f"Unable to read Try Omarchy preferences: {path}"
        ) from error


def validate_launcher_settings(
    plist: dict,
    *,
    cpus: int,
    memory_gib: int,
    disk_gib: int,
    share_path: Path,
    ssh_port: int,
) -> list[str]:
    errors = []
    resources = plist_value(plist, "vmResourcePreferences").get("resources", {})
    expected_resources = {
        "cpuCount": cpus,
        "memoryGiB": memory_gib,
        "diskGiB": disk_gib,
    }
    for key, expected in expected_resources.items():
        if resources.get(key) != expected:
            errors.append(
                f"resource {key} is {resources.get(key)!r}; expected {expected!r}"
            )

    forwarding = plist_value(plist, "portForwardingPreferences")
    expected_forward = {
        "protocol": "tcp",
        "hostPort": ssh_port,
        "guestPort": 22,
    }
    if expected_forward not in forwarding.get("mappings", []):
        errors.append(f"missing SSH forwarding rule {ssh_port} -> 22/tcp")

    sharing = plist_value(plist, "sharedFolderPreferences")
    configured_path = Path(sharing.get("path", "")).expanduser()
    if sharing.get("isEnabled") is not True:
        errors.append("shared folder is disabled")
    elif configured_path.resolve() != share_path.expanduser().resolve():
        errors.append(
            f"shared folder is {configured_path}; expected {share_path.expanduser()}"
        )
    return errors


def app_metadata(app_path: Path, lock: dict) -> dict:
    app_path = app_path.expanduser().resolve()
    if not app_path.is_dir():
        raise TryOmarchyError(
            f"Try Omarchy is not installed at {app_path}; install it manually first"
        )

    info_path = app_path / "Contents" / "Info.plist"
    try:
        info = plistlib.loads(info_path.read_bytes())
    except (OSError, plistlib.InvalidFileException) as error:
        raise TryOmarchyError(
            f"Unable to read installed app metadata: {info_path}"
        ) from error

    expected = lock["app"]
    version = info.get("CFBundleShortVersionString")
    bundle_id = info.get("CFBundleIdentifier")
    if version != expected["version"]:
        raise TryOmarchyError(
            f"Installed Try Omarchy version is {version!r}; reviewed version is "
            f"{expected['version']!r}. Review and update the lock before proceeding."
        )
    if bundle_id != expected["bundle_id"]:
        raise TryOmarchyError(
            f"Installed bundle id is {bundle_id!r}; expected {expected['bundle_id']!r}"
        )

    run(["/usr/bin/codesign", "--verify", "--deep", "--strict", app_path])
    run(["/usr/sbin/spctl", "--assess", "--type", "execute", app_path])
    signature = run(
        ["/usr/bin/codesign", "-dv", "--verbose=4", app_path],
        check=False,
        capture=True,
    )
    signature_text = f"{signature.stdout}\n{signature.stderr}"
    team_match = re.search(r"^TeamIdentifier=(\S+)$", signature_text, re.MULTILINE)
    team_id = team_match.group(1) if team_match else ""
    if signature.returncode != 0 or team_id != expected["team_id"]:
        raise TryOmarchyError(
            f"Installed app signing team is {team_id!r}; expected {expected['team_id']!r}"
        )
    return {
        "path": app_path,
        "version": version,
        "bundle_id": bundle_id,
        "team_id": team_id,
    }


def validate_guest_user(value: str) -> str:
    if not re.fullmatch(r"[a-z_][a-z0-9_-]{0,31}", value):
        raise TryOmarchyError(f"Invalid guest user: {value!r}")
    return value


def validate_remote_dir(value: str) -> str:
    value = value.strip()
    if not re.fullmatch(r"/tmp/dev-ubuntu-workstation\.[A-Za-z0-9]+", value):
        raise TryOmarchyError(f"Refusing unexpected remote temporary path: {value!r}")
    return value


def ssh_options(args, *, batch=True, tty=False, password_only=False) -> list[str]:
    options = [
        "/usr/bin/ssh",
        "-p",
        str(args.ssh_port),
        "-i",
        str(args.private_key),
        "-o",
        "ConnectTimeout=5",
        "-o",
        "ConnectionAttempts=1",
        "-o",
        "IdentitiesOnly=yes",
        "-o",
        "StrictHostKeyChecking=accept-new",
    ]
    if batch:
        options.extend(["-o", "BatchMode=yes"])
    if password_only:
        options.extend(
            [
                "-o",
                "PubkeyAuthentication=no",
                "-o",
                "PreferredAuthentications=keyboard-interactive,password",
            ]
        )
    if tty:
        options.append("-tt")
    options.append(f"{args.guest_user}@{args.ssh_host}")
    return options


def scp_options(args) -> list[str]:
    return [
        "/usr/bin/scp",
        "-P",
        str(args.ssh_port),
        "-i",
        str(args.private_key),
        "-o",
        "BatchMode=yes",
        "-o",
        "ConnectTimeout=5",
        "-o",
        "IdentitiesOnly=yes",
        "-o",
        "StrictHostKeyChecking=accept-new",
    ]


def ssh_command(
    args,
    command: str,
    *,
    check=True,
    capture=False,
    tty=False,
    batch=True,
    password_only=False,
    stdin=None,
):
    return run(
        ssh_options(args, batch=batch, tty=tty, password_only=password_only)
        + [command],
        check=check,
        capture=capture,
        stdin=stdin,
    )


def port_is_open(host: str, port: int) -> bool:
    try:
        with socket.create_connection((host, port), timeout=3):
            return True
    except OSError:
        return False


def key_auth_ready(args) -> bool:
    result = ssh_command(args, "true", check=False, capture=True)
    return result.returncode == 0


def authorize_key(args) -> None:
    note("The guest does not trust this key yet; enter the guest password once")
    remote = """set -eu
umask 077
install -d -m 0700 "$HOME/.ssh"
touch "$HOME/.ssh/authorized_keys"
chmod 0600 "$HOME/.ssh/authorized_keys"
IFS= read -r key
grep -qxF -- "$key" "$HOME/.ssh/authorized_keys" || printf '%s\\n' "$key" >> "$HOME/.ssh/authorized_keys"
"""
    with args.public_key.open("r", encoding="utf-8") as public_key:
        ssh_command(
            args,
            remote,
            batch=False,
            password_only=True,
            stdin=public_key,
        )
    if not key_auth_ready(args):
        raise TryOmarchyError("SSH public-key authorization did not succeed")
    note("SSH public-key authorization is ready")


def package_installed(args, package: str) -> bool:
    result = ssh_command(
        args,
        f"pacman -Q -- {shlex.quote(package)} >/dev/null 2>&1",
        check=False,
        capture=True,
    )
    return result.returncode == 0


def stage_payload(args, layout_file: Optional[Path]) -> str:
    created = ssh_command(
        args,
        f"mktemp -d {REMOTE_PREFIX}XXXXXX",
        capture=True,
    )
    remote_dir = validate_remote_dir(created.stdout)
    payloads = [require_file(path, "Guest payload") for path in GUEST_PAYLOADS]
    if layout_file:
        payloads.append(require_file(layout_file, "Layout file"))
    run(
        scp_options(args)
        + [str(path) for path in payloads]
        + [f"{args.guest_user}@{args.ssh_host}:{remote_dir}/"]
    )
    return remote_dir


def cleanup_payload(args, remote_dir: str) -> None:
    remote_dir = validate_remote_dir(remote_dir)
    ssh_command(
        args,
        f"rm -rf -- {shlex.quote(remote_dir)}",
        check=False,
        capture=True,
    )


def install_missing_apps(args) -> None:
    commands = []
    if not package_installed(args, "claude-desktop"):
        commands.append("omarchy install ai claude")
    if not (
        package_installed(args, "1password")
        and package_installed(args, "1password-cli")
    ):
        commands.append("omarchy install service 1password")
    if not commands:
        note("Claude Desktop and 1Password are already installed")
        return
    note(
        "Installing missing applications through Omarchy; enter guest sudo when prompted"
    )
    ssh_command(args, " && ".join(commands), tty=True)


def print_proposal(args, metadata: dict, key_ready: bool) -> None:
    if args.remove_layout:
        layout = "remove the managed layout"
    elif args.layout_file:
        layout = str(args.layout_file)
    else:
        layout = "preserve the current choice"
    print(
        "\nProposed Try Omarchy workstation setup\n"
        f"  App:             {metadata['version']} ({metadata['team_id']})\n"
        f"  Existing VM:     preserved; no reset or disk replacement\n"
        f"  Resources:       {args.cpus} CPUs, {args.memory_gib} GiB RAM, "
        f"{args.disk_gib} GiB sparse disk\n"
        f"  Shared folder:   {args.share_path}\n"
        f"  SSH:             {args.guest_user}@{args.ssh_host}:{args.ssh_port}\n"
        f"  SSH key:         {'already authorized' if key_ready else 'authorize after guest password prompt'}\n"
        "  Guest apps:      Claude Desktop and 1Password via Omarchy\n"
        f"  Preferences:     Foot {args.foot_font_size}, idle policy {args.idle_mode}\n"
        f"  App layout:      {layout}\n"
        "  Compatibility:   apply the conditional Hyprland/VirGL repair\n"
        "  Host installs:   none\n",
        flush=True,
    )


def confirm(args) -> None:
    if args.yes:
        return
    if not sys.stdin.isatty():
        raise TryOmarchyError(
            "Interactive confirmation is required; rerun in a terminal"
        )
    answer = input("Proceed with this existing VM? [y/N] ").strip().lower()
    if answer not in {"y", "yes"}:
        raise TryOmarchyError("Cancelled without changing the guest")


def preflight(args):
    if sys.platform != "darwin":
        raise TryOmarchyError("Run this controller on the Apple Silicon Mac host")
    if args.ssh_host != "127.0.0.1":
        raise TryOmarchyError("Try Omarchy SSH must remain bound to 127.0.0.1")
    if not 1 <= args.ssh_port <= 65535:
        raise TryOmarchyError("SSH port must be between 1 and 65535")
    if not 1 <= args.cpus <= 128:
        raise TryOmarchyError("CPU count must be between 1 and 128")
    if not 1 <= args.memory_gib <= 1024:
        raise TryOmarchyError("Memory must be between 1 and 1024 GiB")
    if not 16 <= args.disk_gib <= 16384:
        raise TryOmarchyError("Disk must be between 16 and 16384 GiB")
    args.guest_user = validate_guest_user(args.guest_user)
    args.private_key = require_file(args.private_key, "SSH private key")
    args.public_key = require_file(args.public_key, "SSH public key")
    args.share_path = args.share_path.expanduser().resolve()
    if not args.share_path.is_dir():
        raise TryOmarchyError(f"Shared folder does not exist: {args.share_path}")
    if args.layout_file:
        args.layout_file = require_file(args.layout_file, "Layout file")

    lock = load_lock(args.lock_file)
    metadata = app_metadata(args.app_path, lock)
    settings_errors = validate_launcher_settings(
        read_launcher_preferences(),
        cpus=args.cpus,
        memory_gib=args.memory_gib,
        disk_gib=args.disk_gib,
        share_path=args.share_path,
        ssh_port=args.ssh_port,
    )
    if settings_errors:
        formatted = "\n  - ".join(settings_errors)
        raise TryOmarchyError(
            "Try Omarchy launcher settings do not match the runbook:\n  - "
            f"{formatted}\nSave them and choose Restart Try Omarchy before retrying."
        )
    if not port_is_open(args.ssh_host, args.ssh_port):
        raise TryOmarchyError(
            f"SSH is not listening on {args.ssh_host}:{args.ssh_port}; "
            "save the forwarding rule and choose Restart Try Omarchy"
        )
    return metadata


def bootstrap_command(args) -> None:
    metadata = preflight(args)
    key_ready = key_auth_ready(args)
    print_proposal(args, metadata, key_ready)
    confirm(args)
    if not key_ready:
        authorize_key(args)

    remote_dir = ""
    repaired = False
    try:
        remote_dir = stage_payload(args, args.layout_file)
        repair = ssh_command(
            args,
            f"bash {shlex.quote(remote_dir + '/repair-try-omarchy-black-screen.sh')}",
            capture=True,
        )
        print(repair.stdout, end="", flush=True)
        repaired = "Repaired:" in repair.stdout
        if not args.skip_apps:
            install_missing_apps(args)

        apply_parts = [
            "bash",
            remote_dir + "/apply-workstation.sh",
            "--foot-font-size",
            str(args.foot_font_size),
            "--idle-mode",
            args.idle_mode,
        ]
        if args.layout_file:
            apply_parts.extend(
                ["--layout-file", remote_dir + "/" + args.layout_file.name]
            )
        elif args.remove_layout:
            apply_parts.append("--remove-layout")
        apply_command = " ".join(shlex.quote(part) for part in apply_parts)
        ssh_command(args, apply_command)

        shared_name = args.share_path.name
        check_command = (
            f"TRY_OMARCHY_SHARED_FOLDER={shlex.quote(shared_name)} "
            f"bash {shlex.quote(remote_dir + '/check-workstation.sh')}"
        )
        ssh_command(args, check_command)
    finally:
        if remote_dir:
            cleanup_payload(args, remote_dir)

    note("Try Omarchy workstation setup is complete")
    if repaired:
        note("Restart Try Omarchy once to activate the Hyprland compatibility repair")
    elif args.layout_file or args.remove_layout:
        note("Log out and back in once to activate the app layout change")


def check_command(args) -> None:
    preflight(args)
    if not key_auth_ready(args):
        raise TryOmarchyError(
            "SSH key authentication is not ready; run bootstrap first"
        )
    remote_dir = ""
    try:
        remote_dir = stage_payload(args, None)
        shared_name = args.share_path.name
        ssh_command(
            args,
            f"TRY_OMARCHY_SHARED_FOLDER={shlex.quote(shared_name)} "
            f"bash {shlex.quote(remote_dir + '/check-workstation.sh')}",
        )
    finally:
        if remote_dir:
            cleanup_payload(args, remote_dir)


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--app-path", type=Path, default=DEFAULT_APP)
    parser.add_argument("--lock-file", type=Path, default=DEFAULT_LOCK)
    parser.add_argument("--guest-user", default=os.environ.get("USER", ""))
    parser.add_argument("--ssh-host", default="127.0.0.1")
    parser.add_argument("--ssh-port", type=int, default=2222)
    parser.add_argument("--private-key", type=Path, default=DEFAULT_PRIVATE_KEY)
    parser.add_argument("--public-key", type=Path, default=None)
    parser.add_argument("--share-path", type=Path, default=DEFAULT_SHARE)
    parser.add_argument("--cpus", type=int, default=8)
    parser.add_argument("--memory-gib", type=int, default=20)
    parser.add_argument("--disk-gib", type=int, default=64)
    parser.add_argument("--foot-font-size", default="16")
    parser.add_argument(
        "--idle-mode", choices=("host", "guest", "keep"), default="host"
    )
    layout_group = parser.add_mutually_exclusive_group()
    layout_group.add_argument("--layout-file", type=Path)
    layout_group.add_argument("--remove-layout", action="store_true")
    parser.add_argument("--yes", action="store_true")
    parser.add_argument("--skip-apps", action="store_true")
    parser.add_argument("command", choices=("bootstrap", "check"))
    return parser


def main() -> int:
    parser = build_parser()
    args = parser.parse_args()
    if args.public_key is None:
        args.public_key = Path(str(args.private_key) + ".pub")
    try:
        if args.command == "bootstrap":
            bootstrap_command(args)
        else:
            check_command(args)
    except TryOmarchyError as error:
        print(f"Error: {error}", file=sys.stderr)
        return 1
    except subprocess.CalledProcessError as error:
        print(
            f"Error: command failed ({error.returncode}): {shlex.join(error.cmd)}",
            file=sys.stderr,
        )
        return error.returncode or 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
