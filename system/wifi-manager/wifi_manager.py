"""
Claude-OS WiFi Manager Daemon

Core daemon that manages WiFi connectivity. Wraps wpa_supplicant and exposes
a D-Bus API for other system services (and the Claude bridge) to use.

Architecture:
    wifi_manager.py (this file) — daemon entry point, orchestrates components
    scanner.py      — network scanning
    connection.py   — connect/disconnect/monitor
    storage.py      — saved network credential storage
    dbus_service.py — D-Bus IPC interface
"""

import asyncio
import logging
import signal
import sys
import os

from pathlib import Path
from scanner import WiFiScanner
from connection import ConnectionManager
from storage import NetworkStorage
from dbus_service import WiFiDBusService

LOG_FORMAT = "%(asctime)s [%(levelname)s] %(name)s: %(message)s"
CONFIG_DIR = Path(os.environ.get("CLAUDE_OS_CONFIG", "/etc/claude-os"))
DATA_DIR = Path(os.environ.get("CLAUDE_OS_DATA", "/var/lib/claude-os/wifi"))

logger = logging.getLogger("wifi-manager")


class WiFiManager:
    """Main WiFi manager daemon coordinating all WiFi operations."""

    def __init__(self, interface: str = "wlan0"):
        self.interface = interface
        self.running = False

        # Ensure data directories exist
        DATA_DIR.mkdir(parents=True, exist_ok=True)
        CONFIG_DIR.mkdir(parents=True, exist_ok=True)

        # Initialize components
        self.storage = NetworkStorage(DATA_DIR / "networks.json")
        self.scanner = WiFiScanner(interface)
        self.connection = ConnectionManager(interface, self.storage)
        self.dbus_service = WiFiDBusService(self)

    async def start(self):
        """Start the WiFi manager daemon."""
        self.running = True
        logger.info("Starting Claude-OS WiFi Manager on %s", self.interface)

        # Load saved networks
        self.storage.load()
        logger.info("Loaded %d saved networks", len(self.storage.networks))

        # Start the D-Bus service
        await self.dbus_service.start()

        # Start connection monitor (auto-reconnect)
        monitor_task = asyncio.create_task(self.connection.monitor_loop())

        # Try to connect to a known network on startup
        asyncio.create_task(self._auto_connect_on_start())

        logger.info("WiFi Manager is ready")

        try:
            await monitor_task
        except asyncio.CancelledError:
            logger.info("WiFi Manager shutting down")

    async def _auto_connect_on_start(self):
        """Attempt to connect to a known network on daemon startup."""
        await asyncio.sleep(2)  # Let wpa_supplicant initialize

        if self.connection.is_connected():
            logger.info("Already connected to a network")
            return

        networks = await self.scanner.scan()
        for net in networks:
            saved = self.storage.get_network(net["ssid"])
            if saved:
                logger.info("Found known network '%s', connecting...", net["ssid"])
                success = await self.connection.connect(
                    net["ssid"], saved.get("password"), saved.get("security")
                )
                if success:
                    return

        logger.info("No known networks found nearby")

    async def scan(self) -> list[dict]:
        """Scan for available WiFi networks."""
        return await self.scanner.scan()

    async def connect(self, ssid: str, password: str = None,
                      security: str = "wpa2") -> bool:
        """Connect to a WiFi network and optionally save it."""
        success = await self.connection.connect(ssid, password, security)
        if success and password:
            self.storage.save_network(ssid, password, security)
        return success

    async def disconnect(self) -> bool:
        """Disconnect from the current network."""
        return await self.connection.disconnect()

    def forget_network(self, ssid: str) -> bool:
        """Remove a saved network."""
        return self.storage.remove_network(ssid)

    def get_status(self) -> dict:
        """Get current WiFi connection status."""
        return self.connection.get_status()

    def get_saved_networks(self) -> list[dict]:
        """List all saved networks."""
        return self.storage.list_networks()

    async def shutdown(self):
        """Gracefully shut down the daemon."""
        self.running = False
        await self.connection.disconnect()
        self.storage.save()
        logger.info("WiFi Manager stopped")


def main():
    logging.basicConfig(level=logging.INFO, format=LOG_FORMAT)

    interface = sys.argv[1] if len(sys.argv) > 1 else "wlan0"
    manager = WiFiManager(interface=interface)

    loop = asyncio.new_event_loop()

    def handle_signal(sig):
        logger.info("Received signal %s", sig)
        loop.create_task(manager.shutdown())
        loop.stop()

    for sig in (signal.SIGTERM, signal.SIGINT):
        loop.add_signal_handler(sig, handle_signal, sig)

    try:
        loop.run_until_complete(manager.start())
    except KeyboardInterrupt:
        loop.run_until_complete(manager.shutdown())
    finally:
        loop.close()


if __name__ == "__main__":
    main()
