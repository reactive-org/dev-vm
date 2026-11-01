#!/usr/bin/env python3
"""Build an isolated ARM64 Omarchy foundation factory; never operate a VM."""

import argparse
import fcntl
import hashlib
import importlib.util
import json
import os
import platform
import re
import shutil
import subprocess
import sys
import tarfile
import tempfile
import urllib.request
import uuid
from pathlib import Path


ROOT = Path(__file__).resolve().parent.parent
PROFILE = ROOT / "omarchy/image"
ARTIFACTS = ROOT / ".artifacts/omarchy-image"
spec = importlib.util.spec_from_file_location("image_compatibility", PROFILE / "compatibility.py")
compat = importlib.util.module_from_spec(spec)
spec.loader.exec_module(compat)


def run(argv, **kwargs):
    return subprocess.run([str(a) for a in argv], check=True, **kwargs)


def git(source, *args):
    return subprocess.check_output(["git", "-C", str(source), *args], text=True).strip()


def validate_source(source, commit, lock):
    if not re.fullmatch(r"[0-9a-f]{40}", commit):
        raise compat.CompatibilityError("Try source requires an exact 40-character commit")
    if not source.is_dir() or source.is_symlink():
        raise compat.CompatibilityError("Try source must be an existing checkout directory")
    if git(source, "rev-parse", "HEAD") != commit or git(source, "status", "--porcelain"):
        raise compat.CompatibilityError("Try source must be clean and match the selected commit")
    if git(source, "show", f"{commit}:guest/factory/build-image.sh") + "\n" != (
        source / "guest/factory/build-image.sh"
    ).read_text():
        raise compat.CompatibilityError("Working builder differs from its committed source")
    if compat.digest(source / "guest/factory/build-image.sh") != lock["builder_sha256"]:
        raise compat.CompatibilityError("Try factory builder differs from the reviewed v1.3.0 builder")
    if git(source, "merge-base", lock["try_commit"], commit) != lock["try_commit"]:
        raise compat.CompatibilityError("Integration source must descend from the pinned Try baseline")


def download(url, destination, expected):
    if destination.is_symlink():
        raise compat.CompatibilityError("Refusing a linked download cache entry")
    if destination.exists():
        if compat.digest(destination) != expected:
            raise compat.CompatibilityError(f"Cached source checksum mismatch: {destination.name}")
        return
    partial = destination.with_name(destination.name + ".partial")
    if partial.exists() or partial.is_symlink():
        raise compat.CompatibilityError(f"Inspect and remove incomplete source download: {partial}")
    try:
        with urllib.request.urlopen(url, timeout=60) as response, partial.open("xb") as output:
            shutil.copyfileobj(response, output)
        if compat.digest(partial) != expected:
            raise compat.CompatibilityError(f"Downloaded source checksum mismatch: {destination.name}")
        partial.rename(destination)
    finally:
        if partial.is_file() and not partial.is_symlink():
            partial.unlink()


def input_identity(source_commit, size):
    hashes = {}
    paths = list(PROFILE.rglob("*")) + [Path(__file__)] + [
        ROOT / "omarchy/guest" / name for name in (
            "apply-workstation.sh", "apply-theme.sh", "repair-try-omarchy-black-screen.sh",
            "check-workstation.sh",
        )
    ]
    for path in sorted(paths):
        if path.is_file() and "__pycache__" not in path.parts:
            hashes[path.relative_to(ROOT).as_posix()] = compat.digest(path)
    value = {"format": 1, "try_commit": source_commit, "size_gib": size, "inputs": hashes}
    encoded = json.dumps(value, sort_keys=True).encode()
    return hashlib.sha256(encoded).hexdigest(), value


