#!/usr/bin/env python3
"""Create and configure an Omarchy workstation through Omarchy VM Manager."""

from __future__ import annotations

import argparse
import json
import os
import platform
import re
import shlex
import subprocess
import sys
import uuid
from dataclasses import dataclass
from pathlib import Path
from typing import Iterable, Optional


PROJECT_DIR = Path(__file__).resolve().parents[1]
DEFAULT_CLI = PROJECT_DIR.parent / "Omarchy VM Manager" / "bin" / "omarchy-vm"
MINIMUM_MANAGER_VERSION = (0, 6, 0)
GUEST_REPAIR = PROJECT_DIR / "omarchy" / "guest" / "repair-try-omarchy-black-screen.sh"
GUEST_APPLY = PROJECT_DIR / "omarchy" / "guest" / "apply-workstation.sh"
GUEST_CHECK = PROJECT_DIR / "omarchy" / "guest" / "check-workstation.sh"
REMOTE_PREFIX = "/tmp/dev-ubuntu-workstation."
DEFAULT_PACKAGES = ("claude-desktop", "1password", "1password-cli")
PACKAGE_NAME = re.compile(r"[A-Za-z0-9][A-Za-z0-9._+@/-]*")


class WorkstationError(RuntimeError):
    pass


@dataclass(frozen=True)
class ManagedSSH:
    config: Path
    alias: str

    def ssh_argv(self, *, tty: bool = False) -> list[str]:
        options = ["/usr/bin/ssh"]
        if tty:
            options.append("-tt")
        return options + ["-F", str(self.config), self.alias]

    def scp_argv(self) -> list[str]:
        return ["/usr/bin/scp", "-F", str(self.config)]


@dataclass(frozen=True)
class GuestSoftware:
    name: str
    source: Optional[str] = None

    def display(self) -> str:
        return f"{self.source}:{self.name}" if self.source else self.name


def note(message: str) -> None:
    print(f"==> {message}", flush=True)


def run(argv, *, check=True, capture=False, stdin=None):
    options = {"check": check, "text": True, "stdin": stdin}
    if capture:
        options["stdout"] = subprocess.PIPE
        options["stderr"] = subprocess.PIPE
    return subprocess.run([str(value) for value in argv], **options)


def require_file(path: Path, description: str, *, executable=False) -> Path:
    path = path.expanduser().resolve()
    if not path.is_file() or (executable and not os.access(path, os.X_OK)):
        raise WorkstationError(f"{description} is unavailable: {path}")
    return path


def parse_json_reply(result: subprocess.CompletedProcess, command: str) -> dict:
    try:
        value = json.loads(result.stdout)
    except (TypeError, json.JSONDecodeError) as error:
        detail = (result.stderr or "").strip()
        suffix = f": {detail}" if detail else ""
        raise WorkstationError(
            f"Omarchy VM Manager returned invalid JSON for {command}{suffix}"
        ) from error
    if not isinstance(value, dict):
        raise WorkstationError(
            f"Omarchy VM Manager returned an unexpected reply for {command}"
        )
    return value


def guest_summary(guest: object) -> str:
    if not isinstance(guest, dict):
        return ""
    identifier = guest.get("id")
    state = guest.get("state")
    if not isinstance(identifier, str) or not isinstance(state, str):
        return ""
    return f" Guest {identifier} remains {state}; inspect it before retrying."


def cli_call(args, *values: str) -> dict:
    result = run([args.cli_path, *values], check=False, capture=True)
    reply = parse_json_reply(result, " ".join(values))
    if result.returncode != 0 or reply.get("ok") is False:
        failure = reply.get("error")
        if isinstance(failure, dict):
            code = failure.get("code", "command-failed")
            message = failure.get("message", "The command failed.")
        else:
            code = "command-failed"
            message = "The command failed."
        raise WorkstationError(
            f"Omarchy VM Manager {code}: {message}{guest_summary(reply.get('guest'))}"
        )
    return reply


