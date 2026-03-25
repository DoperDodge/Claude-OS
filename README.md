# Claude-OS — A Claude-Powered Mobile Operating System

Claude-OS is an ambitious open-source project to build a fully functional mobile operating system with Claude AI deeply integrated at every layer. The OS is designed from the ground up to be AI-native, with the Claude mobile app as the primary user interface and intelligence engine.

---

## Vision

A mobile OS where Claude isn't just an app — it **is** the OS. Every interaction, from managing WiFi to launching apps, can be driven through natural language. The system is lightweight, privacy-respecting, and built on open standards.

**Target path:** QEMU VM → Google Pixel hardware.

---

## Current Status

> **The backend is built. The visual compositor is rendering.**

Claude-OS boots into QEMU with a graphical compositor that renders directly to the display via DRM/fbdev. The system services (WiFi, notifications, power, audio, storage, app management, bridge API, chat engine) are implemented and functional. The compositor runs a 30fps render loop, drawing a themed scene graph with surface placeholders.

**What works today:**
- Buildroot-based ARM64 Linux image boots in QEMU
- System services start via systemd (WiFi, bridge API, notifications, etc.)
- Claude chat engine calls the Claude API and handles tool use
- Bridge API server on localhost:8080
- Compositor renders to display via fbdev/DRM with Cairo
- QEMU GUI mode with virtio-gpu, touch, and keyboard input
- 157 tests across 9 modules

**What does NOT work yet:**
- No real Wayland protocol (compositor renders directly, no client windows yet)
- No visual home screen, app drawer, or phone-like UI widgets
- Voice engine is scaffolded but not connected to real speech libraries

**Porting roadmap:**
- **Stage 1:** Fully functional graphical OS running in QEMU VM (Phases 1–7)
- **Stage 2:** Validated on x86_64 and ARM64 VMs with GPU passthrough (Phase 8)
- **Stage 3:** Ported to Google Pixel hardware (Phases 9–12)

---

## Architecture Overview

```
┌─────────────────────────────────────────────┐
│              Claude Mobile App              │  ← Primary UI & AI layer
│         (Voice, Chat, Vision, Tools)        │
├─────────────────────────────────────────────┤
│             UI / Compositor Layer           │  ← Wayland + widget toolkit
│   ┌──────────┐  ┌──────────┐  ┌─────────┐  │
│   │ Wayland  │  │  Widget  │  │   OSK   │  │
│   │Compositor│  │ Toolkit  │  │Keyboard │  │
│   └──────────┘  └──────────┘  └─────────┘  │
├─────────────────────────────────────────────┤
│            System Services Layer            │  ← OS services exposed to Claude
│   ┌──────────┐  ┌──────────┐  ┌─────────┐  │
│   │  WiFi /  │  │ Display  │  │  Power  │  │
│   │ Network  │  │ Manager  │  │ Manager │  │
│   └──────────┘  └──────────┘  └─────────┘  │
│   ┌──────────┐  ┌──────────┐  ┌─────────┐  │
│   │  Audio   │  │ Storage  │  │  Input  │  │
│   │ Manager  │  │ Manager  │  │ Manager │  │
│   └──────────┘  └──────────┘  └─────────┘  │
├─────────────────────────────────────────────┤
│         Hardware Abstraction Layer          │  ← Drivers & firmware
│        (Linux Kernel / Android HAL)         │
├──────────────────────┬──────────────────────┤
│   QEMU VM (virtio)   │  Google Pixel (SoC)  │
│  virtio-gpu, net,    │  Tensor G1/G2/G3,    │
│  tablet, balloon     │  Mali GPU, Shannon   │
│  Software rendering  │  modem, sensors      │
└──────────────────────┴──────────────────────┘
```

---

## Visual OS & Hardware Porting Plan

This is the complete roadmap for turning Claude-OS from a text terminal into a fully visual, phone-like operating system — first running in a QEMU VM, then ported to Google Pixel hardware.

