#!/usr/bin/env python3
"""Idempotent Omarchy feature operations used by the tagged Ansible roles."""

import argparse
import hashlib
import json
import os
import platform
import re
import shlex
import subprocess
import sys
from pathlib import Path


FEATURES = ("workstation", "browsers", "docker", "languages", "agents", "credentials")
BROWSERS = {"chromium": "chromium", "firefox": "firefox"}
AGENTS = {"claude", "codex", "opencode", "pi", "copilot", "amp", "crush"}
CREDENTIALS = {"1password", "1password-cli", "github-cli"}
DOCKER_PACKAGES = ("docker", "docker-buildx", "docker-compose", "ufw-docker")
WORKSTATION_PACKAGES = ("herdr", "udiskie", "socat", "imagemagick", "inotify-tools")
LANGUAGE_PACKAGES = {
    "ruby": ("base-devel", "libyaml", "openssl", "readline", "zlib", "libffi", "gmp"),
    "python": ("base-devel", "openssl", "readline", "zlib", "libffi", "xz"),
}


class FeatureError(RuntimeError):
    pass


def run(argv, *, check=True):
    result = subprocess.run(
        [str(x) for x in argv], capture_output=True, text=True,
        cwd=Path.home(), env={**os.environ, "LC_ALL": "C.UTF-8"},
    )
    if check and result.returncode:
        raise FeatureError(f"{argv[0]} failed: {(result.stderr or result.stdout).strip()}")
    return result


def native(argv, *, check=True):
    return run(["bash", "-lc", shlex.join([str(x) for x in argv])], check=check)


def selection(value, allowed, name):
    if not isinstance(value, list) or any(not isinstance(x, str) or x not in allowed for x in value):
        raise FeatureError(f"{name} must be a list selected from {', '.join(sorted(allowed))}")
    if len(value) != len(set(value)):
        raise FeatureError(f"Duplicate {name}")
    return value


def tools(value, *, agents=False):
    if not isinstance(value, dict):
        raise FeatureError("Tools must be a mapping of mise short names to version selectors")
    for tool, version in value.items():
        if not isinstance(tool, str) or not re.fullmatch(r"[a-z][a-z0-9_-]*", tool):
            raise FeatureError("Use a mise registry short name, without backend commands or paths")
        if agents and tool not in AGENTS:
            raise FeatureError(f"Unsupported coding agent: {tool}")
        if not isinstance(version, str) or (version and not re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9._+\-]*", version)):
            raise FeatureError(f"Invalid mise version selector for {tool}")
    return value


def validate_config(feature, value):
    if not isinstance(value, dict):
        raise FeatureError("Feature input must be an object")
    expected = {
        "browsers": {"browsers"}, "docker": set(), "languages": {"tools"},
        "agents": {"tools"}, "credentials": {"packages"},
        "workstation": {"font_size", "idle_mode", "theme", "layout", "remove_layout"},
    }[feature]
    if set(value) != expected:
        raise FeatureError(f"Unexpected or missing fields for {feature}")
    if feature == "browsers":
        selection(value["browsers"], BROWSERS, "browsers")
    elif feature in ("languages", "agents"):
        tools(value["tools"], agents=feature == "agents")
    elif feature == "credentials":
        selection(value["packages"], CREDENTIALS, "credential packages")
    elif feature == "workstation":
        if not re.fullmatch(r"(?:[6-9]|[12][0-9]|3[0-2])(?:\.[0-9]+)?", str(value["font_size"])):
            raise FeatureError("Foot font size must be between 6 and 32")
        if value["idle_mode"] not in ("host", "guest", "keep"):
            raise FeatureError("Idle mode must be host, guest or keep")
        if not isinstance(value["theme"], str) or (value["theme"] and not re.fullmatch(
            r"https://github\.com/[A-Za-z0-9][A-Za-z0-9-]*/[A-Za-z0-9_][A-Za-z0-9._+\-]*/?", value["theme"]
        )):
            raise FeatureError("Theme must be an HTTPS GitHub repository URL")
        if type(value["remove_layout"]) is not bool or not isinstance(value["layout"], str):
            raise FeatureError("Invalid layout selection")
        if value["layout"] and value["remove_layout"]:
            raise FeatureError("Choose a layout or removal, not both")
    return value


