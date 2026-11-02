SHELL := /bin/bash
.DEFAULT_GOAL := help

VM_NAME ?=
OMARCHY_VM_MANAGER_CLI ?=
OMARCHY_VM_MANAGER_APP ?=
OMARCHY_VM_CPUS ?= 8
OMARCHY_VM_MEMORY_GIB ?= 20
OMARCHY_VM_DISK_GIB ?= 64
OMARCHY_VM_WAIT_TIMEOUT ?= 3600
OMARCHY_VM_FOOT_FONT_SIZE ?= 12
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
OMARCHY_FEATURES ?=
OMARCHY_PROFILES ?=
OMARCHY_SETUP_FILE ?=
OMARCHY_CATALOGUE ?=
OMARCHY_PLAYBOOK_RESOLVE ?= no
OMARCHY_VARS_FILE ?=
OMARCHY_PLAYBOOK_CHECK ?= no
OMARCHY_PLAYBOOK_PLAN ?= no
OMARCHY_SETUP_REPO ?=
OMARCHY_SETUP_MANIFEST ?= vm.yml
OMARCHY_SETUP_TRUST_TASKS ?= no
OMARCHY_SETUP_TASKS ?= all
OMARCHY_SETUP_CHECK ?= no
OMARCHY_SETUP_CHECK_TASKS ?= no
OMARCHY_SETUP_DOTFILES_CONFLICT ?= fail

OMARCHY_SETUP_LEGACY_OPTIONS = OMARCHY_VM_PACKAGES OMARCHY_VM_SKIP_APPS OMARCHY_VM_LEAN_DEVELOPER \
	OMARCHY_VM_FOOT_FONT_SIZE OMARCHY_VM_IDLE_MODE OMARCHY_VM_LAYOUT_FILE OMARCHY_VM_THEME \
	OMARCHY_VM_THEME_MIN_STARS OMARCHY_VM_WAIT_TIMEOUT OMARCHY_SETUP_FILE OMARCHY_VARS_FILE \
	OMARCHY_FEATURES OMARCHY_PROFILES OMARCHY_CATALOGUE OMARCHY_PLAYBOOK_CHECK OMARCHY_PLAYBOOK_PLAN

OMARCHY_SETUP_RESOURCE_ARGS = \
	$(if $(filter file default undefined,$(origin OMARCHY_VM_CPUS)),,--cpus "$(OMARCHY_VM_CPUS)") \
	$(if $(filter file default undefined,$(origin OMARCHY_VM_MEMORY_GIB)),,--memory-gib "$(OMARCHY_VM_MEMORY_GIB)") \
	$(if $(filter file default undefined,$(origin OMARCHY_VM_DISK_GIB)),,--disk-gib "$(OMARCHY_VM_DISK_GIB)") \
	$(if $(OMARCHY_VM_FACTORY),--factory "$(OMARCHY_VM_FACTORY)",)

OMARCHY_SETUP_ARGS = --repo "$(OMARCHY_SETUP_REPO)" --manifest "$(OMARCHY_SETUP_MANIFEST)" \
	$(if $(VM_NAME),--vm-name "$(VM_NAME)",) \
	$(if $(OMARCHY_VM_MANAGER_CLI),--cli-path "$(OMARCHY_VM_MANAGER_CLI)",) \
	$(if $(OMARCHY_VM_MANAGER_APP),--manager-app "$(OMARCHY_VM_MANAGER_APP)",) \
	$(if $(filter yes true 1,$(OMARCHY_SETUP_TRUST_TASKS)),--trust-tasks,) \
	$(if $(filter all,$(OMARCHY_SETUP_TASKS)),,--tasks "$(OMARCHY_SETUP_TASKS)") \
	$(if $(filter yes true 1,$(OMARCHY_SETUP_CHECK)),--check,) \
	$(if $(filter yes true 1,$(OMARCHY_SETUP_CHECK_TASKS)),--check-tasks,) \
	--dotfiles-conflict "$(OMARCHY_SETUP_DOTFILES_CONFLICT)" \
	$(foreach option,$(OMARCHY_SETUP_LEGACY_OPTIONS),$(if $(filter file default undefined,$(origin $(option))),,--unsupported-option "$(option)")) \
	$(if $(filter yes true 1,$(OMARCHY_VM_YES)),--yes,)

.PHONY: help omarchy-vm-list bootstrap-omarchy-vm apply-omarchy-vm-guest check-omarchy-vm check-omarchy-vm-guest repair-omarchy-vm-black-screen test-omarchy

help: ## Show available targets and overrides
	@awk 'BEGIN {FS = ":.*## "} /^[a-zA-Z0-9_-]+:.*## / {printf "%-24s %s\n", $$1, $$2}' $(MAKEFILE_LIST)

.PHONY: apply-playbook apply-omarchy-playbook plan-omarchy-features syntax-check

apply-playbook: ## Apply independently selected features through managed SSH
	@python3 ./scripts/omarchy_playbook.py \
		$(if $(OMARCHY_VM_MANAGER_CLI),--cli-path "$(OMARCHY_VM_MANAGER_CLI)",) \
		$(if $(OMARCHY_VM_MANAGER_APP),--manager-app "$(OMARCHY_VM_MANAGER_APP)",) \
		--vm-name "$(if $(VM_NAME),$(VM_NAME),Dev Omarchy)" \
		$(if $(OMARCHY_FEATURES),--features "$(OMARCHY_FEATURES)",) \
		$(if $(OMARCHY_PROFILES),--profiles "$(OMARCHY_PROFILES)",) \
		$(if $(OMARCHY_SETUP_FILE),--setup-file "$(OMARCHY_SETUP_FILE)",) \
		$(if $(OMARCHY_CATALOGUE),--catalogue "$(OMARCHY_CATALOGUE)",) \
		$(if $(filter yes true 1,$(OMARCHY_PLAYBOOK_RESOLVE)),--resolve,) \
		$(if $(OMARCHY_VARS_FILE),--vars-file "$(OMARCHY_VARS_FILE)",) \
		$(if $(filter yes true 1,$(OMARCHY_PLAYBOOK_CHECK)),--check,) \
		$(if $(filter yes true 1,$(OMARCHY_PLAYBOOK_PLAN)),--plan,) \
		$(if $(filter yes true 1,$(OMARCHY_VM_YES)),--yes,)

