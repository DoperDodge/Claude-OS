# Claude-OS — A Claude-Powered Mobile Operating System

Claude-OS is an ambitious open-source project to build a fully functional mobile operating system with Claude AI deeply integrated at every layer. The OS is designed from the ground up to be AI-native, with the Claude mobile app as the primary user interface and intelligence engine.

---

## Vision

A mobile OS where Claude isn't just an app — it **is** the OS. Every interaction, from managing WiFi to launching apps, can be driven through natural language. The system is lightweight, privacy-respecting, and built on open standards.

---

## Current Status

> **The backend is built. Pre-visual hardening complete. Ready for the visual OS.**

Claude-OS currently boots to a **text-only terminal** in QEMU. The system services (WiFi, notifications, power, audio, storage, app management, bridge API, chat engine) are implemented and functional. The kernel, CI, security, and API configuration have been hardened in preparation for the visual OS phase.

**What works today:**
- Buildroot-based ARM64 Linux image boots in QEMU
- System services start via systemd (WiFi, bridge API, notifications, etc.)
- Claude chat engine calls the Claude API and handles tool use
- Bridge API server on localhost:8080
- 167 tests across 9 modules, **now gated in CI**
- Kernel defconfig pre-configured for GPU/DRM/framebuffer display
- TLS certificate pinning on API communication
- `.env`-based API key management for development
- Security module: app sandboxing, encrypted storage, secure boot, TLS pinning

**What does NOT work yet:**
- No graphical display output (no pixels on screen)
- Wayland compositor has stub backend only (`wlroots bindings not yet built`)
- No visual home screen, app drawer, or phone-like UI
- QEMU launches with `-nographic` (no display window)
- Voice engine deferred until visual OS provides a UI surface

---

## Pre-Visual-OS Hardening (Completed)

Before building the visual OS, we completed these hardening tasks to reduce risk and tech debt:

- [x] **Kernel display readiness** — Added `virtio-gpu`, `DRM_FBDEV_EMULATION`, `FRAMEBUFFER_CONSOLE`, `DRM_GEM_SHMEM_HELPER`, keyboard/mouse input configs to the kernel defconfig. The kernel is now ready for graphical QEMU output without further config changes.
- [x] **CI test gating** — Added a `test` job to the GitHub Actions pipeline that runs the full pytest suite (143 tests) on every push and PR. Tests now block merges.
- [x] **API key management** — Chat engine now supports `.env` file for development, `ANTHROPIC_API_KEY` env var, and `/etc/claude-os/api_key` for on-device use. Added `.env.example` template and `.env` to `.gitignore`.
- [x] **Voice engine decision** — Formally deferred to post-visual-OS. Chose **espeak-ng** (TTS) and **Vosk** (STT) as target engines. Code is ready; just needs model binaries and a UI mic button.
- [x] **Security tightening** — Wired TLS certificate pinning into the chat engine's HTTP fallback path. Added `__init__.py` to security module for clean imports. Fixed `load_default_certs` call with explicit purpose. Fixed `_command_exists` bug in voice engine (wasn't checking return code).

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

## Visual OS Plan

This is the complete plan for turning Claude-OS from a text terminal into a fully visual, phone-like operating system running in QEMU with a graphical display.

### Phase 1 — Framebuffer Display in QEMU ✅

Get pixels on screen. No toolkit, no compositor — just proof that we can draw to a display.

- [x] Switch QEMU from `-nographic` to `-device virtio-gpu-pci -display gtk` (or SDL)
- [x] Add `virtio-gpu`, `drm`, and `fbdev` support to the kernel defconfig
- [x] Write a minimal framebuffer test program (`/dev/fb0` or DRM) that draws a colored rectangle
- [x] Write DRM/KMS display backend with dumb buffer API
- [x] Boot splash screen with Claude-OS logo and loading bar
- [x] Verify the QEMU window opens and shows graphics output
- [x] Add a `make run-gui` target that launches QEMU with a graphical window
- [x] 24 tests for display module (pixel packing, rendering, clipping)

**Deliverable:** QEMU opens a window, a colored rectangle is drawn on screen.

### Phase 2 — Wayland Compositor (Minimal)

Get a real compositor running so we can render application windows.

- [ ] Replace the Python wlroots stub with actual wlroots C bindings (via `pywlroots` or FFI)
  - Alternative: use a lightweight off-the-shelf compositor (`cage`, `labwc`, or `sway` in kiosk mode)
- [ ] Add `wlroots`, `wayland`, `libinput`, and `mesa` (for software rendering) to the Buildroot config
- [ ] Compositor launches on boot and displays a solid background color
- [ ] Verify a Wayland client can connect and render a window
- [ ] Mouse/keyboard input passes through from QEMU to Wayland clients

