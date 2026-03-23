# Claude-OS Build System
# Target: ARM64 (aarch64) via QEMU emulation

BUILDROOT_VERSION := 2024.02.1
BUILDROOT_DIR     := buildroot
BUILDROOT_TAR     := buildroot-$(BUILDROOT_VERSION).tar.gz
BUILDROOT_URL     := https://buildroot.org/downloads/$(BUILDROOT_TAR)
OUTPUT_DIR        := output
IMAGE_DIR         := $(OUTPUT_DIR)/images
DEFCONFIG         := $(CURDIR)/tools/build/claude_os_defconfig
OVERLAY_DIR       := $(CURDIR)/tools/build/rootfs-overlay

.PHONY: all setup build clean run menuconfig help

help: ## Show this help
	@grep -E '^[a-zA-Z_-]+:.*?## .*$$' $(MAKEFILE_LIST) | \
		awk 'BEGIN {FS = ":.*?## "}; {printf "  \033[36m%-15s\033[0m %s\n", $$1, $$2}'

all: build ## Build the full OS image

setup: $(BUILDROOT_DIR) ## Download and configure Buildroot
	@echo "[Claude-OS] Buildroot is ready."

$(BUILDROOT_DIR):
	@echo "[Claude-OS] Downloading Buildroot $(BUILDROOT_VERSION)..."
	curl -L -o $(BUILDROOT_TAR) $(BUILDROOT_URL)
	tar xzf $(BUILDROOT_TAR)
	mv buildroot-$(BUILDROOT_VERSION) $(BUILDROOT_DIR)
	rm -f $(BUILDROOT_TAR)
	@echo "[Claude-OS] Applying Claude-OS defconfig..."
	cp $(DEFCONFIG) $(BUILDROOT_DIR)/configs/claude_os_defconfig
	$(MAKE) -C $(BUILDROOT_DIR) claude_os_defconfig \
		BR2_EXTERNAL=$(CURDIR)/tools/build \
		O=$(CURDIR)/$(OUTPUT_DIR)

build: setup ## Build the OS image
	@echo "[Claude-OS] Building OS image (this will take a while on first run)..."
	$(MAKE) -C $(BUILDROOT_DIR) \
		O=$(CURDIR)/$(OUTPUT_DIR) \
		BR2_ROOTFS_OVERLAY=$(OVERLAY_DIR)
	@echo "[Claude-OS] Build complete! Image at $(IMAGE_DIR)/"

menuconfig: setup ## Open Buildroot menuconfig for customization
	$(MAKE) -C $(BUILDROOT_DIR) menuconfig O=$(CURDIR)/$(OUTPUT_DIR)

clean: ## Remove build artifacts
	rm -rf $(OUTPUT_DIR)
	@echo "[Claude-OS] Build output cleaned."

distclean: clean ## Remove everything including Buildroot sources
	rm -rf $(BUILDROOT_DIR) $(BUILDROOT_TAR)
	@echo "[Claude-OS] Full clean complete."

run: ## Launch Claude-OS in QEMU
	@./tools/emulator/run-qemu.sh

run-debug: ## Launch Claude-OS in QEMU with GDB server
	@./tools/emulator/run-qemu.sh --debug
