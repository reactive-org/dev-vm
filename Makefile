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
OMARCHY_MANIFEST_URL ?= https://nightly.omarchy.org/edge-aarch64/latest.json
OMARCHY_IMAGE_SHA256 ?=
OMARCHY_DISPLAY_MODE ?= 4096x2160@60
OMARCHY_WINDOW_SIZE ?=
OMARCHY_LAYOUT_FILE ?=
OMARCHY_TOOLS_ISO ?= /Applications/Parallels Desktop.app/Contents/Resources/Tools/prl-tools-lin-arm.iso
OMARCHY_SHARE_PATH ?= $(HOME)/Parallels/Shared
OMARCHY_ARTIFACTS_DIR ?= $(CURDIR)/.artifacts/omarchy
OMARCHY_VM_MANAGER_DIR ?= $(CURDIR)/../Omarchy VM Manager
OMARCHY_VM_MANAGER_CLI ?= $(OMARCHY_VM_MANAGER_DIR)/bin/omarchy-vm
OMARCHY_VM_CPUS ?= 8
OMARCHY_VM_MEMORY_GIB ?= 20
OMARCHY_VM_WAIT_TIMEOUT ?= 3600
OMARCHY_VM_FOOT_FONT_SIZE ?= 16
OMARCHY_VM_IDLE_MODE ?= host
OMARCHY_VM_LAYOUT_FILE ?=
OMARCHY_VM_YES ?= no
OMARCHY_VM_SKIP_APPS ?= no

.PHONY: help omarchy-vm-list bootstrap-omarchy-vm apply-omarchy-vm-guest check-omarchy-vm check-omarchy-vm-guest repair-omarchy-vm-black-screen bootstrap apply-playbook images vms omarchy-image bootstrap-omarchy apply-omarchy check-omarchy test-omarchy

help: ## Show available targets and overrides
	@awk 'BEGIN {FS = ":.*## "} /^[a-zA-Z0-9_-]+:.*## / {printf "%-24s %s\n", $$1, $$2}' $(MAKEFILE_LIST)

omarchy-vm-list: ## List guests through Omarchy VM Manager
	@"$(OMARCHY_VM_MANAGER_CLI)" list

bootstrap-omarchy-vm: ## Create or configure a managed Omarchy VM
	@python3 ./scripts/omarchy_vm_manager.py \
		--cli-path "$(OMARCHY_VM_MANAGER_CLI)" \
		--vm-name "$(if $(VM_NAME),$(VM_NAME),Dev Omarchy)" \
		--cpus "$(OMARCHY_VM_CPUS)" \
		--memory-gib "$(OMARCHY_VM_MEMORY_GIB)" \
		--timeout "$(OMARCHY_VM_WAIT_TIMEOUT)" \
		--foot-font-size "$(OMARCHY_VM_FOOT_FONT_SIZE)" \
		--idle-mode "$(OMARCHY_VM_IDLE_MODE)" \
		$(if $(filter off,$(OMARCHY_VM_LAYOUT_FILE)),--remove-layout,$(if $(OMARCHY_VM_LAYOUT_FILE),--layout-file "$(OMARCHY_VM_LAYOUT_FILE)",)) \
		$(if $(filter yes true 1,$(OMARCHY_VM_YES)),--yes,) \
		$(if $(filter yes true 1,$(OMARCHY_VM_SKIP_APPS)),--skip-apps,) \
		bootstrap

apply-omarchy-vm-guest: ## Apply workstation preferences inside a managed guest
	@test "$$(uname -s)" = Linux || { printf 'Run this target in a managed Omarchy terminal.\n' >&2; exit 1; }
	@bash ./omarchy/guest/apply-workstation.sh --foot-font-size "$(OMARCHY_VM_FOOT_FONT_SIZE)" --idle-mode "$(OMARCHY_VM_IDLE_MODE)" $(if $(filter off,$(OMARCHY_VM_LAYOUT_FILE)),--remove-layout,$(if $(OMARCHY_VM_LAYOUT_FILE),--layout-file "$(OMARCHY_VM_LAYOUT_FILE)",))

check-omarchy-vm: ## Validate a running managed Omarchy VM
	@python3 ./scripts/omarchy_vm_manager.py \
		--cli-path "$(OMARCHY_VM_MANAGER_CLI)" \
		--vm-name "$(if $(VM_NAME),$(VM_NAME),Dev Omarchy)" \
		--cpus "$(OMARCHY_VM_CPUS)" \
		--memory-gib "$(OMARCHY_VM_MEMORY_GIB)" \
		check

