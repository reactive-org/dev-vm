#!/usr/bin/env python3
"""Create and configure an unattended Omarchy ARM64 Parallels VM."""

import argparse
import getpass
import hashlib
import ipaddress
import json
import os
import re
import shlex
import shutil
import subprocess
import sys
import tempfile
import time
import uuid
from pathlib import Path


PROJECT_DIR = Path(__file__).resolve().parent.parent
GUEST_PAYLOAD_DIR = PROJECT_DIR / "omarchy" / "guest"
DEFAULT_MANIFEST_URL = "https://nightly.omarchy.org/edge-aarch64/latest.json"
DEFAULT_PRLCTL = "/usr/local/bin/prlctl"
DEFAULT_TOOLS_ISO = (
    "/Applications/Parallels Desktop.app/Contents/Resources/Tools/"
    "prl-tools-lin-arm.iso"
)
DEFAULT_ARTIFACTS_DIR = PROJECT_DIR / ".artifacts" / "omarchy"
DEFAULT_DISPLAY_MODE = "4096x2160@60"
DEFAULT_SHARE_PATH = Path.home() / "Parallels" / "Shared"
DEFAULT_SHARE_NAME = "Shared"
DEFAULT_WINDOW_SIZE = 75
WINDOW_SIZE_ACTIONS = {
    50: "center-half",
    67: "center-two-thirds",
    75: "center-three-fourths",
    100: "maximize",
}


class OmarchyError(RuntimeError):
    pass


def note(message):
    print(f"==> {message}", flush=True)


