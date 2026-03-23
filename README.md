# Claude-OS — A Claude-Powered Mobile Operating System

Claude-OS is an ambitious open-source project to build a fully functional mobile operating system with Claude AI deeply integrated at every layer. The OS is designed from the ground up to be AI-native, with the Claude mobile app as the primary user interface and intelligence engine.

---

## Vision

A mobile OS where Claude isn't just an app — it **is** the OS. Every interaction, from managing WiFi to launching apps, can be driven through natural language. The system is lightweight, privacy-respecting, and built on open standards.

---

## Architecture Overview

```
┌─────────────────────────────────────────────┐
│              Claude Mobile App              │  ← Primary UI & AI layer
│         (Voice, Chat, Vision, Tools)        │
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
├─────────────────────────────────────────────┤
│               Hardware (SoC)                │  ← Target device
└─────────────────────────────────────────────┘
```

---

## Goal Features

### 1. WiFi Connectivity

Full WiFi support so the device can connect to the internet — the foundation for everything else.

#### Phase 1 — WiFi Scanning & Connection
- [x] Integrate `wpa_supplicant` or equivalent for WPA2/WPA3 support
- [x] Build a WiFi manager daemon that handles:
  - Scanning for available networks
  - Connecting to known / new networks
  - Storing saved network credentials (encrypted at rest)
  - Automatic reconnection on signal loss
- [x] Expose a D-Bus or socket-based IPC API for other system components to query network state
- [x] Support WPA2-Personal, WPA3-Personal, and open networks

#### Phase 2 — Claude-Driven WiFi Management
- [ ] Allow Claude to scan, list, and connect to WiFi networks via natural language
  - *"Connect me to the coffee shop WiFi"*
  - *"What networks are available?"*
  - *"Forget the hotel network"*
- [ ] Claude-powered network diagnostics
  - *"Why is my internet slow?"* → run speed test, check signal strength, suggest fixes
- [ ] Captive portal detection and assisted login

#### Phase 3 — Advanced Networking
- [ ] Hotspot / tethering support
- [ ] VPN integration (WireGuard / OpenVPN)
- [ ] DNS-over-HTTPS for privacy
- [ ] Network usage monitoring and per-app data tracking
- [ ] Firewall rules configurable through Claude

---

### 2. Claude Mobile App (Primary Interface)

The Claude mobile app serves as both the main user interface and the AI brain of the OS. It replaces the traditional home screen, app drawer, and settings panel.

#### Phase 1 — Core App Shell
- [x] Build or adapt the Claude mobile app to run as the system launcher
- [x] Full-screen chat interface as the default home screen
- [x] Voice input/output support (wake word: *"Hey Claude"*)
- [x] Persistent background service for always-on AI availability
- [ ] Notification tray integration — Claude can read, summarize, and act on notifications

#### Phase 2 — System Integration
- [x] Claude ↔ OS bridge: a secure API layer that lets Claude:
  - Toggle WiFi, Bluetooth, airplane mode
  - Adjust brightness, volume, and power settings
  - Open, close, and switch between apps
  - Read and respond to messages (with user permission)
  - Set alarms, timers, calendar events
- [x] Tool-use framework: Claude can invoke system tools (camera, file manager, browser) as part of a conversation
- [x] Context awareness: Claude has access to (opt-in):
  - Current battery level & charging state
  - Connected network info
  - Time, date, timezone, location
  - Running apps and foreground state

#### Phase 3 — Multimodal & Agentic
- [ ] Vision: Claude can see the screen and help the user navigate unfamiliar apps
- [ ] Agentic workflows: Claude can perform multi-step tasks autonomously
  - *"Download my boarding pass PDF from email and add the flight to my calendar"*
- [ ] On-device model support for basic queries when offline
- [ ] Conversation memory and personalization across sessions

---

## Roadmap

The project is broken into milestones. Each milestone produces a testable artifact.

### Milestone 0 — Project Setup & Tooling ✅
- [x] Choose target hardware (e.g., PinePhone, Pixel via custom ROM, QEMU for emulation)
- [x] Set up cross-compilation toolchain
- [x] Establish base Linux image (kernel + minimal userspace)
- [x] Set up CI/CD pipeline for automated builds
- [x] Create emulator/simulator setup for development without physical hardware

