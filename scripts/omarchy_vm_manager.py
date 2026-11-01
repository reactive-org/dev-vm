#!/usr/bin/env python3
"""Create and configure an Omarchy workstation through Omarchy VM Manager."""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import platform
import random
import re
import shlex
import shutil
import signal
import stat
import subprocess
import sys
import tempfile
import uuid
from contextlib import contextmanager
from dataclasses import dataclass
from html.parser import HTMLParser
from pathlib import Path
from typing import Iterable, Optional
from urllib.error import URLError
from urllib.request import Request, urlopen


PROJECT_DIR = Path(__file__).resolve().parents[1]
DEFAULT_CLI = PROJECT_DIR.parent / "Omarchy VM Manager" / "bin" / "omarchy-vm"
MINIMUM_MANAGER_VERSION = (0, 6, 0)
GUEST_REPAIR = PROJECT_DIR / "omarchy" / "guest" / "repair-try-omarchy-black-screen.sh"
GUEST_APPLY = PROJECT_DIR / "omarchy" / "guest" / "apply-workstation.sh"
GUEST_CHECK = PROJECT_DIR / "omarchy" / "guest" / "check-workstation.sh"
GUEST_THEME = PROJECT_DIR / "omarchy" / "guest" / "apply-theme.sh"
GUEST_LEAN = PROJECT_DIR / "omarchy" / "guest" / "apply-lean-developer.py"
GUEST_LEAN_PACKAGES = GUEST_LEAN.with_name("lean-developer.packages")
THEMES_CATALOG_URL = (
    "https://raw.githubusercontent.com/omacom/omarchy-site/master/themes/index.html"
)
REMOTE_PREFIX = "/tmp/dev-omarchy-workstation."
DEFAULT_PACKAGES = ()
PACKAGE_NAME = re.compile(r"[A-Za-z0-9][A-Za-z0-9._+@/-]*")


class WorkstationError(RuntimeError):
    pass


def theme_repo_url(value: str) -> str:
    """Accept only an HTTPS GitHub repository root with an Omarchy-safe name."""
    match = re.fullmatch(
        r"https://github\.com/([A-Za-z0-9][A-Za-z0-9-]*)/"
        r"([A-Za-z0-9_][A-Za-z0-9._+-]*)/?", value
    )
    if not match:
        raise WorkstationError("Theme must be an HTTPS GitHub repository URL")
    owner, repo = match.groups()
    repo = repo.removesuffix(".git")
    if repo.endswith(".git"):
        raise WorkstationError("Theme URL has an ambiguous repeated .git suffix")
    name = re.sub(r"-theme$", "", re.sub(r"^omarchy-", "", repo)).lower()
    if not re.fullmatch(r"[a-z0-9_][a-z0-9._+-]*", name):
        raise WorkstationError("The repository does not give a usable Omarchy theme name")
    return f"https://github.com/{owner}/{repo}"


class ThemeCatalog(HTMLParser):
    """Read only theme figures, excluding the site's own repository links."""

    def __init__(self):
        super().__init__()
        self.in_theme = False
        self.urls = {}

    def handle_starttag(self, tag, attrs):
        attrs = dict(attrs)
        if tag == "figure":
            self.in_theme = "themes__theme" in attrs.get("class", "").split()
        if self.in_theme and tag == "a":
            try:
                url = theme_repo_url(attrs.get("href", ""))
            except WorkstationError:
                return
            self.urls.setdefault(url.lower(), url)

    def handle_endtag(self, tag):
        if tag == "figure":
            self.in_theme = False


def fetch_theme_resource(request: Request) -> bytes:
    try:
        with urlopen(request, timeout=30) as response:
            return response.read()
    except (URLError, OSError, ValueError):
        # Never echo request headers, tokens, or an API response into logs.
        raise WorkstationError(
            "Theme lookup failed; check connectivity, GitHub credentials and API limits"
        ) from None


def theme_github_auth() -> tuple[Optional[str], Optional[str]]:
    gh = shutil.which("gh")
    token = os.environ.get("GH_TOKEN") or os.environ.get("GITHUB_TOKEN")
    if not gh and not token:
        raise WorkstationError(
            "Theme star lookup requires an authenticated gh CLI or GH_TOKEN/GITHUB_TOKEN on the host"
        )
    return gh, token


