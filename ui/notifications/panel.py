"""
Claude-OS Notification Panel

A pull-down notification shade with:
- Quick settings toggles (WiFi, Bluetooth, brightness, etc.)
- Notification cards grouped by app
- Clear all / dismiss gestures
- Glassmorphic backdrop with blur

Visual Design:
    ┌──────────────────────────────────────┐
    │  [Status Bar]                        │
    ├──────────────────────────────────────┤
    │                                      │
    │  ┌─────────┐ ┌─────────┐ ┌───────┐  │
    │  │  WiFi   │ │Bluetooth│ │ DND   │  │  <- Quick settings toggles
    │  │   ON    │ │  OFF    │ │ OFF   │  │     Pill-shaped, accent when on
    │  └─────────┘ └─────────┘ └───────┘  │
    │  ┌─────────┐ ┌─────────┐ ┌───────┐  │
    │  │  Torch  │ │ Rotate  │ │ Dark  │  │
    │  └─────────┘ └─────────┘ └───────┘  │
    │                                      │
    │  ━━━━━━━━ Brightness ━━━━━━━━━━━━━  │  <- Slider with terracotta accent
    │                                      │
    │  ── Notifications ─────────── Clear  │
    │                                      │
    │  ┌────────────────────────────────┐  │
    │  │ Claude           2m ago       │  │  <- Notification card
    │  │ I found what you asked about  │  │     Glassmorphic, swipe to dismiss
    │  └────────────────────────────────┘  │
    │  ┌────────────────────────────────┐  │
    │  │ Messages          5m ago      │  │
    │  │ Alice: Hey, are you free?     │  │
    │  └────────────────────────────────┘  │
    │                                      │
    └──────────────────────────────────────┘
"""

import logging
import time
from dataclasses import dataclass, field
from enum import Enum, auto

logger = logging.getLogger("notifications")


class NotificationPriority(Enum):
    """Notification priority levels."""
    LOW = auto()
    NORMAL = auto()
    HIGH = auto()
    URGENT = auto()


@dataclass
class Notification:
    """A single notification."""
    id: str
    app_name: str
    title: str
    body: str
    icon: str = ""
    priority: NotificationPriority = NotificationPriority.NORMAL
    timestamp: float = 0.0
    actions: list[str] = field(default_factory=list)
    group_key: str = ""
    read: bool = False


@dataclass
class QuickSetting:
    """A quick settings toggle."""
    id: str
    label: str
    icon: str
    enabled: bool = False
    subtitle: str = ""


