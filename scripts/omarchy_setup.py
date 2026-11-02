#!/usr/bin/env python3
"""Plan and apply a workstation from an explicitly selected local setup repository."""

import argparse
import contextlib
import hashlib
import json
import os
import platform
import re
import shutil
import signal
import stat
import subprocess
import sys
import tempfile
from importlib import util
from pathlib import Path, PurePosixPath

import omarchy_playbook as playbook
import omarchy_vm_manager as manager
from omarchy_data import read_data
from omarchy_profiles import Resolver, fields, version

ROOT = Path(__file__).resolve().parents[1]
ENGINE_SOURCES = (
    "scripts/omarchy_setup.py", "scripts/omarchy_playbook.py", "scripts/omarchy_profiles.py",
    "scripts/omarchy_vm_manager.py", "scripts/omarchy_data.py", "setup.yml", "site.yml",
    "roles/omarchy_setup/tasks/main.yml", "roles/omarchy_setup/defaults/main.yml",
    "omarchy/guest/apply-dotfiles.py",
)


def engine_identity():
    return {"setup_api": 1, "sources": {name: hashlib.sha256((ROOT / name).read_bytes()).hexdigest()
                                         for name in ENGINE_SOURCES}}

_spec = util.spec_from_file_location("omarchy_dotfiles", ROOT / "omarchy/guest/apply-dotfiles.py")
dotfiles = util.module_from_spec(_spec)
_spec.loader.exec_module(dotfiles)


def items(value, label):
    if not isinstance(value, list):
        raise ValueError(f"{label} must be a list")
    return value


def local_path(root, value):
    if (not isinstance(value, str) or not value or PurePosixPath(value).is_absolute()
            or any(p in ("", ".", "..", ".git") for p in value.split("/"))
            or "\\" in value or any(ord(c) < 32 for c in value)):
        raise ValueError("Setup sources must be explicit relative paths inside the setup repository")
    path = root
    for part in value.split("/"):
        path = path / part
        if path.is_symlink():
            raise ValueError(f"Setup sources cannot be symlinks: {value}")
    if not path.exists():
        raise ValueError(f"Missing setup source: {value}")
    return path