def manager_version(args) -> str:
    result = run([args.cli_path, "--version"], check=False, capture=True)
    reply = parse_json_reply(result, "--version")
    version = reply.get("version")
    protocol = reply.get("commandProtocol")
    if result.returncode != 0 or protocol != 1 or not isinstance(version, str):
        raise WorkstationError(
            "Omarchy VM Manager must provide command protocol 1 through --version"
        )
    match = re.fullmatch(r"(\d+)\.(\d+)\.(\d+)", version)
    if (
        not match
        or tuple(int(part) for part in match.groups()) < MINIMUM_MANAGER_VERSION
    ):
        minimum = ".".join(str(part) for part in MINIMUM_MANAGER_VERSION)
        raise WorkstationError(
            f"Omarchy VM Manager {minimum} or newer is required; found {version}"
        )
    return version


def list_guests(args) -> list[dict]:
    reply = cli_call(args, "list")
    guests = reply.get("guests")
    if not isinstance(guests, list) or not all(
        isinstance(guest, dict) for guest in guests
    ):
        raise WorkstationError("Omarchy VM Manager returned an invalid guest list")
    return guests


def find_guest(guests: Iterable[dict], name: str) -> Optional[dict]:
    matches = [guest for guest in guests if guest.get("name") == name]
    if len(matches) > 1:
        raise WorkstationError(
            f"Several managed guests are named {name!r}; use the manager to resolve them"
        )
    return matches[0] if matches else None


def require_identifier(guest: dict) -> str:
    value = guest.get("id")
    try:
        return str(uuid.UUID(str(value))).upper()
    except (ValueError, AttributeError) as error:
        raise WorkstationError("The manager returned an invalid guest UUID") from error


def immutable_guest_errors(guest: dict) -> list[str]:
    errors = []
    if guest.get("protected") is True:
        errors.append("the selected profile is protected")
    ssh = guest.get("ssh")
    if not isinstance(ssh, dict) or ssh.get("enabled") is not True:
        errors.append("managed SSH was not enabled when this guest was created")
    network = guest.get("network")
    if not isinstance(network, dict) or network.get("mode") != "nat":
        errors.append("the guest is not using manager-owned NAT")
    elif network.get("hostAddress") != "127.0.0.1":
        errors.append("the manager did not report a loopback-only host address")
    return errors


def mutable_guest_errors(args, guest: dict) -> list[str]:
    expected = {
        "memoryMiB": args.memory_gib * 1024,
        "cpus": args.cpus,
        "diskGiB": args.disk_gib,
        "clipboard": True,
        "immersive": False,
    }
    return [
        f"{key} is {guest.get(key)!r}; expected {value!r}"
        for key, value in expected.items()
        if guest.get(key) != value
    ]


def format_errors(errors: Iterable[str]) -> str:
    return "\n  - ".join(errors)


def parse_packages(value: str) -> tuple[GuestSoftware, ...]:
    if not value.strip():
        return ()
    packages = []
    seen = set()
    for raw_item in value.split(","):
        item = raw_item.strip()
        if not item:
            raise argparse.ArgumentTypeError(
                "packages must be a comma-separated list without empty entries"
            )
        source = None
        name = item
        if ":" in item:
            source, name = item.split(":", 1)
            if source not in {"pkg", "mise"}:
                raise argparse.ArgumentTypeError(
                    f"unsupported package source {source!r}; use pkg: or mise:"
                )
        if not PACKAGE_NAME.fullmatch(name):
            raise argparse.ArgumentTypeError(f"invalid package name: {name!r}")
        key = (source, name)
        if key in seen:
            raise argparse.ArgumentTypeError(f"duplicate package selection: {item!r}")
        seen.add(key)
        packages.append(GuestSoftware(name=name, source=source))
    return tuple(packages)


