"""
System Tool Manager

Provides system tools that Claude can invoke during conversations.
Each tool wraps a Bridge API call and formats the result for Claude.

These tools are registered with the ChatEngine so Claude can call them
via the tool_use API to perform real actions on the device.
"""

import asyncio
import logging
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "../../system/bridge"))

from client import BridgeClient

logger = logging.getLogger("tools")


class SystemToolManager:
    """
    Manages system tools that Claude can invoke.

    Each method corresponds to a tool that the chat engine registers
    with the Claude API. When Claude decides to use a tool, the
    chat engine calls the matching method here.
    """

    def __init__(self, bridge_url: str = "http://127.0.0.1:8080"):
        self.bridge = BridgeClient(bridge_url)
        self._monitoring = False

    async def initialize(self):
        """Initialize the tool manager and verify bridge connectivity."""
        try:
            health = self.bridge.health()
            logger.info("Bridge API connected: %s", health.get("status"))
        except ConnectionError:
            logger.warning("Bridge API not available — tools will fail "
                           "until bridge is running")

    async def start_monitoring(self):
        """Start background monitoring tasks."""
        self._monitoring = True
        while self._monitoring:
            await asyncio.sleep(30)

    # --- WiFi Tools ---

    async def wifi_scan(self) -> dict:
        """Scan for available WiFi networks."""
        networks = await asyncio.to_thread(self.bridge.wifi_scan)
        return {
            "networks": networks,
            "count": len(networks),
        }

    async def wifi_connect(self, ssid: str, password: str = None) -> dict:
        """Connect to a WiFi network."""
        result = await asyncio.to_thread(
            self.bridge.wifi_connect, ssid, password
        )
        return result

    async def wifi_disconnect(self) -> dict:
        """Disconnect from WiFi."""
        return await asyncio.to_thread(self.bridge.wifi_disconnect)

    async def wifi_status(self) -> dict:
        """Get current WiFi status."""
        return await asyncio.to_thread(self.bridge.wifi_status)

    # --- System Tools ---

    async def get_battery(self) -> dict:
        """Get battery level and charging state."""
        return await asyncio.to_thread(self.bridge.battery)

    async def set_brightness(self, level: int) -> dict:
        """Set screen brightness (0-100)."""
        return await asyncio.to_thread(self.bridge.set_brightness, level)

    async def set_volume(self, level: int) -> dict:
        """Set audio volume (0-100)."""
        return await asyncio.to_thread(self.bridge.set_volume, level)

    async def get_volume(self) -> dict:
        """Get current volume level."""
        return await asyncio.to_thread(self.bridge.volume)

    async def system_info(self) -> dict:
        """Get device system information."""
        return await asyncio.to_thread(self.bridge.system_info)

    # --- Power Tools (permission-gated) ---

    async def shutdown(self) -> dict:
        """Shut down the device."""
        return await asyncio.to_thread(self.bridge.shutdown)

    async def reboot(self) -> dict:
        """Reboot the device."""
        return await asyncio.to_thread(self.bridge.reboot)

    async def suspend(self) -> dict:
        """Suspend the device."""
        return await asyncio.to_thread(self.bridge.suspend)