class NotificationPanel:
    """
    Pull-down notification shade for Claude-OS.

    Contains quick settings toggles, a brightness slider,
    and a scrollable list of grouped notification cards.
    """

    def __init__(self):
        self.visible = False
        self.notifications: list[Notification] = []
        self.quick_settings: list[QuickSetting] = []
        self.brightness: int = 80
        self._pull_progress = 0.0  # 0=hidden, 1=fully shown

        # Load theme
        try:
            from ui.theme import get_theme
            self._theme = get_theme()
        except ImportError:
            self._theme = None

        self._setup_quick_settings()

    def _setup_quick_settings(self):
        """Initialize default quick settings toggles."""
        self.quick_settings = [
            QuickSetting("wifi", "WiFi", "wifi", enabled=True, subtitle="Home"),
            QuickSetting("bluetooth", "Bluetooth", "bluetooth"),
            QuickSetting("dnd", "Do Not Disturb", "moon"),
            QuickSetting("flashlight", "Torch", "flashlight"),
            QuickSetting("rotation", "Auto-Rotate", "rotate", enabled=True),
            QuickSetting("dark_mode", "Dark Mode", "moon_fill"),
        ]

    def show(self):
        """Show the notification panel."""
        self.visible = True
        self._pull_progress = 1.0
        logger.info("Notification panel shown")

    def hide(self):
        """Hide the notification panel."""
        self.visible = False
        self._pull_progress = 0.0
        logger.info("Notification panel hidden")

    def set_pull_progress(self, progress: float):
        """Set pull-down progress for gesture-driven reveal."""
        self._pull_progress = max(0.0, min(1.0, progress))
        self.visible = self._pull_progress > 0.0

    def toggle_quick_setting(self, setting_id: str) -> bool:
        """Toggle a quick setting and return new state."""
        for qs in self.quick_settings:
            if qs.id == setting_id:
                qs.enabled = not qs.enabled
                logger.info("Quick setting %s: %s", setting_id,
                           "ON" if qs.enabled else "OFF")
                return qs.enabled
        return False

    def set_brightness(self, value: int):
        """Set brightness level (0-100)."""
        self.brightness = max(0, min(100, value))

    def add_notification(self, notification: Notification):
        """Add a notification to the panel."""
        if not notification.timestamp:
            notification.timestamp = time.time()
        self.notifications.insert(0, notification)
        logger.info("Notification added: %s - %s",
                    notification.app_name, notification.title)

    def dismiss_notification(self, notification_id: str):
        """Dismiss a single notification."""
        self.notifications = [
            n for n in self.notifications if n.id != notification_id
        ]

    def clear_all(self):
        """Clear all notifications."""
        self.notifications.clear()
        logger.info("All notifications cleared")

    def _format_time_ago(self, timestamp: float) -> str:
        """Format a timestamp as relative time."""
        delta = time.time() - timestamp
        if delta < 60:
            return "now"
        elif delta < 3600:
            mins = int(delta / 60)
            return f"{mins}m ago"
        elif delta < 86400:
            hours = int(delta / 3600)
            return f"{hours}h ago"
        else:
            days = int(delta / 86400)
            return f"{days}d ago"

    def _get_priority_color(self, priority: NotificationPriority) -> str:
        """Get the themed color for a notification priority."""
        if not self._theme:
            return "#5AC8FA"
        colors = self._theme.colors
        return {
            NotificationPriority.LOW: colors.notification_low,
            NotificationPriority.NORMAL: colors.notification_normal,
            NotificationPriority.HIGH: colors.notification_high,
            NotificationPriority.URGENT: colors.notification_urgent,
        }.get(priority, colors.notification_normal)

    def get_render_data(self) -> dict:
        """Return all data needed to render the notification panel."""
        theme = self._theme
        colors = theme.colors if theme else None
        typo = theme.typography if theme else None
        spacing = theme.spacing if theme else None
        effects = theme.effects if theme else None
        anim = theme.animation if theme else None

        return {
            "visible": self.visible,
            "pull_progress": self._pull_progress,
            "background": {
                "color": colors.overlay if colors else "rgba(26,26,46,0.4)",
                "blur_radius": effects.glass_blur_thick if effects else 40.0,
            },
            "quick_settings": {
                "toggles": [
                    {
                        "id": qs.id,
                        "label": qs.label,
                        "icon": qs.icon,
                        "enabled": qs.enabled,
                        "subtitle": qs.subtitle,
                        "active_color": colors.accent if colors else "#D4A574",
                        "inactive_color": colors.surface_secondary if colors else "#F5EDE4",
                        "text_color": (colors.text_on_accent if qs.enabled
                                       else colors.text_primary) if colors else "#1A1A2E",
                    }
                    for qs in self.quick_settings
                ],
                "grid_columns": 3,
                "toggle_radius": spacing.radius_lg if spacing else 16,
                "toggle_padding": spacing.sm if spacing else 8,
            },
            "brightness": {
                "value": self.brightness,
                "track_color": colors.surface_tertiary if colors else "#EDE3D8",
                "fill_color": colors.claude_terracotta if colors else "#D4A574",
                "thumb_color": colors.surface if colors else "#FFFFFF",
                "label_color": colors.text_secondary if colors else "#5A5A72",
            },
            "notifications_section": {
                "header_text": "Notifications",
                "clear_text": "Clear",
                "header_color": colors.text_secondary if colors else "#5A5A72",
                "clear_color": colors.accent if colors else "#D4A574",
                "cards": [
                    {
                        "id": n.id,
                        "app_name": n.app_name,
                        "title": n.title,
                        "body": n.body[:120],
                        "time_ago": self._format_time_ago(n.timestamp),
                        "priority_color": self._get_priority_color(n.priority),
                        "read": n.read,
                        "actions": n.actions,
                        "style": {
                            "background": colors.glass_background if colors else "rgba(255,255,255,0.72)",
                            "border_color": colors.glass_border if colors else "rgba(255,255,255,0.3)",
                            "blur_radius": effects.glass_blur_thin if effects else 10.0,
                            "radius": spacing.notification_radius if spacing else 16,
                            "padding": spacing.card_padding if spacing else 16,
                            "shadow": {
                                "offset": effects.notification_shadow if effects else (0, 8, 24, -4),
                                "opacity": effects.notification_shadow_opacity if effects else 0.18,
                            },
                            "title_size": typo.notification_title_size if typo else 15.0,
                            "title_weight": typo.notification_title_weight if typo else 600,
                            "body_size": typo.notification_body_size if typo else 13.0,
                            "app_size": typo.notification_app_size if typo else 11.0,
                            "title_color": colors.text_primary if colors else "#1A1A2E",
                            "body_color": colors.text_secondary if colors else "#5A5A72",
                            "app_color": colors.text_tertiary if colors else "#8E8E9E",
                        },
                    }
                    for n in self.notifications
                ],
                "empty_text": "No notifications",
                "empty_color": colors.text_tertiary if colors else "#8E8E9E",
            },
            "animation": {
                "enter_duration": anim.notification_enter_duration if anim else 0.45,
                "enter_curve": anim.notification_enter_curve if anim else (0.34, 1.56, 0.64, 1.0),
                "exit_duration": anim.notification_exit_duration if anim else 0.3,
                "exit_curve": anim.notification_exit_curve if anim else (0.42, 0.0, 1.0, 1.0),
            },
        }