check-omarchy-vm-guest: ## Check the workstation from a managed guest terminal
	@test "$$(uname -s)" = Linux || { printf 'Run this target in a managed Omarchy terminal.\n' >&2; exit 1; }
	@bash ./omarchy/guest/check-workstation.sh

repair-omarchy-vm-black-screen: ## Repair the Hyprland 0.57 VirGL alpha regression
	@test "$$(uname -s)" = Linux || { printf 'Run this target in a managed Omarchy terminal.\n' >&2; exit 1; }
	@bash ./omarchy/guest/repair-try-omarchy-black-screen.sh

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

omarchy-image: ## Legacy: download the Omarchy image used by Parallels
	@python3 ./scripts/omarchy_vm.py \
		--prlctl "$(PRLCTL)" \
		--artifacts "$(OMARCHY_ARTIFACTS_DIR)" \
		image \
		--manifest-url "$(OMARCHY_MANIFEST_URL)"

bootstrap-omarchy: ## Legacy: create an Omarchy ARM64 Parallels VM
	@python3 ./scripts/omarchy_vm.py \
		--prlctl "$(PRLCTL)" \
		--artifacts "$(OMARCHY_ARTIFACTS_DIR)" \
		bootstrap \
		--manifest-url "$(OMARCHY_MANIFEST_URL)" \
		--name "$(VM_NAME)" \
		--image "$(IMAGE)" \
		--image-sha256 "$(OMARCHY_IMAGE_SHA256)" \
		--cpus "$(if $(CPUS),$(CPUS),4)" \
		--memory-mb "$(if $(MEMORY_MB),$(MEMORY_MB),12288)" \
		--disk-gb "$(if $(DISK_GB),$(DISK_GB),64)" \
		--guest-user "$(GUEST_USER)" \
		--hostname "$(GUEST_HOSTNAME)" \
		--ssh-key "$(SSH_PUBLIC_KEY)" \
		--ssh-host "$(SSH_HOST)" \
		--ssh-timeout "$(SSH_WAIT_TIMEOUT)" \
		--display-mode "$(OMARCHY_DISPLAY_MODE)" \
		--window-size "$(OMARCHY_WINDOW_SIZE)" \
		--tools-iso "$(OMARCHY_TOOLS_ISO)" \
		--share-path "$(OMARCHY_SHARE_PATH)" $(if $(filter yes true 1,$(RESUME)),--resume,) $(if $(OMARCHY_LAYOUT_FILE),--layout-file "$(OMARCHY_LAYOUT_FILE)",)

apply-omarchy: ## Legacy: reapply the Omarchy Parallels configuration
	@python3 ./scripts/omarchy_vm.py \
		--prlctl "$(PRLCTL)" \
		--artifacts "$(OMARCHY_ARTIFACTS_DIR)" \
		apply \
		--name "$(VM_NAME)" \
		--guest-user "$(GUEST_USER)" \
		--hostname "$(GUEST_HOSTNAME)" \
		--ssh-key "$(SSH_PUBLIC_KEY)" \
		--ssh-host "$(SSH_HOST)" \
		--ssh-timeout "$(SSH_WAIT_TIMEOUT)" \
		--display-mode "$(OMARCHY_DISPLAY_MODE)" \
		--tools-iso "$(OMARCHY_TOOLS_ISO)" \
		--share-path "$(OMARCHY_SHARE_PATH)" $(if $(OMARCHY_LAYOUT_FILE),--layout-file "$(OMARCHY_LAYOUT_FILE)",)

check-omarchy: ## Legacy: check the Omarchy Parallels VM
	@python3 ./scripts/omarchy_vm.py \
		--prlctl "$(PRLCTL)" \
		--artifacts "$(OMARCHY_ARTIFACTS_DIR)" \
		check \
		--name "$(VM_NAME)" \
		--guest-user "$(GUEST_USER)" \
		--hostname "$(GUEST_HOSTNAME)" \
		--ssh-key "$(SSH_PUBLIC_KEY)" \
		--ssh-host "$(SSH_HOST)" \
		--ssh-timeout "$(SSH_WAIT_TIMEOUT)"

test-omarchy: ## Run focused Omarchy bootstrap safety tests
	@PYTHONDONTWRITEBYTECODE=1 python3 -m unittest discover -s tests -p 'test_omarchy*.py' -v