**Deliverable:** Compositor runs, Wayland clients can render, input works.

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
- [ ] Adaptive layout for different screen sizes

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

### Phase 8 — Hardware & Real Device

Move beyond QEMU to a physical phone.

- [ ] PinePhone / PinePhone Pro support:
  - Display driver (DSI panel)
  - Touchscreen driver
  - Modem support (cellular calls, SMS, data)
  - GPS, sensors (accelerometer, gyroscope, proximity, ambient light)
  - Camera (rear + front)
  - Audio (speaker, earpiece, headphone jack)
- [ ] Hardware GPU acceleration (Mali)
- [ ] Power management tuned for battery life
- [ ] SD card hot-plug support
- [ ] USB-C: charging, OTG, display out
- [ ] Flashable image (`.img` file for dd / Tow-Boot)

**Deliverable:** Claude-OS runs on a real phone you can hold in your hand.

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

### Milestone 4 — Security & Privacy ✅
- [x] Encrypted storage (LUKS)
- [x] Secure boot chain
- [x] App sandboxing (namespaces / seccomp)
- [x] Permission system for sensitive actions
- [x] TLS with certificate pinning (now wired into chat engine HTTP path)

### Milestone 5 — Chat Engine ✅
- [x] Claude API integration
- [x] Tool-use conversation loop
- [x] Conversation history and persistence
- [x] System tool registration
- [x] `.env` / env var / config file API key resolution chain

### Milestone 5.5 — Pre-Visual Hardening ✅ **← JUST COMPLETED**
- [x] Kernel defconfig: GPU, DRM, framebuffer console, input devices
- [x] CI: pytest job gating PRs (143 tests)
- [x] API key management: `.env` support + `.env.example` template
- [x] Voice engine decision: espeak-ng (TTS) + Vosk (STT), deferred to post-UI
- [x] Security: TLS pinning integrated into chat engine, module init, bug fixes

### Milestone 6 — Visual OS 🚧 **← IN PROGRESS**
- [x] Framebuffer / GPU display in QEMU (Phase 1 complete)
- [ ] Working Wayland compositor
- [ ] UI toolkit and widget system
- [ ] Lock screen, home screen, status bar
- [ ] On-screen keyboard
- [ ] Claude chat UI with message bubbles
- [ ] Notification panel
- [ ] App drawer

### Milestone 7 — App Ecosystem
- [ ] App framework with window management
- [ ] Built-in system apps (Settings, Files, Browser, Terminal)
- [ ] App install/uninstall

### Milestone 8 — Polish
- [ ] Animations and transitions
- [ ] Dark/light theme
- [ ] Accessibility
- [ ] OTA updates

### Milestone 9 — Real Hardware
- [ ] PinePhone support
- [ ] Hardware drivers (modem, camera, GPS, sensors)
- [ ] Flashable image

---

## Technical Decisions

| Decision | Choice | Status |
|---|---|---|
| Target hardware | **QEMU ARM64** (PinePhone later) | Decided |
| Base system | **Buildroot** (minimal, customizable) | Decided |
| Display server | **Wayland** (wlroots-based compositor) | Decided |
| IPC | **Unix sockets** (daemons) + **HTTP/WebSocket** (bridge) | Decided |
| UI toolkit | TBD: Python+Cairo, GTK4, LVGL, or Flutter | **To decide** |
| Claude integration | Cloud API (on-device later) | Decided |
| Voice STT | **Vosk** (offline, small model) — deferred to post-visual-OS | Decided |
| Voice TTS | **espeak-ng** (lightweight) — deferred to post-visual-OS | Decided |
| API key config | **`.env`** (dev) / **env var** / **config file** (prod) | Decided |
| App runtime | TBD: Native, WebView, or container | **To decide** |
| App packaging | TBD: Custom `.cpk`, Flatpak, or AppImage | **To decide** |

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
│   ├── display/              # Framebuffer & DRM rendering backends
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
├── tests/                    # Test suite (pytest, 167 tests)
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

# Configure API key (required for Claude chat)
cp .env.example .env
# Edit .env and add your Anthropic API key

# Build the OS
make setup    # Downloads Buildroot
make build    # Compiles everything (~30-60 min first time)

# Run tests
pip install pytest pytest-asyncio
pytest tests/ -v

# Run in QEMU (text mode — current default)
make run      # Boots Claude-OS in terminal mode

# Run in QEMU with graphical display (coming soon)
# make run-gui  # Boots with a visual display window
```

---

## Contributing

This project is in active development. The backend services are functional and the next major focus is **building the visual OS** (Milestone 6). Contributions, ideas, and feedback are welcome.

---

## License

TBD — Likely an open-source license (GPLv2 for kernel components, MIT/Apache-2.0 for userspace).