def github_theme_query(query: str, gh: Optional[str], token: Optional[str]) -> str:
    payload = json.dumps({"query": query})
    if gh:
        try:
            result = subprocess.run(
                [gh, "api", "--hostname", "github.com", "graphql", "--input", "-"],
                input=payload, text=True, capture_output=True, timeout=30,
                env={**os.environ, "GH_PROMPT_DISABLED": "1"},
            )
        except (OSError, subprocess.TimeoutExpired):
            raise WorkstationError("GitHub CLI theme lookup failed or timed out") from None
        if result.returncode:
            try:
                reply = json.loads(result.stdout)
                # GraphQL can return usable metadata alongside per-repo errors.
                # The ranking step validates every error before using the data.
                if not (isinstance(reply.get("data"), dict) and reply.get("errors")):
                    raise ValueError("no partial metadata")
            except (ValueError, AttributeError):
                raise WorkstationError(
                    "GitHub CLI theme lookup failed; check gh auth login --hostname github.com, "
                    "connectivity and API limits"
                ) from None
        return result.stdout
    request = Request(
        "https://api.github.com/graphql",
        data=payload.encode(),
        headers={"Authorization": f"Bearer {token}", "Content-Type": "application/json"},
    )
    return fetch_theme_resource(request).decode("utf-8")


def theme_star_counts(urls: list[str]) -> list[tuple[str, int]]:
    gh, token = theme_github_auth()
    ranked = []
    for start in range(0, len(urls), 50):
        batch = urls[start:start + 50]
        fields = []
        for index, url in enumerate(batch):
            owner, repo = url.removeprefix("https://github.com/").split("/")
            fields.append(
                f"r{index}: repository(owner: {json.dumps(owner)}, "
                f"name: {json.dumps(repo)}) {{ stargazerCount }}"
            )
        try:
            reply = json.loads(github_theme_query("query { " + " ".join(fields) + " }", gh, token))
            unavailable = set()
            aliases = {f"r{index}" for index in range(len(batch))}
            for error in reply.get("errors", []):
                path = error.get("path", [])
                if (
                    error.get("type") != "NOT_FOUND"
                    or len(path) != 1
                    or path[0] not in aliases
                    or reply["data"][path[0]] is not None
                ):
                    raise ValueError("incomplete ranking")
                unavailable.add(path[0])
            for index, url in enumerate(batch):
                if f"r{index}" in unavailable:
                    note(f"Skipping unavailable catalog theme: {url}")
                    continue
                stars = reply["data"][f"r{index}"]["stargazerCount"]
                if type(stars) is not int or stars < 0:
                    raise ValueError("invalid star count")
                ranked.append((url, stars))
        except (ValueError, TypeError, KeyError, AttributeError):
            raise WorkstationError(
                "GitHub could not read complete theme metadata; use a URL or unfiltered random"
            ) from None
    if not ranked:
        raise WorkstationError("No available GitHub theme repositories remain in the catalog")
    return ranked


def most_starred_theme(urls: list[str]) -> tuple[str, int]:
    ranked = theme_star_counts(urls)
    # Stable URL order breaks ties so repeated runs with equal counts agree.
    return min(ranked, key=lambda item: (-item[1], item[0].lower()))


def resolve_theme(value: str, min_stars: int = 10) -> str:
    if type(min_stars) is not int or min_stars < 0:
        raise WorkstationError("Theme minimum stars must be a non-negative integer")
    if not value:
        return ""
    if value not in {"random", "most-starred"}:
        return theme_repo_url(value)
    if value == "most-starred" or min_stars:
        theme_github_auth()
    catalog = ThemeCatalog()
    try:
        catalog.feed(fetch_theme_resource(Request(THEMES_CATALOG_URL)).decode("utf-8"))
    except UnicodeError:
        raise WorkstationError("The Omarchy theme catalog was not valid UTF-8") from None
    urls = sorted(catalog.urls.values(), key=str.lower)
    if not urls:
        raise WorkstationError("No GitHub themes found in the Omarchy catalog; use a URL")
    if value == "random":
        if min_stars:
            eligible = [(url, stars) for url, stars in theme_star_counts(urls) if stars >= min_stars]
            if not eligible:
                raise WorkstationError(f"No catalog themes have at least {min_stars} GitHub stars")
            selected, stars = random.SystemRandom().choice(eligible)
            note(
                f"Random theme: {selected} ({stars} GitHub stars; "
                f"{len(eligible)} themes meet the {min_stars}-star minimum)"
            )
        else:
            selected = random.SystemRandom().choice(urls)
            note(f"Random theme: {selected}")
    else:
        selected, stars = most_starred_theme(urls)
        note(f"Most-starred theme: {selected} ({stars} GitHub stars)")
    return selected


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


