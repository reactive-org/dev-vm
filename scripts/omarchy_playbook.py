#!/usr/bin/env python3
"""Apply selected playbook features through an existing managed SSH session."""

import argparse
import json
import os
import platform
import re
import shlex
import shutil
import signal
import subprocess
import sys
import tempfile
from pathlib import Path

import omarchy_vm_manager as manager
from omarchy_data import read_data
from omarchy_profiles import Resolver, contract


ROOT = Path(__file__).resolve().parent.parent
FEATURES = contract.FEATURES
LEGACY_OPTIONS = {
    "omarchy_browsers": ("browsers", "browsers"), "omarchy_languages": ("languages", "tools"),
    "omarchy_agents": ("agents", "tools"), "omarchy_credential_packages": ("credentials", "packages"),
    "omarchy_shell": ("workstation", "shell"),
    "omarchy_oh_my_zsh": ("workstation", "oh_my_zsh"), "omarchy_starship": ("workstation", "starship"),
    "omarchy_oh_my_zsh_plugins": ("workstation", "oh_my_zsh_plugins"),
    "omarchy_oh_my_zsh_update_mode": ("workstation", "oh_my_zsh_update_mode"),
    "omarchy_starship_config": ("workstation", "starship_config"),
    "omarchy_foot_font_size": ("workstation", "font_size"), "omarchy_idle_mode": ("workstation", "idle_mode"),
    "omarchy_theme": ("workstation", "theme"), "omarchy_layout_file": ("workstation", "layout"),
    "omarchy_remove_layout": ("workstation", "remove_layout"),
}
COMPOSITE_OPTIONS = {"omarchy_" + name: name for name in FEATURES
                     if name not in {feature for feature, _ in LEGACY_OPTIONS.values()}}
OPTIONS = set(LEGACY_OPTIONS) | set(COMPOSITE_OPTIONS)


def features(value):
    result = value.split(",")
    if (not result or any(item not in FEATURES and not re.fullmatch(r"[a-z][a-z0-9_-]*\.[a-z][a-z0-9_-]*", item)
                          for item in result) or len(set(result)) != len(result)):
        raise argparse.ArgumentTypeError("Select unique comma-separated names: " + ",".join(FEATURES))
    return result


def write_private(path, data):
    with path.open("x") as stream:
        os.chmod(path, 0o600)
        json.dump(data, stream, indent=2)


def connection_values(guest, connection):
    ssh = guest["ssh"]
    user = ssh.get("user")
    port = ssh.get("port")
    if not isinstance(user, str) or not re.fullmatch(r"[a-z_][a-z0-9_-]{0,31}", user):
        raise manager.WorkstationError("The manager must report the authenticated non-root owner")
    if user == "root" or type(port) is not int or not 1024 <= port <= 65535:
        raise manager.WorkstationError("Invalid managed SSH owner or loopback port")
    return {
        "ansible_host": connection.alias, "ansible_user": user, "ansible_port": port,
        "ansible_connection": "ssh", "ansible_ssh_executable": "/usr/bin/ssh",
        "ansible_ssh_args": "-C -o ControlMaster=no -o ControlPersist=no -o StrictHostKeyChecking=yes -o BatchMode=yes",
        "ansible_ssh_common_args": shlex.join(["-F", str(connection.config)]),
        "ansible_ssh_extra_args": "", "ansible_scp_extra_args": "", "ansible_sftp_extra_args": "",
        "ansible_host_key_checking": True, "ansible_ssh_host_key_checking": True,
        "ansible_private_key_file": "", "ansible_ssh_private_key_file": "",
        "ansible_scp_executable": "/usr/bin/scp", "ansible_sftp_executable": "/usr/bin/sftp",
        "ansible_python_interpreter": "/usr/bin/python3", "ansible_become": False,
    }


def read_options(path, executable=None, temporary=None):
    if not path:
        return {}
    path = manager.require_file(path, "Explicit feature variables")
    value = read_data(path)
    if not isinstance(value, dict) or set(value) - OPTIONS:
        raise manager.WorkstationError("Feature variables may contain only documented omarchy_* options; connection and internal state overrides are refused")
    return value


def overrides(options):
    result = {}
    for variable, value in options.items():
        if variable in LEGACY_OPTIONS:
            feature, field = LEGACY_OPTIONS[variable]
            if field == "font_size" and type(value) in (int, float):
                value = str(value)
            result.setdefault(feature, {})[field] = value
        else:
            result[COMPOSITE_OPTIONS[variable]] = value
    return result


