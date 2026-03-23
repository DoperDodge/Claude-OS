"""
Notification bridge service — connects the Bridge API to the notification manager.
"""

import asyncio
import logging
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "../../notifications"))

from event_bus import EventBus
from notification_manager import NotificationManager

logger = logging.getLogger("bridge.notifications")


class NotificationBridgeService:
    """Bridge service for the notification system."""

    def __init__(self, event_bus: EventBus):
        self.event_bus = event_bus
        self.manager = NotificationManager(event_bus)

    async def handle_post(self, body: dict) -> dict:
        """Post a new notification."""
        app_id = body.get("app_id")
        title = body.get("title")
        msg_body = body.get("body", "")
        if not app_id or not title:
            raise ValueError("Missing required fields: app_id, title")
        return await self.manager.post(
            app_id=app_id,
            title=title,
            body=msg_body,
            priority=body.get("priority", "normal"),
            group=body.get("group", ""),
            actions=body.get("actions"),
        )

    async def handle_get_all(self, body: dict) -> list:
        """Get all notifications."""
        return self.manager.get_all()

    async def handle_get_unread(self, body: dict) -> list:
        """Get unread notifications."""
        return self.manager.get_unread()

    async def handle_summary(self, body: dict) -> dict:
        """Get notification summary (for Claude)."""
        return self.manager.get_summary()

    async def handle_mark_read(self, body: dict) -> dict:
        """Mark a notification as read."""
        notif_id = body.get("id")
        if not notif_id:
            raise ValueError("Missing required field: id")
        return await self.manager.mark_read(notif_id)

    async def handle_dismiss(self, body: dict) -> dict:
        """Dismiss a notification."""
        notif_id = body.get("id")
        if not notif_id:
            raise ValueError("Missing required field: id")
        return await self.manager.dismiss(notif_id)

    async def handle_dismiss_all(self, body: dict) -> dict:
        """Dismiss all notifications."""
        return await self.manager.dismiss_all(app_id=body.get("app_id"))

    async def handle_dnd(self, body: dict) -> dict:
        """Toggle Do Not Disturb mode."""
        enabled = body.get("enabled", True)
        return self.manager.set_dnd(enabled)