@dataclass(frozen=True)
class FactoryInput:
    selector: Optional[str]
    source: Optional[Path] = None
    bundle: Optional[Path] = None


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


def parse_factory(value: str) -> str:
    if value == "official" or re.fullmatch(r"[0-9a-f]{64}", value):
        return value
    if (not value or len(value.encode()) > 4096 or any(ord(c) < 32 for c in value)
            or value.startswith("-") or not (
                "/" in value or value.startswith("~") or value.endswith((".img.zst", ".factory"))
                or Path(value).expanduser().exists())):
        raise argparse.ArgumentTypeError("Factory must be official, a factory path, or an imported manifest SHA-256")
    return value


def factory_metadata(path: Path, maximum=65536) -> bytes:
    descriptor = os.open(path, os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK)
    with os.fdopen(descriptor, "rb") as source:
        info = os.fstat(source.fileno())
        if not stat.S_ISREG(info.st_mode) or not 0 < info.st_size <= maximum:
            raise ValueError(f"Factory metadata must be a bounded regular file: {path.name}")
        data = source.read(maximum + 1)
        current = os.fstat(source.fileno())
        if (len(data) != info.st_size or
                (info.st_size, info.st_mtime_ns, info.st_ctime_ns) !=
                (current.st_size, current.st_mtime_ns, current.st_ctime_ns)):
            raise ValueError(f"Factory metadata changed while reading: {path.name}")
        return data


def factory_payload_name(value) -> bool:
    return isinstance(value, str) and value not in (".", "..") and re.fullmatch(r"[A-Za-z0-9._-]{1,255}", value) is not None


def snapshot_factory_file(source: Path, destination: Path, expected: str) -> None:
    if not isinstance(expected, str) or not re.fullmatch(r"[0-9a-f]{64}", expected):
        raise ValueError(f"Invalid factory checksum: {source.name}")
    digest = hashlib.sha256()
    descriptor = os.open(source, os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK)
    with os.fdopen(descriptor, "rb") as stream, destination.open("xb") as target:
        before = os.fstat(stream.fileno())
        if not stat.S_ISREG(before.st_mode):
            raise ValueError(f"Factory payload must be a regular file: {source.name}")
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
            target.write(chunk)
        after = os.fstat(stream.fileno())
    if ((before.st_size, before.st_mtime_ns, before.st_ctime_ns) !=
            (after.st_size, after.st_mtime_ns, after.st_ctime_ns) or digest.hexdigest() != expected):
        raise ValueError(f"Factory checksum mismatch or changed payload: {source.name}")


