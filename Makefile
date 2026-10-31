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
TRY_OMARCHY_APP ?= /Applications/Try Omarchy.app
TRY_OMARCHY_LOCK ?= $(CURDIR)/omarchy/try-omarchy.lock.json
TRY_OMARCHY_PRIVATE_KEY ?= $(HOME)/.ssh/id_rsa
TRY_OMARCHY_PUBLIC_KEY ?= $(TRY_OMARCHY_PRIVATE_KEY).pub
TRY_OMARCHY_SSH_HOST ?= 127.0.0.1
TRY_OMARCHY_SSH_PORT ?= 2222
TRY_OMARCHY_SHARE_PATH ?= $(HOME)/Shared
TRY_OMARCHY_CPUS ?= 8
TRY_OMARCHY_MEMORY_GIB ?= 20
TRY_OMARCHY_DISK_GIB ?= 64
TRY_OMARCHY_FOOT_FONT_SIZE ?= 16
TRY_OMARCHY_IDLE_MODE ?= host
TRY_OMARCHY_LAYOUT_FILE ?=
TRY_OMARCHY_YES ?= no
TRY_OMARCHY_SKIP_APPS ?= no

.PHONY: help try-omarchy-open bootstrap-try-omarchy apply-try-omarchy check-try-omarchy check-try-omarchy-guest repair-try-omarchy-black-screen bootstrap apply-playbook images vms omarchy-image bootstrap-omarchy apply-omarchy check-omarchy test-omarchy

help: ## Show available targets and overrides
	@awk 'BEGIN {FS = ":.*## "} /^[a-zA-Z0-9_-]+:.*## / {printf "%-24s %s\n", $$1, $$2}' $(MAKEFILE_LIST)

try-omarchy-open: ## Verify and open an already-installed Try Omarchy app
	@test "$$(uname -s)" = Darwin || { printf 'Run this target on the Mac host.\n' >&2; exit 1; }
	@test -d "$(TRY_OMARCHY_APP)" || { printf 'Install the official Try Omarchy app first: %s\n' 'https://github.com/omacom/try-omarchy/releases/latest' >&2; exit 1; }
	@codesign --verify --deep --strict "$(TRY_OMARCHY_APP)"
	@spctl --assess --type execute "$(TRY_OMARCHY_APP)"
	@open "$(TRY_OMARCHY_APP)"

bootstrap-try-omarchy: ## Configure an existing Try Omarchy VM over localhost SSH
	@python3 ./scripts/try_omarchy.py \
		--app-path "$(TRY_OMARCHY_APP)" \
		--lock-file "$(TRY_OMARCHY_LOCK)" \
		--guest-user "$(if $(GUEST_USER),$(GUEST_USER),$(USER))" \
		--ssh-host "$(TRY_OMARCHY_SSH_HOST)" \
		--ssh-port "$(TRY_OMARCHY_SSH_PORT)" \
		--private-key "$(TRY_OMARCHY_PRIVATE_KEY)" \
		--public-key "$(TRY_OMARCHY_PUBLIC_KEY)" \
		--share-path "$(TRY_OMARCHY_SHARE_PATH)" \
		--cpus "$(TRY_OMARCHY_CPUS)" \
		--memory-gib "$(TRY_OMARCHY_MEMORY_GIB)" \
		--disk-gib "$(TRY_OMARCHY_DISK_GIB)" \
		--foot-font-size "$(TRY_OMARCHY_FOOT_FONT_SIZE)" \
		--idle-mode "$(TRY_OMARCHY_IDLE_MODE)" \
		$(if $(filter off,$(TRY_OMARCHY_LAYOUT_FILE)),--remove-layout,$(if $(TRY_OMARCHY_LAYOUT_FILE),--layout-file "$(TRY_OMARCHY_LAYOUT_FILE)",)) \
		$(if $(filter yes true 1,$(TRY_OMARCHY_YES)),--yes,) \
		$(if $(filter yes true 1,$(TRY_OMARCHY_SKIP_APPS)),--skip-apps,) \
		bootstrap

apply-try-omarchy: ## Apply explicit workstation preferences inside Try Omarchy
	@test "$$(uname -s)" = Linux || { printf 'Run this target in a Try Omarchy terminal.\n' >&2; exit 1; }
	@bash ./omarchy/guest/apply-workstation.sh --foot-font-size "$(TRY_OMARCHY_FOOT_FONT_SIZE)" --idle-mode "$(TRY_OMARCHY_IDLE_MODE)" $(if $(filter off,$(TRY_OMARCHY_LAYOUT_FILE)),--remove-layout,$(if $(TRY_OMARCHY_LAYOUT_FILE),--layout-file "$(TRY_OMARCHY_LAYOUT_FILE)",))

check-try-omarchy: ## Validate the Try Omarchy VM from the Mac host
	@python3 ./scripts/try_omarchy.py \
		--app-path "$(TRY_OMARCHY_APP)" \
		--lock-file "$(TRY_OMARCHY_LOCK)" \
		--guest-user "$(if $(GUEST_USER),$(GUEST_USER),$(USER))" \
		--ssh-host "$(TRY_OMARCHY_SSH_HOST)" \
		--ssh-port "$(TRY_OMARCHY_SSH_PORT)" \
		--private-key "$(TRY_OMARCHY_PRIVATE_KEY)" \
		--public-key "$(TRY_OMARCHY_PUBLIC_KEY)" \
		--share-path "$(TRY_OMARCHY_SHARE_PATH)" \
		--cpus "$(TRY_OMARCHY_CPUS)" \
		--memory-gib "$(TRY_OMARCHY_MEMORY_GIB)" \
		--disk-gib "$(TRY_OMARCHY_DISK_GIB)" \
		check

check-try-omarchy-guest: ## Check Try Omarchy from a guest terminal
	@test "$$(uname -s)" = Linux || { printf 'Run this target in a Try Omarchy terminal.\n' >&2; exit 1; }
	@TRY_OMARCHY_SHARED_FOLDER="$(notdir $(TRY_OMARCHY_SHARE_PATH))" \
		bash ./omarchy/guest/check-workstation.sh

repair-try-omarchy-black-screen: ## Repair the Hyprland 0.57 VirGL alpha regression
	@test "$$(uname -s)" = Linux || { printf 'Run this target in a Try Omarchy terminal.\n' >&2; exit 1; }
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