class FeatureRunner:
    def __init__(self, feature, config, check=False):
        self.feature = feature
        self.config = validate_config(feature, config)
        self.check = check
        self.actions = []
        self.notes = []

    def preflight(self):
        if platform.system() != "Linux" or platform.machine() != "aarch64" or os.geteuid() == 0:
            raise FeatureError("Run as the non-root owner of an Omarchy aarch64 guest")
        if native(["command", "-v", "omarchy"], check=False).returncode:
            raise FeatureError("Omarchy is required")
        if run(["pacman", "-Qq", "try-omarchy"], check=False).returncode:
            raise FeatureError("The native Try Omarchy integration package is required")
        if self.feature != "workstation" and not self.check:
            if run(["sudo", "-n", "true"], check=False).returncode:
                raise FeatureError("Enable Omarchy's native temporary sudo grant before applying features")

    def installed(self, package):
        result = run(["pacman", "-Qq", "--", package], check=False)
        if result.returncode not in (0, 1):
            raise FeatureError("Unable to inspect the guest package database")
        return result.returncode == 0

    def mutate(self, argv, description):
        self.actions.append(description)
        if not self.check:
            native(argv)

    def packages(self, packages):
        missing = [name for name in packages if not self.installed(name)]
        if missing:
            self.mutate(["omarchy-pkg-add", *missing], "Install packages: " + ", ".join(missing))
        return missing

    def browsers(self):
        for browser in self.config["browsers"]:
            if not self.installed(BROWSERS[browser]):
                self.mutate(["omarchy-install-browser", browser], "Install browser: " + browser)

    def docker(self):
        self.packages(DOCKER_PACKAGES)
        if self.check:
            self.actions.append("Verify Docker firewall integration with the native sudo grant")
            self.notes.append("Firewall repair is conservatively reported in check mode; no privileged writes run")
        else:
            status = native(["sudo", "-n", "ufw", "status"]).stdout
            if not status.startswith("Status: active"):
                raise FeatureError("Docker requires the existing Omarchy UFW policy to be active; no policy was replaced")
            paths = ("/etc/ufw/after.rules", "/etc/ufw/after6.rules", "/etc/ufw/user.rules", "/etc/ufw/user6.rules")
            before = native(["sudo", "-n", "sha256sum", *paths]).stdout
            native(["sudo", "-n", "ufw-docker", "install"])
            for subnet in ("172.16.0.0/12", "192.168.0.0/16"):
                native(["sudo", "-n", "ufw", "allow", "in", "proto", "udp", "from", subnet,
                        "to", "172.17.0.1", "port", "53", "comment", "allow-docker-dns"])
            after = native(["sudo", "-n", "sha256sum", *paths]).stdout
            if before != after:
                native(["sudo", "-n", "ufw", "reload"])
                self.actions.append("Configure native Docker firewall integration")
        enabled = not native(["systemctl", "is-enabled", "--quiet", "docker.socket"], check=False).returncode
        active = not native(["systemctl", "is-active", "--quiet", "docker.socket"], check=False).returncode
        service_active = not native(["systemctl", "is-active", "--quiet", "docker.service"], check=False).returncode
        if not service_active and (not enabled or not active):
            self.mutate(["sudo", "-n", "systemctl", "enable", "--now", "docker.socket"], "Enable Docker socket activation")

    def configured_tool(self, tool):
        result = native(["mise", "ls", "--json", tool])
        try:
            value = json.loads(result.stdout)
        except ValueError as error:
            raise FeatureError("mise returned invalid tool metadata") from error
        if isinstance(value, dict):
            rows = value.get(tool, [])
        elif isinstance(value, list):
            # A tool-filtered `mise ls --json TOOL` returns an array whose
            # rows omit the tool name. Older/unfiltered output can name it.
            rows = value
        else:
            raise FeatureError("mise returned an unsupported tool metadata format")
        if not isinstance(rows, list) or any(not isinstance(row, dict) for row in rows):
            raise FeatureError("mise returned unsupported tool rows")
        return any(
            row.get("tool", row.get("name", tool)) == tool
            and (row.get("source") or row.get("requested_version") or row.get("active"))
            for row in rows
        )

    def toolchain(self):
        requested = self.config["tools"]
        if not requested:
            return
        missing_mise = bool(self.packages(["mise-bin"]))
        if missing_mise:
            self.mutate(["mise", "reshim", "--system"], "Initialize Omarchy's lazy tool shims")
            self.mutate(["mise", "reshim"], "Initialize user tool shims")
        for tool, version in requested.items():
            if self.feature == "languages":
                self.packages(LANGUAGE_PACKAGES.get(tool, ()))
            selector = f"{tool}@{version}" if version else tool
            if self.check and missing_mise:
                self.actions.append("Install mise tool: " + selector)
                continue
            configured = self.configured_tool(tool)
            desired = native(["mise", "where", selector], check=False)
            current = native(["mise", "where", tool], check=False)
            if configured and desired.returncode == 0 and current.returncode == 0 and desired.stdout.strip() == current.stdout.strip():
                continue
            if version:
                self.mutate(["mise", "use", "--global", selector], "Select mise tool: " + selector)
            elif configured:
                self.mutate(["mise", "install", tool], "Install Omarchy's configured tool: " + tool)
            else:
                self.mutate(["mise", "use", "--global", tool + "@latest"], "Select user mise tool: " + tool)

    def snapshot(self):
        home = Path.home()
        paths = (
            ".config/foot/foot.ini", ".config/omarchy/shell.json", ".config/hypr/hyprland.lua",
            ".config/hypr/looknfeel.lua", ".config/hypr/dev-workstation-layout.lua",
            ".config/systemd/user/omarchy-sleep-lock.service",
            ".config/systemd/user/dev-workstation-first-login.service.d/90-session-order.conf",
            ".local/state/omarchy/current/theme.name", ".local/state/omarchy/current/theme",
        )
        result = {}
        for name in paths:
            path = home / name
            if path.is_symlink():
                result[name] = ("link", os.readlink(path))
            elif path.is_file():
                result[name] = ("file", hashlib.sha256(path.read_bytes()).hexdigest())
        return result

    def first_login_ordering(self, unit=Path("/usr/lib/systemd/user/dev-workstation-first-login.service")):
        # Repair only the exact repository unit shipped by preferences 1-1.
        if not unit.is_file() or hashlib.sha256(unit.read_bytes()).hexdigest() != "2184718491edc880ff5256728419d97a4640d762da30dd4e2cfa1030f13f48aa":
            return
        path = Path.home() / ".config/systemd/user/dev-workstation-first-login.service.d/90-session-order.conf"
        content = "[Unit]\nAfter=graphical-session.target try-omarchy-session.service\n"
        if path.is_symlink() or (path.exists() and path.read_text() != content):
            raise FeatureError("Preserving a customized first-login ordering override")
        if not path.exists():
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text(content)
            path.chmod(0o644)
            native(["systemctl", "--user", "daemon-reload"])

    def workstation(self):
        payload = Path(__file__).resolve().parent
        layout = self.config["layout"]
        if layout and (Path(layout).resolve().parent != payload or not Path(layout).is_file()):
            raise FeatureError("Layout must be the explicitly staged payload file")
        self.packages(WORKSTATION_PACKAGES)
        if self.check:
            self.actions.append("Compare/apply the selected workstation preferences and GPU compatibility repair")
            self.notes.append("Workstation check mode reports conservatively and executes no configuration scripts")
            return
        before = self.snapshot()
        self.first_login_ordering()
        command = ["bash", str(payload / "apply-workstation.sh"), "--foot-font-size", str(self.config["font_size"]),
                   "--idle-mode", self.config["idle_mode"]]
        if self.config["theme"]:
            command += ["--theme-url", self.config["theme"]]
        if layout:
            command += ["--layout-file", layout]
        elif self.config["remove_layout"]:
            command += ["--remove-layout"]
        native(command)
        native(["bash", str(payload / "repair-try-omarchy-black-screen.sh")])
        if before != self.snapshot():
            self.actions.append("Apply workstation preferences")

    def apply(self):
        self.preflight()
        if self.feature in ("agents", "languages"):
            self.toolchain()
        elif self.feature == "credentials":
            self.packages(self.config["packages"])
        else:
            getattr(self, self.feature)()
        return {"changed": bool(self.actions), "actions": self.actions, "notes": self.notes,
                "check_mode": self.check, "feature": self.feature}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--feature", choices=FEATURES, required=True)
    parser.add_argument("--check", action="store_true")
    args = parser.parse_args()
    runner = None
    try:
        config = json.load(sys.stdin)
        runner = FeatureRunner(args.feature, config, args.check)
        print(json.dumps(runner.apply()))
    except (OSError, ValueError, FeatureError) as error:
        print(json.dumps({"changed": bool(runner and runner.actions), "actions": runner.actions if runner else []}))
        print(str(error), file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