def run(argv, *, capture=False, input_text=None, check=True, timeout=None):
    options = {"check": False, "text": True, "timeout": timeout}
    if capture:
        options.update(stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    if input_text is not None:
        options["input"] = input_text
    try:
        result = subprocess.run(list(argv), **options)
    except subprocess.TimeoutExpired as error:
        if not check:
            return subprocess.CompletedProcess(list(argv), 124, "", "timed out")
        command = " ".join(shlex.quote(part) for part in argv)
        raise OmarchyError(
            f"Command timed out after {error.timeout} seconds: {command}"
        ) from error
    if check and result.returncode != 0:
        detail = ""
        if capture:
            detail = (result.stderr or result.stdout or "").strip()
        if detail:
            raise OmarchyError(f"Command failed ({result.returncode}): {detail}")
        command = " ".join(shlex.quote(part) for part in argv)
        raise OmarchyError(f"Command failed ({result.returncode}): {command}")
    return result


def require_executable(path_or_name):
    if "/" in path_or_name:
        path = Path(path_or_name).expanduser()
        if path.is_file() and os.access(str(path), os.X_OK):
            return str(path)
    else:
        resolved = shutil.which(path_or_name)
        if resolved:
            return resolved
    raise OmarchyError(f"Required executable is unavailable: {path_or_name}")


def prompt(label, default=""):
    suffix = f" [{default}]" if default else ""
    answer = input(f"{label}{suffix}: ").strip()
    return answer or default


def confirm(label, assume_yes=False):
    if assume_yes:
        return True
    return input(f"{label} [y/N]: ").strip().lower() in {"y", "yes"}


def slugify(value):
    value = re.sub(r"[^a-z0-9._-]+", "-", value.lower()).strip("-")
    return value or "omarchy"


def hostname_from_name(value):
    value = re.sub(r"[^a-z0-9-]+", "-", value.lower()).strip("-")
    return value[:63].rstrip("-") or "dev-omarchy"


def validate_account(value):
    if not re.fullmatch(r"[a-z_][a-z0-9_-]{0,31}", value):
        raise OmarchyError("Guest user must be a valid lowercase Linux account name")
    return value


def validate_hostname(value):
    if not re.fullmatch(r"[a-z0-9](?:[a-z0-9-]{0,61}[a-z0-9])?", value):
        raise OmarchyError("Guest hostname must be a valid lowercase hostname")
    return value


def validate_display_mode(value):
    pattern = r"[1-9][0-9]{2,4}x[1-9][0-9]{2,4}@[1-9][0-9]*(?:\.[0-9]+)?"
    if not re.fullmatch(pattern, value):
        raise OmarchyError("Display mode must look like 4096x2160@60")
    return value


def validate_window_size(value):
    normalized = str(value).strip().lower().removesuffix("%").strip()
    if normalized in {"", "default"}:
        return DEFAULT_WINDOW_SIZE
    if normalized in {"off", "none", "manual"}:
        return None
    try:
        percentage = int(normalized)
    except ValueError as error:
        raise OmarchyError(
            "Host window size must be 50, 67, 75, 100, or off"
        ) from error
    if percentage not in WINDOW_SIZE_ACTIONS:
        raise OmarchyError("Host window size must be 50, 67, 75, 100, or off")
    return percentage


def resolve_layout(value, *, default_mode, prompt_if_missing=False):
    if value is None and prompt_if_missing and sys.stdin.isatty():
        value = prompt(
            "Per-VM app layout Lua file (optional; leave blank for native Omarchy)"
        )
    if value is None:
        return default_mode, None
    normalized = str(value).strip()
    if not normalized or normalized.lower() in {"off", "none", "native"}:
        return "remove", None
    layout_file = Path(normalized).expanduser().resolve()
    if not layout_file.is_file():
        raise OmarchyError(f"App layout file does not exist: {layout_file}")
    return "install", layout_file


def resolve_window_size(value):
    if value:
        return validate_window_size(value)
    if sys.stdin.isatty():
        value = prompt(
            "Host window size on its current display (50, 67, 75, 100, or off)",
            str(DEFAULT_WINDOW_SIZE),
        )
    return validate_window_size(value)


def resize_host_window(percentage):
    if percentage is None:
        return False
    if sys.platform != "darwin":
        note(
            f"Resize the Parallels window manually to {percentage}% of its display; "
            "automatic host resizing is only available on macOS"
        )
        return False
    opener = shutil.which("open")
    if not opener:
        note(f"Resize the Parallels window manually to {percentage}% of its display")
        return False
    rectangle = run([opener, "-Ra", "Rectangle Pro"], capture=True, check=False)
    if rectangle.returncode != 0:
        note(
            f"Rectangle Pro is unavailable; resize the Parallels window manually "
            f"to {percentage}% of its display"
        )
        return False
    activated = run([opener, "-a", "Parallels Desktop"], capture=True, check=False)
    if activated.returncode != 0:
        note(
            f"Unable to activate Parallels Desktop; resize its window manually "
            f"to {percentage}% of its display"
        )
        return False
    time.sleep(1)
    action = WINDOW_SIZE_ACTIONS[percentage]
    resized = run(
        [opener, "-g", f"rectangle-pro://execute-action?name={action}"],
        capture=True,
        check=False,
    )
    if resized.returncode != 0:
        note(
            f"Rectangle Pro could not resize the window; do it manually at "
            f"{percentage}% of its display"
        )
        return False
    note(f"Sized the Parallels window to {percentage}% of its current display")
    return True


def sha256_file(path):
    digest = hashlib.sha256()
    with path.open("rb") as source:
        for block in iter(lambda: source.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def validate_manifest(data):
    required = {"version", "channel", "arch", "url", "sha256", "size"}
    missing = sorted(required - data.keys())
    if missing:
        raise OmarchyError(f"Omarchy manifest is missing: {', '.join(missing)}")
    if data["arch"] != "aarch64":
        raise OmarchyError(f"Expected an aarch64 manifest, found {data['arch']!r}")
    if not str(data["url"]).startswith("https://"):
        raise OmarchyError("Omarchy manifest image URL must use HTTPS")
    if not re.fullmatch(r"[0-9a-f]{64}", str(data["sha256"])):
        raise OmarchyError("Omarchy manifest contains an invalid SHA-256")
    if not isinstance(data["size"], int) or data["size"] <= 0:
        raise OmarchyError("Omarchy manifest contains an invalid image size")
    return data


def fetch_manifest(url, curl):
    result = run([curl, "-fsSL", url], capture=True)
    try:
        return validate_manifest(json.loads(result.stdout))
    except json.JSONDecodeError as error:
        raise OmarchyError(f"Unable to parse Omarchy manifest: {error}") from error


def download_image(manifest, artifacts_dir, curl):
    images_dir = artifacts_dir / "images"
    images_dir.mkdir(parents=True, exist_ok=True)
    image = images_dir / Path(str(manifest["url"])).name
    expected_hash = str(manifest["sha256"])
    expected_size = int(manifest["size"])
    if image.is_file():
        if (
            image.stat().st_size == expected_size
            and sha256_file(image) == expected_hash
        ):
            note(f"Reusing verified Omarchy image: {image}")
            return image
        raise OmarchyError(
            f"Existing image does not match the manifest: {image}. Move it aside and retry."
        )

    partial = image.with_suffix(image.suffix + ".part")
    command = [curl, "--location", "--fail", "--progress-bar"]
    if partial.exists():
        command.extend(["--continue-at", "-"])
    command.extend(["--output", str(partial), str(manifest["url"])])
    note(
        f"Downloading Omarchy {manifest['version']} ({expected_size / 1024**3:.1f} GiB)"
    )
    run(command)
    if partial.stat().st_size != expected_size:
        raise OmarchyError(
            f"Downloaded image has size {partial.stat().st_size}, expected {expected_size}"
        )
    actual_hash = sha256_file(partial)
    if actual_hash != expected_hash:
        raise OmarchyError(
            f"Downloaded image SHA-256 is {actual_hash}, expected {expected_hash}"
        )
    partial.replace(image)
    image.chmod(0o644)
    return image


def find_default_ssh_key():
    for name in ("id_ed25519.pub", "id_ecdsa.pub", "id_rsa.pub"):
        candidate = Path.home() / ".ssh" / name
        if candidate.is_file():
            return candidate
    return None


def private_key_for(public_key):
    if public_key.suffix == ".pub":
        private = public_key.with_suffix("")
        if private.is_file():
            return private
    raise OmarchyError(f"Matching private SSH key is unavailable for {public_key}")


def find_sha512_openssl():
    candidates = [
        "/opt/homebrew/opt/openssl@3/bin/openssl",
        "/usr/local/opt/openssl@3/bin/openssl",
        shutil.which("openssl") or "",
    ]
    for candidate in candidates:
        if not candidate or not Path(candidate).is_file():
            continue
        result = run(
            [candidate, "passwd", "-6", "-stdin"],
            capture=True,
            input_text="probe\n",
            check=False,
        )
        if result.returncode == 0 and result.stdout.startswith("$6$"):
            return candidate
    raise OmarchyError(
        "OpenSSL with SHA-512 crypt support is required; run 'brew install openssl@3'"
    )


def hash_password(password, openssl):
    result = run(
        [openssl, "passwd", "-6", "-stdin"],
        capture=True,
        input_text=password + "\n",
    )
    password_hash = result.stdout.strip()
    if not password_hash.startswith("$6$"):
        raise OmarchyError("OpenSSL did not produce a SHA-512 password hash")
    return password_hash


def partition_sizes(disk_gb):
    mib = 1024 * 1024
    gib = 1024 * 1024 * 1024
    boot_start = mib
    boot_size = 2 * gib
    root_start = boot_start + boot_size
    root_size = disk_gb * gib - root_start - mib
    if root_size <= 0:
        raise OmarchyError("Disk is too small for the Omarchy partition layout")
    return boot_start, boot_size, root_start, root_size


def runtime_packages(channel, image_name=""):
    marker = f"{channel} {image_name}".lower()
    if any(word in marker for word in ("edge", "dev", "local", "pr")):
        return "omarchy-settings-dev", "omarchy-dev"
    return "omarchy-settings", "omarchy"


def build_user_configuration(
    *,
    disk_gb,
    hostname,
    timezone,
    keyboard_layout,
    channel,
    image_name,
    target_disk="/dev/sda",
):
    boot_start, boot_size, root_start, root_size = partition_sizes(disk_gb)
    settings_package, runtime_package = runtime_packages(channel, image_name)

    def size(value):
        return {
            "sector_size": {"unit": "B", "value": 512},
            "unit": "B",
            "value": value,
        }

    return {
        "app_config": None,
        "archinstall-language": "English",
        "auth_config": {},
        "audio_config": {"audio": "pipewire"},
        "bootloader_config": {
            "bootloader": "Limine",
            "uki": False,
            "removable": False,
        },
        "custom_commands": [],
        "omarchy_install": {
            "mode": "full_disk",
            "defer_provisioning": False,
            "target_mount": "/mnt",
            "boot": {
                "esp_mount": "/boot",
                "esp_path": "/EFI/limine",
                "efi_binary": "limine_aa64.efi",
                "enable_fallback": True,
            },
            "storage": {"kernel": "linux-omarchy"},
        },
        "disk_config": {
            "config_type": "default_layout",
            "device_modifications": [
                {
                    "device": target_disk,
                    "partitions": [
                        {
                            "btrfs": [],
                            "dev_path": None,
                            "flags": ["boot", "esp"],
                            "fs_type": "fat32",
                            "mount_options": [],
                            "mountpoint": "/boot",
                            "obj_id": str(uuid.uuid4()),
                            "size": size(boot_size),
                            "start": size(boot_start),
                            "status": "create",
                            "type": "primary",
                        },
                        {
                            "btrfs": [
                                {"mountpoint": "/", "name": "@"},
                                {"mountpoint": "/home", "name": "@home"},
                                {"mountpoint": "/var/log", "name": "@log"},
                                {"mountpoint": "/var/cache/pacman/pkg", "name": "@pkg"},
                            ],
                            "dev_path": None,
                            "flags": [],
                            "fs_type": "btrfs",
                            "mount_options": ["compress=zstd"],
                            "mountpoint": None,
                            "obj_id": str(uuid.uuid4()),
                            "size": size(root_size),
                            "start": size(root_start),
                            "status": "create",
                            "type": "primary",
                        },
                    ],
                    "wipe": True,
                }
            ],
        },
        "hostname": hostname,
        "kernels": ["linux-omarchy"],
        "network_config": {"type": "iso"},
        "ntp": True,
        "parallel_downloads": 8,
        "script": None,
        "services": [],
        "swap": True,
        "timezone": timezone,
        "locale_config": {
            "kb_layout": keyboard_layout,
            "sys_enc": "UTF-8",
            "sys_lang": "en_AU.UTF-8",
        },
        "mirror_config": {
            "custom_repositories": [],
            "custom_servers": [{"url": "https://arm-mirror.omarchy.org/$arch/$repo"}],
            "mirror_regions": {},
            "optional_repositories": [],
        },
        "packages": [
            "base-devel",
            "git",
            "omarchy-keyring",
            settings_package,
            runtime_package,
        ],
        "profile_config": {"gfx_driver": None, "greeter": None, "profile": {}},
        "version": "3.0.9",
    }


def build_cidata_iso(
    *, output, xorriso, guest_user, password_hash, public_key, configuration
):
    output.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(prefix="dev-vm-cidata-") as temporary:
        directory = Path(temporary)
        credentials = {
            "root_enc_password": password_hash,
            "users": [
                {
                    "enc_password": password_hash,
                    "groups": [],
                    "sudo": True,
                    "username": guest_user,
                }
            ],
        }
        (directory / "user_configuration.json").write_text(
            json.dumps(configuration, indent=2) + "\n", encoding="utf-8"
        )
        (directory / "user_credentials.json").write_text(
            json.dumps(credentials, indent=2) + "\n", encoding="utf-8"
        )
        (directory / "user_encrypt_installation.txt").write_text(
            "false\n", encoding="utf-8"
        )
        (directory / "authorized_keys").write_text(
            public_key.read_text(encoding="utf-8").strip() + "\n", encoding="utf-8"
        )
        temporary_iso = output.with_suffix(output.suffix + ".tmp")
        temporary_iso.unlink(missing_ok=True)
        run(
            [
                xorriso,
                "-as",
                "mkisofs",
                "-quiet",
                "-o",
                str(temporary_iso),
                "-V",
                "cidata",
                "-J",
                "-r",
                str(directory),
            ]
        )
        temporary_iso.replace(output)
        output.chmod(0o600)


def prl_output(prlctl, *arguments):
    return run([prlctl, *arguments], capture=True).stdout


def vm_names(prlctl):
    output = prl_output(prlctl, "list", "--all", "--output", "name", "--no-header")
    return [line.strip() for line in output.splitlines() if line.strip()]


def vm_exists(prlctl, name):
    return name in vm_names(prlctl)


def next_vm_name(prlctl):
    existing = set(vm_names(prlctl))
    name = "Dev Omarchy"
    number = 2
    while name in existing:
        name = f"Dev Omarchy {number}"
        number += 1
    return name


def vm_info(prlctl, name):
    return prl_output(prlctl, "list", "--info", name)


def vm_state(prlctl, name):
    match = re.search(r"^State:\s*(\S+)", vm_info(prlctl, name), flags=re.MULTILINE)
    if not match:
        raise OmarchyError(f"Unable to determine the state of Parallels VM {name!r}")
    return match.group(1)


def wait_for_vm_state(prlctl, name, expected, timeout_seconds=180):
    started = time.monotonic()
    while time.monotonic() - started < timeout_seconds:
        state = vm_state(prlctl, name)
        if state == expected:
            return
        time.sleep(2)
    raise OmarchyError(
        f"Parallels VM {name!r} did not reach state {expected!r} within "
        f"{timeout_seconds} seconds"
    )


def parallels_ipv4_from_info(info):
    match = re.search(r"^\s*IP Addresses:\s*(.+)$", info, flags=re.MULTILINE)
    if not match:
        return ""
    for value in match.group(1).split(","):
        try:
            address = ipaddress.ip_address(value.strip())
        except ValueError:
            continue
        if (
            address.version == 4
            and not address.is_loopback
            and not address.is_link_local
        ):
            return str(address)
    return ""


def parallels_ipv4(prlctl, name):
    return parallels_ipv4_from_info(vm_info(prlctl, name))


def prl_set(prlctl, name, *arguments):
    run([prlctl, "set", name, *arguments])


def configure_vm(
    *, prlctl, name, cpus, memory_mb, disk_gb, installer_iso, cidata_iso, resume
):
    exists = vm_exists(prlctl, name)
    if exists and not resume:
        raise OmarchyError(
            f"A VM named {name!r} already exists. Use --resume only for this "
            "workflow's interrupted VM; existing VMs are never replaced automatically."
        )
    if not exists:
        run([prlctl, "create", name, "--distribution", "manjaro"])

    prl_set(prlctl, name, "--cpus", str(cpus), "--memsize", str(memory_mb))
    info = vm_info(prlctl, name)
    match = re.search(r"^\s*hdd0 .* ([0-9]+)Mb ", info, flags=re.MULTILINE)
    requested_disk_mb = disk_gb * 1024
    current_disk_mb = int(match.group(1)) if match else 0
    if current_disk_mb <= requested_disk_mb:
        prl_set(
            prlctl,
            name,
            "--device-set",
            "hdd0",
            "--size",
            str(requested_disk_mb),
            "--type",
            "expand",
            "--online-compact",
            "on",
        )
    else:
        note(
            f"Keeping existing {current_disk_mb} MB disk; refusing to shrink it "
            f"to {requested_disk_mb} MB"
        )

    settings = (
        (
            "--bios-type",
            "efi-arm64",
            "--efi-secure-boot",
            "off",
            "--device-bootorder",
            "hdd0 cdrom0",
        ),
        (
            "--video-adapter-type",
            "virtio",
            "--videosize",
            "auto",
            "--3d-accelerate",
            "highest",
            "--vertical-sync",
            "on",
            "--high-resolution",
            "on",
            "--high-resolution-in-guest",
            "on",
            "--native-scaling-in-guest",
            "off",
        ),
        (
            "--faster-vm",
            "on",
            "--hypervisor-type",
            "apple",
            "--nested-virt",
            "off",
            "--longer-battery-life",
            "off",
            "--smart-mouse-optimize",
            "auto",
            "--support-usb30",
            "on",
        ),
        (
            "--sync-host-printers",
            "off",
            "--sync-default-printer",
            "off",
            "--show-host-printer-ui",
            "off",
            "--auto-share-camera",
            "off",
            "--auto-share-smart-card",
            "off",
            "--auto-share-gamepad",
            "off",
        ),
        (
            "--shf-host",
            "off",
            "--shf-host-defined",
            "off",
            "--shf-host-automount",
            "off",
            "--shf-guest",
            "off",
            "--shared-profile",
            "off",
            "--sh-app-host-to-guest",
            "off",
            "--sh-app-guest-to-host",
            "off",
            "--show-guest-app-folder-in-dock",
            "off",
            "--bounce-dock-icon-when-app-flashes",
            "off",
        ),
        (
            "--smart-mount",
            "off",
            "--smart-mount-removable-drives",
            "off",
            "--smart-mount-dvd-drives",
            "off",
            "--smart-mount-network-shares",
            "off",
            "--shared-clipboard",
            "on",
            "--shared-cloud",
            "off",
        ),
        (
            "--sync-vm-hostname",
            "off",
            "--sync-ssh-ids",
            "off",
            "--show-dev-tools",
            "off",
            "--share-host-location",
            "off",
            "--rosetta-linux",
            "off",
            "--tools-autoupdate",
            "yes",
        ),
        (
            "--time-sync",
            "on",
            "--time-sync-smart-mode",
            "off",
            "--disable-timezone-sync",
            "on",
            "--time-sync-interval",
            "60",
        ),
        (
            "--autostart",
            "off",
            "--autostop",
            "suspend",
            "--startup-view",
            "window",
            "--on-window-close",
            "suspend",
        ),
    )
    for setting in settings:
        prl_set(prlctl, name, *setting)

    prl_set(
        prlctl,
        name,
        "--device-set",
        "cdrom0",
        "--image",
        str(installer_iso),
        "--connect",
    )
    info = vm_info(prlctl, name)
    if re.search(r"^\s*cdrom1\s", info, flags=re.MULTILINE):
        prl_set(
            prlctl,
            name,
            "--device-set",
            "cdrom1",
            "--image",
            str(cidata_iso),
            "--connect",
        )
    else:
        prl_set(
            prlctl,
            name,
            "--device-add",
            "cdrom",
            "--image",
            str(cidata_iso),
            "--iface",
            "sata",
            "--connect",
        )


def ssh_options(private_key, known_hosts):
    return [
        "-o",
        "BatchMode=yes",
        "-o",
        "ConnectTimeout=5",
        "-o",
        "ConnectionAttempts=1",
        "-o",
        "GlobalKnownHostsFile=/dev/null",
        "-o",
        "IdentitiesOnly=yes",
        "-o",
        "LogLevel=ERROR",
        "-o",
        "PasswordAuthentication=no",
        "-o",
        "PreferredAuthentications=publickey",
        "-o",
        "StrictHostKeyChecking=accept-new",
        "-o",
        f"UserKnownHostsFile={known_hosts}",
        "-i",
        str(private_key),
    ]


def ssh_command(
    ssh,
    *,
    private_key,
    known_hosts,
    guest_user,
    host,
    remote_command,
    capture=False,
    input_text=None,
    check=True,
    timeout=None,
):
    return run(
        [
            ssh,
            *ssh_options(private_key, known_hosts),
            f"{guest_user}@{host}",
            remote_command,
        ],
        capture=capture,
        input_text=input_text,
        check=check,
        timeout=timeout,
    )


def wait_for_ssh(
    ssh,
    *,
    private_key,
    known_hosts,
    guest_user,
    host,
    timeout_seconds,
    host_resolver=None,
):
    started = time.monotonic()
    next_report = 0
    note(f"Waiting up to {timeout_seconds} seconds for SSH at {guest_user}@{host}")
    while True:
        elapsed = int(time.monotonic() - started)
        if elapsed >= timeout_seconds:
            raise OmarchyError(f"Timed out waiting for SSH at {guest_user}@{host}")
        if host_resolver is not None:
            resolved_host = host_resolver()
            if resolved_host and resolved_host != host:
                note(f"Parallels now reports SSH at {guest_user}@{resolved_host}")
                host = resolved_host
        result = ssh_command(
            ssh,
            private_key=private_key,
            known_hosts=known_hosts,
            guest_user=guest_user,
            host=host,
            remote_command="true",
            capture=True,
            check=False,
            timeout=10,
        )
        if result.returncode == 0:
            note(f"SSH is ready after {elapsed} seconds")
            return host
        if elapsed >= next_report:
            print(f"    ... still waiting for SSH ({elapsed}s)", flush=True)
            next_report = elapsed + 30
        time.sleep(5)


def update_omarchy(ssh, *, private_key, known_hosts, guest_user, host):
    note(
        "Updating Omarchy through its supported entrypoint; "
        "enter the guest sudo password when prompted"
    )
    run(
        [
            ssh,
            *ssh_options(private_key, known_hosts),
            "-tt",
            f"{guest_user}@{host}",
            "/usr/bin/env OMARCHY_PATH=/usr/share/omarchy "
            "/usr/bin/omarchy update -y",
        ],
        timeout=1800,
    )


def reboot_guest(
    ssh,
    *,
    private_key,
    known_hosts,
    guest_user,
    host,
    password,
    timeout_seconds,
    message,
    host_resolver=None,
):
    boot_id = ssh_command(
        ssh,
        private_key=private_key,
        known_hosts=known_hosts,
        guest_user=guest_user,
        host=host,
        remote_command="cat /proc/sys/kernel/random/boot_id",
        capture=True,
    ).stdout.strip()
    note(message)
    ssh_command(
        ssh,
        private_key=private_key,
        known_hosts=known_hosts,
        guest_user=guest_user,
        host=host,
        remote_command="sudo -S -p '' systemctl reboot",
        input_text=password + "\n",
        check=False,
    )
    started = time.monotonic()
    while time.monotonic() - started < timeout_seconds:
        if host_resolver is not None:
            host = host_resolver() or host
        result = ssh_command(
            ssh,
            private_key=private_key,
            known_hosts=known_hosts,
            guest_user=guest_user,
            host=host,
            remote_command="cat /proc/sys/kernel/random/boot_id",
            capture=True,
            check=False,
            timeout=10,
        )
        if result.returncode == 0 and result.stdout.strip() not in {"", boot_id}:
            note("The Omarchy guest is back online")
            return host
        time.sleep(5)
    raise OmarchyError("The Omarchy guest did not return after reboot")


def configure_host_share(prlctl, name, share_path):
    if not share_path.is_dir():
        note(f"Skipping optional host share; directory is absent: {share_path}")
        return False
    prl_set(
        prlctl,
        name,
        "--shf-host",
        "on",
        "--shf-host-defined",
        "off",
        "--shf-host-automount",
        "off",
    )
    update = run(
        [
            prlctl,
            "set",
            name,
            "--shf-host-set",
            DEFAULT_SHARE_NAME,
            "--path",
            str(share_path),
            "--mode",
            "rw",
            "--enable",
        ],
        check=False,
    )
    if update.returncode != 0:
        prl_set(
            prlctl,
            name,
            "--shf-host-add",
            DEFAULT_SHARE_NAME,
            "--path",
            str(share_path),
            "--mode",
            "rw",
            "--enable",
        )
    return True


def attach_tools_iso(prlctl, name, tools_iso):
    if not tools_iso.is_file():
        raise OmarchyError(f"Parallels Tools ISO is unavailable: {tools_iso}")
    if str(tools_iso) in vm_info(prlctl, name):
        return
    prl_set(
        prlctl,
        name,
        "--device-add",
        "cdrom",
        "--image",
        str(tools_iso),
        "--iface",
        "sata",
        "--connect",
    )


def disconnect_install_media(prlctl, name):
    info = vm_info(prlctl, name)
    for device in ("cdrom0", "cdrom1"):
        if re.search(rf"^\s*{device}\s", info, flags=re.MULTILINE):
            prl_set(prlctl, name, "--device-set", device, "--disconnect")


def prompt_password():
    first = getpass.getpass("Omarchy sudo password: ")
    second = getpass.getpass("Confirm Omarchy sudo password: ")
    if not first:
        raise OmarchyError("Omarchy sudo password cannot be empty")
    if first != second:
        raise OmarchyError("Omarchy sudo passwords did not match")
    return first


def apply_guest(
    *,
    prlctl,
    name,
    guest_user,
    host,
    public_key,
    password,
    display_mode,
    layout_mode,
    layout_file,
    tools_iso,
    share_path,
    ssh_timeout,
    host_resolver=None,
):
    if not vm_exists(prlctl, name):
        raise OmarchyError(f"Parallels VM does not exist: {name}")
    validate_display_mode(display_mode)
    if layout_mode not in {"keep", "install", "remove"}:
        raise OmarchyError(f"Invalid app layout mode: {layout_mode}")
    if layout_mode == "install" and layout_file is None:
        raise OmarchyError("Installing an app layout requires a layout file")
    private_key = private_key_for(public_key)
    ssh = require_executable("ssh")
    scp = require_executable("scp")
    initial_state = vm_state(prlctl, name)
    if initial_state not in {"running", "stopped"}:
        raise OmarchyError(
            f"Parallels VM {name!r} must be running or stopped, not {initial_state!r}"
        )
    attach_tools_iso(prlctl, name, tools_iso)
    share_enabled = configure_host_share(prlctl, name, share_path)
    disconnect_install_media(prlctl, name)
    if initial_state == "stopped":
        note(f"Starting {name} with the updated virtual hardware")
        run([prlctl, "start", name])

    with tempfile.TemporaryDirectory(prefix="dev-vm-known-hosts-") as temporary:
        known_hosts = Path(temporary) / "known_hosts"
        known_hosts.touch(mode=0o600)
        host = wait_for_ssh(
            ssh,
            private_key=private_key,
            known_hosts=known_hosts,
            guest_user=guest_user,
            host=host,
            timeout_seconds=ssh_timeout,
            host_resolver=host_resolver,
        )
        if initial_state == "running":
            note(
                f"Gracefully stopping {name} to apply pending virtual hardware changes"
            )
            ssh_command(
                ssh,
                private_key=private_key,
                known_hosts=known_hosts,
                guest_user=guest_user,
                host=host,
                remote_command="sudo -S -p '' systemctl poweroff",
                input_text=password + "\n",
                check=False,
            )
            wait_for_vm_state(prlctl, name, "stopped")
            note(f"Starting {name} with the updated virtual hardware")
            run([prlctl, "start", name])
            host = wait_for_ssh(
                ssh,
                private_key=private_key,
                known_hosts=known_hosts,
                guest_user=guest_user,
                host=host,
                timeout_seconds=ssh_timeout,
                host_resolver=host_resolver,
            )
        update_omarchy(
            ssh,
            private_key=private_key,
            known_hosts=known_hosts,
            guest_user=guest_user,
            host=host,
        )
        host = reboot_guest(
            ssh,
            private_key=private_key,
            known_hosts=known_hosts,
            guest_user=guest_user,
            host=host,
            password=password,
            timeout_seconds=ssh_timeout,
            message="Rebooting into the Omarchy-updated kernel",
            host_resolver=host_resolver,
        )
        ssh_command(
            ssh,
            private_key=private_key,
            known_hosts=known_hosts,
            guest_user=guest_user,
            host=host,
            remote_command="rm -rf /tmp/dev-vm-omarchy",
        )
        run(
            [
                scp,
                *ssh_options(private_key, known_hosts),
                "-r",
                str(GUEST_PAYLOAD_DIR),
                f"{guest_user}@{host}:/tmp/dev-vm-omarchy",
            ]
        )
        if layout_mode == "install":
            run(
                [
                    scp,
                    *ssh_options(private_key, known_hosts),
                    str(layout_file),
                    f"{guest_user}@{host}:/tmp/dev-vm-omarchy/custom-layout.lua",
                ]
            )
        remote_arguments = [
            "sudo",
            "-S",
            "-p",
            "",
            "bash",
            "/tmp/dev-vm-omarchy/configure.sh",
            "--user",
            guest_user,
            "--display-mode",
            display_mode,
            "--layout-mode",
            layout_mode,
            "--share",
            "yes" if share_enabled else "no",
            "--payload",
            "/tmp/dev-vm-omarchy",
        ]
        if layout_mode == "install":
            remote_arguments.extend(
                ["--layout-file", "/tmp/dev-vm-omarchy/custom-layout.lua"]
            )
        note("Applying Omarchy guest configuration")
        ssh_command(
            ssh,
            private_key=private_key,
            known_hosts=known_hosts,
            guest_user=guest_user,
            host=host,
            remote_command=" ".join(shlex.quote(part) for part in remote_arguments),
            input_text=password + "\n",
            timeout=1800,
        )
        reboot_guest(
            ssh,
            private_key=private_key,
            known_hosts=known_hosts,
            guest_user=guest_user,
            host=host,
            password=password,
            timeout_seconds=ssh_timeout,
            message="Rebooting after Parallels Tools and workstation configuration",
            host_resolver=host_resolver,
        )


def run_status(*, guest_user, host, public_key, ssh_timeout, host_resolver=None):
    private_key = private_key_for(public_key)
    ssh = require_executable("ssh")
    commands = [
        "set -u",
        "printf '%s\\n' '--- system ---'",
        "uname -a",
        "printf 'Omarchy: '",
        "omarchy-version 2>/dev/null || pacman -Q omarchy-dev omarchy 2>/dev/null || true",
        "printf '%s\\n' '--- failed system units ---'",
        "systemctl --failed --no-legend || true",
        "printf '%s\\n' '--- failed user units ---'",
        "systemctl --user --failed --no-legend || true",
        "printf '%s\\n' '--- guest idle policy ---'",
        "jq -c '.idle' \"$HOME/.config/omarchy/shell.json\" 2>/dev/null || true",
        "printf 'Sleep lock: '",
        "systemctl --user is-enabled omarchy-sleep-lock.service 2>/dev/null || true",
        "printf '%s\\n' '--- Parallels Tools ---'",
        "systemctl is-active prltoolsd.service 2>/dev/null || true",
        "cat /usr/lib/parallels-tools/version 2>/dev/null || true",
        "printf '%s\\n' '--- guest clipboard helper ---'",
        "printf 'Native prlcc chain: '",
        "systemctl --user is-active app-prlcc@autostart.service 2>/dev/null || true",
        "printf 'prlcp processes: '",
        "pgrep -cx prlcp 2>/dev/null || printf '0\\n'",
        "printf '%s\\n' '--- workstation packages ---'",
        "pacman -Q docker docker-compose mise-bin chromium claude-desktop 1password 1password-cli 2>/dev/null || true",
        "printf '%s\\n' '--- shared folder ---'",
        "findmnt /mnt/shared 2>/dev/null || true",
        "printf '%s\\n' '--- graphical session report ---'",
        'cat "$HOME/.local/state/dev-vm/session-check.txt" 2>/dev/null || '
        "printf '%s\\n' 'Not available yet; log in graphically once.'",
    ]
    command = "\n".join(commands)
    with tempfile.TemporaryDirectory(prefix="dev-vm-known-hosts-") as temporary:
        known_hosts = Path(temporary) / "known_hosts"
        known_hosts.touch(mode=0o600)
        host = wait_for_ssh(
            ssh,
            private_key=private_key,
            known_hosts=known_hosts,
            guest_user=guest_user,
            host=host,
            timeout_seconds=ssh_timeout,
            host_resolver=host_resolver,
        )
        result = ssh_command(
            ssh,
            private_key=private_key,
            known_hosts=known_hosts,
            guest_user=guest_user,
            host=host,
            remote_command="bash -lc " + shlex.quote(command),
            capture=True,
        )
        print(result.stdout, end="")
        lowered = result.stdout.lower()
        if "llvmpipe" in lowered or "softpipe" in lowered:
            raise OmarchyError(
                "Software rendering detected; hardware rendering is required"
            )


def add_connection_arguments(parser):
    parser.add_argument("--name", default="", help="Parallels VM name")
    parser.add_argument("--guest-user", default="", help="Omarchy account")
    parser.add_argument("--hostname", default="", help="Omarchy hostname")
    parser.add_argument("--ssh-host", default="", help="SSH hostname or address")
    parser.add_argument("--ssh-key", default="", help="SSH public-key path")
    parser.add_argument("--ssh-timeout", type=int, default=2700)


def build_parser():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--prlctl", default=DEFAULT_PRLCTL)
    parser.add_argument("--artifacts", default=str(DEFAULT_ARTIFACTS_DIR))
    subparsers = parser.add_subparsers(dest="command", required=True)

    image = subparsers.add_parser("image", help="Download and verify Omarchy ARM64")
    image.add_argument("--manifest-url", default=DEFAULT_MANIFEST_URL)

    bootstrap = subparsers.add_parser(
        "bootstrap", help="Create, install, and configure a new Omarchy VM"
    )
    add_connection_arguments(bootstrap)
    bootstrap.add_argument("--manifest-url", default=DEFAULT_MANIFEST_URL)
    bootstrap.add_argument("--image", default="")
    bootstrap.add_argument("--image-sha256", default="")
    bootstrap.add_argument("--cpus", type=int, default=4)
    bootstrap.add_argument("--memory-mb", type=int, default=12288)
    bootstrap.add_argument("--disk-gb", type=int, default=64)
    bootstrap.add_argument("--timezone", default="Australia/Melbourne")
    bootstrap.add_argument("--keyboard-layout", default="us")
    bootstrap.add_argument("--display-mode", default=DEFAULT_DISPLAY_MODE)
    bootstrap.add_argument(
        "--window-size",
        default="",
        help="host window percentage: 50, 67, 75, 100, or off",
    )
    bootstrap.add_argument(
        "--layout-file",
        default=None,
        help="optional per-VM Hyprland app-layout Lua file",
    )
    bootstrap.add_argument("--tools-iso", default=DEFAULT_TOOLS_ISO)
    bootstrap.add_argument("--share-path", default=str(DEFAULT_SHARE_PATH))
    bootstrap.add_argument("--resume", action="store_true")
    bootstrap.add_argument("--yes", action="store_true")
    bootstrap.add_argument("--no-apply", action="store_true")

    apply_parser = subparsers.add_parser(
        "apply", help="Reapply host integration and workstation configuration"
    )
    add_connection_arguments(apply_parser)
    apply_parser.add_argument("--display-mode", default=DEFAULT_DISPLAY_MODE)
    apply_parser.add_argument(
        "--layout-file",
        default=None,
        help="per-VM app layout; omit to preserve, or use 'off' to remove",
    )
    apply_parser.add_argument("--tools-iso", default=DEFAULT_TOOLS_ISO)
    apply_parser.add_argument("--share-path", default=str(DEFAULT_SHARE_PATH))

    check = subparsers.add_parser("check", help="Report Omarchy VM health")
    add_connection_arguments(check)

    return parser


def resolve_identity(args, prlctl=None, for_new=False):
    default_name = next_vm_name(prlctl) if for_new else "Dev Omarchy"
    name = args.name or default_name
    if not args.name and sys.stdin.isatty():
        name = prompt("VM name", name)
    guest_user = args.guest_user or getpass.getuser().lower()
    if not args.guest_user and sys.stdin.isatty():
        guest_user = prompt("Omarchy user", guest_user)
    guest_user = validate_account(guest_user)
    hostname = args.hostname or hostname_from_name(name)
    if not args.hostname and sys.stdin.isatty():
        hostname = prompt("Omarchy hostname", hostname)
    hostname = validate_hostname(hostname)
    default_key = find_default_ssh_key()
    key_value = args.ssh_key
    if not key_value and sys.stdin.isatty():
        key_value = prompt("SSH public key", str(default_key or ""))
    if not key_value:
        raise OmarchyError("An SSH public key is required")
    public_key = Path(key_value).expanduser().resolve()
    if not public_key.is_file():
        raise OmarchyError(f"SSH public key does not exist: {public_key}")
    private_key_for(public_key)
    return name, guest_user, hostname, public_key


def image_command(args):
    curl = require_executable("curl")
    artifacts = Path(args.artifacts).expanduser().resolve()
    manifest = fetch_manifest(args.manifest_url, curl)
    print(download_image(manifest, artifacts, curl))


def bootstrap_command(args):
    prlctl = require_executable(args.prlctl)
    curl = require_executable("curl")
    xorriso = require_executable("xorriso")
    openssl = find_sha512_openssl()
    artifacts = Path(args.artifacts).expanduser().resolve()
    display_mode = validate_display_mode(args.display_mode)
    window_size = resolve_window_size(args.window_size)
    layout_mode, layout_file = resolve_layout(
        args.layout_file, default_mode="remove", prompt_if_missing=True
    )
    if args.disk_gb < 32:
        raise OmarchyError("Omarchy VM disk must be at least 32 GB")
    if args.cpus < 1 or args.memory_mb < 4096:
        raise OmarchyError("Omarchy requires at least 1 CPU and 4096 MB RAM")

    name, guest_user, hostname, public_key = resolve_identity(
        args, prlctl, for_new=True
    )
    if args.image:
        image = Path(args.image).expanduser().resolve()
        if not image.is_file():
            raise OmarchyError(f"Omarchy image does not exist: {image}")
        if not re.fullmatch(r"[0-9a-f]{64}", args.image_sha256):
            raise OmarchyError("A local image requires --image-sha256")
        actual_hash = sha256_file(image)
        if actual_hash != args.image_sha256:
            raise OmarchyError(
                f"Local image SHA-256 is {actual_hash}, expected {args.image_sha256}"
            )
        manifest = {
            "version": image.stem,
            "channel": "edge" if "edge" in image.name else "stable",
            "arch": "aarch64",
            "url": image.as_uri(),
            "sha256": actual_hash,
            "size": image.stat().st_size,
        }
    else:
        manifest = fetch_manifest(args.manifest_url, curl)
        image = artifacts / "images" / Path(str(manifest["url"])).name

    ssh_host = args.ssh_host or f"{hostname}.local"
    seed_iso = artifacts / f"{slugify(name)}-cidata.iso"
    share = Path(args.share_path).expanduser()
    action = "resume interrupted setup" if args.resume else "create new VM"
    window_description = (
        f"{window_size}% of its current display" if window_size else "manual"
    )
    layout_description = str(layout_file) if layout_file else "native Omarchy"
    print(
        "\nProposed Omarchy Parallels VM\n"
        f"  Action:          {action}\n"
        f"  Name:            {name}\n"
        f"  Image:           {manifest['url']}\n"
        f"  SHA-256:         {manifest['sha256']}\n"
        "  Architecture:    ARM64 / EFI / linux-omarchy\n"
        f"  CPUs:            {args.cpus}\n"
        f"  Memory:          {args.memory_mb} MB\n"
        f"  Disk:            {args.disk_gb} GB expanding; /dev/sda will be wiped\n"
        f"  Display:         fixed {display_mode}, scale 1.0, hardware rendering required\n"
        f"  Host window:     {window_description}\n"
        f"  App layout:      {layout_description}\n"
        f"  Guest:           {guest_user}@{hostname}\n"
        f"  SSH:             {guest_user}@{ssh_host}\n"
        f"  Host share:      {share if share.is_dir() else 'disabled (folder absent)'}\n"
        "  Applications:    Omarchy defaults plus Claude Desktop and 1Password\n"
        "  Encryption:      disabled for this disposable evaluation VM\n"
    )
    if not confirm("Proceed with this VM", args.yes):
        note("Cancelled; no VM was changed")
        return

    password = prompt_password()
    password_hash = hash_password(password, openssl)
    if not args.image:
        image = download_image(manifest, artifacts, curl)
    configuration = build_user_configuration(
        disk_gb=args.disk_gb,
        hostname=hostname,
        timezone=args.timezone,
        keyboard_layout=args.keyboard_layout,
        channel=str(manifest["channel"]),
        image_name=image.name,
    )
    build_cidata_iso(
        output=seed_iso,
        xorriso=xorriso,
        guest_user=guest_user,
        password_hash=password_hash,
        public_key=public_key,
        configuration=configuration,
    )
    del password_hash
    configure_vm(
        prlctl=prlctl,
        name=name,
        cpus=args.cpus,
        memory_mb=args.memory_mb,
        disk_gb=args.disk_gb,
        installer_iso=image,
        cidata_iso=seed_iso,
        resume=args.resume,
    )
    note(f"Starting {name}")
    run([prlctl, "start", name])
    private_key = private_key_for(public_key)
    ssh = require_executable("ssh")
    with tempfile.TemporaryDirectory(prefix="dev-vm-known-hosts-") as temporary:
        known_hosts = Path(temporary) / "known_hosts"
        known_hosts.touch(mode=0o600)
        ssh_host = wait_for_ssh(
            ssh,
            private_key=private_key,
            known_hosts=known_hosts,
            guest_user=guest_user,
            host=ssh_host,
            timeout_seconds=args.ssh_timeout,
            host_resolver=(
                None
                if args.ssh_host
                else lambda: parallels_ipv4(prlctl, name) or f"{hostname}.local"
            ),
        )
    disconnect_install_media(prlctl, name)
    if args.no_apply:
        resize_host_window(window_size)
        note("Base Omarchy installation is ready; guest configuration was skipped")
        return
    apply_guest(
        prlctl=prlctl,
        name=name,
        guest_user=guest_user,
        host=ssh_host,
        public_key=public_key,
        password=password,
        display_mode=display_mode,
        layout_mode=layout_mode,
        layout_file=layout_file,
        tools_iso=Path(args.tools_iso).expanduser().resolve(),
        share_path=share.resolve(),
        ssh_timeout=args.ssh_timeout,
        host_resolver=(
            None
            if args.ssh_host
            else lambda: parallels_ipv4(prlctl, name) or f"{hostname}.local"
        ),
    )
    password = ""
    seed_iso.unlink(missing_ok=True)
    resize_host_window(window_size)
    note("Omarchy VM is ready. Log in graphically once, then run make check-omarchy.")


def apply_command(args):
    prlctl = require_executable(args.prlctl)
    name, guest_user, hostname, public_key = resolve_identity(args, prlctl)
    seed_iso = (
        Path(args.artifacts).expanduser().resolve() / f"{slugify(name)}-cidata.iso"
    )
    password = prompt_password()
    layout_mode, layout_file = resolve_layout(args.layout_file, default_mode="keep")
    ssh_host = args.ssh_host or parallels_ipv4(prlctl, name) or f"{hostname}.local"
    apply_guest(
        prlctl=prlctl,
        name=name,
        guest_user=guest_user,
        host=ssh_host,
        public_key=public_key,
        password=password,
        display_mode=validate_display_mode(args.display_mode),
        layout_mode=layout_mode,
        layout_file=layout_file,
        tools_iso=Path(args.tools_iso).expanduser().resolve(),
        share_path=Path(args.share_path).expanduser().resolve(),
        ssh_timeout=args.ssh_timeout,
        host_resolver=(
            None
            if args.ssh_host
            else lambda: parallels_ipv4(prlctl, name) or f"{hostname}.local"
        ),
    )
    password = ""
    seed_iso.unlink(missing_ok=True)
    note("Removed the credential-bearing CIDATA image")


def check_command(args):
    prlctl = require_executable(args.prlctl)
    name, guest_user, hostname, public_key = resolve_identity(args)
    ssh_host = args.ssh_host or parallels_ipv4(prlctl, name) or f"{hostname}.local"
    run_status(
        guest_user=guest_user,
        host=ssh_host,
        public_key=public_key,
        ssh_timeout=args.ssh_timeout,
        host_resolver=(
            None
            if args.ssh_host
            else lambda: parallels_ipv4(prlctl, name) or f"{hostname}.local"
        ),
    )


def main():
    args = build_parser().parse_args()
    try:
        if args.command == "image":
            image_command(args)
        elif args.command == "bootstrap":
            bootstrap_command(args)
        elif args.command == "apply":
            apply_command(args)
        elif args.command == "check":
            check_command(args)
    except (OmarchyError, KeyboardInterrupt) as error:
        print(f"Error: {error}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
