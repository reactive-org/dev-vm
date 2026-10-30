#!/usr/bin/env python3
"""Parallels NixOS controller; all Nix evaluation and installation runs in Linux."""
import argparse
import getpass
import hashlib
import ipaddress
import json
import os
from pathlib import Path
import re
import shlex
import shutil
import subprocess
import sys
import tempfile
import time
import uuid

from nixos_media import copy_tree, prepare_iso, source_archive

PROJECT = Path(__file__).resolve().parent.parent


class GuestChannelError(RuntimeError):
    pass


class HostKeyError(RuntimeError):
    pass


def run(argv, **kwargs):
    return subprocess.run([str(x) for x in argv], check=True, **kwargs)


def output(argv, **kwargs):
    return subprocess.check_output([str(x) for x in argv], text=True, **kwargs).strip()


def require(condition, message):
    if not condition:
        raise ValueError(message)


def vm_info(args):
    records = json.loads(output([args.prlctl, "list", "--all", "--json"]))
    matches = [record for record in records if record.get("Name", record.get("name")) == args.name]
    require(len(matches) == 1, "Expected exactly one registered VM named " + args.name)
    return json.loads(output([args.prlctl, "list", "-i", args.name, "--json"]))[0]


def guest_root(args, command, retry=False, **kwargs):
    # prlctl exec flattens arguments to a guest shell. Quote every argument,
    # and pass all operator settings in a data file rather than shell text.
    # Give SDK diagnostics a separate descriptor so its terminal handling cannot
    # interfere with the controller's potentially large error reports.
    kwargs.setdefault("stderr", subprocess.PIPE)
    for attempt in range(5 if retry else 1):
        try:
            value = output([args.prlctl, "exec", args.name] + [shlex.quote(str(x)) for x in command], timeout=25, **kwargs)
            if value.startswith(("Unable to open new session", "PrlJob_", "PrlVm_")):
                raise GuestChannelError("Parallels guest administration channel is not ready")
            return value
        except (subprocess.CalledProcessError, subprocess.TimeoutExpired, GuestChannelError):
            if not retry or attempt == 4:
                raise
            time.sleep(min(3, 0.5 * (2 ** attempt)))


def new_artifact(args, label):
    parent = args.artifacts.expanduser().resolve()
    require(parent != args.source and args.source not in parent.parents, "ARTIFACTS_DIR must be outside the NixOS source tree")
    parent.mkdir(parents=True, exist_ok=True, mode=0o700)
    folder = parent / (label + "-" + uuid.uuid4().hex)
    folder.mkdir(mode=0o700)
    return folder


def default_key():
    for name in ("id_ed25519.pub", "id_ecdsa.pub", "id_rsa.pub"):
        candidate = Path.home() / ".ssh" / name
        if candidate.is_file():
            return str(candidate)
    return ""


def public_key(args):
    path = Path(args.ssh_key or default_key()).expanduser()
    require(path.is_file(), "Set SSH_PUBLIC_KEY to an existing authorized public key")
    fields = path.read_text().strip().split()
    require(len(fields) >= 2 and re.fullmatch(r"(ssh-ed25519|ssh-rsa|ecdsa-sha2-nistp\d+|sk-\S+)", fields[0]), "Invalid SSH public key")
    run(["ssh-keygen", "-l", "-f", path], stdout=subprocess.DEVNULL)
    return path, " ".join(fields[:2]) + "\n"


def ssh_options(args, host, key, known):
    identity = key.with_suffix("") if key.suffix == ".pub" and key.with_suffix("").is_file() else key
    return ["-o", "BatchMode=yes", "-o", "ConnectTimeout=5", "-o", "ConnectionAttempts=1",
            "-o", "StrictHostKeyChecking=yes", "-o", "GlobalKnownHostsFile=/dev/null",
            "-o", "HostKeyAlgorithms=ssh-ed25519", "-o", "UserKnownHostsFile=" + str(known),
            "-o", "IdentitiesOnly=yes", "-i", str(identity)]