---

### STAGE 1 — Graphical OS in QEMU VM (Phases 1–7)

> Goal: A fully functional, phone-like graphical OS running in a virtual machine.

---

### Phase 1 — Framebuffer Display in QEMU ✅

Get pixels on screen. No toolkit, no compositor — just proof that we can draw to a display.

- [x] Switch QEMU from `-nographic` to `-device virtio-gpu-pci -display gtk` (or SDL)
- [x] Verify kernel defconfig has `CONFIG_DRM_VIRTIO_GPU=y` and `CONFIG_FB=y` (already present)
- [x] Add `mesa3d` (software renderer, `llvmpipe`) to the Buildroot config
- [x] Write a minimal framebuffer test program (`/dev/fb0` or DRM) that draws a colored rectangle
- [x] Verify the QEMU window opens and shows graphics output
- [x] Add a `make run-gui` target that launches QEMU with a graphical window
- [x] Add a `make run-gui-sdl` target for headless environments (SDL display)
- [x] Configure QEMU virtio-tablet device for absolute pointer input (mouse/touch)

**Deliverable:** QEMU opens a window, a colored rectangle is drawn on screen. Mouse cursor works.

### Phase 2 — Compositor with DRM/fbdev Rendering ✅

Get a real compositor running that renders to the display.

- [x] Replace the Python wlroots stub with direct DRM/fbdev rendering backend
  - Uses `/dev/fb0` (fbdev emulation) as primary, DRM dumb buffers as fallback
  - Renders via Cairo (pycairo) with raw pixel fallback
- [x] Add `wayland`, `wayland-protocols`, `libxkbcommon`, `pycairo` to Buildroot config
- [x] Compositor launches on boot and displays a solid themed background color
- [x] Scene graph render loop at 30fps with surface placeholders
- [x] VT switching (KD_GRAPHICS) to take over display from fbcon
- [x] Configure `XDG_RUNTIME_DIR`, IPC socket, and systemd service correctly
- [x] QEMU virtio-gpu configured with phone resolution (1080x2340)
- [x] Getty on tty1 disabled when compositor is running
- [x] Mouse/keyboard input passes through from QEMU to guest

**Deliverable:** Compositor runs, renders themed background with surface placeholders, input devices work.

### Phase 3 — UI Toolkit & Basic Rendering

Build the foundation for drawing actual UI elements (buttons, text, layouts).

- [ ] Choose a UI rendering approach:
  - **Option A:** Python + Cairo/Pango (draw to Wayland buffers directly)
  - **Option B:** GTK4 with Wayland backend (heavier but full widget set)
  - **Option C:** LVGL (lightweight, designed for embedded, C-based)
  - **Option D:** Flutter for Embedded Linux (Dart, GPU-accelerated)
- [ ] Implement a base `Widget` class with layout, drawing, and input handling
- [ ] Core widgets: `Label`, `Button`, `TextInput`, `ScrollView`, `Container`
- [ ] Font rendering with a system font (e.g., Noto Sans)
- [ ] Theme system with colors, spacing, and typography constants
- [ ] Touch/click event propagation through the widget tree
- [ ] Resolution-independent layout system (dp/sp units for Pixel portability)

**Deliverable:** Can render text, buttons, and scrollable containers on screen.

### Phase 4 — Phone UI Shell

Build the visual phone experience — the parts a user sees and touches.

#### 4a — Lock Screen
- [ ] Lock screen with clock, date, and "swipe up to unlock" gesture
- [ ] PIN/password entry screen
- [ ] Lock screen notifications (preview text)

#### 4b — Home Screen (Claude Chat)
- [ ] Full-screen Claude chat interface as the home screen
- [ ] Message bubbles (user on right, Claude on left) with word-wrap
- [ ] Text input bar at the bottom with on-screen keyboard trigger
- [ ] Microphone button for voice input
- [ ] Auto-scroll to latest message
- [ ] Typing indicator while Claude is responding
- [ ] Markdown rendering in Claude responses (bold, code blocks, lists)

