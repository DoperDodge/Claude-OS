"""
Event bus for real-time communication between bridge services.

Services emit events (e.g., "wifi.connected", "battery.low") which are
forwarded to WebSocket clients (the Claude app) and other subscribers.
"""

import asyncio
import logging
from typing import Callable

logger = logging.getLogger("bridge.events")

# Type alias for event handlers
EventHandler = Callable[[str, dict], asyncio.coroutine]


class EventBus:
    """Publish-subscribe event bus for inter-service communication."""

    def __init__(self):
        self._subscribers: dict[str, list[EventHandler]] = {}
        self._wildcard_subscribers: list[EventHandler] = []

    def subscribe(self, event_type: str, handler: EventHandler):
        """Subscribe to events of a specific type, or '*' for all events."""
        if event_type == "*":
            self._wildcard_subscribers.append(handler)
        else:
            if event_type not in self._subscribers:
                self._subscribers[event_type] = []
            self._subscribers[event_type].append(handler)

    def unsubscribe(self, event_type: str, handler: EventHandler):
        """Remove a subscription."""
        if event_type == "*":
            if handler in self._wildcard_subscribers:
                self._wildcard_subscribers.remove(handler)
        elif event_type in self._subscribers:
            if handler in self._subscribers[event_type]:
                self._subscribers[event_type].remove(handler)

    async def emit(self, event_type: str, data: dict = None):
        """
        Emit an event to all subscribers.

        Args:
            event_type: Dot-separated event name (e.g., "wifi.connected")
            data: Event payload
        """
        data = data or {}
        logger.debug("Event: %s %s", event_type, data)

        handlers = list(self._wildcard_subscribers)
        if event_type in self._subscribers:
            handlers.extend(self._subscribers[event_type])

        for handler in handlers:
            try:
                await handler(event_type, data)
            except Exception as e:
                logger.error("Event handler error for '%s': %s", event_type, e)

    async def shutdown(self):
        """Clear all subscriptions."""
        self._subscribers.clear()
        self._wildcard_subscribers.clear()