def managed_ssh(guest: dict) -> ManagedSSH:
    identifier = require_identifier(guest)
    ssh = guest.get("ssh")
    if not isinstance(ssh, dict) or ssh.get("status") != "ready":
        status = ssh.get("status") if isinstance(ssh, dict) else None
        raise WorkstationError(
            f"Managed SSH is not ready; current status is {status!r}"
        )
    command = ssh.get("command")
    if not isinstance(command, str):
        raise WorkstationError("The manager did not return its pinned SSH command")
    try:
        tokens = shlex.split(command)
    except ValueError as error:
        raise WorkstationError("The manager returned an invalid SSH command") from error
    alias = "omarchy-" + identifier.lower()
    expected_config = (
        Path.home()
        / "Library"
        / "Application Support"
        / "Omarchy VM Manager"
        / "VMs"
        / identifier
        / ".manager-ssh"
        / "config"
    )
    if tokens != ["/usr/bin/ssh", "-F", str(expected_config), alias]:
        raise WorkstationError(
            "The manager returned an SSH command outside its reviewed per-guest boundary"
        )
    require_file(expected_config, "Manager-owned SSH configuration")
    return ManagedSSH(expected_config, alias)


def validate_remote_dir(value: str) -> str:
    value = value.strip()
    if not re.fullmatch(r"/tmp/dev-ubuntu-workstation\.[A-Za-z0-9]+", value):
        raise WorkstationError(f"Refusing unexpected remote temporary path: {value!r}")
    return value


def ssh_command(
    connection: ManagedSSH,
    command: str,
    *,
    check=True,
    capture=False,
    tty=False,
):
    return run(
        connection.ssh_argv(tty=tty) + [command],
        check=check,
        capture=capture,
    )


def guest_login_command(
    connection: ManagedSSH,
    command: str,
    *,
    check=True,
    capture=False,
    tty=False,
):
    return ssh_command(
        connection,
        f"bash -lc {shlex.quote(command)}",
        check=check,
        capture=capture,
        tty=tty,
    )


def stage_payload(
    connection: ManagedSSH, payloads: Iterable[Path]
) -> tuple[str, list[Path]]:
    created = ssh_command(
        connection,
        f"mktemp -d {REMOTE_PREFIX}XXXXXX",
        capture=True,
    )
    remote_dir = validate_remote_dir(created.stdout)
    files = [require_file(path, "Guest payload") for path in payloads]
    run(
        connection.scp_argv()
        + [str(path) for path in files]
        + [f"{connection.alias}:{remote_dir}/"]
    )
    return remote_dir, files


def cleanup_payload(connection: ManagedSSH, remote_dir: str) -> None:
    remote_dir = validate_remote_dir(remote_dir)
    ssh_command(
        connection,
        f"rm -rf -- {shlex.quote(remote_dir)}",
        check=False,
        capture=True,
    )


def package_installed(connection: ManagedSSH, package: str) -> bool:
    result = ssh_command(
        connection,
        f"pacman -Q -- {shlex.quote(package)} >/dev/null 2>&1",
        check=False,
        capture=True,
    )
    return result.returncode == 0


def mise_tool_configured(connection: ManagedSSH, tool: str) -> bool:
    result = ssh_command(
        connection,
        f"mise ls --json {shlex.quote(tool)} >/dev/null 2>&1",
        check=False,
        capture=True,
    )
    return result.returncode == 0


def mise_tool_installed(connection: ManagedSSH, tool: str) -> bool:
    result = ssh_command(
        connection,
        f"mise where {shlex.quote(tool)} >/dev/null 2>&1",
        check=False,
        capture=True,
    )
    return result.returncode == 0


def resolve_software_source(
    connection: ManagedSSH, software: GuestSoftware
) -> GuestSoftware:
    if software.source:
        return software
    source = "mise" if mise_tool_configured(connection, software.name) else "pkg"
    return GuestSoftware(name=software.name, source=source)


