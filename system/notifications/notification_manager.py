"""
Claude-OS Notification Manager

Centralized notification system for the OS. Apps post notifications
here, and Claude can read, summarize, and act on them.

Features:
- Priority levels (low, normal, high, urgent)
- Notification grouping by app
- Persistent storage (survives reboots)
- Claude integration — Claude can read and dismiss notifications
- Action buttons — notifications can include actionable responses
- Do Not Disturb mode
"""

import asyncio
import json
import logging
import os
import time
import uuid
from dataclasses import dataclass, field
from enum import IntEnum
from pathlib import Path

logger = logging.getLogger("notifications")

NOTIFICATIONS_DIR = Path(
    os.environ.get("CLAUDE_OS_DATA", "/var/lib/claude-os")
) / "notifications"


class Priority(IntEnum):
    """Notification priority levels."""
    LOW = 0
    NORMAL = 1
    HIGH = 2
    URGENT = 3


@dataclass
class NotificationAction:
    """An actionable button on a notification."""
    action_id: str
    label: str
    callback_url: str = ""  # Bridge API endpoint to call


@dataclass
class Notification:
    """A single notification."""
    id: str
    app_id: str
    title: str
    body: str
    priority: Priority = Priority.NORMAL
    timestamp: float = field(default_factory=time.time)
    read: bool = False
    dismissed: bool = False
    group: str = ""
    icon: str = ""
    actions: list[NotificationAction] = field(default_factory=list)
    expires_at: float = 0  # 0 = never expires

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "app_id": self.app_id,
            "title": self.title,
            "body": self.body,
            "priority": self.priority.name.lower(),
            "timestamp": self.timestamp,
            "read": self.read,
            "dismissed": self.dismissed,
            "group": self.group,
            "icon": self.icon,
            "actions": [
                {"action_id": a.action_id, "label": a.label}
                for a in self.actions
            ],
        }

    @classmethod
    def from_dict(cls, data: dict) -> "Notification":
        priority_map = {
            "low": Priority.LOW, "normal": Priority.NORMAL,
            "high": Priority.HIGH, "urgent": Priority.URGENT,
        }
        return cls(
            id=data["id"],
            app_id=data["app_id"],
            title=data["title"],
            body=data["body"],
            priority=priority_map.get(data.get("priority", "normal"),
                                       Priority.NORMAL),
            timestamp=data.get("timestamp", time.time()),
            read=data.get("read", False),
            dismissed=data.get("dismissed", False),
            group=data.get("group", ""),
            icon=data.get("icon", ""),
            actions=[
                NotificationAction(
                    action_id=a["action_id"], label=a["label"],
                    callback_url=a.get("callback_url", ""),
                )
                for a in data.get("actions", [])
            ],
        )


