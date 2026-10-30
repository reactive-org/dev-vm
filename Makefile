SHELL := /bin/bash
.DEFAULT_GOAL := help

PRLCTL ?= /usr/local/bin/prlctl
DOWNLOADS_DIR ?=
SIZING_VM ?=
VM_NAME ?=
IMAGE ?=
CPUS ?=
MEMORY_MB ?=
DISK_GB ?=
START_VM ?=
RESUME ?= no
AUTOINSTALL ?= yes
GUEST_USER ?=
GUEST_HOSTNAME ?=
SSH_PUBLIC_KEY ?=
ARTIFACTS_DIR ?=
WAIT_FOR_SSH ?= yes
SSH_HOST ?=
SSH_WAIT_TIMEOUT ?= 2700
RUN_ANSIBLE ?= yes
ANSIBLE_PLAYBOOK ?=
BECOME_ARGS ?= --ask-become-pass
PLAYBOOK_ARGS ?=
DEVELOPER_EXTRA_TASKS_FILE ?=
SSH_KNOWN_HOSTS_FILE ?=
SOURCE ?=
DESTINATION ?=
FILE_MODE ?= 600
NIXOS_HOST ?= workstation-test
LOCAL_FLAKE ?=
NIXOS_PASSWORD_HASH_FILE ?=
NIXOS_SHARE ?= yes
NIXOS_BUILD_ONLY ?= no
IMAGE_SHA256 ?=
NIXOS_RESUME_DIR ?=
NIXOS_RETRY_BLANK ?= no
export SOURCE DESTINATION FILE_MODE SSH_HOST GUEST_USER SSH_KNOWN_HOSTS_FILE
export PRLCTL VM_NAME IMAGE CPUS MEMORY_MB DISK_GB GUEST_HOSTNAME SSH_PUBLIC_KEY
export DOWNLOADS_DIR ARTIFACTS_DIR SSH_WAIT_TIMEOUT NIXOS_HOST LOCAL_FLAKE
export NIXOS_PASSWORD_HASH_FILE NIXOS_SHARE NIXOS_BUILD_ONLY IMAGE_SHA256
export NIXOS_RESUME_DIR NIXOS_RETRY_BLANK

.PHONY: help bootstrap bootstrap-nixos resume-nixos apply-nixos check-nixos nixos-images nixos-status configure-nixos-share copy-nixos-user-file clipboard-to-vm clipboard-from-vm apply-playbook images vms

help: ## Show available targets and overrides
	@awk 'BEGIN {FS = ":.*## "} /^[a-zA-Z0-9_-]+:.*## / {printf "%-18s %s\n", $$1, $$2}' $(MAKEFILE_LIST)

bootstrap-nixos: ## Confirm, create and install a fresh ARM64 NixOS VM unattended
	@python3 ./scripts/nixos-vm.py bootstrap

resume-nixos: ## Finish an interrupted bootstrap, or explicitly retry its original blank VM
	@python3 ./scripts/nixos-vm.py resume

apply-nixos: ## Build and switch an existing NixOS VM, preserving its instance configuration
	@python3 ./scripts/nixos-vm.py apply

check-nixos: ## Build the selected configuration in an existing VM without switching
	@NIXOS_BUILD_ONLY=yes python3 ./scripts/nixos-vm.py apply

nixos-images: ## List downloaded NixOS ARM64 installer ISOs, newest first
	@python3 ./scripts/nixos-vm.py images

nixos-status: ## Inspect the latest asynchronous guest deployment
	@python3 ./scripts/nixos-vm.py status

configure-nixos-share: ## Expose only the existing ~/Parallels/Shared folder to a NixOS VM
	@bash ./scripts/configure-nixos-share.sh "$(PRLCTL)" "$(VM_NAME)"

copy-nixos-user-file: ## Explicitly copy one selected file into a mutable guest home; refuse overwrite
	@python3 ./scripts/nixos-copy-user-file.py --host "$$SSH_HOST" --user "$$GUEST_USER" --known-hosts "$$SSH_KNOWN_HOSTS_FILE" --source "$$SOURCE" --destination "$$DESTINATION" --mode "$$FILE_MODE"

clipboard-to-vm: ## Copy macOS clipboard text to the NixOS Wayland clipboard over SSH
	@python3 ./scripts/nixos-clipboard.py to-vm --host "$(SSH_HOST)" --user "$(GUEST_USER)" --known-hosts "$(SSH_KNOWN_HOSTS_FILE)"

clipboard-from-vm: ## Copy NixOS Wayland clipboard text to macOS over SSH
	@python3 ./scripts/nixos-clipboard.py from-vm --host "$(SSH_HOST)" --user "$(GUEST_USER)" --known-hosts "$(SSH_KNOWN_HOSTS_FILE)"

bootstrap: ## Interactively create an ARM64 Ubuntu VM from an ISO
	@./scripts/bootstrap-vm.sh \
		--prlctl "$(PRLCTL)" \
		--downloads "$(DOWNLOADS_DIR)" \
		--sizing-vm "$(SIZING_VM)" \
		--name "$(VM_NAME)" \
		--image "$(IMAGE)" \
		--cpus "$(CPUS)" \
		--memory-mb "$(MEMORY_MB)" \
		--disk-gb "$(DISK_GB)" \
		--start "$(START_VM)" \
		--resume "$(RESUME)" \
		--autoinstall "$(AUTOINSTALL)" \
		--guest-user "$(GUEST_USER)" \
		--hostname "$(GUEST_HOSTNAME)" \
		--ssh-key "$(SSH_PUBLIC_KEY)" \
		--artifacts "$(ARTIFACTS_DIR)" \
		--wait-for-ssh "$(WAIT_FOR_SSH)" \
		--ssh-host "$(SSH_HOST)" \
		--ssh-timeout "$(SSH_WAIT_TIMEOUT)" \
		--run-ansible "$(RUN_ANSIBLE)" \
		--ansible "$(ANSIBLE_PLAYBOOK)" \
		--developer-extra-tasks "$(DEVELOPER_EXTRA_TASKS_FILE)"

apply-playbook: ## Apply site.yml to an existing bootstrapped Parallels VM
	@./scripts/apply-playbook.sh \
		--prlctl "$(PRLCTL)" \
		--name "$(VM_NAME)" \
		--guest-user "$(GUEST_USER)" \
		--ssh-host "$(SSH_HOST)" \
		--ssh-key "$(SSH_PUBLIC_KEY)" \
		--ssh-timeout "$(SSH_WAIT_TIMEOUT)" \
		--ansible "$(ANSIBLE_PLAYBOOK)" \
		--developer-extra-tasks "$(DEVELOPER_EXTRA_TASKS_FILE)" \
		-- $(BECOME_ARGS) $(PLAYBOOK_ARGS)

images: ## List discovered Ubuntu Server ARM64 ISO images, newest first
	@./scripts/bootstrap-vm.sh --downloads "$(DOWNLOADS_DIR)" --list-images

vms: ## List registered Parallels VMs
	@"$(PRLCTL)" list --all --output uuid,name,status