class Setup:
    def __init__(self, root, manifest="vm.yml"):
        self.root = Path(root).expanduser().resolve(strict=True)
        self.roots = set()
        self.manifest = manifest
        path = self.source(manifest)
        value = fields(read_data(path), {"schema_version", "id", "vm", "setup", "dotfiles", "tasks", "assets", "vars"},
                       {"schema_version", "id"}, "setup repository manifest")
        version(value["schema_version"])
        self.id = value["id"]
        if not isinstance(self.id, str) or not re.fullmatch(r"[a-z][a-z0-9_-]{0,63}", self.id):
            raise ValueError("Setup id must be a stable lowercase name")
        self.vm = self.validate_vm(value.get("vm", {}))
        self.variables = value.get("vars", {})
        if not isinstance(self.variables, dict):
            raise ValueError("Setup vars must be a mapping")
        selection = fields(value.get("setup", {}), {"schema_version", "catalogues", "profiles", "features", "options"})
        selection = {"schema_version": 1, **selection}
        for catalogue in items(selection.get("catalogues", []), "catalogues"):
            self.source(catalogue)
        self.resolver = Resolver()
        self.plan = self.resolver.resolve(selection=selection, base_dir=self.root)
        for source in self.plan["sources"]:
            path = Path(source["path"])
            if path != playbook.contract.CATALOGUE_PATH:
                self.source(str(path.relative_to(self.root)))
        workstation = self.plan["options"].get("workstation", {})
        if workstation.get("layout"):
            workstation["layout"] = str(self.source(workstation["layout"]))
        self.dotfiles = []
        targets = set()
        for entry in items(value.get("dotfiles", []), "dotfiles"):
            fields(entry, {"source", "target", "mode"}, {"source", "target"}, "dotfile")
            source = self.source(entry["source"])
            target = dotfiles.relative_target(entry["target"])
            mode = entry.get("mode", "0644")
            if not isinstance(mode, str) or not re.fullmatch(r"0[0-7]{3}", mode):
                raise ValueError("Dotfile mode must be a quoted octal permission such as '0644'")
            files = self.walk(source)
            for path in files:
                destination = target if source.is_file() else target + "/" + path.relative_to(source).as_posix()
                destination = dotfiles.relative_target(destination)
                if destination in targets or any(destination.startswith(t + "/") or t.startswith(destination + "/") for t in targets):
                    raise ValueError("Dotfile destinations must not overlap")
                targets.add(destination)
                self.dotfiles.append({"source": str(path), "target": destination,
                                      "sha256": hashlib.sha256(path.read_bytes()).hexdigest(), "mode": int(mode, 8)})
        self.tasks = []
        names = set()
        for entry in items(value.get("tasks", []), "tasks"):
            fields(entry, {"name", "file"}, {"name", "file"}, "custom task")
            name = entry["name"]
            if not isinstance(name, str) or not re.fullmatch(r"[a-z][a-z0-9_-]*", name) or name in names or name == "all":
                raise ValueError("Custom tasks need unique lowercase names; 'all' is reserved")
            names.add(name)
            path = self.source(entry["file"])
            if not path.is_file():
                raise ValueError("Custom task entry points must be files")
            # Do not parse executable Ansible YAML through the plain-data loader.
            self.tasks.append({"name": name, "file": str(path), "tag": "setup." + name})
        for asset in items(value.get("assets", []), "assets"):
            self.source(asset)
        self.inputs = self.capture()
        self.engine = engine_identity()
        for source in self.plan["sources"]:
            self.resolver.verify_source(source)

    def source(self, value):
        path = local_path(self.root, value)
        self.roots.add(value)
        return path

    def walk(self, path):
        if path.is_symlink():
            raise ValueError("Setup assets cannot contain symlinks")
        if path.is_file():
            if path.stat().st_size > 32 * 1024 * 1024:
                raise ValueError("An individual setup asset exceeds 32 MiB")
            return [path]
        if not path.is_dir():
            raise ValueError("Setup assets must be regular files or directories")
        result = []
        for child in sorted(path.iterdir()):
            if child.name == ".git":
                raise ValueError("Select setup assets explicitly; .git directories cannot be included")
            result.extend(self.walk(child))
        return result

    def capture(self):
        result, size = {}, 0
        for name in sorted(self.roots):
            for path in self.walk(local_path(self.root, name)):
                relative = path.relative_to(self.root).as_posix()
                if relative in result:
                    continue
                data = path.read_bytes()
                size += len(data)
                if len(result) >= 4096 or size > 32 * 1024 * 1024:
                    raise ValueError("Setup inputs exceed 4096 files or 32 MiB; select smaller asset paths")
                result[relative] = (data, stat.S_IMODE(path.stat().st_mode) & 0o777)
        return result

    def verify(self):
        if self.capture() != self.inputs:
            raise ValueError("Setup inputs changed after planning; review a new proposal")
        if engine_identity() != self.engine:
            raise ValueError("Setup engine changed after planning; review a new proposal")
        for source in self.plan["sources"]:
            self.resolver.verify_source(source)

    @contextlib.contextmanager
    def snapshot(self):
        with tempfile.TemporaryDirectory(prefix="dev-omarchy-setup-") as directory:
            root = Path(directory)
            for relative, (data, mode) in self.inputs.items():
                path = root / relative
                path.parent.mkdir(parents=True, exist_ok=True)
                path.write_bytes(data)
                path.chmod(mode)
            frozen = Setup(root, self.manifest)
            # Factory images are verified by VM Manager, never copied into the input snapshot.
            frozen.vm = self.vm.copy()
            yield frozen

    def validate_vm(self, value):
        fields(value, {"name", "factory", "cpus", "memory_gib", "disk_gib", "packages", "lean_developer"}, label="VM configuration")
        result = {"name": "Dev Omarchy", "cpus": 8, "memory_gib": 20, "disk_gib": 64,
                  "packages": [], "lean_developer": False, **value}
        for key, low, high in (("cpus", 4, 128), ("memory_gib", 4, 1024), ("disk_gib", 64, 8192)):
            if key in result and (type(result[key]) is not int or not low <= result[key] <= high):
                raise ValueError(f"Invalid VM {key}; expected an integer from {low} to {high}")
        if "name" in result and (not isinstance(result["name"], str) or not result["name"]
                                 or len(result["name"].encode()) > 128 or any(ord(c) < 32 for c in result["name"])):
            raise ValueError("Invalid VM name")
        if "lean_developer" in result and type(result["lean_developer"]) is not bool:
            raise ValueError("lean_developer must be boolean")
        packages = items(result.get("packages", []), "VM packages")
        if any(not isinstance(package, str) or "," in package for package in packages):
            raise ValueError("VM packages must be individual package selectors")
        try:
            manager.parse_packages(",".join(packages))
        except argparse.ArgumentTypeError as error:
            raise ValueError(str(error)) from error
        if "factory" in result:
            factory = result["factory"]
            if (not isinstance(factory, str) or not factory or len(factory.encode()) > 4096
                    or any(ord(c) < 32 for c in factory)):
                raise ValueError("Factory must be official, a manifest hash or a local path")
            if factory != "official" and not re.fullmatch(r"[a-f0-9]{64}", factory):
                factory = str((self.root / Path(factory).expanduser()).resolve())
            result["factory"] = manager.parse_factory(factory)
        return result

    def proposal(self):
        value = {"schema_version": 1, "id": self.id, "engine": self.engine, "vm": self.vm, "features": self.plan,
                "dotfiles": self.dotfiles, "tasks": self.tasks,
                "inputs": [{"path": p, "sha256": hashlib.sha256(data).hexdigest(), "mode": mode}
                           for p, (data, mode) in sorted(self.inputs.items())],
                "custom_task_effects": "Opaque trusted Ansible code; may execute on the host as well as the guest"}
        def relative(item):
            if isinstance(item, dict):
                return {key: relative(value) for key, value in item.items()}
            if isinstance(item, list):
                return [relative(value) for value in item]
            if isinstance(item, str) and item.startswith(str(self.root) + os.sep):
                return str(Path(item).relative_to(self.root))
            return item
        return relative(value)