def install_selected_software(
    connection: ManagedSSH, selection: Iterable[GuestSoftware]
) -> None:
    selected = [resolve_software_source(connection, item) for item in selection]
    if not selected:
        note("No guest software selected")
        return

    commands = []
    package_names = {item.name for item in selected if item.source == "pkg"}
    handled_packages = set()
    if "claude-desktop" in package_names and not package_installed(
        connection, "claude-desktop"
    ):
        commands.append("omarchy install ai claude")
    if "claude-desktop" in package_names:
        handled_packages.add("claude-desktop")

    one_password = {"1password", "1password-cli"}
    if one_password <= package_names:
        if not all(package_installed(connection, name) for name in one_password):
            commands.append("omarchy install service 1password")
        handled_packages.update(one_password)

    for item in selected:
        if item.source == "pkg":
            if item.name in handled_packages or package_installed(
                connection, item.name
            ):
                continue
            commands.append(f"omarchy-pkg-add {shlex.quote(item.name)}")
        elif not mise_tool_installed(connection, item.name):
            commands.append(f"mise install {shlex.quote(item.name)}")

    if not commands:
        note("Selected guest software is already installed")
        return
    note(
        "Installing selected guest software through Omarchy and mise; "
        "enter guest sudo if prompted"
    )
    guest_login_command(connection, " && ".join(commands), tty=True)


def update_guest_system(connection: ManagedSSH) -> None:
    note(
        "Updating Omarchy and system packages through Omarchy; "
        "enter guest sudo if prompted"
    )
    guest_login_command(connection, "omarchy update -y", tty=True)


def confirm(args) -> None:
    if args.yes:
        return
    if not sys.stdin.isatty():
        raise WorkstationError(
            "Interactive confirmation is required; rerun in a terminal"
        )
    answer = input("Proceed with this managed VM? [y/N] ").strip().lower()
    if answer not in {"y", "yes"}:
        raise WorkstationError("Cancelled without changing the managed guest")


def preflight(args) -> str:
    if sys.platform != "darwin" or platform.machine() != "arm64":
        raise WorkstationError("Run this controller on an Apple Silicon Mac host")
    args.cli_path = require_file(
        args.cli_path, "Omarchy VM Manager CLI", executable=True
    )
    if (
        not args.vm_name
        or len(args.vm_name.encode("utf-8")) > 128
        or any(ord(character) < 32 for character in args.vm_name)
    ):
        raise WorkstationError("VM name must be a non-empty printable name")
    if not 4 <= args.cpus <= 128:
        raise WorkstationError("CPU count must be between 4 and 128")
    if not 4 <= args.memory_gib <= 1024:
        raise WorkstationError("Memory must be between 4 and 1024 GiB")
    if not 64 <= args.disk_gib <= 8192:
        raise WorkstationError("Disk capacity must be between 64 and 8192 GiB")
    if not 1 <= args.timeout <= 3600:
        raise WorkstationError("Timeout must be between 1 and 3600 seconds")
    if args.layout_file:
        args.layout_file = require_file(args.layout_file, "Layout file")
    return manager_version(args)


def print_proposal(
    args,
    *,
    manager: str,
    action: str,
    guest: Optional[dict],
    mutable_errors: Iterable[str],
) -> None:
    if args.remove_layout:
        layout = "remove the managed layout"
    elif args.layout_file:
        layout = str(args.layout_file)
    else:
        layout = "preserve the current choice"
    identifier = guest.get("id") if guest else "assigned by the manager"
    corrections = list(mutable_errors)
    packages = ", ".join(item.display() for item in args.packages) or "none"
    correction_text = (
        "\n  VM updates:      " + "; ".join(corrections) if corrections else ""
    )
    print(
        "\nProposed Omarchy workstation setup\n"
        f"  Manager CLI:     {manager} (command protocol 1)\n"
        f"  Managed VM:      {args.vm_name} ({identifier})\n"
        f"  VM action:       {action}\n"
        f"  Resources:       {args.cpus} CPUs, {args.memory_gib} GiB RAM, {args.disk_gib} GiB disk\n"
        "  Integration:     manager-owned NAT, Retina/VirGL, clipboard and SSH\n"
        "  VM storage:      manager-owned factory image and independent disk\n"
        f"  Guest software:  {packages}\n"
        f"  Preferences:     Foot {args.foot_font_size}, idle policy {args.idle_mode}\n"
        f"  App layout:      {layout}\n"
        "  Compatibility:   apply the conditional Hyprland/VirGL repair\n"
        "  Lifecycle:       update Omarchy, apply customizations, reboot and validate\n"
        "  Host installs:   none"
        f"{correction_text}\n",
        flush=True,
    )


