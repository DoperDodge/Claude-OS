#!/usr/bin/env bash
# Claude-OS QEMU Launcher
# Boots Claude-OS in a QEMU ARM64 virtual machine

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
GUI_MODE=false
DISPLAY_BACKEND="gtk"
SCREEN_WIDTH=480
SCREEN_HEIGHT=960

# Parse arguments
while [[ $# -gt 0 ]]; do
    case $1 in
        --gui)
            GUI_MODE=true
            shift
            ;;
        --display)
            DISPLAY_BACKEND="$2"
            shift 2
            ;;
        --resolution)
            # Parse WxH format
            SCREEN_WIDTH="${2%%x*}"
            SCREEN_HEIGHT="${2##*x}"
            shift 2
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
            echo "Usage: $0 [--gui] [--display gtk|sdl] [--resolution WxH] [--debug] [--memory MB] [--cpus N]"
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
)

# Display mode: GUI with virtio-gpu or text-only serial
if [[ "$GUI_MODE" == true ]]; then
    QEMU_CMD+=(
        -append "root=/dev/vda console=tty0 rw"

        # Virtio GPU — the guest kernel drives this via DRM/virtio-gpu
        -device virtio-gpu-pci,xres="$SCREEN_WIDTH",yres="$SCREEN_HEIGHT"

        # Display backend (gtk opens a window, sdl is an alternative)
        -display "$DISPLAY_BACKEND"

        # Keyboard and mouse input passed to guest
        -device virtio-keyboard-pci
        -device virtio-mouse-pci
    )
    echo "[Claude-OS] GUI mode: ${SCREEN_WIDTH}x${SCREEN_HEIGHT} via ${DISPLAY_BACKEND}"
else
    QEMU_CMD+=(
        -append "root=/dev/vda console=ttyAMA0 rw"
        -nographic
    )
fi

QEMU_CMD+=(
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

# Add GDB server if debug mode
if [[ "$DEBUG_MODE" == true ]]; then
    QEMU_CMD+=(-s -S)
    echo "[Claude-OS] Debug mode: GDB server listening on tcp::1234"
    echo "[Claude-OS] Connect with: gdb-multiarch -ex 'target remote :1234'"
fi

echo "[Claude-OS] Starting QEMU (${CPUS} CPUs, ${MEMORY}MB RAM)..."
if [[ "$GUI_MODE" == true ]]; then
    echo "[Claude-OS] Close the QEMU window to exit"
else
    echo "[Claude-OS] Press Ctrl+A then X to exit QEMU"
fi
echo ""

exec "${QEMU_CMD[@]}"