def connect(args, artifact):
    key, _ = public_key(args)
    deadline = time.monotonic() + args.timeout
    next_report = 0
    while time.monotonic() < deadline:
        try:
            host = args.ssh_host
            if not host:
                raw = output([args.prlctl, "list", "--full", "--output", "ip", "--no-header", args.name])
                for token in raw.replace(",", " ").split():
                    try:
                        address = ipaddress.ip_address(token)
                        if address.version == 4 and not address.is_loopback:
                            host = str(address)
                            break
                    except ValueError:
                        continue
            require(host and re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9.:-]*", host), "Waiting for the selected VM's address")
            # Enrol the host key through the hypervisor's authenticated guest
            # channel. No accept-new, keyscan trust, or global known_hosts edits.
            line = guest_root(args, ["/run/current-system/sw/bin/cat", "/etc/ssh/ssh_host_ed25519_key.pub"], stderr=subprocess.DEVNULL)
            fields = line.split()
            require(len(fields) >= 2 and fields[0] == "ssh-ed25519", "Guest host key unavailable")
            known = Path(args.known_hosts).expanduser() if args.known_hosts else artifact / "known_hosts"
            if args.known_hosts:
                try:
                    entries = output(["ssh-keygen", "-F", host, "-f", known])
                except subprocess.CalledProcessError as error:
                    raise HostKeyError("Provided known-hosts file has no entry for the selected VM address") from error
                if not any(row.split()[1:3] == fields[:2] for row in entries.splitlines() if row and not row.startswith("#")):
                    raise HostKeyError("Provided known-hosts file does not match the selected VM")
            else:
                known.write_text(host + " " + " ".join(fields[:2]) + "\n")
                known.chmod(0o600)
            options = ssh_options(args, host, key, known)
            target = args.user + "@" + host
            run(["ssh"] + options + [target, "true"], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, timeout=10)
            return options, target
        except (ValueError, subprocess.CalledProcessError, subprocess.TimeoutExpired, GuestChannelError):
            now = time.monotonic()
            if now >= next_report:
                print("Waiting for guest Tools and verified key-based SSH...", flush=True)
                next_report = now + 30
            time.sleep(3)
    raise TimeoutError("Guest Tools and verified SSH did not become ready; inspect the VM console")


def wait_job(args, job):
    deadline = time.monotonic() + args.timeout
    previous = None
    report_at = 0
    while time.monotonic() < deadline:
        try:
            state = guest_root(args, ["/run/current-system/sw/bin/cat", "/var/lib/nixos-workstation/jobs/" + job + "/status"], stderr=subprocess.DEVNULL)
            if state and (state != previous or time.monotonic() >= report_at):
                print("Deployment: " + state, flush=True)
                previous = state
                report_at = time.monotonic() + 30
            if state == "success":
                return
            if state == "failed":
                print(guest_root(args, ["/run/current-system/sw/bin/tail", "-n", "35", "/var/lib/nixos-workstation/jobs/" + job + "/log"]), file=sys.stderr)
                raise RuntimeError("Guest deployment failed; inspect the log above for validation or rollback status")
        except (subprocess.CalledProcessError, subprocess.TimeoutExpired, GuestChannelError):
            pass  # The guest channel may restart during a Tools update.
        time.sleep(2)
    raise TimeoutError("Deployment is still running or unreachable; use make nixos-status to inspect it")


