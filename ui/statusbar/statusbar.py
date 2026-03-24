"""
Claude-OS Status Bar

A frosted-glass status bar rendered as a Wayland layer-shell surface.
Inspired by Apple's Dynamic Island merged with Claude's warm aesthetic.

Layout:
    ┌─────────────────────────────────────────────────┐
    │                                                 │
    │  9:41      ┌──────────────┐     ●●● 85% ▐██▌   │
    │            │ Claude-OS  ⦿ │     WiFi  BAT       │
    │            └──────────────┘                     │
    │                                                 │
    └─────────────────────────────────────────────────┘

Features:
    - Frosted glass background with warm tint
    - Dynamic Island-style center pill (shows active context)
    - SF-style iconography (battery, wifi, signal)
    - Smooth transitions when indicators change
    - Responds to theme mode (light/dark)
"""

import asyncio
import json
import logging
import os
import sys
import time
from dataclasses import dataclass, field
from enum import Enum, auto

# Add bridge client to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "../../system/bridge"))

logger = logging.getLogger("statusbar")


# ---------------------------------------------------------------------------
# Status icons (symbolic, rendered as vector paths in production)
# ---------------------------------------------------------------------------

class BatteryIcon(Enum):
    """Battery icon states."""
    FULL = "battery_full"
    THREE_QUARTER = "battery_75"
    HALF = "battery_50"
    QUARTER = "battery_25"
    LOW = "battery_low"
    CRITICAL = "battery_critical"
    CHARGING = "battery_charging"

    @staticmethod
    def from_level(level: int, charging: bool = False) -> "BatteryIcon":
        if charging:
            return BatteryIcon.CHARGING
        if level > 80:
            return BatteryIcon.FULL
        if level > 55:
            return BatteryIcon.THREE_QUARTER
        if level > 30:
            return BatteryIcon.HALF
        if level > 15:
            return BatteryIcon.QUARTER
        if level > 5:
            return BatteryIcon.LOW
        return BatteryIcon.CRITICAL


class WifiIcon(Enum):
    """WiFi signal icon states."""
    OFF = "wifi_off"
    WEAK = "wifi_1"
    FAIR = "wifi_2"
    GOOD = "wifi_3"
    STRONG = "wifi_full"

    @staticmethod
    def from_signal(connected: bool, strength: int = 0) -> "WifiIcon":
        if not connected:
            return WifiIcon.OFF
        if strength > 75:
            return WifiIcon.STRONG
        if strength > 50:
            return WifiIcon.GOOD
        if strength > 25:
            return WifiIcon.FAIR
        return WifiIcon.WEAK


# ---------------------------------------------------------------------------
# Dynamic Island context
# ---------------------------------------------------------------------------

class IslandContext(Enum):
    """What the Dynamic Island-style pill is showing."""
    IDLE = auto()           # Just "Claude-OS" branding
    LISTENING = auto()      # Voice input active (pulsing ring)
    THINKING = auto()       # Claude is processing (animated dots)
    TIMER = auto()          # Timer/stopwatch running
    MUSIC = auto()          # Audio playing (waveform)
    CALL = auto()           # Phone call active
    NAVIGATION = auto()     # Turn-by-turn directions


@dataclass
class IslandState:
    """Current Dynamic Island content."""
    context: IslandContext = IslandContext.IDLE
    primary_text: str = "Claude-OS"
    secondary_text: str = ""
    icon: str = ""
    progress: float = 0.0   # For timers, progress bars
    expanded: bool = False   # True = expanded pill view


# ---------------------------------------------------------------------------
# Status Bar State & Component
# ---------------------------------------------------------------------------

@dataclass
class StatusBarState:
    """Current state of all status bar indicators."""
    # Clock
    time_str: str = "00:00"
    date_str: str = ""

    # Battery
    battery_level: int = -1  # -1 = unknown
    battery_charging: bool = False
    battery_icon: BatteryIcon = BatteryIcon.FULL

    # WiFi
    wifi_connected: bool = False
    wifi_ssid: str = ""
    wifi_signal: int = 0  # 0-100
    wifi_icon: WifiIcon = WifiIcon.OFF

    # Notifications
    notification_count: int = 0
    has_unread: bool = False

    # Display
    brightness: int = 100

    # Dynamic Island
    island: IslandState = field(default_factory=IslandState)


