SHELL := /bin/bash
.DEFAULT_GOAL := help

VM_NAME ?=
OMARCHY_VM_MANAGER_DIR ?= $(CURDIR)/../Omarchy VM Manager
OMARCHY_VM_MANAGER_CLI ?= $(OMARCHY_VM_MANAGER_DIR)/bin/omarchy-vm
OMARCHY_VM_CPUS ?= 8
OMARCHY_VM_MEMORY_GIB ?= 20
OMARCHY_VM_DISK_GIB ?= 64
OMARCHY_VM_WAIT_TIMEOUT ?= 3600
OMARCHY_VM_FOOT_FONT_SIZE ?= 16
OMARCHY_VM_IDLE_MODE ?= host
OMARCHY_VM_LAYOUT_FILE ?=
OMARCHY_VM_FACTORY ?=
OMARCHY_VM_THEME ?=
OMARCHY_VM_THEME_MIN_STARS ?= 10
OMARCHY_VM_YES ?= no
OMARCHY_VM_PACKAGES ?=
OMARCHY_VM_SKIP_APPS ?= no
OMARCHY_VM_LEAN_DEVELOPER ?= no
OMARCHY_IMAGE_TRY_SOURCE ?=
OMARCHY_IMAGE_TRY_COMMIT ?=
OMARCHY_IMAGE_SIZE_GIB ?= 20
OMARCHY_IMAGE_PLAN ?= no
OMARCHY_FEATURES ?= workstation
OMARCHY_VARS_FILE ?=
OMARCHY_PLAYBOOK_CHECK ?= no
OMARCHY_PLAYBOOK_PLAN ?= no

.PHONY: help omarchy-vm-list bootstrap-omarchy-vm apply-omarchy-vm-guest check-omarchy-vm check-omarchy-vm-guest repair-omarchy-vm-black-screen test-omarchy

help: ## Show available targets and overrides
	@awk 'BEGIN {FS = ":.*## "} /^[a-zA-Z0-9_-]+:.*## / {printf "%-24s %s\n", $$1, $$2}' $(MAKEFILE_LIST)

.PHONY: apply-playbook apply-omarchy-playbook syntax-check

apply-playbook: ## Apply independently selected features through managed SSH
	@python3 ./scripts/omarchy_playbook.py \
		--cli-path "$(OMARCHY_VM_MANAGER_CLI)" \
		--vm-name "$(if $(VM_NAME),$(VM_NAME),Dev Omarchy)" \
		--features "$(OMARCHY_FEATURES)" \
		$(if $(OMARCHY_VARS_FILE),--vars-file "$(OMARCHY_VARS_FILE)",) \
		$(if $(filter yes true 1,$(OMARCHY_PLAYBOOK_CHECK)),--check,) \
		$(if $(filter yes true 1,$(OMARCHY_PLAYBOOK_PLAN)),--plan,) \
		$(if $(filter yes true 1,$(OMARCHY_VM_YES)),--yes,)

apply-omarchy-playbook: apply-playbook ## Alias for the Omarchy feature playbook

syntax-check: ## Validate the Omarchy playbook without connecting to a guest
	@ansible-playbook -i inventory.ini site.yml --syntax-check

.PHONY: build-omarchy-image check-omarchy-image

build-omarchy-image: ## Build a minimal ARM64 Omarchy factory without operating a VM
	@python3 ./scripts/omarchy_image.py \
		--manager-dir "$(OMARCHY_VM_MANAGER_DIR)" \
		$(if $(OMARCHY_IMAGE_TRY_SOURCE),--try-source "$(OMARCHY_IMAGE_TRY_SOURCE)",) \
		$(if $(OMARCHY_IMAGE_TRY_COMMIT),--try-commit "$(OMARCHY_IMAGE_TRY_COMMIT)",) \
		--size-gib "$(OMARCHY_IMAGE_SIZE_GIB)" \
		$(if $(filter yes true 1,$(OMARCHY_IMAGE_PLAN)),--plan,)

check-omarchy-image: ## Build/check minimal provisioning packages without creating a disk
	@python3 ./scripts/omarchy_image.py \
		--manager-dir "$(OMARCHY_VM_MANAGER_DIR)" \
		$(if $(OMARCHY_IMAGE_TRY_SOURCE),--try-source "$(OMARCHY_IMAGE_TRY_SOURCE)",) \
		$(if $(OMARCHY_IMAGE_TRY_COMMIT),--try-commit "$(OMARCHY_IMAGE_TRY_COMMIT)",) \
		--size-gib "$(OMARCHY_IMAGE_SIZE_GIB)" --check-only \
		$(if $(filter yes true 1,$(OMARCHY_IMAGE_PLAN)),--plan,)