def apply(args):
    info = vm_info(args)
    if info["State"] != "running":
        run([args.prlctl, "start", args.name])
    artifact = new_artifact(args, "apply")
    options, target = connect(args, artifact)
    # Refuse non-NixOS targets before staging any source or root worker.
    check = 'test "$(uname -m)" = aarch64 && . /etc/os-release && test "$ID" = nixos'
    run(["ssh"] + options + [target, check])
    deployment = uuid.uuid4().hex
    remote = "/tmp/nixos-deploy-" + deployment
    digest = source_archive(args.source, artifact / "source.tar")
    shutil.copyfile(args.source / "automation/apply.sh", artifact / "apply-worker.sh")
    copy_tree(args.source / "local", artifact / "default-local")
    request = {"FLAKE_HOST": args.flake_host, "GUEST_USER": args.user,
               "LOCAL_ACTION": "replace" if args.local_flake else "preserve", "SOURCE_SHA256": digest,
               "APPLY_ACTION": "build" if args.build_only else "switch"}
    (artifact / "request.sh").write_text("\n".join(key + "=" + shlex.quote(value) for key, value in request.items()) + "\n")
    if args.local_flake:
        copy_tree(Path(args.local_flake).expanduser(), artifact / "local")
    run(["ssh"] + options + [target, "umask 077; mkdir " + shlex.quote(remote)])
    run(["scp"] + options + [str(artifact / name) for name in ("source.tar", "apply-worker.sh", "request.sh")] + [target + ":" + remote + "/"])
    run(["scp", "-r"] + options + [str(artifact / "default-local"), target + ":" + remote + "/"])
    if args.local_flake:
        run(["scp", "-r"] + options + [str(artifact / "local"), target + ":" + remote + "/"])
    job = guest_root(args, ["/run/current-system/sw/bin/bash", remote + "/apply-worker.sh", remote], retry=True).splitlines()[-1]
    require(re.fullmatch(r"[a-f0-9]{32}", job), "Invalid deployment job returned by guest")
    (artifact / "deployment.json").write_text(json.dumps({"vm": args.name, "job": job}, indent=2) + "\n")
    print("Started deployment " + job, flush=True)
    wait_job(args, job)
    run(["ssh"] + options + [target, "if systemctl --user is-active --quiet graphical-session.target; then hyprctl -i 0 configerrors; fi"])
    print("Build-only validation passed." if args.build_only else "NixOS applied successfully. Current login sessions were preserved.")


def password_hash(args):
    if args.password_hash_file:
        path = Path(args.password_hash_file).expanduser().resolve()
        roots = [args.source] + ([Path(args.local_flake).expanduser().resolve()] if args.local_flake else [])
        require(not any(root == path or root in path.parents for root in roots), "Password-hash file must be outside all Nix source/local-input trees")
        require(path.stat().st_mode & 0o077 == 0, "Password-hash file must have mode 0600 or stricter")
        hashed = path.read_text().strip()
    else:
        password = getpass.getpass("Guest login/sudo password: ")
        require(password and password == getpass.getpass("Confirm guest password: "), "Passwords are empty or do not match")
        require(len(password.encode()) <= 72, "bcrypt passwords must be at most 72 UTF-8 bytes")
        result = subprocess.run(["/usr/sbin/htpasswd", "-niB", "-C", "12", ""], input=password + "\n", text=True, check=True, capture_output=True)
        hashed = result.stdout.split(":", 1)[1].strip()
        del password
    require(re.fullmatch(r"\$2[aby]\$\d{2}\$[./A-Za-z0-9]{53}", hashed), "Expected a bcrypt password hash")
    return hashed


def images(args):
    root = Path(args.downloads).expanduser()
    candidates = sorted(root.rglob("*aarch64-linux.iso"), key=lambda p: p.stat().st_mtime, reverse=True)
    for candidate in candidates:
        print(candidate)
    return candidates


def prepare(args, artifact):
    payload = artifact / "payload"
    payload.mkdir(mode=0o700)
    token = uuid.uuid4().hex
    (payload / "token").write_text(token + "\n")
    _, key = public_key(args)
    hashed = password_hash(args)
    copy_tree(args.source, payload / "source")
    (payload / "authorized-key.pub").write_text(key)
    (payload / "password.hash").write_text(hashed + "\n")
    del hashed
    manifest = {"INSTALL_TOKEN": token, "GUEST_USER": args.user, "GUEST_HOSTNAME": args.hostname,
                "DISK": "/dev/sda", "SHARED_FOLDER": "true" if args.share else "false"}
    (payload / "manifest.sh").write_text("\n".join(key + "=" + shlex.quote(value) for key, value in manifest.items()) + "\n")
    if args.local_flake:
        copy_tree(Path(args.local_flake).expanduser(), payload / "local")
    iso = artifact / "installer-aarch64-linux.iso"
    prepare_iso(args.image, iso, payload, artifact)
    print("Private installer media ready: " + str(iso), flush=True)
    return iso, token


