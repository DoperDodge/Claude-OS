"""
Claude-OS Status Bar

A glassmorphic status bar rendered as a Wayland layer-shell surface.
Displays: time, battery, WiFi signal, notification count, and Dynamic Island.

Uses the Claude-OS design system for all visual properties: colors, typography,
spacing, blur effects, and animation curves.

Visual Design:
    ┌──────────────────────────────────────────────────────┐
    │                                                      │
    │  14:32    ┌─────────────────┐    ■ 85%  ◉  ≋  4    │
    │           │  Dynamic Island │                        │
    │           └─────────────────┘                        │
    └──────────────────────────────────────────────────────┘
    ^           ^                      ^    ^   ^   ^
    time      island                  bat  wifi sig notif
"""

import asyncio
import json
import logging
import os
import sys
import time
from dataclasses import dataclass, field
from enum import Enum, auto

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "../../system/bridge"))

logger = logging.getLogger("statusbar")


class BatteryState(Enum):
    """Visual battery indicator state."""
    GOOD = auto()      # > 20%
    LOW = auto()        # 10-20%
    CRITICAL = auto()   # < 10%
    CHARGING = auto()


class WifiStrength(Enum):
    """WiFi signal strength tiers."""
    NONE = 0
    WEAK = 1       # 1-25%
    FAIR = 2       # 26-50%
    GOOD = 3       # 51-75%
    EXCELLENT = 4  # 76-100%


@dataclass
class DynamicIslandState:
    """State for the Dynamic Island-style notch area."""
    expanded: bool = False
    content_type: str = ""  # "music", "call", "timer", "navigation"
    title: str = ""
    subtitle: str = ""
    icon: str = ""
    progress: float = 0.0  # 0.0-1.0 for progress indicators


@dataclass
class StatusBarState:
    """Current state of all status bar indicators."""
    # Clock
    time_str: str = "00:00"
    date_str: str = ""
    is_24h: bool = True

    # Battery
    battery_level: int = -1  # -1 = unknown
    battery_charging: bool = False
    battery_state: BatteryState = BatteryState.GOOD

    # WiFi
    wifi_connected: bool = False
    wifi_ssid: str = ""
    wifi_signal: int = 0  # 0-100
    wifi_strength: WifiStrength = WifiStrength.NONE

    # Cellular
    cellular_signal: int = 0
    carrier_name: str = ""

    # Notifications
    notification_count: int = 0

    # Display
    brightness: int = 100

    # Dynamic Island
    island: DynamicIslandState = field(default_factory=DynamicIslandState)