@contextmanager
def prepare_factory_input(args):
    value = args.factory
    if value is None or value == "official" or re.fullmatch(r"[0-9a-f]{64}", value):
        yield FactoryInput(value)
        return
    try:
        selected = Path(value).expanduser().resolve(strict=True)
        image = selected if selected.is_file() else None
        source = selected.parent if image else selected
        if not source.is_dir():
            raise ValueError("Choose a successful build directory, its .img.zst file, or a prepared factory bundle")
        metadata = json.loads(factory_metadata(source / "factory.json"))
        image_name = metadata.get("compressed", {}).get("path")
        if not factory_payload_name(image_name) or not image_name.endswith(".img.zst"):
            raise ValueError("factory.json must name a flat .img.zst payload")
        if image and image.name != image_name:
            raise ValueError("The selected image does not match its companion factory.json")
        manifest_path = source / "reviewed-factory.json"
        prepared = manifest_path.exists() or manifest_path.is_symlink()
        if prepared:
            manifest_bytes = factory_metadata(manifest_path)
            files = json.loads(manifest_bytes).get("files")
            if (not isinstance(files, dict) or not 2 <= len(files) <= 32
                    or any(not factory_payload_name(name) or name == "reviewed-factory.json" for name in files)
                    or set(path.name for path in source.iterdir()) != set(files) | {"reviewed-factory.json"}
                    or "factory.json" not in files or image_name not in files):
                raise ValueError("Prepared factory contents must match the flat manifest payload list")
        else:
            checksums = {}
            for line in factory_metadata(source / "SHA256SUMS", 1024 * 1024).decode().splitlines():
                digest, separator, name = line.partition("  ")
                if (not separator or not re.fullmatch(r"[0-9a-f]{64}", digest)
                        or not name or Path(name).is_absolute() or ".." in Path(name).parts or name in checksums):
                    raise ValueError("Invalid or duplicate entry in factory SHA256SUMS")
                checksums[name] = digest
            names = ("factory.json", image_name, "compatibility.json", "image-build.json",
                     "source-compatibility.json", "provisioning-check.json", "user-provisioning-check.json")
            if any(name not in checksums for name in names):
                raise ValueError("A build image requires its checksums and companion provisioning evidence")
            files = {name: checksums[name] for name in names}
        with tempfile.TemporaryDirectory(prefix="dev-omarchy-factory-") as temporary:
            bundle = Path(temporary).resolve()
            for name, digest in files.items():
                snapshot_factory_file(source / name, bundle / name, digest)
            if prepared:
                (bundle / "reviewed-factory.json").write_bytes(manifest_bytes)
            else:
                helper = require_file(args.manager_dir / "Scripts/prepare_factory_bundle.py", "Factory preparation helper")
                result = run([
                    sys.executable, helper, bundle, "--name", "Minimal Omarchy", "--owner-contract", "lean-e4fffc6",
                    "--compatibility", "compatibility.json", "--image-build", "image-build.json",
                    "--provisioning", "compatibility.json", "--provisioning", "image-build.json",
                    "--provisioning", "source-compatibility.json", "--provisioning", "provisioning-check.json",
                    "--provisioning", "user-provisioning-check.json",
                ], check=False, capture=True)
                if result.returncode:
                    raise WorkstationError("Factory preparation failed: " + (result.stderr or "").strip())
            digest = hashlib.sha256(factory_metadata(bundle / "reviewed-factory.json")).hexdigest()
            yield FactoryInput(digest, selected, bundle)
    except (OSError, ValueError, TypeError, AttributeError) as error:
        raise WorkstationError(f"Cannot prepare custom factory: {error}") from error


def import_factory_input(args, factory: FactoryInput) -> None:
    if factory.bundle is None:
        return
    reply = cli_call(args, "factory-import", str(factory.bundle))
    factories = reply.get("factories")
    if (not isinstance(factories, list) or len(factories) != 1 or not isinstance(factories[0], dict)
            or factories[0].get("kind") != "custom" or factories[0].get("manifestSHA256") != factory.selector):
        raise WorkstationError("The imported factory does not match the prepared proposal; no VM was created")


def guest_factory(guest: dict) -> str:
    factory = guest.get("factory")
    if factory is None:
        return "official"  # Older official profiles did not record a factory field.
    if isinstance(factory, dict):
        if factory.get("kind") == "official":
            return "official"
        digest = factory.get("manifestSHA256")
        if factory.get("kind") == "custom" and isinstance(digest, str) and re.fullmatch(r"[0-9a-f]{64}", digest):
            return digest
    raise WorkstationError("The manager returned an invalid guest factory identity")


def check_factory(guest: dict, selected: Optional[str]) -> None:
    if selected is not None and guest_factory(guest) != selected:
        raise WorkstationError(
            "The selected factory does not match this guest; factory selection is creation-only. "
            "Choose a new VM name. The existing VM will not be replaced."
        )


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
    if not re.fullmatch(r"/tmp/dev-omarchy-workstation\.[A-Za-z0-9]+", value):
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
    for browser in ("chromium", "firefox"):
        if browser in package_names:
            if not package_installed(connection, browser):
                commands.append(f"omarchy install browser {browser}")
            handled_packages.add(browser)
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


def enable_bootstrap_sudo(connection: ManagedSSH) -> None:
    note(
        "Enabling Omarchy passwordless sudo for 60 minutes; "
        "confirm the native prompt and enter the guest sudo password"
    )
    # The native command returns success even when its confirmation is declined.
    # Require an active grant before starting any privileged setup work.
    guest_login_command(
        connection,
        "omarchy sudo passwordless 60 && omarchy sudo passwordless --active",
        tty=True,
    )