#### 4c — Status Bar
- [ ] Always-on-top status bar at the top of the screen (24-32px)
- [ ] Clock (HH:MM)
- [ ] Battery percentage and icon
- [ ] WiFi signal strength icon
- [ ] Notification indicator dots

#### 4d — On-Screen Keyboard
- [ ] QWERTY keyboard that slides up from the bottom
- [ ] Shift, numbers/symbols layer toggle
- [ ] Key press visual feedback (highlight)
- [ ] Backspace, enter, space bar
- [ ] Keyboard auto-hides when tapping outside the text input

#### 4e — Notification Panel
- [ ] Swipe down from top to reveal notification panel
- [ ] Notification cards with app icon, title, body, timestamp
- [ ] Tap to open, swipe to dismiss
- [ ] Quick settings toggles (WiFi, Bluetooth, brightness, volume)

#### 4f — App Drawer
- [ ] Swipe up from bottom of home screen to open app drawer
- [ ] Grid of installed app icons with labels
- [ ] Tap to launch, long-press for options
- [ ] Search bar at the top

**Deliverable:** Looks and feels like a phone. Lock screen → home screen → chat with Claude → notifications → app drawer.

### Phase 5 — App Framework & Window Management

Let third-party and system apps run as visual windows.

- [ ] App windows render as Wayland surfaces managed by the compositor
- [ ] App switching: swipe gesture or recent-apps view (thumbnail cards)
- [ ] App lifecycle tied to visual state (foreground = visible, background = suspended)
- [ ] System apps:
  - [ ] **Settings** — WiFi, display, sound, about, accounts
  - [ ] **File Manager** — browse `/home`, SD card, downloads
  - [ ] **Web Browser** — lightweight WebView-based browser (e.g., webkitgtk)
  - [ ] **Terminal** — built-in terminal emulator for power users
  - [ ] **Contacts / Dialer** — placeholder UI for future telephony
- [ ] App install/uninstall flow (`.cpk` Claude-OS packages or Flatpak)

**Deliverable:** Multiple apps can run, switch between them, each renders in its own window.

### Phase 6 — Animations & Polish

Make it feel smooth and modern.

- [ ] Screen transitions (slide left/right between screens)
- [ ] Keyboard slide-up/slide-down animation
- [ ] Notification panel slide-down animation
- [ ] App launch zoom animation
- [ ] Smooth scrolling in chat and lists
- [ ] Loading spinners and skeleton screens
- [ ] Haptic-style visual feedback (button press ripple effect)
- [ ] Dark mode / light mode theme toggle
- [ ] Adaptive layout for different screen sizes (VM and Pixel resolutions)

**Deliverable:** The OS feels responsive and polished, not janky.

### Phase 7 — Claude Visual Integration

Claude can see and interact with the visual OS.

- [ ] Claude can take screenshots of the current display
- [ ] Claude can read on-screen text and describe what's shown
- [ ] Claude can generate and display rich responses:
  - Inline images, charts, code blocks with syntax highlighting
  - Interactive cards (e.g., WiFi network picker, file browser)
  - Action buttons within chat ("Connect", "Open", "Share")
- [ ] Claude-driven UI: Claude can dynamically create UI screens
  - *"Show me my calendar this week"* → Claude renders a calendar view
  - *"Make a shopping list"* → Claude shows an editable checklist
- [ ] Ambient mode: Claude provides a glanceable dashboard when idle (weather, reminders, news)

**Deliverable:** Claude is deeply visual — it sees the screen, renders rich UI, and creates dynamic interfaces.

---

### STAGE 2 — VM Hardening & Portability (Phase 8)

> Goal: Validate the OS across VM environments and prepare for real hardware.

---

### Phase 8 — VM Portability & GPU Passthrough

Ensure Claude-OS runs reliably across VM environments and can leverage real GPUs.