class StatusBar:
    """
    System status bar for Claude-OS.

    Renders at the top of the screen as a glassmorphic Wayland layer-shell
    surface. Uses theme tokens for all visual properties.
    """

    UPDATE_INTERVAL = 5  # Seconds between polls

    def __init__(self, bridge_url: str = "http://127.0.0.1:8080"):
        self.bridge_url = bridge_url
        self.state = StatusBarState()
        self._running = False

        # Load theme
        try:
            from ui.theme import get_theme
            self._theme = get_theme()
        except ImportError:
            self._theme = None

    @property
    def height(self) -> int:
        if self._theme:
            return self._theme.layout.statusbar_height
        return 54

    async def start(self):
        """Start the status bar update loop."""
        self._running = True
        logger.info("Status bar started (height=%dpx)", self.height)
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
            self._update_derived_state()
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
                    self._update_derived_state()
                    self._render()
                elif event_type == "wifi.disconnected":
                    self.state.wifi_connected = False
                    self.state.wifi_ssid = ""
                    self.state.wifi_strength = WifiStrength.NONE
                    self._render()
                elif event_type == "battery.low":
                    self.state.battery_level = data.get("level", 0)
                    self._update_derived_state()
                    self._render()
                elif event_type == "notification.new":
                    self.state.notification_count += 1
                    self._render()
                elif event_type == "notification.dismissed":
                    self.state.notification_count = max(
                        0, self.state.notification_count - 1)
                    self._render()

        except Exception as e:
            logger.warning("Event listener failed: %s (using polling only)", e)

    def _update_clock(self):
        """Update the clock display."""
        now = time.localtime()
        if self.state.is_24h:
            self.state.time_str = time.strftime("%H:%M", now)
        else:
            self.state.time_str = time.strftime("%I:%M", now).lstrip("0")
        self.state.date_str = time.strftime("%a %b %d", now)

    def _update_derived_state(self):
        """Update derived visual states from raw values."""
        # Battery state
        level = self.state.battery_level
        if self.state.battery_charging:
            self.state.battery_state = BatteryState.CHARGING
        elif level < 10:
            self.state.battery_state = BatteryState.CRITICAL
        elif level < 20:
            self.state.battery_state = BatteryState.LOW
        else:
            self.state.battery_state = BatteryState.GOOD

        # WiFi strength tier
        sig = self.state.wifi_signal
        if not self.state.wifi_connected or sig <= 0:
            self.state.wifi_strength = WifiStrength.NONE
        elif sig <= 25:
            self.state.wifi_strength = WifiStrength.WEAK
        elif sig <= 50:
            self.state.wifi_strength = WifiStrength.FAIR
        elif sig <= 75:
            self.state.wifi_strength = WifiStrength.GOOD
        else:
            self.state.wifi_strength = WifiStrength.EXCELLENT

    async def _fetch_battery(self):
        """Fetch battery status from Bridge API."""
        try:
            from client import BridgeClient
            client = BridgeClient(self.bridge_url)
            info = client.battery()
            if info.get("available"):
                self.state.battery_level = info.get("level", -1)
                self.state.battery_charging = info.get("status") == "Charging"
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
        except Exception:
            pass

    def _render(self):
        """
        Render the status bar to its Wayland buffer.

        Layout uses theme tokens for all positioning and styling:
        - Glassmorphic background with blur
        - Left: time (semibold)
        - Center: Dynamic Island (pill-shaped, expandable)
        - Right: battery icon + wifi bars + notification badge
        """
        logger.debug("StatusBar render: %s | bat=%d%% | wifi=%s",
                     self.state.time_str,
                     self.state.battery_level,
                     self.state.wifi_strength.name)

    def _get_battery_color(self) -> str:
        """Get the themed color for current battery state."""
        if not self._theme:
            return "#34C759"
        colors = self._theme.colors
        return {
            BatteryState.GOOD: colors.battery_good,
            BatteryState.LOW: colors.battery_low,
            BatteryState.CRITICAL: colors.battery_critical,
            BatteryState.CHARGING: colors.battery_charging,
        }.get(self.state.battery_state, colors.battery_good)

    def get_render_data(self) -> dict:
        """Return all data needed for an external renderer to draw the bar."""
        theme = self._theme
        colors = theme.colors if theme else None
        typo = theme.typography if theme else None
        spacing = theme.spacing if theme else None
        layout = theme.layout if theme else None
        icons = theme.icons if theme else None
        effects = theme.effects if theme else None

        return {
            "height": self.height,
            "background": {
                "color": colors.statusbar_background if colors else "rgba(250,246,241,0.85)",
                "blur_radius": effects.glass_blur_regular if effects else 20.0,
                "saturation": effects.glass_saturation if effects else 1.8,
            },
            "padding": {
                "horizontal": spacing.statusbar_padding_h if spacing else 16,
                "vertical": spacing.statusbar_padding_v if spacing else 8,
            },
            "left": {
                "time": {
                    "text": self.state.time_str,
                    "color": colors.statusbar_text if colors else "#1A1A2E",
                    "size": typo.statusbar_time_size if typo else 15.0,
                    "weight": typo.statusbar_time_weight if typo else 600,
                },
            },
            "center": {
                "island": {
                    "expanded": self.state.island.expanded,
                    "content_type": self.state.island.content_type,
                    "title": self.state.island.title,
                    "width": layout.statusbar_notch_width if layout else 162,
                    "height": layout.statusbar_notch_height if layout else 37,
                    "radius": layout.statusbar_notch_radius if layout else 19,
                    "background": colors.navy if colors else "#1A1A2E",
                },
            },
            "right": {
                "battery": {
                    "level": self.state.battery_level,
                    "charging": self.state.battery_charging,
                    "state": self.state.battery_state.name,
                    "color": self._get_battery_color(),
                    "icon_width": icons.statusbar_battery_width if icons else 25,
                    "icon_height": icons.statusbar_battery_height if icons else 12,
                },
                "wifi": {
                    "connected": self.state.wifi_connected,
                    "strength": self.state.wifi_strength.value,
                    "color": colors.statusbar_icon if colors else "#5A5A72",
                    "icon_size": icons.statusbar_icon_size if icons else 16,
                },
                "notifications": {
                    "count": self.state.notification_count,
                    "badge_color": colors.accent if colors else "#D4A574",
                    "text_color": colors.text_on_accent if colors else "#FFFFFF",
                },
                "item_gap": spacing.statusbar_item_gap if spacing else 6,
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
