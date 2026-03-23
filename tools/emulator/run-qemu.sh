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

# Parse arguments
while [[ $# -gt 0 ]]; do
    case $1 in
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
            echo "Usage: $0 [--debug] [--memory MB] [--cpus N]"
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
    -append "root=/dev/vda console=ttyAMA0 rw"
    -nographic

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
echo "[Claude-OS] Press Ctrl+A then X to exit QEMU"
echo ""

exec "${QEMU_CMD[@]}"