- [ ] **x86_64 VM support:** Create a secondary Buildroot defconfig targeting x86_64 QEMU
  - Kernel defconfig: `kernel/qemu_x86_64_defconfig`
  - Buildroot config: `tools/build/claude_os_x86_64_defconfig`
  - `make build-x86` and `make run-gui-x86` targets
- [ ] **VirtualBox / VMware support:**
  - Generate `.ova` and `.vmdk` images from the Buildroot output
  - Add VirtualBox Guest Additions and VMware Tools to the build
  - `make export-ova` target for one-click VM image generation
- [ ] **GPU passthrough (QEMU/KVM):**
  - Document PCI passthrough setup for NVIDIA/AMD GPUs
  - Test with `virgl` (Virgil 3D) for GPU-accelerated rendering in QEMU
  - Verify Wayland compositor works with hardware-accelerated Mesa
- [ ] **Automated VM testing:**
  - QEMU boot-to-UI smoke test in CI (headless with virtual framebuffer)
  - Screenshot comparison tests (render expected UI, compare bitmaps)
- [ ] **Shared folder / host integration:**
  - 9P virtio-fs for sharing files between host and VM
  - Clipboard sharing via `spice-vdagent` (SPICE protocol)
- [ ] **ISO image generation:**
  - `make iso` target that produces a bootable `.iso` for any VM
  - UEFI boot support (OVMF firmware)

**Deliverable:** Claude-OS runs in QEMU, VirtualBox, and VMware. GPU acceleration works. Distributable `.iso` and `.ova` images.

---

### STAGE 3 — Google Pixel Hardware Port (Phases 9–12)

> Goal: Run Claude-OS natively on Google Pixel phones.

---

### Phase 9 — Pixel Kernel & Boot Chain

Get the Linux kernel booting on a Google Pixel (starting with Pixel 6/7/8 — Google Tensor SoC).

- [ ] **Android kernel fork:**
  - Fork the Google Android kernel source for the target Pixel device
  - Branch: `android-gs-raviole-6.x` (Pixel 6) or `android-gs-tangorpro-6.x` (Pixel 7+)
  - Create `kernel/pixel_defconfig` with Tensor SoC support
- [ ] **Bootloader integration:**
  - Use the stock Pixel bootloader (unlocked via `fastboot oem unlock`)
  - Build a boot image (`boot.img`) compatible with the Pixel boot chain
  - Generic Kernel Image (GKI) compliance for kernel module loading
  - Support A/B partition scheme used by Pixels
- [ ] **Device tree / Device Tree Overlays (DTBOs):**
  - Include Google-provided DTBs for display, touch, sensors
  - Custom DTBO for Claude-OS-specific configuration
- [ ] **Minimal userspace on Pixel:**
  - `init` → systemd → serial console over USB (adb-style)
  - Verify kernel boots and reaches a shell prompt
  - Bring up USB gadget mode for host communication during development
- [ ] **Buildroot Pixel profile:**
  - `tools/build/claude_os_pixel_defconfig` — Pixel-specific package set
  - Cross-compile toolchain targeting `aarch64` with Tensor-specific flags
  - `make build-pixel` and `make flash-pixel` targets

**Deliverable:** Linux kernel boots on a Pixel phone, reaches a shell prompt over USB.

### Phase 10 — Pixel Display, Touch & Core Hardware

Bring up the display, touchscreen, and essential hardware on the Pixel.

- [ ] **Display (Samsung AMOLED panel):**
  - DSI display driver (from Android kernel source)
  - DRM/KMS integration for Wayland compositor
  - Correct resolution: 1080×2400 (Pixel 6) / 1080×2340 (Pixel 7/8)
  - Panel backlight control via sysfs
  - 90Hz / 120Hz refresh rate support (device-dependent)
- [ ] **Touchscreen (Goodix / SEC):**
  - Multi-touch driver with 10-point touch support
  - Touch event routing through libinput to Wayland compositor
  - Gesture recognition (swipe, pinch, long-press)