def disable_bootstrap_sudo(connection: ManagedSSH) -> None:
    note("Disabling Omarchy passwordless sudo after the bootstrap work")
    command = "bash -lc " + shlex.quote("omarchy sudo passwordless --disable")
    message = (
        "Could not confirm that bootstrap passwordless sudo was disabled. "
        "Run 'omarchy sudo passwordless --disable' inside the guest. "
        "Omarchy's 60-minute expiry and reboot cleanup remain the fallback."
    )
    try:
        # Cleanup must not wait for terminal input or hang on a lost connection.
        # Omarchy's --disable uses noninteractive sudo and handles an expired or
        # already revoked grant without enabling anything or prompting again.
        result = subprocess.run(
            connection.ssh_argv() + [command],
            stdin=subprocess.DEVNULL,
            capture_output=True,
            text=True,
            timeout=30,
        )
    except (OSError, subprocess.SubprocessError):
        raise WorkstationError(message) from None
    if result.returncode:
        raise WorkstationError(message)


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
    if args.lean_developer:
        require_file(GUEST_LEAN, "Lean developer payload")
        require_file(GUEST_LEAN_PACKAGES, "Lean developer package list")
    return manager_version(args)


def print_proposal(
    args,
    *,
    manager: str,
    action: str,
    guest: Optional[dict],
    mutable_errors: Iterable[str],
    factory_input: Optional[FactoryInput] = None,
) -> None:
    if args.remove_layout:
        layout = "remove the managed layout"
    elif args.layout_file:
        layout = str(args.layout_file)
    else:
        layout = "preserve the current choice"
    identifier = guest.get("id") if guest else "assigned by the manager"
    factory = (factory_input.selector if factory_input else args.factory) or (guest_factory(guest) if guest else "official")
    factory_source = f"\n  Factory source:  {factory_input.source} (verify/import through VM Manager)" if factory_input and factory_input.source else ""
    corrections = list(mutable_errors)
    packages = ", ".join(item.display() for item in args.packages) or "none"
    correction_text = (
        "\n  VM updates:      " + "; ".join(corrections) if corrections else ""
    )
    lean_text = "disabled (preserve installed software)"
    if args.lean_developer:
        keep = {item.name for item in args.packages}
        candidates = [
            name for line in GUEST_LEAN_PACKAGES.read_text().splitlines()
            if (name := line.split("#", 1)[0].strip()) and name not in keep
        ]
        lean_text = (
            "opt-in; remove when installed and safe: " + ", ".join(candidates)
            + "\n                   Retain required desktop/VM packages and selected guest software"
        )
    print(
        "\nProposed Omarchy workstation setup\n"
        f"  Manager CLI:     {manager} (command protocol 1)\n"
        f"  Managed VM:      {args.vm_name} ({identifier})\n"
        f"  VM action:       {action}\n"
        f"  Factory:         {factory}{factory_source}\n"
        f"  Resources:       {args.cpus} CPUs, {args.memory_gib} GiB RAM, {args.disk_gib} GiB disk\n"
        "  Integration:     manager-owned NAT, Retina/VirGL, clipboard and SSH\n"
        "  VM storage:      manager-owned factory image and independent disk\n"
        f"  Guest software:  {packages}\n"
        f"  Lean developer:  {lean_text}\n"
        f"  Preferences:     Foot {args.foot_font_size}, idle policy {args.idle_mode}\n"
        f"  App layout:      {layout}\n"
        f"  Theme:           {args.theme or 'preserve the current choice'}\n"
        "  Guest sudo:      native 60-minute passwordless grant; revoke on completion or failure\n"
        "  Compatibility:   apply the conditional Hyprland/VirGL repair\n"
        "  Lifecycle:       update Omarchy, apply customizations, reboot and validate\n"
        "  Host installs:   none"
        f"{correction_text}\n",
        flush=True,
    )


def ready_guest(args) -> tuple[dict, str]:
    manager = preflight(args)
    guest = find_guest(list_guests(args), args.vm_name)
    with prepare_factory_input(args) as factory:
        return ready_guest_with_factory(args, manager, guest, factory)