def plan_variables(plan):
    value = {"omarchy_features": plan["features"], "omarchy_extensions": [], "omarchy_resolved_plan": []}
    for name, config in plan["options"].items():
        extension = name not in FEATURES
        value["omarchy_resolved_plan"].append({"feature": name, "config": config, "extension": extension})
        if extension:
            value["omarchy_extensions"].append({"name": name, "config": config})
        elif name in COMPOSITE_OPTIONS.values():
            value["omarchy_" + name] = config
        else:
            for variable, (feature, field) in LEGACY_OPTIONS.items():
                if feature == name:
                    value[variable] = config[field]
    return value


def ready_connection(args):
    manager.manager_version(args)
    guest = manager.find_guest(manager.list_guests(args), args.vm_name)
    if guest is None:
        raise manager.WorkstationError("Create the selected guest through VM Manager before applying features")
    errors = manager.immutable_guest_errors(guest)
    if errors:
        raise manager.WorkstationError("Incompatible guest: " + "; ".join(errors))
    if guest.get("active") is not True:
        raise manager.WorkstationError("Start the selected guest through VM Manager first; the playbook runner never starts or resizes a VM")
    reply = manager.cli_call(args, "get", manager.require_identifier(guest))
    current = reply.get("guest")
    if not isinstance(current, dict) or manager.require_identifier(current) != manager.require_identifier(guest):
        raise manager.WorkstationError("The manager returned a different guest")
    if manager.immutable_guest_errors(current):
        raise manager.WorkstationError("Guest policy changed while resolving managed SSH")
    connection = manager.managed_ssh(current)
    return current, connection


def verify_owner_docker(connection):
    # Each call opens a fresh pinned SSH session, with newly configured groups.
    # Use the local socket explicitly: a remote context cannot validate this VM.
    result = manager.guest_login_command(
        connection,
        "env -u DOCKER_HOST -u DOCKER_CONTEXT /usr/bin/docker --host unix:///var/run/docker.sock "
        "version --format '{{.Server.Version}}' && /usr/bin/docker compose version && /usr/bin/docker buildx version",
        check=False, capture=True,
    )
    if result.returncode or not result.stdout.strip():
        raise manager.WorkstationError("Owner cannot use the local Docker daemon without sudo: " + (result.stderr or result.stdout).strip())
    print("Owner Docker access verified without sudo: " + result.stdout.strip(), flush=True)


def enable_owner_docker(connection):
    probe = manager.guest_login_command(connection, "omarchy-sudo-docker --configured", check=False, capture=True)
    if probe.returncode not in (0, 1):
        raise manager.WorkstationError("Unable to inspect native Omarchy Docker access policy")
    if probe.returncode == 0:
        manager.note("Enable Sudoless Docker at Omarchy's native confirmation; this grants root-equivalent access inside the guest")
        manager.guest_login_command(connection, "OMARCHY_DEFER_REBOOT=1 omarchy-setup-security-sudoless-docker", tty=True)
        after = manager.guest_login_command(connection, "omarchy-sudo-docker --configured", check=False, capture=True)
        if after.returncode != 1:
            raise manager.WorkstationError("Native Sudoless Docker opt-in was not enabled; owner access is required by the selected developer profile")
        manager.note("Restart the desktop session through VM Manager before using Docker in existing terminals; no automatic reboot will interrupt your work")
    verify_owner_docker(connection)