class StatusBar:
    """
    System status bar for Claude-OS.

    Renders at the top of the screen as a Wayland layer-shell surface.
    Uses frosted glass compositing with Claude's warm cream tint.

    Visual design:
    - Height: 54 logical pixels
    - Background: frosted glass (24px blur, warm white tint at 60% opacity)
    - Left cluster: time (semibold 14pt)
    - Center: Dynamic Island pill (220×36px, 18px radius)
    - Right cluster: notification dots, wifi icon, battery icon + percentage
    - All elements use theme colors (adapt to light/dark)
    """

    HEIGHT = 54   # Logical pixels (increased from 48 for modern feel)
    ISLAND_WIDTH = 220
    ISLAND_HEIGHT = 36
    ISLAND_RADIUS = 18
    UPDATE_INTERVAL = 5  # Seconds between polls

    def __init__(self, bridge_url: str = "http://127.0.0.1:8080"):
        self.bridge_url = bridge_url
        self.state = StatusBarState()
        self._running = False

    async def start(self):
        """Start the status bar update loop."""
        self._running = True
        logger.info("Status bar started (height=%dpx, island=%dx%d)",
                     self.HEIGHT, self.ISLAND_WIDTH, self.ISLAND_HEIGHT)

        # Run both the poller and the event listener
        await asyncio.gather(
            self._poll_loop(),
            self._event_listener(),
        )

    async def stop(self):
        """Stop the status bar."""
        self._running = False

    async def _poll_loop(self):
        """Periodically poll the Bridge API for status updates."""
        while self._running:
            self._update_clock()
            await self._fetch_battery()
            await self._fetch_wifi()
            self._render()
            await asyncio.sleep(self.UPDATE_INTERVAL)

    async def _event_listener(self):
        """Listen for real-time events from the Bridge API."""
        try:
            from client import AsyncBridgeClient
            client = AsyncBridgeClient(self.bridge_url)

            async for event in client.events():
                event_type = event.get("event", "")
                data = event.get("data", {})

                if event_type == "wifi.connected":
                    self.state.wifi_connected = True
                    self.state.wifi_ssid = data.get("ssid", "")
                    self.state.wifi_icon = WifiIcon.from_signal(
                        True, data.get("signal_strength", 50))
                    self._render()
                elif event_type == "wifi.disconnected":
                    self.state.wifi_connected = False
                    self.state.wifi_ssid = ""
                    self.state.wifi_icon = WifiIcon.OFF
                    self._render()
                elif event_type == "battery.low":
                    self.state.battery_level = data.get("level", 0)
                    self.state.battery_icon = BatteryIcon.from_level(
                        self.state.battery_level, self.state.battery_charging)
                    self._render()
                elif event_type == "notification.new":
                    self.state.notification_count += 1
                    self.state.has_unread = True
                    self._render()
                elif event_type == "audio.mute_changed":
                    self._render()

        except Exception as e:
            logger.warning("Event listener failed: %s (using polling only)", e)

    def _update_clock(self):
        """Update the clock display."""
        now = time.localtime()
        self.state.time_str = time.strftime("%H:%M", now)
        self.state.date_str = time.strftime("%a %b %d", now)

    async def _fetch_battery(self):
        """Fetch battery status from Bridge API."""
        try:
            from client import BridgeClient
            client = BridgeClient(self.bridge_url)
            info = client.battery()
            if info.get("available"):
                self.state.battery_level = info.get("level", -1)
                self.state.battery_charging = info.get("status") == "Charging"
                self.state.battery_icon = BatteryIcon.from_level(
                    self.state.battery_level, self.state.battery_charging)
        except Exception:
            pass

    async def _fetch_wifi(self):
        """Fetch WiFi status from Bridge API."""
        try:
            from client import BridgeClient
            client = BridgeClient(self.bridge_url)
            status = client.wifi_status()
            self.state.wifi_connected = status.get("connected", False)
            self.state.wifi_ssid = status.get("ssid", "")
            self.state.wifi_signal = status.get("signal_strength", 0)
            self.state.wifi_icon = WifiIcon.from_signal(
                self.state.wifi_connected, self.state.wifi_signal)
        except Exception:
            pass

    # --- Dynamic Island ---

    def set_island_context(self, context: IslandContext,
                           primary: str = "", secondary: str = "",
                           icon: str = ""):
        """Update the Dynamic Island display."""
        self.state.island = IslandState(
            context=context,
            primary_text=primary or "Claude-OS",
            secondary_text=secondary,
            icon=icon,
        )
        self._render()

    def expand_island(self):
        """Expand the island to show more detail."""
        self.state.island.expanded = True
        self._render()

    def collapse_island(self):
        """Collapse the island back to pill size."""
        self.state.island.expanded = False
        self._render()

    # --- Rendering ---

    def _render(self):
        """
        Render the status bar.

        Production pipeline:
        1. Capture background region (for blur)
        2. Apply Gaussian blur (radius 24px)
        3. Tint with warm white at 60% opacity
        4. Draw Dynamic Island pill (dark, rounded)
        5. Draw left cluster (time, semibold)
        6. Draw right cluster (icons)
        7. Commit buffer to Wayland

        Development: log the current state.
        """
        left = self.state.time_str
        center = self.state.island.primary_text
        right_parts = []

        # Notification dots
        if self.state.notification_count > 0:
            right_parts.append(f"•{self.state.notification_count}")

        # Battery indicator
        if self.state.battery_level >= 0:
            charge_icon = "⚡" if self.state.battery_charging else ""
            right_parts.append(f"{charge_icon}{self.state.battery_level}%")

        # WiFi indicator
        if self.state.wifi_connected:
            right_parts.append(f"WiFi:{self.state.wifi_ssid}")
        else:
            right_parts.append("WiFi:OFF")

        right = "  ".join(right_parts)

        logger.debug("StatusBar: [%s]  ⌈%s⌉  [%s]", left, center, right)

    def get_layout(self) -> dict:
        """Return the current status bar layout for external renderers."""
        return {
            "height": self.HEIGHT,
            "blur": {
                "radius": 24,
                "saturation": 1.6,
                "tint": "warm_white_60",
            },
            "left": {
                "time": self.state.time_str,
            },
            "center": {
                "island": {
                    "width": self.ISLAND_WIDTH,
                    "height": self.ISLAND_HEIGHT,
                    "radius": self.ISLAND_RADIUS,
                    "context": self.state.island.context.name,
                    "primary_text": self.state.island.primary_text,
                    "secondary_text": self.state.island.secondary_text,
                    "expanded": self.state.island.expanded,
                },
            },
            "right": {
                "notifications": {
                    "count": self.state.notification_count,
                    "has_unread": self.state.has_unread,
                },
                "wifi": {
                    "connected": self.state.wifi_connected,
                    "ssid": self.state.wifi_ssid,
                    "signal": self.state.wifi_signal,
                    "icon": self.state.wifi_icon.value,
                },
                "battery": {
                    "level": self.state.battery_level,
                    "charging": self.state.battery_charging,
                    "icon": self.state.battery_icon.value,
                },
            },
        }


async def main():
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    )
    bar = StatusBar()
    await bar.start()


if __name__ == "__main__":
    asyncio.run(main())