def task_selection(setup, selected):
    available = {task["name"] for task in setup.tasks}
    if selected is None:
        return setup.tasks
    names = selected.split(",") if selected else []
    if len(set(names)) != len(names) or set(names) - available:
        raise ValueError("Select unique custom task names declared in the manifest")
    return [task for task in setup.tasks if task["name"] in names]


def require_task_trust(args, tasks):
    if tasks and not args.trust_tasks:
        raise ValueError("Custom tasks are executable Ansible code with host access. Review them and explicitly pass --trust-tasks (OMARCHY_SETUP_TRUST_TASKS=yes)")


def execute(setup, args, guest, connection, ansible):
    tasks = task_selection(setup, args.tasks)
    # Check mode never executes external tasks unless explicitly requested as well as trusted.
    tasks = tasks if not args.check or args.check_tasks else []
    require_task_trust(args, tasks)
    with tempfile.TemporaryDirectory(prefix="dev-omarchy-run-") as directory:
        temporary = Path(directory)
        command = playbook.execution_command(temporary, setup.plan, guest, connection, ansible, check=args.check)
        if not args.check:
            # Also apply vm.packages on existing guests; bootstrap has already ensured them.
            manager.install_selected_software(connection, manager.parse_packages(",".join(setup.vm.get("packages", []))))
        if setup.plan["features"]:
            subprocess.run(command, check=True, cwd=ROOT)
        if not args.check and setup.plan["options"].get("docker", {}).get("access") == "sudoless":
            playbook.enable_owner_docker(connection)
        custom = temporary / "setup.json"
        value = {"omarchy_setup_id": setup.id, "omarchy_setup_files": setup.dotfiles,
                 "omarchy_setup_tasks": tasks, "omarchy_setup_dir": str(setup.root),
                 "omarchy_setup_vars": setup.variables, "omarchy_setup_conflict": args.dotfiles_conflict,
                 "omarchy_setup_record": {"id": setup.id, "engine": setup.engine,
                                          "inputs": setup.proposal()["inputs"], "tasks": [t["name"] for t in tasks],
                                          "features": setup.plan["features"], "vm": setup.vm}}
        playbook.write_private(custom, value)
        # Keep pinned connection parameters, but allow trusted task-level become keywords.
        custom_command = command.copy()
        custom_command[custom_command.index(str(ROOT / "site.yml"))] = str(ROOT / "setup.yml")
        custom_command[custom_command.index("--tags") + 1] = ",".join(["dotfiles", "setup-record"] + [t["tag"] for t in tasks])
        task_connection = temporary / "task-connection.json"
        fixed = playbook.connection_values(guest, connection)
        # Task-level become is allowed for trusted tasks; the play still defaults to the owner.
        fixed.pop("ansible_become")
        playbook.write_private(task_connection, fixed)
        task_inventory = temporary / "task-inventory.json"
        playbook.write_private(task_inventory, {"all": {"children": {"omarchy": {"hosts": {"workstation": fixed}}}}})
        custom_command[custom_command.index("-i") + 1] = str(task_inventory)
        custom_command[custom_command.index("--extra-vars") + 1] = "@" + str(task_connection)
        custom_command += ["--extra-vars", "@" + str(custom)]
        subprocess.run(custom_command, check=True, cwd=ROOT)