def playbook(args):
    # Resolve and validate local data before even inspecting a manager connection.
    options = read_options(args.vars_file)
    resolver = Resolver()
    plan = resolver.resolve(profiles=getattr(args, "profiles", None), features=args.features,
                            setup_file=getattr(args, "setup_file", None),
                            catalogues=getattr(args, "catalogue", None), overrides=overrides(options))
    if args.vars_file:
        resolver.source(args.vars_file)
    if getattr(args, "resolve", False):
        print(json.dumps(plan, indent=2))
        return
    if sys.platform != "darwin" or platform.machine() != "arm64":
        raise manager.WorkstationError("Run the playbook launcher on an Apple Silicon Mac")
    if not args.vm_name or len(args.vm_name.encode()) > 128 or any(ord(c) < 32 for c in args.vm_name):
        raise manager.WorkstationError("VM name must be a non-empty printable name")
    args.cli_path = manager.require_file(
        manager.installed_cli(args.cli_path, getattr(args, "manager_app", None)),
        "Omarchy VM Manager CLI", executable=True,
    )
    ansible = shutil.which("ansible-playbook")
    if not ansible:
        raise manager.WorkstationError("An existing ansible-playbook is required; no host tools are installed")
    with tempfile.TemporaryDirectory(prefix="dev-omarchy-ansible-") as folder:
        temporary = Path(folder)
        guest, connection = ready_connection(args)
        fixed = connection_values(guest, connection)
        inventory = temporary / "inventory.json"
        variables = temporary / "features.json"
        write_private(inventory, {"all": {"children": {"omarchy": {"hosts": {"workstation": fixed}}}}})
        owner_docker = plan["options"].get("docker", {}).get("access") == "sudoless"
        write_private(variables, {**plan_variables(plan), **fixed,
                                  "omarchy_defer_docker_access": owner_docker and not args.check})
        command = [ansible, "-i", str(inventory), str(ROOT / "site.yml"),
                   "--tags", ",".join(plan["features"]), "--extra-vars", "@" + str(variables)]
        if args.check:
            command.append("--check")
        print("Resolved proposal:\n" + json.dumps(plan, indent=2), flush=True)
        print(f"Guest: {args.vm_name}\nFeatures: {', '.join(plan['features'])}\n"
              f"Variables: {args.vars_file or 'repository defaults'}\n"
              f"Mode: {'check (temporary payload only)' if args.check else 'apply'}\n"
              "Connection: VM Manager's authenticated, pinned SSH\n"
              f"Guest sudo: {'unchanged' if args.check else 'one early password; native persistent grant, revoked on exit; manual cleanup if SSH is lost'}\n"
              "VM lifecycle and resource settings: unchanged", flush=True)
        if args.plan or not plan["features"]:
            return
        manager.confirm(args)
        for source in plan["sources"]:
            resolver.verify_source(source)
        privileged = not args.check
        previous = {}

        def interrupted(signum, _frame):
            raise manager.WorkstationError(f"Playbook interrupted by {signal.Signals(signum).name}")

        for signum in (signal.SIGTERM, signal.SIGHUP):
            previous[signum] = signal.signal(signum, interrupted)
        try:
            try:
                if privileged:
                    manager.enable_bootstrap_sudo(connection)
                subprocess.run(command, check=True, cwd=ROOT)
                if privileged and owner_docker:
                    enable_owner_docker(connection)
            except BaseException:
                if privileged:
                    try:
                        manager.disable_bootstrap_sudo(connection)
                    except manager.WorkstationError as error:
                        print(f"Warning: {error}", file=sys.stderr, flush=True)
                raise
            else:
                if privileged:
                    manager.disable_bootstrap_sudo(connection)
        finally:
            for signum, handler in previous.items():
                signal.signal(signum, handler)
        if privileged and owner_docker:
            # A broad setup sudo grant must not mask a broken developer setup.
            verify_owner_docker(connection)
        print("Selected features complete. Use VM Manager for any required new login or restart.", flush=True)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--cli-path", type=Path, default=manager.DEFAULT_CLI)
    parser.add_argument("--manager-app", type=Path, help="Installed manager .app containing the CLI")
    parser.add_argument("--vm-name", default="Dev Omarchy")
    parser.add_argument("--features", type=features)
    parser.add_argument("--profiles", type=lambda value: value.split(","))
    parser.add_argument("--setup-file", type=Path)
    parser.add_argument("--catalogue", type=Path, action="append")
    parser.add_argument("--resolve", action="store_true", help="Print the resolved local plan without contacting a VM")
    parser.add_argument("--vars-file", type=Path)
    parser.add_argument("--check", action="store_true")
    parser.add_argument("--plan", action="store_true")
    parser.add_argument("--yes", action="store_true")
    args = parser.parse_args()
    try:
        playbook(args)
    except (OSError, ValueError, subprocess.CalledProcessError, manager.WorkstationError) as error:
        print(f"Omarchy playbook failed: {error}", file=sys.stderr)
        return 1
    except KeyboardInterrupt:
        return 130
    return 0


if __name__ == "__main__":
    sys.exit(main())
