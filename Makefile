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

.PHONY: all setup build clean run run-gui run-gui-sdl run-debug menuconfig help preview test fbtest render-test

help: ## Show this help
	@grep -E '^[a-zA-Z_-]+:.*?## .*$$' $(MAKEFILE_LIST) | \
		awk 'BEGIN {FS = ":.*?## "}; {printf "  \033[36m%-15s\033[0m %s\n", $$1, $$2}'

all: build ## Build the full OS image

setup: $(BUILDROOT_DIR) ## Download and configure Buildroot
	@if [ ! -f $(OUTPUT_DIR)/.config ]; then \
		echo "[Claude-OS] Applying Claude-OS defconfig..."; \
		cp $(DEFCONFIG) $(BUILDROOT_DIR)/configs/claude_os_defconfig; \
		$(MAKE) -C $(BUILDROOT_DIR) claude_os_defconfig \
			BR2_EXTERNAL=$(CURDIR)/tools/build \
			O=$(CURDIR)/$(OUTPUT_DIR); \
	fi
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

run: ## Launch Claude-OS in QEMU (text mode)
	@./tools/emulator/run-qemu.sh

run-gui: ## Launch Claude-OS in QEMU with graphical display (GTK)
	@./tools/emulator/run-qemu.sh --gui

run-gui-sdl: ## Launch Claude-OS in QEMU with graphical display (SDL)
	@./tools/emulator/run-qemu.sh --sdl

run-debug: ## Launch Claude-OS in QEMU with GDB server
	@./tools/emulator/run-qemu.sh --debug

preview: ## Generate visual UI preview (open preview.html in browser)
	@python3 tools/preview/generate_preview.py
	@echo "[Claude-OS] Open preview.html in your browser!"

fbtest: ## Build the DRM framebuffer test program
	@$(MAKE) -C tools/fbtest CROSS_COMPILE=aarch64-linux-gnu-
	@echo "[Claude-OS] DRM test built: tools/fbtest/drm_test"

render-test: ## Render a test frame to PNG (headless, no QEMU needed)
	@python3 tools/fbtest/render_test.py --output frame.png
	@echo "[Claude-OS] Test frame: frame.png"

test: ## Run the test suite
	@python3 -m pytest tests/ -v
