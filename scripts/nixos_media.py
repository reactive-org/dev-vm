"""ARM64 NixOS ISO preparation with Python's standard library and xorriso."""
import hashlib
import pathlib
import re
import shutil
import struct
import subprocess
import tarfile


INSTANCE_FILES = {"hardware-configuration.nix", "installation.nix", "integration.nix", "identity.nix", "authorized-keys.pub"}


def copy_tree(source, target):
    """Copy source code only; reject symlinks instead of following host paths."""
    source, target = pathlib.Path(source).resolve(), pathlib.Path(target).resolve()
    if source == target or source in target.parents:
        raise ValueError("Copy destination must be outside the source tree")
    for item in source.rglob("*"):
        if item.is_symlink():
            raise ValueError("Source trees must not contain symlinks: " + str(item))
    shutil.copytree(source, target, dirs_exist_ok=True, ignore=shutil.ignore_patterns(".git", "__pycache__", ".DS_Store"))


def source_archive(source, output):
    source = pathlib.Path(source)
    with tarfile.open(output, "w") as archive:
        for item in sorted(source.rglob("*")):
            relative = item.relative_to(source)
            if any(part in (".git", "__pycache__", ".DS_Store") for part in relative.parts):
                continue
            if relative.parts[0] == "local" or (relative.parts[0] == "hosts" and item.name in INSTANCE_FILES):
                continue
            if item.is_symlink():
                raise ValueError("Source trees must not contain symlinks: " + str(item))
            if item.is_file():
                archive.add(item, arcname=str(relative), recursive=False)
    output = pathlib.Path(output)
    output.chmod(0o600)
    return hashlib.sha256(output.read_bytes()).hexdigest()


class FatImage:
    """Replace a short-name FAT12/16 file without allocating new clusters.

    The official ARM64 ISO has a small EFI image and an oversized GRUB menu.
    Only that menu's existing clusters and length field are changed.
    """
    def __init__(self, data):
        self.data = bytearray(data)
        self.bps = self.u16(11)
        self.spc = self.data[13]
        if self.bps not in (512, 1024, 2048, 4096) or not self.spc:
            raise ValueError("Unsupported EFI FAT geometry")
        self.fat = self.u16(14) * self.bps
        self.root = (self.u16(14) + self.data[16] * self.u16(22)) * self.bps
        self.root_size = self.u16(17) * 32
        self.first_data = self.root + ((self.root_size + self.bps - 1) // self.bps) * self.bps
        self.cluster_size = self.bps * self.spc
        count = (len(self.data) - self.first_data) // self.cluster_size
        self.bits = 12 if count < 4085 else 16
        if count >= 65525 or self.root_size == 0:
            raise ValueError("Only FAT12/16 EFI images are supported")

    def u16(self, offset):
        return struct.unpack_from("<H", self.data, offset)[0]

    def chain(self, cluster):
        result, seen = [], set()
        end = 0xff8 if self.bits == 12 else 0xfff8
        while cluster < end:
            if cluster < 2 or cluster in seen:
                raise ValueError("Invalid EFI FAT cluster chain")
            seen.add(cluster)
            offset = self.first_data + (cluster - 2) * self.cluster_size
            if offset + self.cluster_size > len(self.data):
                raise ValueError("EFI FAT cluster outside image")
            result.append(offset)
            if self.bits == 12:
                value = self.u16(self.fat + cluster * 3 // 2)
                cluster = value >> 4 if cluster % 2 else value & 0xfff
            else:
                cluster = self.u16(self.fat + cluster * 2)
        return result

    def entry(self, path):
        offsets = list(range(self.root, self.root + self.root_size, 32))
        for index, part in enumerate(path):
            base, _, extension = part.upper().partition(".")
            name = (base.ljust(8) + extension.ljust(3)).encode("ascii")
            found = None
            for offset in offsets:
                if self.data[offset] == 0:
                    break
                if self.data[offset] != 0xe5 and self.data[offset + 11] != 15 and self.data[offset:offset + 11] == name:
                    found = offset
                    break
            if found is None:
                raise ValueError("EFI image is missing " + "/".join(path))
            if index == len(path) - 1:
                return found
            if not self.data[found + 11] & 16:
                raise ValueError("Invalid EFI directory")
            offsets = [offset + step for offset in self.chain(self.u16(found + 26)) for step in range(0, self.cluster_size, 32)]
        raise ValueError("Empty EFI path")

    def replace(self, path, payload):
        entry = self.entry(path)
        clusters = self.chain(self.u16(entry + 26))
        if len(payload) > len(clusters) * self.cluster_size:
            raise ValueError("New EFI menu exceeds its allocated space")
        padded = payload.ljust(len(clusters) * self.cluster_size, b"\0")
        for index, offset in enumerate(clusters):
            self.data[offset:offset + self.cluster_size] = padded[index * self.cluster_size:(index + 1) * self.cluster_size]
        struct.pack_into("<I", self.data, entry + 28, len(payload))


def grub_menu(original, token):
    if not re.fullmatch(r"[a-f0-9]{32}", token):
        raise ValueError("Invalid installer token")
    if "workstation.install=" in original or "systemd.run=" in original:
        raise ValueError("Use an upstream ISO, not previously generated private installer media")
    linux = re.search(r"^\s*linux\s+(/boot/\S+/Image\s+.*)$", original, re.M)
    initrd = re.search(r"^\s*initrd\s+(/boot/\S+/initrd)\s*$", original, re.M)
    if not linux or not initrd or "init=/nix/store/" not in linux.group(1):
        raise ValueError("Expected the upstream ARM64 NixOS EFI menu")
    arguments = " ".join(part for part in linux.group(1).split() if part not in ("splash", "quiet"))
    return ("set timeout=3\nset default=0\n"
            "search --set=root --file /EFI/nixos-installer-image\n"
            "menuentry 'Install confirmed NixOS workstation on blank VM disk' {\n"
            "  terminal_output console\n  linux " + arguments +
            " systemd.unit=kernel-command-line.target systemd.run=/iso/workstation/boot.sh systemd.run_success_action=poweroff"
            " systemd.run_failure_action=none workstation.install=" + token +
            " console=tty0 console=ttyS0,115200n8\n  initrd " + initrd.group(1) + "\n}\n")


def prepare_iso(image, output, payload, scratch):
    image, output, payload, scratch = map(pathlib.Path, (image, output, payload, scratch))
    original = subprocess.check_output(["bsdtar", "-xOf", str(image), "EFI/BOOT/grub.cfg"], text=True)
    token = (payload / "token").read_text().strip()
    menu = grub_menu(original, token).encode()
    (scratch / "grub.cfg").write_bytes(menu)
    efi = FatImage(subprocess.check_output(["bsdtar", "-xOf", str(image), "boot/efi.img"]))
    efi.replace(["EFI", "BOOT", "GRUB.CFG"], menu)
    (scratch / "efi.img").write_bytes(efi.data)
    boot = payload / "boot.sh"
    boot.write_text("#!/bin/sh\nexec /run/current-system/sw/bin/bash /iso/workstation/source/automation/install-unattended.sh\n")
    boot.chmod(0o755)
    # Never reuse a credential-bearing ISO from another VM or installation.
    subprocess.run(["xorriso", "-abort_on", "SORRY", "-indev", str(image), "-outdev", str(output),
                    "-boot_image", "any", "replay", "-map", str(scratch / "grub.cfg"), "/EFI/BOOT/grub.cfg",
                    "-map", str(scratch / "efi.img"), "/boot/efi.img", "-map", str(payload), "/workstation"], check=True)
    output.chmod(0o600)
