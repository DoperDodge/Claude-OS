#!/usr/bin/env bash
# Claude-OS QEMU Launcher
# Boots Claude-OS in a QEMU ARM64 virtual machine
# Supports text mode (default), GUI with GTK, and GUI with SDL

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(cd "$SCRIPT_DIR/../.." && pwd)"
IMAGE_DIR="$PROJECT_ROOT/output/images"

KERNEL="$IMAGE_DIR/Image"
ROOTFS="$IMAGE_DIR/rootfs.ext4"

# QEMU settings
MEMORY="1024"
CPUS="2"
MACHINE="virt"
CPU="cortex-a57"
DEBUG_MODE=false
DISPLAY_MODE="text"  # text, gtk, sdl

# Parse arguments
while [[ $# -gt 0 ]]; do
    case $1 in
        --gui|--gtk)
            DISPLAY_MODE="gtk"
            shift
            ;;
        --sdl)
            DISPLAY_MODE="sdl"
            shift
            ;;
        --debug)
            DEBUG_MODE=true
            shift
            ;;
        --memory)
            MEMORY="$2"
            shift 2
            ;;
        --cpus)
            CPUS="$2"
            shift 2
            ;;
        *)
            echo "Unknown option: $1"
            echo "Usage: $0 [--gui|--gtk|--sdl] [--debug] [--memory MB] [--cpus N]"
            echo ""
            echo "Display modes:"
            echo "  (default)     Text-only serial console (-nographic)"
            echo "  --gui, --gtk  Graphical window using GTK display"
            echo "  --sdl         Graphical window using SDL display (works over SSH/headless)"
            exit 1
            ;;
    esac
done

# Validate images exist
if [[ ! -f "$KERNEL" ]]; then
    echo "Error: Kernel image not found at $KERNEL"
    echo "Run 'make build' first to build the OS image."
    exit 1
fi

if [[ ! -f "$ROOTFS" ]]; then
    echo "Error: Root filesystem not found at $ROOTFS"
    echo "Run 'make build' first to build the OS image."
    exit 1
fi

# Build QEMU command
QEMU_CMD=(
    qemu-system-aarch64
    -machine "$MACHINE"
    -cpu "$CPU"
    -m "$MEMORY"
    -smp "$CPUS"
    -kernel "$KERNEL"
    -drive "file=$ROOTFS,format=raw,if=virtio"

    # Networking: user-mode with port forwarding
    # Host port 2222 -> Guest port 22 (SSH)
    # Host port 8080 -> Guest port 8080 (Claude bridge API)
    -netdev user,id=net0,hostfwd=tcp::2222-:22,hostfwd=tcp::8080-:8080
    -device virtio-net-pci,netdev=net0

    # Simulated WiFi adapter (mac80211_hwsim in guest kernel)
    -device virtio-net-pci,netdev=wifi0
    -netdev user,id=wifi0

    # Virtio RNG for faster boot
    -device virtio-rng-pci
)

# Configure display mode
case "$DISPLAY_MODE" in
    text)
        QEMU_CMD+=(
            -append "root=/dev/vda console=ttyAMA0 rw"
            -nographic
        )
        ;;
    gtk|sdl)
        QEMU_CMD+=(
            # Kernel console on both serial AND virtual framebuffer
            -append "root=/dev/vda console=ttyAMA0 console=tty0 rw"

            # Virtio GPU — provides DRM device + fbdev in guest
            # xres/yres sets the initial display resolution
            -device virtio-gpu-pci,xres=1080,yres=2340

            # Display backend (gtk shows a window, sdl works headless)
            -display "$DISPLAY_MODE"

            # Virtio tablet — absolute pointer (like a touchscreen)
            -device virtio-tablet-pci

            # Virtio keyboard — keyboard input to guest
            -device virtio-keyboard-pci

            # Keep serial console accessible on stdio as well
            -serial mon:stdio
        )
        ;;
esac

# Add GDB server if debug mode
if [[ "$DEBUG_MODE" == true ]]; then
    QEMU_CMD+=(-s -S)
    echo "[Claude-OS] Debug mode: GDB server listening on tcp::1234"
    echo "[Claude-OS] Connect with: gdb-multiarch -ex 'target remote :1234'"
fi

echo "[Claude-OS] Starting QEMU (${CPUS} CPUs, ${MEMORY}MB RAM, display=${DISPLAY_MODE})..."
if [[ "$DISPLAY_MODE" == "text" ]]; then
    echo "[Claude-OS] Press Ctrl+A then X to exit QEMU"
else
    echo "[Claude-OS] Close the QEMU window or press Ctrl+C to exit"
    echo "[Claude-OS] Serial console available on this terminal"
fi
echo ""

exec "${QEMU_CMD[@]}"
