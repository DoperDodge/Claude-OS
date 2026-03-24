"""
Claude-OS Notification Panel

A frosted glass notification panel that slides down from the top of
the screen, revealing quick settings toggles and notification cards.

Design:
    ┌──────────────────────────────────┐
    │ ▓▓▓▓▓▓▓▓ Frosted Glass ▓▓▓▓▓▓▓ │
    │                                  │
    │  ┌──┐  ┌──┐  ┌──┐  ┌──┐  ┌──┐  │  ← Quick Settings tiles
    │  │Wi│  │BT│  │🔆│  │🔇│  │🔄│  │    (64×64, 16px radius)
    │  │Fi│  │  │  │  │  │  │  │  │  │
    │  └──┘  └──┘  └──┘  └──┘  └──┘  │
    │                                  │
    │  ─ Brightness ───────────○───── │  ← Brightness slider
    │                                  │
    │  ┌──────────────────────────┐   │
    │  │ Claude                    │   │  ← Notification card
    │  │ "Here's your summary..." │   │    (frosted glass, 16px radius)
    │  │                     2m   │   │
    │  └──────────────────────────┘   │
    │                                  │
    │  ┌──────────────────────────┐   │
    │  │ System                    │   │
    │  │ "Battery at 20%"         │   │
    │  │                    10m   │   │
    │  └──────────────────────────┘   │
    │                                  │
    │         ─────────                │  ← Dismiss handle
    └──────────────────────────────────┘

Animations:
    - Panel slides down with spring (smooth, gentle)
    - Quick settings tiles stagger-animate in (0.03s each)
    - Notification cards stagger from top (0.05s each)
    - Dismiss: spring-animate up
    - Swipe notification card right to dismiss (with spring)
    - Toggle tiles: scale bounce on tap
"""

import logging
import time
from dataclasses import dataclass, field
from enum import Enum, auto

logger = logging.getLogger("notifications")


# ---------------------------------------------------------------------------
# Quick Settings
# ---------------------------------------------------------------------------

class QuickSettingType(Enum):
    """Types of quick setting toggles."""
    WIFI = auto()
    BLUETOOTH = auto()
    BRIGHTNESS = auto()
    VOLUME = auto()
    DO_NOT_DISTURB = auto()
    AIRPLANE = auto()
    FLASHLIGHT = auto()
    DARK_MODE = auto()
    ROTATION_LOCK = auto()


@dataclass
class QuickSetting:
    """A quick setting toggle tile."""
    type: QuickSettingType
    label: str
    icon: str           # Icon name (resolved by renderer)
    enabled: bool = False
    value: int = 0      # For sliders (brightness, volume): 0-100


# Default quick settings layout
DEFAULT_QUICK_SETTINGS = [
    QuickSetting(QuickSettingType.WIFI, "Wi-Fi", "wifi", True),
    QuickSetting(QuickSettingType.BLUETOOTH, "Bluetooth", "bluetooth", False),
    QuickSetting(QuickSettingType.BRIGHTNESS, "Brightness", "brightness", True, 80),
    QuickSetting(QuickSettingType.VOLUME, "Volume", "volume", True, 60),
    QuickSetting(QuickSettingType.DO_NOT_DISTURB, "Focus", "moon", False),
    QuickSetting(QuickSettingType.DARK_MODE, "Dark Mode", "dark_mode", False),
    QuickSetting(QuickSettingType.AIRPLANE, "Airplane", "airplane", False),
    QuickSetting(QuickSettingType.FLASHLIGHT, "Flashlight", "flashlight", False),
]


# ---------------------------------------------------------------------------
# Notification Cards
# ---------------------------------------------------------------------------

class NotificationPriority(Enum):
    LOW = auto()
    DEFAULT = auto()
    HIGH = auto()
    URGENT = auto()


@dataclass
class Notification:
    """A notification in the panel."""
    id: str
    app_id: str
    app_name: str
    title: str
    body: str
    timestamp: float = field(default_factory=time.time)
    icon: str = ""
    priority: NotificationPriority = NotificationPriority.DEFAULT
    actions: list[dict] = field(default_factory=list)  # [{label, action_id}]
    group_key: str = ""
    read: bool = False
    dismiss_progress: float = 0.0  # For swipe-to-dismiss animation


# ---------------------------------------------------------------------------
# Notification Panel
# ---------------------------------------------------------------------------