def adapt_builder(text, lock):
    text = compat.replace_once(
        text,
        'target_install base-devel git limine efibootmgr omarchy-keyring archlinuxarm-keyring "$settings_package"\n'
        'target_install lua51 luarocks\ntarget_install omarchy-nvim\n',
        'target_install git limine efibootmgr omarchy-keyring archlinuxarm-keyring\n'
        'pacstrap -C "$builder_conf" -G -M -c -U "$target" /packages/omarchy-settings-dev-*.pkg.tar.zst\n',
    )
    text = compat.replace_once(
        text, 'target_install "$runtime_package"\n',
        'pacstrap -C "$builder_conf" -G -M -c -U "$target" /packages/omarchy-dev-*.pkg.tar.zst\n',
    )
    start = text.index('# The default set for the aarch64 platform,')
    end = text.index('if ((${#extra_packages[@]})); then', start)
    text = text[:start] + (
        'mapfile -t available </profile/resolved-base.packages\n'
        'unavailable=()\ntarget_install "${available[@]}"\n\n'
    ) + text[end:]
    start = text.index('node_index=$(curl ')
    end = text.index('touch "$provisioning/pending"', start)
    node = lock["node_file"]
    text = text[:start] + (
        f'node_file={node}\nnode_sha={lock["node_sha256"]}\n'
        f'cp /downloads/{node} "$provisioning/packages/$node_file"\n'
        'echo "$node_sha  $provisioning/packages/$node_file" | sha256sum -c --quiet -\n'
    ) + text[end:]
    text = compat.replace_once(
        text, 'log "Recording provenance"\n',
        'log "Checking user finalization in an isolated snapshot"\n'
        'btrfs -q subvolume snapshot "$top/@" "$top/@user-check"\n'
        'check_root="$state/user-check"\nmkdir -p "$check_root"\n'
        'do_mount -o "$btrfs_options,subvol=@user-check" "$root_loop" "$check_root"\n'
        'bash /profile/check-user.sh "$check_root" /output\n'
        'umount "$check_root"\nunset \'mounted[${#mounted[@]}-1]\'\n'
        'btrfs -q subvolume delete "$top/@user-check"\n'
        'python3 /profile/compatibility.py audit-root "$target" /profile /output/compatibility.json\n'
        'log "Recording provenance"\n',
    )
    text = compat.replace_once(
        text, 'image_name=omarchy-aarch64-$channel.img\n',
        'image_name=omarchy-workstation-aarch64-$channel.img\n',
    )
    text = compat.replace_once(
        text, '# Omarchy\'s factory reset restores @factory (orchestrator create_factory_snapshot).\n',
        'python3 /profile/compatibility.py audit-seal "$target" /output/compatibility.json\n\n'
        '# Omarchy\'s factory reset restores @factory (orchestrator create_factory_snapshot).\n',
    )
    return text


def stage_inputs(source, destination, lock, commit=None):
    upstream = destination / "upstream"
    upstream.mkdir()
    archive = destination / "try-source.tar"
    with archive.open("wb") as stream:
        run(["git", "-C", source, "archive", commit or lock["try_commit"], "guest", "LICENSE"], stdout=stream)
    with tarfile.open(archive) as stream:
        for member in stream.getmembers():
            if (member.name.startswith("/") or ".." in Path(member.name).parts
                    or not (member.isfile() or member.isdir())):
                raise compat.CompatibilityError("Unsafe upstream source archive")
        stream.extractall(upstream)
    archive.unlink()
    compat.normalize_source_permissions(upstream)
    profile = destination / "profile"
    shutil.copytree(PROFILE, profile, ignore=shutil.ignore_patterns("__pycache__"))
    (profile / "resolved-base.packages").write_text("\n".join(compat.package_list(PROFILE / "base.packages")) + "\n")
    compat.prepare_integration(upstream / "guest/package/try-omarchy")
    builder = upstream / "guest/factory/build-image.sh"
    if compat.digest(builder) != lock["builder_sha256"]:
        raise compat.CompatibilityError("Exported factory builder differs from the reviewed source")
    builder.write_text(adapt_builder(builder.read_text(), lock))
    run(["bash", "-n", builder])
    files = profile / "preferences/files"
    library = files / "usr/lib/dev-workstation"
    library.mkdir(parents=True)
    for name in ("apply-workstation.sh", "apply-theme.sh", "repair-try-omarchy-black-screen.sh", "check-workstation.sh"):
        shutil.copy2(ROOT / "omarchy/guest" / name, library / name)
    shutil.copy2(profile / "preferences/first-login.sh", library / "first-login.sh")
    unit = files / "usr/lib/systemd/user/dev-workstation-first-login.service"
    unit.parent.mkdir(parents=True)
    shutil.copy2(profile / "preferences/first-login.service", unit)
    (upstream / "guest/package/try-omarchy/LICENSE").write_bytes((upstream / "LICENSE").read_bytes())