- [ ] **GPU (Mali G78 / Immortalis):**
  - Mali GPU driver (Panthor/Panfrost for open-source, or ARM binary blobs)
  - Mesa integration for OpenGL ES / Vulkan
  - Verify GPU-accelerated Wayland rendering
- [ ] **Wi-Fi & Bluetooth (Broadcom BCM4389):**
  - Load firmware blobs from `/vendor` partition or bundled in rootfs
  - Verify `wpa_supplicant` connects to real Wi-Fi networks
  - BlueZ integration for Bluetooth
- [ ] **USB-C:**
  - Charging detection and battery management (via fuel gauge driver)
  - USB gadget mode (ADB-like shell, file transfer)
  - USB host mode (OTG peripherals)
- [ ] **Audio (Cirrus Logic CS35L41 / CS40L26):**
  - ALSA/PipeWire audio routing
  - Speaker, earpiece, and headphone output
  - Microphone input (for voice commands)

**Deliverable:** Pixel shows the Claude-OS UI on its display. Touch, Wi-Fi, audio, and GPU work.

### Phase 11 — Pixel Telephony & Sensors

Turn the Pixel into a full phone running Claude-OS.

- [ ] **Cellular modem (Samsung Shannon / Exynos modem):**
  - RIL (Radio Interface Layer) or `oFono` integration
  - Voice calls (dialer app)
  - SMS send/receive
  - Mobile data (LTE/5G) with APN configuration
  - SIM card detection and management
  - Claude integration: *"Call Mom"*, *"Send a text to John"*
- [ ] **GPS / Location:**
  - GNSS driver (GPS, GLONASS, Galileo)
  - Location services daemon
  - Claude integration: *"Where am I?"*, *"Navigate to..."*
- [ ] **Sensors:**
  - Accelerometer + gyroscope (screen rotation, motion gestures)
  - Proximity sensor (screen off during calls)
  - Ambient light sensor (auto-brightness)
  - Barometer
  - Fingerprint reader (under-display, Pixel 6+) — for lock screen auth
- [ ] **Camera (Google camera ISP):**
  - Rear camera basic capture (photo, video)
  - Front camera for selfies / video calls
  - Camera2 API or V4L2 integration
  - Claude vision: *"What am I looking at?"*
- [ ] **NFC:**
  - NFC tag reading
  - Future: contactless payments, device pairing
- [ ] **Haptics (vibration motor):**
  - Haptic feedback for keyboard presses, notifications
  - Pattern-based vibration for calls and alarms

**Deliverable:** Full phone functionality — calls, texts, data, GPS, camera, sensors all working.

### Phase 12 — Pixel Release & Distribution

Ship a flashable Claude-OS image for Google Pixel phones.

- [ ] **Flashable image pipeline:**
  - `make pixel-image` generates a complete set of partition images
  - `make flash-pixel` flashes via `fastboot` (boot, system, vendor, dtbo)
  - Factory reset support (wipe userdata, keep OS)
  - Dual-boot option: Claude-OS alongside stock Android (A/B slots)
- [ ] **OTA updates:**
  - Update server for over-the-air OS updates
  - A/B seamless updates (update inactive slot, reboot to switch)
  - Rollback on failed update
  - Claude-managed updates: *"Is there an update available?"*
- [ ] **Battery optimization:**
  - Power governor tuned for Tensor SoC
  - Suspend-to-RAM with fast wake
  - Per-app battery usage tracking
  - Adaptive brightness and refresh rate
  - Target: full-day battery life
- [ ] **Security hardening for Pixel:**
  - Verified boot (dm-verity on system partition)
  - SELinux policy for Claude-OS services
  - Titan M2 security chip integration (hardware-backed keystore)
  - Monthly security patch cadence
