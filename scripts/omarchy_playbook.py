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


ROOT = Path(__file__).resolve().parent.parent
FEATURES = ("workstation", "browsers", "docker", "languages", "agents", "credentials")
OPTIONS = {
    "omarchy_browsers", "omarchy_languages", "omarchy_agents", "omarchy_credential_packages",
    "omarchy_foot_font_size", "omarchy_idle_mode", "omarchy_theme", "omarchy_layout_file", "omarchy_remove_layout",
}


def features(value):
    result = value.split(",")
    if not result or any(item not in FEATURES for item in result) or len(set(result)) != len(result):
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


def read_options(path, executable, temporary):
    if not path:
        return {}
    path = manager.require_file(path, "Explicit feature variables")
    inventory = temporary / "configuration-inventory.json"
    write_private(inventory, {"all": {"hosts": {"configuration": {}}}})
    result = subprocess.run(
        [str(executable), "-i", str(inventory), "--playbook-dir", str(temporary),
         "--list", "--extra-vars", "@" + str(path)],
        check=True, capture_output=True, text=True, cwd=temporary,
        env={**os.environ, "ANSIBLE_CONFIG": str(ROOT / "ansible.cfg"),
             "ANSIBLE_LOCAL_TEMP": str(temporary / "ansible-local")},
    )
    try:
        value = json.loads(result.stdout)["_meta"]["hostvars"]["configuration"]
    except (ValueError, KeyError, TypeError) as error:
        raise manager.WorkstationError("Unable to parse the explicit feature variables") from error
    if isinstance(value, dict) and value.get("ansible_local") == {}:
        value.pop("ansible_local")
    if not isinstance(value, dict) or set(value) - OPTIONS:
        raise manager.WorkstationError("Feature variables may contain only documented omarchy_* options; connection and internal state overrides are refused")
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


def playbook(args):
    if sys.platform != "darwin" or platform.machine() != "arm64":
        raise manager.WorkstationError("Run the playbook launcher on an Apple Silicon Mac")
    if not args.vm_name or len(args.vm_name.encode()) > 128 or any(ord(c) < 32 for c in args.vm_name):
        raise manager.WorkstationError("VM name must be a non-empty printable name")
    args.cli_path = manager.require_file(args.cli_path, "Omarchy VM Manager CLI", executable=True)
    ansible = shutil.which("ansible-playbook")
    inventory_tool = shutil.which("ansible-inventory")
    if not ansible or not inventory_tool:
        raise manager.WorkstationError("Existing ansible-playbook and ansible-inventory commands are required; no host tools are installed")
    with tempfile.TemporaryDirectory(prefix="dev-omarchy-ansible-") as folder:
        temporary = Path(folder)
        options = read_options(args.vars_file, inventory_tool, temporary)
        guest, connection = ready_connection(args)
        fixed = connection_values(guest, connection)
        inventory = temporary / "inventory.json"
        variables = temporary / "features.json"
        write_private(inventory, {"all": {"children": {"omarchy": {"hosts": {"workstation": fixed}}}}})
        write_private(variables, {**options, **fixed, "omarchy_features": args.features})
        command = [ansible, "-i", str(inventory), str(ROOT / "site.yml"),
                   "--tags", ",".join(args.features), "--extra-vars", "@" + str(variables)]
        if args.check:
            command.append("--check")
        print(f"Guest: {args.vm_name}\nFeatures: {', '.join(args.features)}\n"
              f"Variables: {args.vars_file or 'repository defaults'}\n"
              f"Mode: {'check (temporary payload only)' if args.check else 'apply'}\n"
              "Connection: VM Manager's authenticated, pinned SSH\n"
              "VM lifecycle and resource settings: unchanged", flush=True)
        if args.plan:
            return
        manager.confirm(args)
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
        print("Selected features complete. Use VM Manager for any required new login or restart.", flush=True)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--cli-path", type=Path, default=manager.DEFAULT_CLI)
    parser.add_argument("--vm-name", default="Dev Omarchy")
    parser.add_argument("--features", type=features, default=["workstation"])
    parser.add_argument("--vars-file", type=Path)
    parser.add_argument("--check", action="store_true")
    parser.add_argument("--plan", action="store_true")
    parser.add_argument("--yes", action="store_true")
    args = parser.parse_args()
    try:
        playbook(args)
    except (OSError, subprocess.CalledProcessError, manager.WorkstationError) as error:
        print(f"Omarchy playbook failed: {error}", file=sys.stderr)
        return 1
    except KeyboardInterrupt:
        return 130
    return 0


if __name__ == "__main__":
    sys.exit(main())