def ready_guest(args) -> tuple[dict, str]:
    manager = preflight(args)
    guest = find_guest(list_guests(args), args.vm_name)
    immutable_errors = immutable_guest_errors(guest) if guest else []
    if immutable_errors:
        raise WorkstationError(
            "The existing managed guest cannot be adopted:\n  - "
            + format_errors(immutable_errors)
        )
    mutable_errors = mutable_guest_errors(args, guest) if guest else []

    if guest is None:
        action = "create, start and wait for authenticated SSH"
    elif guest.get("active") is True:
        if mutable_errors:
            raise WorkstationError(
                "Stop the managed guest before changing its configuration:\n  - "
                + format_errors(mutable_errors)
            )
        action = "preserve the running VM and verify authenticated SSH"
    else:
        action = (
            "update the stopped VM, then start and wait for authenticated SSH"
            if mutable_errors
            else "start the existing VM and wait for authenticated SSH"
        )

    print_proposal(
        args,
        manager=manager,
        action=action,
        guest=guest,
        mutable_errors=mutable_errors,
    )
    confirm(args)

    if guest is None:
        reply = cli_call(
            args,
            "create",
            args.vm_name,
            "--memory",
            f"{args.memory_gib}GiB",
            "--cpus",
            str(args.cpus),
            "--disk",
            f"{args.disk_gib}GiB",
            "--clipboard",
            "on",
            "--immersive",
            "off",
            "--ssh",
            "on",
            "--owner-defaults",
            "on",
            "--start",
            "--wait",
            "ssh",
            "--timeout",
            str(args.timeout),
        )
        guest = reply.get("guest")
    else:
        identifier = require_identifier(guest)
        if mutable_errors:
            cli_call(
                args,
                "update",
                identifier,
                "--memory",
                f"{args.memory_gib}GiB",
                "--cpus",
                str(args.cpus),
                "--disk",
                f"{args.disk_gib}GiB",
                "--clipboard",
                "on",
                "--immersive",
                "off",
            )
        if guest.get("active") is not True:
            reply = cli_call(
                args,
                "start",
                identifier,
                "--wait",
                "ssh",
                "--timeout",
                str(args.timeout),
            )
        elif guest.get("ssh", {}).get("status") == "ready":
            reply = cli_call(args, "get", identifier)
        else:
            reply = cli_call(
                args,
                "wait",
                identifier,
                "--for",
                "ssh",
                "--timeout",
                str(args.timeout),
            )
        guest = reply.get("guest")

    if not isinstance(guest, dict):
        raise WorkstationError("The manager did not return the ready guest")
    post_errors = immutable_guest_errors(guest) + mutable_guest_errors(args, guest)
    if post_errors:
        raise WorkstationError(
            "The ready guest does not match the accepted proposal:\n  - "
            + format_errors(post_errors)
        )
    return guest, manager


