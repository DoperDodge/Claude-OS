"""
Claude-OS Status Bar

A lightweight status bar rendered as a Wayland layer-shell surface.
Shows: clock, battery level, WiFi signal, and notification indicators.

Communicates with the Bridge API to get real-time system status.
"""

import asyncio
import json
import logging
import os
import sys
import time
from dataclasses import dataclass

# Add bridge client to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "../../system/bridge"))

logger = logging.getLogger("statusbar")


@dataclass
class StatusBarState:
    """Current state of all status bar indicators."""
    # Clock
    time_str: str = "00:00"
    date_str: str = ""

    # Battery
    battery_level: int = -1  # -1 = unknown
    battery_charging: bool = False

    # WiFi
    wifi_connected: bool = False
    wifi_ssid: str = ""
    wifi_signal: int = 0  # 0-100

    # Notifications
    notification_count: int = 0

    # Display
    brightness: int = 100


class StatusBar:
    """
    System status bar for Claude-OS.

    Renders at the top of the screen as a Wayland layer-shell surface.
    Polls the Bridge API and listens for events to stay up-to-date.
    """

    HEIGHT = 48  # Logical pixels
    UPDATE_INTERVAL = 5  # Seconds between polls

    def __init__(self, bridge_url: str = "http://127.0.0.1:8080"):
        self.bridge_url = bridge_url
        self.state = StatusBarState()
        self._running = False

    async def start(self):
        """Start the status bar update loop."""
        self._running = True
        logger.info("Status bar started")

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
                    self._render()
                elif event_type == "wifi.disconnected":
                    self.state.wifi_connected = False
                    self.state.wifi_ssid = ""
                    self._render()
                elif event_type == "battery.low":
                    self.state.battery_level = data.get("level", 0)
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
        Render the status bar.

        In production, this draws to a Wayland buffer using Cairo or similar.
        The layout is:

        ┌──────────────────────────────────────────┐
        │ 14:32        Claude-OS        🔋 85% 📶  │
        └──────────────────────────────────────────┘
        """
        # Build the status string (for logging / framebuffer rendering)
        left = self.state.time_str
        center = "Claude-OS"
        right_parts = []

        # Battery indicator
        if self.state.battery_level >= 0:
            charge_icon = "+" if self.state.battery_charging else ""
            right_parts.append(f"BAT:{self.state.battery_level}%{charge_icon}")

        # WiFi indicator
        if self.state.wifi_connected:
            right_parts.append(f"WiFi:{self.state.wifi_ssid}")
        else:
            right_parts.append("WiFi:OFF")

        right = " | ".join(right_parts)

        logger.debug("StatusBar: [%s]  %s  [%s]", left, center, right)

        # In production: draw to wl_buffer using Cairo
        # cairo_surface -> draw background -> draw text -> commit to Wayland

    def get_layout(self) -> dict:
        """Return the current status bar layout for external renderers."""
        return {
            "height": self.HEIGHT,
            "left": {
                "time": self.state.time_str,
            },
            "center": {
                "title": "Claude-OS",
            },
            "right": {
                "battery": {
                    "level": self.state.battery_level,
                    "charging": self.state.battery_charging,
                },
                "wifi": {
                    "connected": self.state.wifi_connected,
                    "ssid": self.state.wifi_ssid,
                    "signal": self.state.wifi_signal,
                },
                "notifications": self.state.notification_count,
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