- [ ] **Pixel model support matrix:**
  - [ ] Pixel 6 / 6 Pro (GS101 Tensor)
  - [ ] Pixel 7 / 7 Pro (GS201 Tensor G2)
  - [ ] Pixel 8 / 8 Pro (GS301 Tensor G3)
  - [ ] Pixel 9 / 9 Pro (Tensor G4) — stretch goal
- [ ] **User documentation:**
  - Unlock bootloader guide
  - Flash instructions (Linux, macOS, Windows)
  - Known issues and workarounds per device
  - Reverting to stock Android guide

**Deliverable:** Anyone with a supported Pixel can download an image, flash it, and run Claude-OS as their daily driver.

---

## Feature Details

### WiFi Connectivity

#### Phase 1 — WiFi Scanning & Connection ✅
- [x] `wpa_supplicant` integration for WPA2/WPA3
- [x] WiFi manager daemon (scan, connect, saved networks, auto-reconnect)
- [x] D-Bus and socket-based IPC API
- [x] WPA2-Personal, WPA3-Personal, and open networks

#### Phase 2 — Claude-Driven WiFi Management (Partial)
- [x] Claude can scan, list, and connect via natural language
- [ ] Claude-powered network diagnostics
- [ ] Captive portal detection and assisted login

#### Phase 3 — Advanced Networking
- [ ] Hotspot / tethering
- [ ] VPN integration (WireGuard / OpenVPN)
- [ ] DNS-over-HTTPS
- [ ] Network usage monitoring
- [ ] Claude-configurable firewall rules

### Claude App (Primary Interface)

#### Phase 1 — Core App Shell ✅ (Backend Only)
- [x] App runs as system launcher (logic only, no visual rendering)
- [x] Chat engine with Claude API integration
- [x] Voice engine scaffolded (wake word: *"Hey Claude"*)
- [x] Notification integration via bridge API

#### Phase 2 — System Integration ✅
- [x] Bridge API: Claude can toggle WiFi, adjust volume, manage apps, read notifications
- [x] Tool-use framework: Claude invokes system tools in conversation
- [x] Context awareness: battery, network, time, running apps

#### Phase 3 — Multimodal & Agentic
- [ ] Vision: Claude can see the screen
- [ ] Agentic multi-step workflows
- [ ] On-device model for offline use
- [ ] Conversation memory across sessions

---

## Milestone Tracker

### Milestone 0 — Project Setup & Tooling ✅
- [x] Target hardware: QEMU ARM64
- [x] Cross-compilation toolchain (Buildroot)
- [x] Base Linux image (kernel + minimal userspace)
- [x] CI/CD pipeline
- [x] Emulator setup

### Milestone 1 — Bootable System ✅
- [x] Boot to Linux environment in QEMU
- [x] Shell access for debugging
- [ ] ~~Framebuffer/DRM display output~~ *(not yet — QEMU runs `-nographic`)*
- [ ] ~~Touchscreen input~~ *(not yet — no display to touch)*

### Milestone 2 — WiFi Connectivity ✅
- [x] Kernel drivers for WiFi
- [x] `wpa_supplicant` integration
- [x] WiFi manager daemon with IPC
- [x] CLI tool for scan/connect
- [x] Auto-connect on boot

### Milestone 3 — System Services ✅
- [x] Power management
- [x] Audio manager
- [x] Storage manager
- [x] App lifecycle management
- [x] Notification system
- [x] Bridge API server

### Milestone 4 — Security & Privacy ✅ (Scaffolded)
- [x] Encrypted storage (LUKS)
- [x] Secure boot chain
- [x] App sandboxing (namespaces / seccomp)
- [x] Permission system for sensitive actions
- [x] TLS with certificate pinning

### Milestone 5 — Chat Engine ✅
- [x] Claude API integration
- [x] Tool-use conversation loop
- [x] Conversation history and persistence
- [x] System tool registration