def after_revoke(setup, connection):
    if setup.plan["options"].get("docker", {}).get("access") == "sudoless":
        playbook.verify_owner_docker(connection)


def bootstrap_args(setup, args):
    values = setup.vm
    command = ["--vm-name", args.vm_name or values.get("name", "Dev Omarchy")]
    for key in ("cpus", "memory_gib", "disk_gib", "factory"):
        value = getattr(args, key, None)
        if value is None:
            value = values.get(key)
        if value is not None:
            command += ["--" + key.replace("_", "-"), str(value)]
    command += ["--packages", ",".join(values.get("packages", []))]
    if values.get("lean_developer"):
        command += ["--lean-developer"]
    preferences = setup.plan["options"].get("workstation", {})
    for key, flag in (("font_size", "foot-font-size"), ("idle_mode", "idle-mode"), ("theme", "theme"), ("layout", "layout-file")):
        if preferences.get(key):
            command += ["--" + flag, str(preferences[key])]
    if preferences.get("remove_layout"):
        command += ["--remove-layout"]
    if args.cli_path:
        command += ["--cli-path", str(args.cli_path)]
    if args.manager_app:
        command += ["--manager-app", str(args.manager_app)]
    if args.yes:
        command += ["--yes"]
    return manager.build_parser().parse_args(command + ["bootstrap"])