### Milestone 1 — Minimal Bootable System (partial)
- [x] Boot to a minimal Linux environment on target hardware / emulator
- [ ] Framebuffer or DRM-based display output
- [ ] Touchscreen input driver
- [x] Basic shell access over USB/serial for debugging

### Milestone 2 — WiFi Connectivity ✅
- [x] Kernel drivers for target WiFi chipset
- [x] `wpa_supplicant` integration
- [x] WiFi manager daemon with IPC API
- [x] CLI tool to scan/connect (for testing before UI exists)
- [x] Automated connection on boot to a configured network

### Milestone 3 — Display & UI Framework ✅
- [x] Choose or build a lightweight UI toolkit (candidates: Flutter, LVGL, custom Wayland compositor)
- [x] Implement a basic Wayland compositor for app rendering
- [x] Touch gesture handling (tap, swipe, pinch)
- [x] On-screen keyboard
- [x] Status bar (clock, battery, WiFi indicator)

### Milestone 4 — Claude App as System Launcher ✅
- [x] Port or build the Claude mobile app for the OS
- [x] App launches as the system home screen on boot
- [x] Chat interface with keyboard and voice input
- [x] Secure bridge API between Claude app and system services
- [x] Claude can query and control WiFi through the bridge

### Milestone 5 — Core OS Services (partial)
- [x] Power management (suspend, wake, shutdown)
- [x] Audio playback and microphone access
- [ ] Storage management and file system access
- [ ] Basic app lifecycle management (launch, suspend, kill)
- [ ] Notification system

### Milestone 6 — Security & Privacy (partial)
- [ ] Encrypted storage (LUKS or dm-crypt)
- [ ] Secure boot chain
- [ ] Sandboxed app execution (namespaces / seccomp)
- [x] Permission system — Claude must request user approval for sensitive actions
- [ ] All Claude API communication over TLS with certificate pinning

### Milestone 7 — Polish & Usability
- [ ] OTA update system
- [ ] Crash reporting and diagnostics
- [ ] Battery optimization
- [ ] Accessibility features
- [ ] User onboarding flow

---

## Technical Decisions (To Be Made)

| Decision | Options Under Consideration | Status |
|---|---|---|
| Target hardware | **QEMU ARM64 emulator** (PinePhone later) | **Decided** |
| Base system | **Buildroot** (minimal, fast, customizable) | **Decided** |
| UI framework | **Custom Wayland compositor** (Python + wlroots) | **Decided** |
| Display server | **Wayland (wlroots)** with layer-shell for overlays | **Decided** |
| IPC mechanism | **Unix sockets** (daemons) + **HTTP/WebSocket** (bridge API) | **Decided** |
| Claude integration | API-based (cloud), on-device hybrid, or both | TBD |
| App runtime | Native only, WebView-based, or Linux container | TBD |

---

## Repository Structure (Planned)

```
Claude-OS/
├── README.md                 # This file
├── kernel/                   # Kernel config, patches, and modules
├── system/                   # Core OS daemons and services
│   ├── wifi-manager/         # WiFi scanning, connection, management
│   ├── power-manager/        # Suspend, wake, shutdown
│   ├── audio-manager/        # Audio routing and control
│   ├── display-manager/      # Compositor and display control
│   └── bridge/               # Claude ↔ OS secure bridge API
├── ui/                       # UI framework and components
│   ├── compositor/           # Wayland compositor
│   ├── keyboard/             # On-screen keyboard
│   └── statusbar/            # System status bar
├── claude-app/               # Claude mobile app (launcher)
│   ├── chat/                 # Chat interface
│   ├── voice/                # Voice input/output
│   └── tools/                # System tool integrations
├── tools/                    # Build scripts, CI, and dev utilities
│   ├── build/                # Cross-compilation and image building
│   ├── emulator/             # QEMU / emulator configs
│   └── ci/                   # CI/CD pipeline configs
└── docs/                     # Additional documentation
    ├── architecture.md
    ├── contributing.md
    └── hardware-support.md
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

# Run in QEMU
make run      # Boots Claude-OS in a virtual ARM64 machine
```

---

## Contributing

This project is in the early planning stage. Contributions, ideas, and feedback are welcome. Check back as the roadmap progresses for contribution guidelines.

---

## License

TBD — Likely an open-source license (GPLv2 for kernel components, MIT/Apache-2.0 for userspace).
