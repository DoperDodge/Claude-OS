"""
Claude-OS Bridge Client SDK

Python client for the Claude app (or any service) to interact with
the Bridge API. Provides both sync and async interfaces.

Usage:
    from client import BridgeClient

    client = BridgeClient()

    # Scan for WiFi networks
    networks = client.wifi_scan()

    # Connect to a network
    client.wifi_connect("MyNetwork", "password123")

    # Get system info
    info = client.system_info()

    # Listen for real-time events
    async for event in client.events():
        print(event)
"""

import asyncio
import json
import logging
from typing import AsyncIterator
from urllib.request import urlopen, Request
from urllib.error import URLError

logger = logging.getLogger("bridge.client")

DEFAULT_BASE_URL = "http://127.0.0.1:8080"


class BridgeClient:
    """Synchronous client for the Bridge API."""

    def __init__(self, base_url: str = DEFAULT_BASE_URL):
        self.base_url = base_url.rstrip("/")

    def _get(self, path: str) -> dict:
        """Send a GET request."""
        url = f"{self.base_url}{path}"
        try:
            req = Request(url, headers={"Accept": "application/json"})
            with urlopen(req, timeout=30) as resp:
                data = json.loads(resp.read().decode())
                return data.get("data", data)
        except URLError as e:
            logger.error("GET %s failed: %s", path, e)
            raise ConnectionError(f"Bridge API unavailable: {e}")

    def _post(self, path: str, body: dict = None) -> dict:
        """Send a POST request."""
        url = f"{self.base_url}{path}"
        payload = json.dumps(body or {}).encode()
        try:
            req = Request(
                url, data=payload, method="POST",
                headers={
                    "Content-Type": "application/json",
                    "Accept": "application/json",
                },
            )
            with urlopen(req, timeout=30) as resp:
                data = json.loads(resp.read().decode())
                return data.get("data", data)
        except URLError as e:
            logger.error("POST %s failed: %s", path, e)
            raise ConnectionError(f"Bridge API unavailable: {e}")

    # --- WiFi ---

    def wifi_scan(self) -> list[dict]:
        """Scan for available WiFi networks."""
        return self._get("/api/wifi/scan")

    def wifi_connect(self, ssid: str, password: str = None,
                     security: str = "wpa2") -> dict:
        """Connect to a WiFi network."""
        return self._post("/api/wifi/connect", {
            "ssid": ssid,
            "password": password or "",
            "security": security,
        })

    def wifi_disconnect(self) -> dict:
        """Disconnect from current network."""
        return self._post("/api/wifi/disconnect")

    def wifi_status(self) -> dict:
        """Get WiFi connection status."""
        return self._get("/api/wifi/status")

    def wifi_saved(self) -> list[dict]:
        """List saved WiFi networks."""
        return self._get("/api/wifi/saved")

    def wifi_forget(self, ssid: str) -> dict:
        """Forget a saved network."""
        return self._post("/api/wifi/forget", {"ssid": ssid})

    # --- System ---

    def system_info(self) -> dict:
        """Get system information."""
        return self._get("/api/system/info")

    def battery(self) -> dict:
        """Get battery status."""
        return self._get("/api/system/battery")

    def set_brightness(self, level: int) -> dict:
        """Set screen brightness (0-100)."""
        return self._post("/api/system/brightness", {"level": level})

    # --- Power ---

    def shutdown(self, delay_seconds: int = 0) -> dict:
        """Shut down the device."""
        return self._post("/api/power/shutdown",
                          {"delay_seconds": delay_seconds})

    def reboot(self) -> dict:
        """Reboot the device."""
        return self._post("/api/power/reboot")

    def suspend(self) -> dict:
        """Suspend the device."""
        return self._post("/api/power/suspend")

    # --- Audio ---

    def volume(self) -> dict:
        """Get current volume level."""
        return self._get("/api/audio/volume")

    def set_volume(self, level: int) -> dict:
        """Set volume (0-100)."""
        return self._post("/api/audio/volume", {"level": level})

    def mute(self, mute: bool = None) -> dict:
        """Mute, unmute, or toggle mute."""
        return self._post("/api/audio/mute", {"mute": mute})

    # --- Health ---

    def health(self) -> dict:
        """Check if the Bridge API is running."""
        return self._get("/api/health")

    def permissions(self) -> dict:
        """List all permissions."""
        return self._get("/api/permissions")


class AsyncBridgeClient:
    """Async client with WebSocket event streaming support."""

    def __init__(self, base_url: str = DEFAULT_BASE_URL):
        self.base_url = base_url.rstrip("/")
        self._sync = BridgeClient(base_url)

    async def events(self) -> AsyncIterator[dict]:
        """
        Stream real-time events from the Bridge API via WebSocket.

        Yields dicts with 'event' and 'data' keys.
        """
        try:
            import aiohttp

            ws_url = self.base_url.replace("http", "ws") + "/api/events"
            async with aiohttp.ClientSession() as session:
                async with session.ws_connect(ws_url) as ws:
                    logger.info("Connected to event stream")
                    async for msg in ws:
                        if msg.type == aiohttp.WSMsgType.TEXT:
                            yield json.loads(msg.data)
                        elif msg.type == aiohttp.WSMsgType.ERROR:
                            break
        except ImportError:
            raise RuntimeError("aiohttp required for event streaming")

    # Wrap sync methods as async for convenience
    async def wifi_scan(self) -> list[dict]:
        return await asyncio.to_thread(self._sync.wifi_scan)

    async def wifi_connect(self, ssid: str, password: str = None,
                           security: str = "wpa2") -> dict:
        return await asyncio.to_thread(
            self._sync.wifi_connect, ssid, password, security
        )

    async def wifi_status(self) -> dict:
        return await asyncio.to_thread(self._sync.wifi_status)

    async def system_info(self) -> dict:
        return await asyncio.to_thread(self._sync.system_info)

    async def battery(self) -> dict:
        return await asyncio.to_thread(self._sync.battery)
