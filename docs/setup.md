# Claude-OS Development Setup

## Prerequisites

### Host System
- Linux (Ubuntu 22.04+ recommended) or macOS with Docker
- At least 10GB free disk space (Buildroot downloads and builds are large)
- Internet connection for initial setup

### Required Packages (Ubuntu/Debian)

```bash
sudo apt-get update
sudo apt-get install -y \
    build-essential \
    gcc-aarch64-linux-gnu \
    qemu-system-aarch64 \
    libncurses-dev \
    unzip \
    bc \
    cpio \
    rsync \
    wget \
    curl \
    python3 \
    file \
    git
```

### Required Packages (Arch Linux)

```bash
sudo pacman -S \
    base-devel \
    aarch64-linux-gnu-gcc \
    qemu-system-aarch64 \
    ncurses \
    bc \
    cpio \
    rsync \
    wget \
    curl \
    python
```

## Building

### 1. Clone the repository

```bash
git clone https://github.com/DoperDodge/Claude-OS.git
cd Claude-OS
```

### 2. Setup Buildroot

This downloads Buildroot and applies the Claude-OS configuration:

```bash
make setup
```

### 3. Build the OS image

```bash
make build
```

This will take 30-60 minutes on first run (downloads and compiles the kernel, toolchain, and all packages). Subsequent builds are incremental and much faster.

### 4. Run in QEMU

```bash
make run
```

This boots Claude-OS in a QEMU ARM64 virtual machine. Press `Ctrl+A` then `X` to exit.

### 5. SSH into the VM

While QEMU is running, you can SSH in from another terminal:

```bash
ssh -p 2222 root@localhost
# Password: claude
```

## Customization

### Modify Buildroot config

```bash
make menuconfig
```

### Modify kernel config

Edit `kernel/qemu_aarch64_defconfig` and rebuild.

### Add files to the root filesystem

Place files in `tools/build/rootfs-overlay/`. The directory structure mirrors the root filesystem. For example, `tools/build/rootfs-overlay/usr/bin/my-script` will appear at `/usr/bin/my-script` in the OS.

## Debugging

### Run with GDB

```bash
make run-debug
```

Then in another terminal:

```bash
gdb-multiarch -ex 'target remote :1234'
```

## Available Make Targets

| Command | Description |
|---|---|
| `make help` | Show all available targets |
| `make setup` | Download and configure Buildroot |
| `make build` | Build the full OS image |
| `make run` | Launch in QEMU |
| `make run-debug` | Launch in QEMU with GDB server |
| `make menuconfig` | Open Buildroot configuration menu |
| `make clean` | Remove build artifacts |
| `make distclean` | Remove everything including Buildroot sources |
