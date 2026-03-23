"""
App lifecycle bridge service — connects the Bridge API to the app manager.
"""

import asyncio
import logging
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "../../app-manager"))

from event_bus import EventBus
from app_manager import AppManager

logger = logging.getLogger("bridge.apps")


class AppsBridgeService:
    """Bridge service for app lifecycle management."""

    def __init__(self, event_bus: EventBus):
        self.event_bus = event_bus
        self.manager = AppManager(event_bus)

    async def handle_list_running(self, body: dict) -> list:
        """List running apps."""
        return self.manager.list_running()

    async def handle_list_installed(self, body: dict) -> list:
        """List installed apps."""
        return self.manager.list_installed()

    async def handle_app_info(self, body: dict) -> dict:
        """Get detailed app info."""
        app_id = body.get("app_id")
        if not app_id:
            raise ValueError("Missing required field: app_id")
        return self.manager.get_app_info(app_id)

    async def handle_launch(self, body: dict) -> dict:
        """Launch an app."""
        app_id = body.get("app_id")
        if not app_id:
            raise ValueError("Missing required field: app_id")
        return await self.manager.launch(app_id)

    async def handle_kill(self, body: dict) -> dict:
        """Kill an app."""
        app_id = body.get("app_id")
        if not app_id:
            raise ValueError("Missing required field: app_id")
        return await self.manager.kill(app_id)

    async def handle_suspend(self, body: dict) -> dict:
        """Suspend an app."""
        app_id = body.get("app_id")
        if not app_id:
            raise ValueError("Missing required field: app_id")
        return await self.manager.suspend(app_id)

    async def handle_resume(self, body: dict) -> dict:
        """Resume a suspended app."""
        app_id = body.get("app_id")
        if not app_id:
            raise ValueError("Missing required field: app_id")
        return await self.manager.resume(app_id)

    async def handle_switch(self, body: dict) -> dict:
        """Switch to an app (bring to foreground)."""
        app_id = body.get("app_id")
        if not app_id:
            raise ValueError("Missing required field: app_id")
        return await self.manager.switch_to(app_id)