def bootstrap(args):
    inventory = json.loads(output([args.prlctl, "list", "--all", "--json"]))
    require(not any(vm.get("Name", vm.get("name")) == args.name for vm in inventory), "VM already exists; bootstrap never installs over an existing VM")
    if not args.image:
        candidates = images(args)
        require(candidates, "Set IMAGE to an accessible official NixOS ARM64 ISO")
        args.image = str(candidates[0])
    args.image = str(Path(args.image).expanduser().resolve())
    require(Path(args.image).is_file(), "Installer ISO does not exist")
    if args.image_sha256:
        digest = hashlib.sha256()
        with open(args.image, "rb") as image:
            for chunk in iter(lambda: image.read(1024 * 1024), b""):
                digest.update(chunk)
        require(digest.hexdigest() == args.image_sha256.lower(), "Source ISO checksum does not match IMAGE_SHA256")
    args.share = (Path.home() / "Parallels/Shared").is_dir() and not args.no_share
    print("Create: " + args.name)
    print("ISO: " + args.image)
    print("User/hostname: " + args.user + " / " + args.hostname)
    print(f"ARM64 EFI; {args.cpus} CPUs; {args.memory} MB RAM; {args.disk} GB expanding disk")
    print("Install target: only the new blank /dev/sda; existing VMs and nonblank disks are refused")
    print("Explicit ~/Parallels/Shared: " + ("read-write at /mnt/shared; enables guest FUSE user_allow_other" if args.share else "disabled"))
    print("No passwordless-sudo provisioning rule; host software is not installed by this workflow")
    require(input("Type create to confirm this VM proposal: ").strip() == "create", "Cancelled")
    artifact = new_artifact(args, "install")
    iso, token = prepare(args, artifact)
    environment = os.environ.copy()
    environment["NIXOS_CONFIRMED_CREATE"] = args.name
    environment["NIXOS_SKIP_SHARE"] = "no" if args.share else "yes"
    (artifact / "serial.log").touch(mode=0o600)
    environment["NIXOS_SERIAL_LOG"] = str(artifact / "serial.log")
    run(["bash", PROJECT / "scripts/bootstrap-nixos.sh", args.prlctl, args.name, iso,
         args.cpus, args.memory, args.disk], env=environment)
    metadata = {"vm_id": vm_info(args)["ID"], "vm": args.name, "user": args.user, "token": token}
    (artifact / "bootstrap.json").write_text(json.dumps(metadata, indent=2) + "\n")
    finish_install(args, artifact, token)