def ready_guest_with_factory(args, manager: str, guest: Optional[dict], factory: FactoryInput) -> tuple[dict, str]:
    if guest is not None:
        check_factory(guest, factory.selector)
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

    args.theme = resolve_theme(args.theme, min_stars=args.theme_min_stars)
    print_proposal(
        args,
        manager=manager,
        action=action,
        guest=guest,
        mutable_errors=mutable_errors,
        factory_input=factory,
    )
    confirm(args)
    import_factory_input(args, factory)

    if guest is None:
        reply = cli_call(
            args,
            "create",
            args.vm_name,
            *(["--factory", factory.selector] if factory.selector else []),
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
    check_factory(guest, factory.selector)
    post_errors = immutable_guest_errors(guest) + mutable_guest_errors(args, guest)
    if post_errors:
        raise WorkstationError(
            "The ready guest does not match the accepted proposal:\n  - "
            + format_errors(post_errors)
        )
    return guest, manager


def apply_workstation(args, connection: ManagedSSH) -> None:
    payloads = [GUEST_REPAIR, GUEST_APPLY, GUEST_THEME]
    if args.lean_developer:
        payloads.extend([GUEST_LEAN, GUEST_LEAN_PACKAGES])
    if args.layout_file:
        payloads.append(args.layout_file)
    remote_dir = ""
    try:
        remote_dir, _ = stage_payload(connection, payloads)
        install_selected_software(connection, args.packages)

        if args.lean_developer:
            lean_parts = ["python3", remote_dir + "/" + GUEST_LEAN.name]
            for item in args.packages:
                lean_parts.extend(["--keep", item.name])
            guest_login_command(connection, shlex.join(lean_parts), tty=True)

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
        if args.theme:
            apply_parts.extend(["--theme-url", args.theme])
        guest_login_command(connection, " ".join(shlex.quote(part) for part in apply_parts))

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

    def interrupted(signum, _frame):
        raise WorkstationError(f"Bootstrap interrupted by {signal.Signals(signum).name}")

    previous_handlers = {
        signum: signal.signal(signum, interrupted)
        for signum in (signal.SIGTERM, signal.SIGHUP)
    }
    try:
        try:
            # Start cleanup coverage before enable: a lost SSH reply or an
            # interrupted authorization can leave the native grant active.
            enable_bootstrap_sudo(connection)
            update_guest_system(connection)
            apply_workstation(args, connection)
        except BaseException:
            try:
                disable_bootstrap_sudo(connection)
            except WorkstationError as error:
                print(f"Warning: {error}", file=sys.stderr, flush=True)
            raise
        else:
            # Revoke before restarting: the manager needs no sudo, and this
            # leaves no grant behind if its restart or subsequent checks fail.
            disable_bootstrap_sudo(connection)
    finally:
        for signum, handler in previous_handlers.items():
            signal.signal(signum, handler)

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
    parser.add_argument("--manager-dir", type=Path, default=PROJECT_DIR.parent / "Omarchy VM Manager",
                        help="Existing manager checkout containing the factory preparation helper")
    parser.add_argument("--vm-name", default="Dev Omarchy")
    parser.add_argument("--factory", type=parse_factory, metavar="official|PATH|MANIFEST_SHA256",
                        help="official, a build/image/bundle path to import, or an imported manifest; omission preserves an existing guest or uses official")
    parser.add_argument("--cpus", type=int, default=8)
    parser.add_argument("--memory-gib", type=int, default=20)
    parser.add_argument("--disk-gib", type=int, default=64)
    parser.add_argument("--timeout", type=int, default=3600)
    parser.add_argument("--foot-font-size", default="16")
    parser.add_argument(
        "--theme", default="", metavar="URL|random|most-starred",
        help="optional HTTPS GitHub theme repository, or a selection from the Omarchy catalog",
    )
    parser.add_argument(
        "--theme-min-stars", type=int, default=10, metavar="COUNT",
        help="minimum GitHub stars for random theme selection (default: 10; 0 disables filtering)",
    )
    parser.add_argument(
        "--idle-mode", choices=("host", "guest", "keep"), default="host"
    )
    layout_group = parser.add_mutually_exclusive_group()
    layout_group.add_argument("--layout-file", type=Path)
    layout_group.add_argument("--remove-layout", action="store_true")
    parser.add_argument("--yes", action="store_true")
    parser.add_argument(
        "--lean-developer", action="store_true",
        help="remove optional desktop apps and hardware tools; retain required VM integration",
    )
    parser.add_argument(
        "--packages",
        type=parse_packages,
        default=tuple(GuestSoftware(name=name) for name in DEFAULT_PACKAGES),
        help=(
            "comma-separated guest software (default: "
            + (",".join(DEFAULT_PACKAGES) or "none")
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
    except KeyboardInterrupt:
        print("Bootstrap cancelled.", file=sys.stderr)
        return 130
    except subprocess.CalledProcessError as error:
        print(
            f"Error: command failed ({error.returncode}): {shlex.join(error.cmd)}",
            file=sys.stderr,
        )
        return error.returncode or 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