def apply_workstation(args, connection: ManagedSSH) -> None:
    payloads = [GUEST_REPAIR, GUEST_APPLY]
    if args.layout_file:
        payloads.append(args.layout_file)
    remote_dir = ""
    try:
        remote_dir, _ = stage_payload(connection, payloads)
        install_selected_software(connection, args.packages)

        apply_parts = [
            "bash",
            remote_dir + "/" + GUEST_APPLY.name,
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
        ssh_command(connection, " ".join(shlex.quote(part) for part in apply_parts))

        repair = ssh_command(
            connection,
            f"bash {shlex.quote(remote_dir + '/' + GUEST_REPAIR.name)}",
            capture=True,
        )
        print(repair.stdout, end="", flush=True)
    finally:
        if remote_dir:
            cleanup_payload(connection, remote_dir)


def restart_guest(args, guest: dict) -> dict:
    note("Rebooting the managed VM and waiting for authenticated SSH")
    reply = cli_call(
        args,
        "restart",
        require_identifier(guest),
        "--wait",
        "ssh",
        "--timeout",
        str(args.timeout),
    )
    current = reply.get("guest")
    if not isinstance(current, dict):
        raise WorkstationError("The manager did not return the restarted guest")
    errors = immutable_guest_errors(current) + mutable_guest_errors(args, current)
    if errors:
        raise WorkstationError(
            "The restarted guest does not match the workstation contract:\n  - "
            + format_errors(errors)
        )
    return current


def check_guest_workstation(connection: ManagedSSH) -> None:
    remote_dir = ""
    try:
        remote_dir, _ = stage_payload(connection, [GUEST_CHECK])
        ssh_command(
            connection,
            f"bash {shlex.quote(remote_dir + '/' + GUEST_CHECK.name)}",
        )
    finally:
        if remote_dir:
            cleanup_payload(connection, remote_dir)


def bootstrap_command(args) -> None:
    guest, _ = ready_guest(args)
    connection = managed_ssh(guest)
    update_guest_system(connection)
    apply_workstation(args, connection)
    guest = restart_guest(args, guest)
    check_guest_workstation(managed_ssh(guest))
    note("Managed Omarchy workstation setup is complete")


def check_command(args) -> None:
    preflight(args)
    guest = find_guest(list_guests(args), args.vm_name)
    if guest is None:
        raise WorkstationError(f"No managed guest is named {args.vm_name!r}")
    errors = immutable_guest_errors(guest) + mutable_guest_errors(args, guest)
    if errors:
        raise WorkstationError(
            "The managed guest does not match the workstation contract:\n  - "
            + format_errors(errors)
        )
    if guest.get("active") is not True:
        raise WorkstationError(
            "The managed guest is stopped; run bootstrap to start it"
        )
    reply = cli_call(args, "get", require_identifier(guest))
    current = reply.get("guest")
    if not isinstance(current, dict):
        raise WorkstationError("The manager did not return the current guest")
    check_guest_workstation(managed_ssh(current))


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--cli-path", type=Path, default=DEFAULT_CLI)
    parser.add_argument("--vm-name", default="Dev Omarchy")
    parser.add_argument("--cpus", type=int, default=8)
    parser.add_argument("--memory-gib", type=int, default=20)
    parser.add_argument("--disk-gib", type=int, default=64)
    parser.add_argument("--timeout", type=int, default=3600)
    parser.add_argument("--foot-font-size", default="16")
    parser.add_argument(
        "--idle-mode", choices=("host", "guest", "keep"), default="host"
    )
    layout_group = parser.add_mutually_exclusive_group()
    layout_group.add_argument("--layout-file", type=Path)
    layout_group.add_argument("--remove-layout", action="store_true")
    parser.add_argument("--yes", action="store_true")
    parser.add_argument(
        "--packages",
        type=parse_packages,
        default=tuple(GuestSoftware(name=name) for name in DEFAULT_PACKAGES),
        help=(
            "comma-separated guest software (default: "
            + ",".join(DEFAULT_PACKAGES)
            + "); unprefixed Omarchy mise tools use mise, other names use "
            "omarchy-pkg-add"
        ),
    )
    parser.add_argument("command", choices=("bootstrap", "check"))
    return parser


def main() -> int:
    args = build_parser().parse_args()
    try:
        if args.command == "bootstrap":
            bootstrap_command(args)
        else:
            check_command(args)
    except WorkstationError as error:
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