class NotificationPanel:
    """
    Claude-OS notification panel.

    Renders as a fullscreen overlay with frosted glass background.
    Contains quick settings tiles at top, brightness/volume sliders,
    and scrollable notification cards below.

    Visual specs:
    - Background: frosted glass (20px blur, warm white tint 70%)
    - Quick settings: 64×64px tiles, 16px radius, accent color when enabled
    - Notification cards: white/elevated bg, 16px radius, subtle shadow
    - Staggered spring entrance for all elements
    - Swipe-right on card to dismiss with spring physics
    - Pull down further to reveal more quick settings
    """

    MAX_NOTIFICATIONS = 50

    def __init__(self):
        self.visible = False
        self.offset: float = 0.0  # 0=hidden, 1=fully open
        self.quick_settings: list[QuickSetting] = list(DEFAULT_QUICK_SETTINGS)
        self.notifications: list[Notification] = []
        self._on_toggle = None
        self._on_notification_tap = None
        self._on_notification_dismiss = None

    def set_handlers(self, on_toggle=None, on_notification_tap=None,
                     on_notification_dismiss=None):
        """Set event callbacks."""
        self._on_toggle = on_toggle
        self._on_notification_tap = on_notification_tap
        self._on_notification_dismiss = on_notification_dismiss

    # --- Panel Control ---

    def show(self):
        """Show the notification panel (animated by compositor)."""
        self.visible = True
        self.offset = 1.0
        logger.info("Notification panel shown")

    def hide(self):
        """Hide the notification panel."""
        self.visible = False
        self.offset = 0.0
        logger.info("Notification panel hidden")

    def set_offset(self, offset: float):
        """Set panel offset for interactive drag (0-1)."""
        self.offset = max(0.0, min(1.0, offset))

    # --- Quick Settings ---

    def toggle_setting(self, setting_type: QuickSettingType):
        """Toggle a quick setting on/off."""
        for qs in self.quick_settings:
            if qs.type == setting_type:
                qs.enabled = not qs.enabled
                if self._on_toggle:
                    self._on_toggle(setting_type, qs.enabled)
                logger.info("Quick setting %s: %s",
                            setting_type.name, "ON" if qs.enabled else "OFF")
                return

    def set_slider_value(self, setting_type: QuickSettingType, value: int):
        """Set a slider value (brightness, volume)."""
        for qs in self.quick_settings:
            if qs.type == setting_type:
                qs.value = max(0, min(100, value))
                return

    # --- Notifications ---

    def add_notification(self, notification: Notification):
        """Add a notification to the panel."""
        # Check for grouping
        if notification.group_key:
            for existing in self.notifications:
                if existing.group_key == notification.group_key:
                    # Update existing grouped notification
                    existing.title = notification.title
                    existing.body = notification.body
                    existing.timestamp = notification.timestamp
                    return

        self.notifications.insert(0, notification)

        # Cap total
        if len(self.notifications) > self.MAX_NOTIFICATIONS:
            self.notifications = self.notifications[:self.MAX_NOTIFICATIONS]

        logger.info("Notification added: %s — %s", notification.app_name,
                     notification.title)

    def dismiss_notification(self, notification_id: str):
        """Dismiss a notification by ID."""
        self.notifications = [
            n for n in self.notifications if n.id != notification_id
        ]
        if self._on_notification_dismiss:
            self._on_notification_dismiss(notification_id)

    def dismiss_all(self):
        """Dismiss all notifications."""
        self.notifications.clear()
        logger.info("All notifications dismissed")

    def mark_read(self, notification_id: str):
        """Mark a notification as read."""
        for n in self.notifications:
            if n.id == notification_id:
                n.read = True
                return

    @property
    def unread_count(self) -> int:
        return sum(1 for n in self.notifications if not n.read)

    # --- Rendering ---

    def get_render_data(self) -> dict:
        """
        Return all data needed to render the notification panel.

        Includes visual specs for the Claude × Apple design.
        """
        def _time_ago(ts: float) -> str:
            diff = time.time() - ts
            if diff < 60:
                return "now"
            if diff < 3600:
                return f"{int(diff / 60)}m"
            if diff < 86400:
                return f"{int(diff / 3600)}h"
            return f"{int(diff / 86400)}d"

        return {
            "visible": self.visible,
            "offset": self.offset,
            "quick_settings": [
                {
                    "type": qs.type.name,
                    "label": qs.label,
                    "icon": qs.icon,
                    "enabled": qs.enabled,
                    "value": qs.value,
                }
                for qs in self.quick_settings
            ],
            "notifications": [
                {
                    "id": n.id,
                    "app_name": n.app_name,
                    "title": n.title,
                    "body": n.body[:120],
                    "icon": n.icon,
                    "time_ago": _time_ago(n.timestamp),
                    "priority": n.priority.name,
                    "actions": n.actions,
                    "read": n.read,
                    "dismiss_progress": n.dismiss_progress,
                }
                for n in self.notifications[:20]  # Show max 20
            ],
            "unread_count": self.unread_count,
            # Style config
            "style": {
                "background": {
                    "blur_radius": 20,
                    "saturation": 1.8,
                    "tint": "warm_white_70",
                },
                "quick_settings_tile": {
                    "size": 64,
                    "radius": 16,
                    "margin": 12,
                    "active_color": "accent",
                    "inactive_color": "bg_tertiary",
                },
                "notification_card": {
                    "radius": 16,
                    "padding": 14,
                    "margin_bottom": 10,
                    "shadow": "sm",
                },
                "animation": {
                    "tile_stagger": 0.03,
                    "card_stagger": 0.05,
                    "spring": {"damping": 0.9, "stiffness": 180},
                },
            },
        }