def run(args):
    if getattr(args, "unsupported_option", None):
        raise ValueError("External setups do not accept these legacy overrides: " + ", ".join(args.unsupported_option)
                         + ". Move selections into the manifest or use the documented OMARCHY_SETUP_* options.")
    original = Setup(args.repo, args.manifest)
    overrides = {key: getattr(args, key) for key in ("cpus", "memory_gib", "disk_gib", "factory")
                 if getattr(args, key) is not None}
    if args.vm_name:
        overrides["name"] = args.vm_name
    if args.factory and args.factory != "official" and not re.fullmatch(r"[a-f0-9]{64}", args.factory):
        args.factory = str(Path(args.factory).expanduser().resolve())
        overrides["factory"] = args.factory
    original.vm = original.validate_vm({**original.vm, **overrides})
    with original.snapshot() as setup:
        tasks = task_selection(setup, args.tasks)
        proposal = setup.proposal()
        proposal["tasks"] = [task for task in proposal["tasks"] if task["name"] in {t["name"] for t in tasks}]
        proposal["repository"] = str(original.root)
        proposal["mode"] = args.command
        proposal["check"] = args.check
        proposal["custom_tasks_in_check"] = bool(args.check_tasks)
        proposal["tasks_skipped_in_check"] = [t["name"] for t in tasks] if args.check and not args.check_tasks else []
        proposal["dotfiles_conflict"] = args.dotfiles_conflict
        print(json.dumps(proposal, indent=2), flush=True)
        if args.command == "plan":
            return
        if args.check_tasks and not args.check:
            raise ValueError("--check-tasks requires --check")
        if args.command == "bootstrap" and args.check:
            raise ValueError("Bootstrap changes VM lifecycle; use apply --check instead")
        require_task_trust(args, tasks if not args.check or args.check_tasks else [])
        if sys.platform != "darwin" or platform.machine() != "arm64":
            raise ValueError("Run setup on an Apple Silicon Mac")
        ansible = shutil.which("ansible-playbook")
        if not ansible:
            raise ValueError("An existing ansible-playbook is required; no host software is installed")

        def verify():
            original.verify()
            setup.verify()

        if args.command == "bootstrap":
            native = bootstrap_args(setup, args)
            native.setup_proposal = "External setup: " + setup.id + "; dotfiles and custom tasks follow workstation features."
            native.setup_verify = verify
            native.setup_apply = lambda guest, connection: execute(setup, args, guest, connection, ansible)
            native.setup_after_revoke = lambda connection: after_revoke(setup, connection)
            manager.bootstrap_command(native)
            return
        args.vm_name = args.vm_name or setup.vm.get("name", "Dev Omarchy")
        args.cli_path = manager.require_file(manager.installed_cli(args.cli_path, args.manager_app), "Omarchy VM Manager CLI", executable=True)
        guest, connection = playbook.ready_connection(args)
        manager.confirm(args)
        verify()
        if args.check:
            execute(setup, args, guest, connection, ansible)
            return

        def interrupted(signum, _frame):
            raise manager.WorkstationError(f"Setup interrupted by {signal.Signals(signum).name}")

        previous = {s: signal.signal(s, interrupted) for s in (signal.SIGTERM, signal.SIGHUP)}
        try:
            try:
                manager.enable_bootstrap_sudo(connection)
                execute(setup, args, guest, connection, ansible)
            except BaseException:
                try:
                    manager.disable_bootstrap_sudo(connection)
                except manager.WorkstationError as error:
                    print(f"Warning: {error}", file=sys.stderr, flush=True)
                raise
            else:
                manager.disable_bootstrap_sudo(connection)
                after_revoke(setup, connection)
        finally:
            for signum, handler in previous.items():
                signal.signal(signum, handler)
        manager.note("External setup complete. Use VM Manager for any required restart or new login.")


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("command", choices=("plan", "apply", "bootstrap"))
    parser.add_argument("--repo", type=Path, required=True)
    parser.add_argument("--manifest", default="vm.yml")
    parser.add_argument("--vm-name")
    parser.add_argument("--cli-path", type=Path)
    parser.add_argument("--manager-app", type=Path)
    parser.add_argument("--cpus", type=int)
    parser.add_argument("--memory-gib", type=int)
    parser.add_argument("--disk-gib", type=int)
    parser.add_argument("--factory")
    parser.add_argument("--tasks", help="Comma-separated task names; empty selects no custom tasks")
    parser.add_argument("--trust-tasks", action="store_true")
    parser.add_argument("--check", action="store_true")
    parser.add_argument("--check-tasks", action="store_true")
    parser.add_argument("--dotfiles-conflict", choices=("fail", "backup"), default="fail")
    parser.add_argument("--yes", action="store_true")
    parser.add_argument("--unsupported-option", action="append", help=argparse.SUPPRESS)
    try:
        run(parser.parse_args())
    except (OSError, ValueError, manager.WorkstationError, subprocess.CalledProcessError) as error:
        print(f"Omarchy setup failed: {error}", file=sys.stderr)
        return 1
    except KeyboardInterrupt:
        print("Omarchy setup interrupted.", file=sys.stderr)
        return 130
    return 0


if __name__ == "__main__":
    sys.exit(main())
