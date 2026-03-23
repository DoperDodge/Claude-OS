"""
Claude-OS Bridge API Server

The central API that connects the Claude app to all OS services.
Runs as an HTTP/WebSocket server on localhost:8080.

Architecture:
    Claude App  <-->  Bridge API  <-->  System Services
                      (this file)       (WiFi, Power, Audio, etc.)

The bridge enforces permissions — Claude must request user approval
for sensitive actions like toggling airplane mode or reading messages.
"""

import asyncio
import json
import logging
import signal
import sys
from pathlib import Path

from http_server import HTTPServer
from permissions import PermissionManager
from services.wifi import WiFiBridgeService
from services.system import SystemBridgeService
from services.power import PowerBridgeService
from services.audio import AudioBridgeService
from event_bus import EventBus

LOG_FORMAT = "%(asctime)s [%(levelname)s] %(name)s: %(message)s"
CONFIG_DIR = Path(os.environ.get("CLAUDE_OS_CONFIG", "/etc/claude-os"))

import os

logger = logging.getLogger("bridge")


class BridgeServer:
    """Main bridge API server coordinating all service modules."""

    def __init__(self, host: str = "127.0.0.1", port: int = 8080):
        self.host = host
        self.port = port

        # Core components
        self.event_bus = EventBus()
        self.permissions = PermissionManager(CONFIG_DIR / "permissions.json")

        # Service modules
        self.wifi = WiFiBridgeService(self.event_bus)
        self.system = SystemBridgeService(self.event_bus)
        self.power = PowerBridgeService(self.event_bus)
        self.audio = AudioBridgeService(self.event_bus)

        # HTTP server with all routes
        self.http = HTTPServer(self)

    async def start(self):
        """Start the bridge API server."""
        logger.info("Starting Claude-OS Bridge API on %s:%d", self.host, self.port)

        self.permissions.load()

        # Register all service routes
        self.http.register_routes()

        # Start the HTTP/WebSocket server
        await self.http.start(self.host, self.port)

        logger.info("Bridge API is ready")

    async def shutdown(self):
        """Gracefully shut down."""
        logger.info("Bridge API shutting down")
        await self.http.stop()
        await self.event_bus.shutdown()


def main():
    logging.basicConfig(level=logging.INFO, format=LOG_FORMAT)

    host = os.environ.get("BRIDGE_HOST", "127.0.0.1")
    port = int(os.environ.get("BRIDGE_PORT", "8080"))

    server = BridgeServer(host=host, port=port)
    loop = asyncio.new_event_loop()

    def handle_signal(sig):
        logger.info("Received signal %s", sig)
        loop.create_task(server.shutdown())
        loop.stop()

    for sig in (signal.SIGTERM, signal.SIGINT):
        loop.add_signal_handler(sig, handle_signal, sig)

    try:
        loop.run_until_complete(server.start())
    except KeyboardInterrupt:
        loop.run_until_complete(server.shutdown())
    finally:
        loop.close()


if __name__ == "__main__":
    main()