def build(args):
    lock = json.loads((PROFILE / "inputs.lock.json").read_text())
    source = args.try_source.expanduser().absolute()
    commit = args.try_commit or lock["try_commit"]
    validate_source(source, commit, lock)
    required = compat.package_list(PROFILE / "base.packages")
    excluded = compat.package_list(PROFILE / "excluded.packages")
    if set(required) & set(excluded):
        raise compat.CompatibilityError("Required and excluded package profiles overlap")
    identity, provenance = input_identity(commit, args.size_gib)
    print(f"Omarchy desktop-foundation {'compatibility check' if args.check_only else 'image build'}", flush=True)
    print(f"  Try source: {commit}\n  Omarchy: {lock['omarchy_version']}\n"
          f"  Platform: macOS Apple Silicon / aarch64 guest\n  Disk: {args.size_gib} GiB, UEFI/Limine, Btrfs\n"
          f"  Required packages: {len(required)} roots plus dependency closure\n"
          f"  Output: {ARTIFACTS}\n  Operations: isolated guest containers; no VM operations", flush=True)
    if args.plan:
        return
    if platform.system() != "Darwin" or platform.machine() != "arm64":
        raise compat.CompatibilityError("The image workflow requires an Apple Silicon Mac")
    if not shutil.which("docker"):
        raise compat.CompatibilityError("Docker is required; install/start it separately")
    architecture = subprocess.check_output(["docker", "info", "--format", "{{.Architecture}}"], text=True).strip()
    if architecture not in ("aarch64", "arm64"):
        raise compat.CompatibilityError("Docker must provide an ARM64 Linux builder")
    for directory in (ROOT / ".artifacts", ARTIFACTS, ARTIFACTS / "downloads", ARTIFACTS / "package-cache"):
        if directory.is_symlink():
            raise compat.CompatibilityError(f"Refusing linked artifact directory: {directory}")
        directory.mkdir(exist_ok=True)
    if shutil.disk_usage(ARTIFACTS).free < (4 if args.check_only else args.size_gib + 4) * 1024 ** 3:
        raise compat.CompatibilityError("Insufficient artifact-volume space for a new factory and compression")
    with (ARTIFACTS / "build.lock").open("a") as guard:
        fcntl.flock(guard, fcntl.LOCK_EX | fcntl.LOCK_NB)
        downloads = ARTIFACTS / "downloads"
        downloads.mkdir(exist_ok=True)
        for repo, revision in (("omarchy", lock["omarchy_commit"]), ("omarchy-pkgs", lock["recipes_commit"])):
            download(f"https://codeload.github.com/omacom/{repo}/tar.gz/{revision}",
                     downloads / f"{repo}-{revision}.tar.gz", lock["archives"][repo])
        version = lock["node_file"].split("-linux-", 1)[0][5:]
        download(f"https://nodejs.org/dist/{version}/{lock['node_file']}",
                 downloads / lock["node_file"], lock["node_sha256"])
        stage = Path(tempfile.mkdtemp(prefix=".building-", dir=ARTIFACTS))
        output = stage / "output"
        output.mkdir()
        factory_work = stage / "factory-work"
        factory_work.mkdir()
        stage_inputs(source, stage, lock, commit)
        image = "dev-vm-omarchy-image-builder:" + identity[:16]
        run(["docker", "build", "--platform", "linux/arm64", "-f",
             stage / "upstream/guest/factory/Containerfile", "-t", image, stage / "upstream"])
        image_id = subprocess.check_output(["docker", "image", "inspect", "--format", "{{.Id}}", image], text=True).strip()
        volume = "dev-vm-image-" + uuid.uuid4().hex
        run(["docker", "volume", "create", "--label", "dev.dev-vm.role=image-build", volume], stdout=subprocess.DEVNULL)
        try:
            command = ["docker", "run", "--rm", "--platform", "linux/arm64",
                       "--cidfile", stage / "container.id"]
            if not args.check_only:
                command += ["--privileged"]
            command += ["--mount", f"type=bind,src={stage / 'upstream'},dst=/workspace,readonly",
                        "--mount", f"type=bind,src={stage / 'profile'},dst=/input-profile,readonly",
                        "--mount", f"type=bind,src={downloads},dst=/downloads,readonly",
                        "--mount", f"type=bind,src={factory_work},dst=/factory-work",
                        "--mount", f"type=bind,src={ARTIFACTS / 'package-cache'},dst=/factory-work/pacman-cache",
                        "--mount", f"type=bind,src={output},dst=/output",
                        "--mount", f"type=volume,src={volume},dst=/work",
                        "--entrypoint", "/bin/bash", image_id,
                        "/input-profile/build-container.sh", "check" if args.check_only else "build", str(args.size_gib)]
            run(command)
        finally:
            cidfile = stage / "container.id"
            if cidfile.is_file():
                container = cidfile.read_text().strip()
                if re.fullmatch(r"[a-f0-9]{64}", container):
                    subprocess.run(["docker", "container", "rm", "--force", container],
                                   stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, check=False)
            run(["docker", "volume", "rm", volume], stdout=subprocess.DEVNULL)
        provenance.update({"input_identity": identity, "builder_image": image_id,
                           "validation": "container-only" if args.check_only else "sealed-image-static-checks",
                           "manager_admitted": False, "guest_boot_tested": False,
                           "live_arch_repositories": True})
        (output / "image-build.json").write_text(json.dumps(provenance, indent=2, sort_keys=True) + "\n")
        sums = []
        for path in sorted(output.rglob("*")):
            if path.is_file() and path.name != "SHA256SUMS":
                sums.append(f"{compat.digest(path)}  {path.relative_to(output).as_posix()}")
        (output / "SHA256SUMS").write_text("\n".join(sums) + "\n")
        if args.check_only:
            suffix = "check-" + uuid.uuid4().hex[:12]
        else:
            factory = json.loads((output / "factory.json").read_text())
            image_path = output / factory["compressed"]["path"]
            if compat.digest(image_path) != factory["compressed"]["sha256"]:
                raise compat.CompatibilityError("Compressed factory checksum differs")
            suffix = factory["disk"]["sha256"][:16]
        destination = ARTIFACTS / (identity[:16] + "-" + suffix)
        if destination.exists():
            raise compat.CompatibilityError("Output identity already exists; refusing replacement")
        output.rename(destination)
        shutil.rmtree(stage)
        print(f"Verified output: {destination}\nVM Manager admission and real GPU/first-boot checks remain required.", flush=True)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--try-source", type=Path, default=ROOT.parent / "Omarchy VM Manager/Vendor/try-omarchy")
    parser.add_argument("--try-commit", help="Exact reviewed integration-source commit; defaults to the lock")
    parser.add_argument("--size-gib", type=int, default=20)
    parser.add_argument("--check-only", action="store_true", help="Build/check guest packages without loop devices or a factory disk")
    parser.add_argument("--plan", action="store_true", help="Check local inputs and print the proposal without Docker or downloads")
    args = parser.parse_args()
    if not 20 <= args.size_gib <= 128:
        parser.error("--size-gib must be between 20 and 128")
    try:
        build(args)
    except KeyboardInterrupt:
        parser.exit(130, "Omarchy image build interrupted; no VM was operated.\n")
    except (OSError, ValueError, compat.CompatibilityError, subprocess.CalledProcessError) as error:
        parser.exit(1, f"Omarchy image build failed: {error}\n")


if __name__ == "__main__":
    main()