### Milestone 6 — Visual OS in VM 🚧 **← WE ARE HERE**
- [ ] Framebuffer / GPU display in QEMU (Phase 1)
- [ ] Working Wayland compositor (Phase 2)
- [ ] UI toolkit and widget system (Phase 3)
- [ ] Lock screen, home screen, status bar (Phase 4)
- [ ] On-screen keyboard (Phase 4d)
- [ ] Claude chat UI with message bubbles (Phase 4b)
- [ ] Notification panel (Phase 4e)
- [ ] App drawer (Phase 4f)

### Milestone 7 — App Ecosystem
- [ ] App framework with window management (Phase 5)
- [ ] Built-in system apps (Settings, Files, Browser, Terminal)
- [ ] App install/uninstall

### Milestone 8 — Polish & VM Distribution
- [ ] Animations and transitions (Phase 6)
- [ ] Dark/light theme
- [ ] Claude visual integration — screenshots, rich UI (Phase 7)
- [ ] VM portability — VirtualBox, VMware `.ova` images (Phase 8)
- [ ] GPU passthrough and virgl acceleration (Phase 8)
- [ ] Bootable `.iso` image generation

### Milestone 9 — Pixel Kernel & Boot 📱
- [ ] Android kernel fork for Google Tensor SoC (Phase 9)
- [ ] Boot chain integration with Pixel bootloader
- [ ] Device tree and DTBO support
- [ ] `make build-pixel` and `make flash-pixel` targets
- [ ] Shell prompt over USB on Pixel hardware

### Milestone 10 — Pixel Display & Core Hardware 📱
- [ ] AMOLED display driver (DSI panel) (Phase 10)
- [ ] Multi-touch input via Goodix/SEC driver
- [ ] Mali GPU acceleration (Panfrost/Panthor)
- [ ] Wi-Fi, Bluetooth, USB-C, audio on real hardware

### Milestone 11 — Pixel Full Phone 📱
- [ ] Cellular modem — calls, SMS, mobile data (Phase 11)
- [ ] GPS, sensors, camera, NFC, haptics
- [ ] Claude telephony integration (*"Call Mom"*, *"Text John"*)

### Milestone 12 — Pixel Release 📱
- [ ] Flashable image pipeline for Pixel 6/7/8/9 (Phase 12)
- [ ] OTA updates with A/B seamless switching
- [ ] Security hardening (verified boot, Titan M2, SELinux)
- [ ] User-facing flash guide and documentation

---

## Technical Decisions

| Decision | Choice | Status |
|---|---|---|
| VM target | **QEMU ARM64** (primary dev environment) | Decided |
| Hardware target | **Google Pixel 6/7/8** (Tensor SoC) | Decided |
| Base system | **Buildroot** (minimal, customizable) | Decided |
| Pixel kernel | **Android kernel fork** (GKI-based) | Decided |
| Display server | **Wayland** (wlroots-based compositor) | Decided |
| GPU (VM) | **Mesa llvmpipe** (software) + **virgl** (accelerated) | Decided |
| GPU (Pixel) | **Panfrost/Panthor** (open-source Mali) or ARM blobs | **To decide** |
| IPC | **Unix sockets** (daemons) + **HTTP/WebSocket** (bridge) | Decided |
| UI toolkit | TBD: Python+Cairo, GTK4, LVGL, or Flutter | **To decide** |
| Claude integration | Cloud API (on-device later) | Decided |
| App runtime | TBD: Native, WebView, or container | **To decide** |
| App packaging | TBD: Custom `.cpk`, Flatpak, or AppImage | **To decide** |
| Distribution | `.iso` (VM) + `fastboot` images (Pixel) | Decided |
| Telephony (Pixel) | TBD: oFono or Android RIL | **To decide** |

---

## Repository Structure