apply-omarchy-playbook: apply-playbook ## Alias for the Omarchy feature playbook

plan-omarchy-features: OMARCHY_PLAYBOOK_RESOLVE = yes
plan-omarchy-features: apply-playbook ## Resolve profiles and local extensions without connecting to a VM

syntax-check: ## Validate the Omarchy playbook without connecting to a guest
	@ansible-playbook -i inventory.ini site.yml --syntax-check
	@ansible-playbook -i inventory.ini setup.yml --syntax-check

.PHONY: plan-omarchy-setup apply-omarchy-setup bootstrap-omarchy-setup

plan-omarchy-setup: ## Preview an external setup repository without connecting or running tasks
	@python3 ./scripts/omarchy_setup.py plan $(OMARCHY_SETUP_ARGS) $(OMARCHY_SETUP_RESOURCE_ARGS)

apply-omarchy-setup: ## Apply external features, dotfiles and explicitly trusted guest tasks
	@python3 ./scripts/omarchy_setup.py apply $(OMARCHY_SETUP_ARGS)

bootstrap-omarchy-setup: ## Create/configure a VM from an external setup repository
	@python3 ./scripts/omarchy_setup.py bootstrap $(OMARCHY_SETUP_ARGS) $(OMARCHY_SETUP_RESOURCE_ARGS)

.PHONY: build-omarchy-image check-omarchy-image

build-omarchy-image: ## Build a minimal ARM64 Omarchy factory without operating a VM
	@python3 ./scripts/omarchy_image.py \
		$(if $(OMARCHY_IMAGE_TRY_SOURCE),--try-source "$(OMARCHY_IMAGE_TRY_SOURCE)",) \
		$(if $(OMARCHY_IMAGE_TRY_COMMIT),--try-commit "$(OMARCHY_IMAGE_TRY_COMMIT)",) \
		--size-gib "$(OMARCHY_IMAGE_SIZE_GIB)" \
		$(if $(filter yes true 1,$(OMARCHY_IMAGE_PLAN)),--plan,)

check-omarchy-image: ## Build/check minimal provisioning packages without creating a disk
	@python3 ./scripts/omarchy_image.py \
		$(if $(OMARCHY_IMAGE_TRY_SOURCE),--try-source "$(OMARCHY_IMAGE_TRY_SOURCE)",) \
		$(if $(OMARCHY_IMAGE_TRY_COMMIT),--try-commit "$(OMARCHY_IMAGE_TRY_COMMIT)",) \
		--size-gib "$(OMARCHY_IMAGE_SIZE_GIB)" --check-only \
		$(if $(filter yes true 1,$(OMARCHY_IMAGE_PLAN)),--plan,)

omarchy-vm-list: ## List guests through Omarchy VM Manager
	@python3 ./scripts/omarchy_vm_manager.py \
		$(if $(OMARCHY_VM_MANAGER_CLI),--cli-path "$(OMARCHY_VM_MANAGER_CLI)",) \
		$(if $(OMARCHY_VM_MANAGER_APP),--manager-app "$(OMARCHY_VM_MANAGER_APP)",) list

bootstrap-omarchy-vm: ## Create or configure a managed Omarchy VM
ifneq ($(strip $(OMARCHY_SETUP_REPO)),)
	@$(MAKE) --no-print-directory bootstrap-omarchy-setup
else
	@python3 ./scripts/omarchy_vm_manager.py \
		$(if $(OMARCHY_VM_MANAGER_CLI),--cli-path "$(OMARCHY_VM_MANAGER_CLI)",) \
		$(if $(OMARCHY_VM_MANAGER_APP),--manager-app "$(OMARCHY_VM_MANAGER_APP)",) \
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
endif

apply-omarchy-vm-guest: ## Apply workstation preferences inside a managed guest
	@test "$$(uname -s)" = Linux || { printf 'Run this target in a managed Omarchy terminal.\n' >&2; exit 1; }
	@bash ./omarchy/guest/apply-workstation.sh --foot-font-size "$(OMARCHY_VM_FOOT_FONT_SIZE)" --idle-mode "$(OMARCHY_VM_IDLE_MODE)" $(if $(OMARCHY_VM_THEME),--theme-url "$(OMARCHY_VM_THEME)",) $(if $(filter off,$(OMARCHY_VM_LAYOUT_FILE)),--remove-layout,$(if $(OMARCHY_VM_LAYOUT_FILE),--layout-file "$(OMARCHY_VM_LAYOUT_FILE)",))

check-omarchy-vm: ## Validate a running managed Omarchy VM
	@python3 ./scripts/omarchy_vm_manager.py \
		$(if $(OMARCHY_VM_MANAGER_CLI),--cli-path "$(OMARCHY_VM_MANAGER_CLI)",) \
		$(if $(OMARCHY_VM_MANAGER_APP),--manager-app "$(OMARCHY_VM_MANAGER_APP)",) \
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