omarchy-vm-list: ## List guests through Omarchy VM Manager
	@"$(OMARCHY_VM_MANAGER_CLI)" list

bootstrap-omarchy-vm: ## Create or configure a managed Omarchy VM
	@python3 ./scripts/omarchy_vm_manager.py \
		--cli-path "$(OMARCHY_VM_MANAGER_CLI)" \
		--manager-dir "$(OMARCHY_VM_MANAGER_DIR)" \
		--vm-name "$(if $(VM_NAME),$(VM_NAME),Dev Omarchy)" \
		$(if $(OMARCHY_VM_FACTORY),--factory "$(OMARCHY_VM_FACTORY)",) \
		--cpus "$(OMARCHY_VM_CPUS)" \
		--memory-gib "$(OMARCHY_VM_MEMORY_GIB)" \
		--disk-gib "$(OMARCHY_VM_DISK_GIB)" \
		--timeout "$(OMARCHY_VM_WAIT_TIMEOUT)" \
		--foot-font-size "$(OMARCHY_VM_FOOT_FONT_SIZE)" \
		--idle-mode "$(OMARCHY_VM_IDLE_MODE)" \
		--packages "$(if $(filter yes true 1,$(OMARCHY_VM_SKIP_APPS)),,$(OMARCHY_VM_PACKAGES))" \
		$(if $(filter yes true 1,$(OMARCHY_VM_LEAN_DEVELOPER)),--lean-developer,) \
		--theme "$(OMARCHY_VM_THEME)" \
		--theme-min-stars "$(OMARCHY_VM_THEME_MIN_STARS)" \
		$(if $(filter off,$(OMARCHY_VM_LAYOUT_FILE)),--remove-layout,$(if $(OMARCHY_VM_LAYOUT_FILE),--layout-file "$(OMARCHY_VM_LAYOUT_FILE)",)) \
		$(if $(filter yes true 1,$(OMARCHY_VM_YES)),--yes,) \
		bootstrap

apply-omarchy-vm-guest: ## Apply workstation preferences inside a managed guest
	@test "$$(uname -s)" = Linux || { printf 'Run this target in a managed Omarchy terminal.\n' >&2; exit 1; }
	@bash ./omarchy/guest/apply-workstation.sh --foot-font-size "$(OMARCHY_VM_FOOT_FONT_SIZE)" --idle-mode "$(OMARCHY_VM_IDLE_MODE)" $(if $(OMARCHY_VM_THEME),--theme-url "$(OMARCHY_VM_THEME)",) $(if $(filter off,$(OMARCHY_VM_LAYOUT_FILE)),--remove-layout,$(if $(OMARCHY_VM_LAYOUT_FILE),--layout-file "$(OMARCHY_VM_LAYOUT_FILE)",))

check-omarchy-vm: ## Validate a running managed Omarchy VM
	@python3 ./scripts/omarchy_vm_manager.py \
		--cli-path "$(OMARCHY_VM_MANAGER_CLI)" \
		--vm-name "$(if $(VM_NAME),$(VM_NAME),Dev Omarchy)" \
		--cpus "$(OMARCHY_VM_CPUS)" \
		--memory-gib "$(OMARCHY_VM_MEMORY_GIB)" \
		--disk-gib "$(OMARCHY_VM_DISK_GIB)" \
		check

check-omarchy-vm-guest: ## Check the workstation from a managed guest terminal
	@test "$$(uname -s)" = Linux || { printf 'Run this target in a managed Omarchy terminal.\n' >&2; exit 1; }
	@bash ./omarchy/guest/check-workstation.sh

repair-omarchy-vm-black-screen: ## Repair the Hyprland 0.57 VirGL alpha regression
	@test "$$(uname -s)" = Linux || { printf 'Run this target in a managed Omarchy terminal.\n' >&2; exit 1; }
	@bash ./omarchy/guest/repair-try-omarchy-black-screen.sh

test-omarchy: ## Run focused Omarchy bootstrap safety tests
	@PYTHONDONTWRITEBYTECODE=1 python3 -m unittest discover -s tests -p 'test_omarchy*.py' -v