class NotificationManager:
    """
    Central notification manager for Claude-OS.

    All apps post notifications through this manager. Claude has
    full access to read, summarize, and act on notifications.
    """

    MAX_NOTIFICATIONS = 200
    MAX_PER_APP = 50

    def __init__(self, event_bus=None):
        self.event_bus = event_bus
        self.notifications: list[Notification] = []
        self.do_not_disturb = False
        self._running = False

    async def start(self):
        """Start the notification manager."""
        self._running = True
        self._load()
        logger.info("Notification manager started (%d stored notifications)",
                     len(self.notifications))
        await self._cleanup_loop()

    # --- Post / Query ---

    async def post(self, app_id: str, title: str, body: str,
                   priority: str = "normal", group: str = "",
                   actions: list[dict] = None) -> dict:
        """
        Post a new notification.

        Args:
            app_id: Source app ID
            title: Notification title
            body: Notification body text
            priority: "low", "normal", "high", "urgent"
            group: Grouping key (e.g., "messages", "downloads")
            actions: Optional action buttons

        Returns:
            The created notification as a dict
        """
        priority_map = {
            "low": Priority.LOW, "normal": Priority.NORMAL,
            "high": Priority.HIGH, "urgent": Priority.URGENT,
        }

        notif = Notification(
            id=str(uuid.uuid4())[:8],
            app_id=app_id,
            title=title,
            body=body,
            priority=priority_map.get(priority, Priority.NORMAL),
            group=group,
            actions=[
                NotificationAction(
                    action_id=a.get("action_id", ""),
                    label=a.get("label", ""),
                    callback_url=a.get("callback_url", ""),
                )
                for a in (actions or [])
            ],
        )

        self.notifications.insert(0, notif)
        self._enforce_limits(app_id)
        self._save()

        logger.info("Notification posted: [%s] %s: %s",
                     app_id, title, body[:60])

        # Emit event (unless DND for low/normal priority)
        if not self.do_not_disturb or notif.priority >= Priority.HIGH:
            if self.event_bus:
                await self.event_bus.emit("notification.new", notif.to_dict())

        return notif.to_dict()

    def get_all(self, include_dismissed: bool = False) -> list[dict]:
        """Get all notifications."""
        results = self.notifications
        if not include_dismissed:
            results = [n for n in results if not n.dismissed]
        return [n.to_dict() for n in results]

    def get_unread(self) -> list[dict]:
        """Get unread notifications."""
        return [
            n.to_dict() for n in self.notifications
            if not n.read and not n.dismissed
        ]

    def get_by_app(self, app_id: str) -> list[dict]:
        """Get notifications from a specific app."""
        return [
            n.to_dict() for n in self.notifications
            if n.app_id == app_id and not n.dismissed
        ]

    def get_summary(self) -> dict:
        """
        Get a summary of notifications — designed for Claude to read.

        Returns a structured summary that Claude can use to inform
        the user about what they've missed.
        """
        active = [n for n in self.notifications if not n.dismissed]
        unread = [n for n in active if not n.read]

        # Group by app
        by_app = {}
        for n in unread:
            if n.app_id not in by_app:
                by_app[n.app_id] = []
            by_app[n.app_id].append(n)

        # Group by priority
        urgent = [n for n in unread if n.priority >= Priority.URGENT]
        high = [n for n in unread if n.priority == Priority.HIGH]

        return {
            "total_active": len(active),
            "total_unread": len(unread),
            "urgent_count": len(urgent),
            "high_count": len(high),
            "by_app": {
                app_id: {
                    "count": len(notifs),
                    "latest": notifs[0].to_dict(),
                }
                for app_id, notifs in by_app.items()
            },
            "urgent": [n.to_dict() for n in urgent],
        }

    # --- Actions ---

    async def mark_read(self, notification_id: str) -> dict:
        """Mark a notification as read."""
        notif = self._find(notification_id)
        notif.read = True
        self._save()
        return {"marked_read": notification_id}

    async def dismiss(self, notification_id: str) -> dict:
        """Dismiss a notification."""
        notif = self._find(notification_id)
        notif.dismissed = True
        self._save()

        if self.event_bus:
            await self.event_bus.emit("notification.dismissed", {
                "id": notification_id,
            })

        return {"dismissed": notification_id}

    async def dismiss_all(self, app_id: str = None) -> dict:
        """Dismiss all notifications, optionally filtered by app."""
        count = 0
        for n in self.notifications:
            if not n.dismissed:
                if app_id is None or n.app_id == app_id:
                    n.dismissed = True
                    count += 1
        self._save()
        return {"dismissed_count": count}

    async def mark_all_read(self) -> dict:
        """Mark all notifications as read."""
        count = 0
        for n in self.notifications:
            if not n.read:
                n.read = True
                count += 1
        self._save()
        return {"marked_read_count": count}

    def set_dnd(self, enabled: bool) -> dict:
        """Toggle Do Not Disturb mode."""
        self.do_not_disturb = enabled
        logger.info("Do Not Disturb: %s", "ON" if enabled else "OFF")
        return {"do_not_disturb": enabled}

    # --- Internal ---

    def _find(self, notification_id: str) -> Notification:
        """Find a notification by ID."""
        for n in self.notifications:
            if n.id == notification_id:
                return n
        raise ValueError(f"Notification not found: {notification_id}")

    def _enforce_limits(self, app_id: str):
        """Enforce max notification limits."""
        # Per-app limit
        app_notifs = [n for n in self.notifications if n.app_id == app_id]
        if len(app_notifs) > self.MAX_PER_APP:
            # Remove oldest from this app
            excess = app_notifs[self.MAX_PER_APP:]
            for n in excess:
                self.notifications.remove(n)

        # Global limit
        if len(self.notifications) > self.MAX_NOTIFICATIONS:
            self.notifications = self.notifications[:self.MAX_NOTIFICATIONS]

    def _save(self):
        """Persist notifications to disk."""
        try:
            NOTIFICATIONS_DIR.mkdir(parents=True, exist_ok=True)
            path = NOTIFICATIONS_DIR / "notifications.json"
            data = [n.to_dict() for n in self.notifications]
            path.write_text(json.dumps(data, indent=2))
        except OSError as e:
            logger.error("Failed to save notifications: %s", e)

    def _load(self):
        """Load notifications from disk."""
        path = NOTIFICATIONS_DIR / "notifications.json"
        if path.exists():
            try:
                data = json.loads(path.read_text())
                self.notifications = [
                    Notification.from_dict(d) for d in data
                ]
            except (json.JSONDecodeError, KeyError) as e:
                logger.error("Failed to load notifications: %s", e)

    async def _cleanup_loop(self):
        """Periodically clean up expired and old notifications."""
        while self._running:
            now = time.time()

            # Remove expired notifications
            self.notifications = [
                n for n in self.notifications
                if n.expires_at == 0 or n.expires_at > now
            ]

            # Remove dismissed notifications older than 24 hours
            cutoff = now - 86400
            self.notifications = [
                n for n in self.notifications
                if not n.dismissed or n.timestamp > cutoff
            ]

            self._save()
            await asyncio.sleep(300)  # Every 5 minutes

    async def stop(self):
        """Stop the notification manager."""
        self._running = False
        self._save()
        logger.info("Notification manager stopped")


def main():
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    )
    manager = NotificationManager()
    asyncio.run(manager.start())


if __name__ == "__main__":
    main()
