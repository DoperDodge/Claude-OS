"""
WiFi bridge service — connects the Bridge API to the WiFi manager daemon.

Communicates with the WiFi manager over its Unix socket IPC.
"""

import asyncio
import json
import logging
import socket

from event_bus import EventBus

logger = logging.getLogger("bridge.wifi")

WIFI_SOCK = "/run/claude-os/wifi.sock"


class WiFiBridgeService:
    """Bridge service that proxies WiFi operations to the WiFi manager daemon."""

    def __init__(self, event_bus: EventBus):
        self.event_bus = event_bus
        self._last_status = {}

        # Start background status poller
        asyncio.ensure_future(self._poll_status())

    async def handle_scan(self, body: dict) -> list[dict]:
        """Scan for available WiFi networks."""
        result = await self._send_to_daemon("scan")
        return result.get("result", [])

    async def handle_connect(self, body: dict) -> dict:
        """Connect to a WiFi network."""
        ssid = body.get("ssid")
        password = body.get("password", "")
        security = body.get("security", "wpa2")

        if not ssid:
            raise ValueError("Missing required field: ssid")

        result = await self._send_to_daemon("connect", {
            "ssid": ssid,
            "password": password,
            "security": security,
        })

        success = result.get("result", False)
        if success:
            await self.event_bus.emit("wifi.connected", {"ssid": ssid})
        else:
            await self.event_bus.emit("wifi.connect_failed", {"ssid": ssid})

        return {"connected": success, "ssid": ssid}

    async def handle_disconnect(self, body: dict) -> dict:
        """Disconnect from current network."""
        result = await self._send_to_daemon("disconnect")
        await self.event_bus.emit("wifi.disconnected", {})
        return {"disconnected": result.get("result", False)}

    async def handle_status(self, body: dict) -> dict:
        """Get current WiFi status."""
        result = await self._send_to_daemon("status")
        return result.get("result", {"connected": False})

    async def handle_saved(self, body: dict) -> list[dict]:
        """List saved networks."""
        result = await self._send_to_daemon("saved_networks")
        return result.get("result", [])

    async def handle_forget(self, body: dict) -> dict:
        """Forget a saved network."""
        ssid = body.get("ssid")
        if not ssid:
            raise ValueError("Missing required field: ssid")

        result = await self._send_to_daemon("forget", {"ssid": ssid})
        return {"forgotten": result.get("result", False), "ssid": ssid}

    async def _send_to_daemon(self, method: str, params: dict = None) -> dict:
        """Send a request to the WiFi manager daemon via Unix socket."""
        request = json.dumps({"method": method, "params": params or {}})

        try:
            reader, writer = await asyncio.open_unix_connection(WIFI_SOCK)
            writer.write(request.encode())
            await writer.drain()

            response = await reader.read(65536)
            writer.close()
            await writer.wait_closed()

            return json.loads(response.decode())
        except FileNotFoundError:
            logger.error("WiFi manager not running (socket not found)")
            return {"error": "WiFi manager not running"}
        except ConnectionRefusedError:
            logger.error("WiFi manager refused connection")
            return {"error": "WiFi manager unavailable"}
        except Exception as e:
            logger.error("WiFi daemon communication error: %s", e)
            return {"error": str(e)}

    async def _poll_status(self):
        """Periodically check WiFi status and emit events on changes."""
        await asyncio.sleep(5)  # Initial delay

        while True:
            try:
                status = await self._send_to_daemon("status")
                current = status.get("result", {})

                # Detect connection state changes
                was_connected = self._last_status.get("connected", False)
                is_connected = current.get("connected", False)

                if is_connected and not was_connected:
                    await self.event_bus.emit("wifi.connected", current)
                elif not is_connected and was_connected:
                    await self.event_bus.emit("wifi.disconnected", {})

                self._last_status = current
            except Exception:
                pass

            await asyncio.sleep(10)