```
Claude-OS/
├── README.md                 # This file
├── Makefile                  # Build, run, test targets
├── kernel/                   # Kernel config, patches, modules
├── system/                   # Core OS daemons and services
│   ├── wifi-manager/         # WiFi scanning, connection, management
│   ├── power-manager/        # Suspend, wake, shutdown
│   ├── audio-manager/        # Audio routing and control
│   ├── display-manager/      # Display session orchestrator
│   ├── bridge/               # Claude ↔ OS bridge API (HTTP/WS)
│   ├── notifications/        # Notification manager
│   ├── app-manager/          # App lifecycle management
│   ├── security/             # Encryption, sandboxing, secure boot
│   └── onboarding/           # First-boot setup flow
├── ui/                       # Visual UI layer
│   ├── compositor/           # Wayland compositor (wlroots)
│   ├── toolkit/              # Widget system (TBD)
│   ├── keyboard/             # On-screen keyboard
│   ├── statusbar/            # System status bar
│   ├── lockscreen/           # Lock screen (TODO)
│   ├── notifications/        # Notification panel UI (TODO)
│   └── appdrawer/            # App drawer UI (TODO)
├── claude-app/               # Claude app (launcher + chat)
│   ├── chat/                 # Chat engine + UI
│   ├── voice/                # Voice input/output
│   └── tools/                # System tool integrations
├── apps/                     # Built-in system apps (TODO)
│   ├── settings/             # Settings app
│   ├── files/                # File manager
│   ├── browser/              # Web browser
│   └── terminal/             # Terminal emulator
├── tests/                    # Test suite (pytest, 143 tests)
├── tools/                    # Build scripts and dev utilities
│   ├── build/                # Buildroot config, rootfs overlay
│   ├── emulator/             # QEMU configs
│   └── ci/                   # CI/CD pipeline
└── docs/                     # Documentation
```

---

## Getting Started

See [docs/setup.md](docs/setup.md) for full instructions. Quick start:

```bash
# Install dependencies (Ubuntu/Debian)
sudo apt-get install build-essential gcc-aarch64-linux-gnu qemu-system-aarch64 \
    libncurses-dev unzip bc cpio rsync wget curl python3 file

# Build the OS
make setup    # Downloads Buildroot
make build    # Compiles everything (~30-60 min first time)

# Run in QEMU (text mode — current default)
make run          # Boots Claude-OS in terminal mode

# Run in QEMU with graphical display (coming soon)
# make run-gui      # Boots with a visual display window (GTK)
# make run-gui-sdl  # Boots with a visual display window (SDL, for headless/SSH)

# VM distribution (coming soon)
# make iso          # Generate bootable .iso image
# make export-ova   # Generate .ova for VirtualBox/VMware

# Google Pixel build (coming later)
# make build-pixel  # Cross-compile for Pixel hardware
# make flash-pixel  # Flash to connected Pixel via fastboot
```

---

## Supported Targets

| Target | Status | Build Command | Output |
|---|---|---|---|
| QEMU ARM64 (text) | **Working** | `make build && make run` | Terminal in QEMU |
| QEMU ARM64 (GUI) | **Phase 1** | `make build && make run-gui` | Graphical window |
| QEMU x86_64 (GUI) | **Phase 8** | `make build-x86 && make run-gui-x86` | Graphical window |
| VirtualBox / VMware | **Phase 8** | `make export-ova` | `.ova` image |
| Bootable ISO | **Phase 8** | `make iso` | `.iso` image |
| Google Pixel 6 | **Phase 9–12** | `make build-pixel DEVICE=pixel6` | Fastboot images |
| Google Pixel 7 | **Phase 9–12** | `make build-pixel DEVICE=pixel7` | Fastboot images |
| Google Pixel 8 | **Phase 9–12** | `make build-pixel DEVICE=pixel8` | Fastboot images |

---

## Contributing

This project is in active development. The backend services are functional and the next major focus is **building the visual OS in a VM** (Milestone 6), with a long-term goal of **running natively on Google Pixel phones** (Milestones 9–12). Contributions, ideas, and feedback are welcome.

---

## License

TBD — Likely an open-source license (GPLv2 for kernel components, MIT/Apache-2.0 for userspace).