def finish_install(args, artifact, token, already_installed=False):
    if not already_installed:
        deadline, report = time.monotonic() + args.timeout, 0
        while time.monotonic() < deadline:
            if vm_info(args)["State"] == "stopped":
                break
            if time.monotonic() >= report:
                print("Installing inside the new VM; waiting for successful installer poweroff...", flush=True)
                report = time.monotonic() + 30
            time.sleep(5)
        else:
            raise TimeoutError("Installer did not power off. Inspect the VM console; private media retained at " + str(artifact))
    run([args.prlctl, "set", args.name, "--device-set", "cdrom0", "--disconnect"])
    if vm_info(args)["State"] != "running":
        run([args.prlctl, "start", args.name])
    options, target = connect(args, artifact)
    installed = guest_root(args, ["/run/current-system/sw/bin/cat", "/var/lib/nixos-workstation/install-token"], retry=True)
    require(installed == token, "Installed VM marker does not match this bootstrap")
    for user, expected in ((args.user, "P"), ("root", "L")):
        status = guest_root(args, ["/run/current-system/sw/bin/passwd", "-S", user], retry=True).split()
        require(len(status) >= 2 and status[1] == expected, "Installed account password/lock state is incorrect")
    sudo_check = subprocess.run(["ssh"] + options + [target, "sudo -n -k true"], capture_output=True)
    require(sudo_check.returncode != 0, "Installed sudo unexpectedly works without the selected password")
    run(["ssh"] + options + [target, "for unit in sshd prltoolsd greetd; do systemctl is-active --quiet \"$unit\" || exit 1; done"])
    # Apply the captured source through the same transactional path as later
    # updates, including its full checks and Lua parser check. Preserve the
    # private local input already installed from this media snapshot.
    deployment_args = argparse.Namespace(**vars(args))
    deployment_args.source = artifact / "payload/source"
    deployment_args.local_flake = ""
    deployment_args.build_only = False
    apply(deployment_args)
    # Detach before deleting credential-bearing media. On failure it remains in
    # the private artifact directory for explicit recovery, never in Git/Nix.
    (artifact / "installer-aarch64-linux.iso").unlink(missing_ok=True)
    shutil.rmtree(artifact / "payload")
    (artifact / "efi.img").unlink(missing_ok=True)
    metadata = json.loads((artifact / "bootstrap.json").read_text())
    metadata["phase"] = "complete"
    (artifact / "bootstrap.json").write_text(json.dumps(metadata, indent=2) + "\n")
    print("NixOS installed; verified SSH and graphical login service are ready.")
    print("Log into the VM with the selected account and your password. Enable app integrations/sign-ins manually.")


def resume(args):
    require(args.resume_dir, "Set NIXOS_RESUME_DIR to this workflow's private install directory")
    artifact = Path(args.resume_dir).expanduser().resolve()
    metadata = json.loads((artifact / "bootstrap.json").read_text())
    require(args.name == metadata["vm"], "VM_NAME does not match the original confirmed bootstrap")
    info = vm_info(args)
    require(info["ID"] == metadata["vm_id"], "Resume requires the same workflow-created VM")
    args.user = metadata["user"]
    if metadata.get("phase") == "complete" or not (artifact / "payload/source").is_dir():
        print("Bootstrap already completed; use make apply-nixos for later updates.")
        return
    iso = artifact / "installer-aarch64-linux.iso"
    if args.retry_blank:
        require(info["State"] == "stopped" and iso.is_file(), "Blank-disk retry requires the same VM stopped and its private media present")
        print("Retrying only the original confirmed VM; the installer still refuses a nonblank disk.", flush=True)
        run([args.prlctl, "set", args.name, "--device-set", "cdrom0", "--image", iso, "--connect"])
        run([args.prlctl, "start", args.name])
        finish_install(args, artifact, metadata["token"])
    else:
        ready = info["State"] == "stopped" or info.get("GuestTools", {}).get("state") == "installed"
        finish_install(args, artifact, metadata["token"], already_installed=ready)


def main():
    os.umask(0o077)
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("action", choices=["bootstrap", "resume", "apply", "images", "status", "prepare-iso"])
    parser.add_argument("--prlctl", default=os.environ.get("PRLCTL") or "/usr/local/bin/prlctl")
    parser.add_argument("--name", default=os.environ.get("VM_NAME") or "")
    parser.add_argument("--source", type=Path, default=PROJECT / "nixos")
    parser.add_argument("--image", default=os.environ.get("IMAGE", ""))
    parser.add_argument("--image-sha256", default=os.environ.get("IMAGE_SHA256", ""))
    parser.add_argument("--downloads", default=os.environ.get("DOWNLOADS_DIR") or str(Path.home() / "Downloads"))
    parser.add_argument("--cpus", type=int, default=int(os.environ.get("CPUS") or 4))
    parser.add_argument("--memory", type=int, default=int(os.environ.get("MEMORY_MB") or 12288))
    parser.add_argument("--disk", type=int, default=int(os.environ.get("DISK_GB") or 24))
    parser.add_argument("--user", default=os.environ.get("GUEST_USER") or "developer")
    parser.add_argument("--hostname", default=os.environ.get("GUEST_HOSTNAME", ""))
    parser.add_argument("--ssh-key", default=os.environ.get("SSH_PUBLIC_KEY", ""))
    parser.add_argument("--ssh-host", default=os.environ.get("SSH_HOST", ""))
    parser.add_argument("--known-hosts", default=os.environ.get("SSH_KNOWN_HOSTS_FILE", ""))
    parser.add_argument("--timeout", type=int, default=int(os.environ.get("SSH_WAIT_TIMEOUT") or 2700))
    parser.add_argument("--flake-host", default=os.environ.get("NIXOS_HOST") or "workstation-test")
    parser.add_argument("--local-flake", default=os.environ.get("LOCAL_FLAKE", ""))
    parser.add_argument("--artifacts", type=Path, default=Path(os.environ.get("ARTIFACTS_DIR") or PROJECT / ".artifacts/nixos"))
    parser.add_argument("--password-hash-file", default=os.environ.get("NIXOS_PASSWORD_HASH_FILE", ""))
    parser.add_argument("--no-share", action="store_true", default=os.environ.get("NIXOS_SHARE") == "no")
    parser.add_argument("--build-only", action="store_true", default=os.environ.get("NIXOS_BUILD_ONLY") == "yes")
    parser.add_argument("--resume-dir", default=os.environ.get("NIXOS_RESUME_DIR", ""))
    parser.add_argument("--retry-blank", action="store_true", default=os.environ.get("NIXOS_RETRY_BLANK") == "yes")
    args = parser.parse_args()
    if not args.name and args.action not in ("apply", "status", "resume"):
        args.name = "NixOS Workstation"
    args.source = args.source.expanduser().resolve()
    require((args.source / "flake.lock").is_file(), "Pinned NixOS source and flake.lock required")
    require((args.source / "hosts" / args.flake_host / "default.nix").is_file(), "Unknown NIXOS_HOST")
    if args.action in ("bootstrap", "prepare-iso", "resume"):
        require(args.flake_host == "workstation-test", "The initial unattended installer uses NIXOS_HOST=workstation-test")
    require(re.fullmatch(r"[a-z_][a-z0-9_-]*", args.user), "Invalid GUEST_USER")
    require(re.fullmatch(r"[A-Za-z0-9_-]+", args.flake_host), "Invalid NIXOS_HOST")
    require(args.cpus > 0 and args.memory >= 2048 and args.disk >= 24 and args.timeout > 0, "Invalid resource sizing or timeout")
    require(args.name and not any(ord(character) < 32 for character in args.name), "Invalid VM name")
    if not args.hostname:
        args.hostname = re.sub(r"[^a-z0-9-]+", "-", args.name.lower()).strip("-")[:63].rstrip("-")
    require(re.fullmatch(r"[a-z0-9][a-z0-9-]{0,62}", args.hostname), "Invalid GUEST_HOSTNAME")
    if args.action == "images":
        images(args)
    elif args.action == "apply":
        apply(args)
    elif args.action == "status":
        vm_info(args)
        job = guest_root(args, ["/run/current-system/sw/bin/cat", "/var/lib/nixos-workstation/latest-job"])
        require(re.fullmatch(r"[a-f0-9]{32}", job), "Invalid deployment ID")
        print("Deployment " + job + ": " + guest_root(args, ["/run/current-system/sw/bin/cat", "/var/lib/nixos-workstation/jobs/" + job + "/status"]))
    elif args.action == "prepare-iso":
        require(args.image, "Set IMAGE")
        args.share = (Path.home() / "Parallels/Shared").is_dir() and not args.no_share
        prepare(args, new_artifact(args, "prepared"))
    elif args.action == "resume":
        resume(args)
    else:
        bootstrap(args)


if __name__ == "__main__":
    try:
        main()
    except (ValueError, OSError, RuntimeError, subprocess.CalledProcessError, subprocess.TimeoutExpired) as error:
        print("NixOS workflow failed: " + str(error), file=sys.stderr)
        sys.exit(1)
    except KeyboardInterrupt:
        print("Cancelled. The VM and private recovery artifacts were retained.", file=sys.stderr)
        sys.exit(130)
