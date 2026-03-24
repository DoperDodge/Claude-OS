"""
Claude-OS Lock Screen

A beautiful, theme-aware lock screen with:
- Large clock display with date
- Subtle background gradient (navy -> charcoal)
- Swipe-up-to-unlock gesture with spring animation
- Notification previews on lock screen
- Battery and charging status indicator

Visual Design:
    ┌──────────────────────────────────┐
    │                                  │
    │                                  │
    │           14:32                  │  <- Display large, bold, cream
    │        Tuesday                   │  <- Title medium, secondary text
    │       March 24                   │
    │                                  │
    │                                  │
    │    ┌─────────────────────┐       │
    │    │ Messages (2)        │       │  <- Notification previews
    │    │ Claude: Hey there.. │       │     Glassmorphic cards
    │    └─────────────────────┘       │
    │                                  │
    │       ─────────────              │  <- Swipe up indicator (animated)
    │       Swipe up to unlock         │
    └──────────────────────────────────┘
"""

import logging
import time
from dataclasses import dataclass, field

logger = logging.getLogger("lockscreen")


@dataclass
class LockScreenNotification:
    """A notification preview shown on the lock screen."""
    app_name: str = ""
    title: str = ""
    body: str = ""
    icon: str = ""
    timestamp: float = 0.0
    count: int = 1


class LockScreen:
    """
    Claude-OS lock screen with themed visuals.

    Displays time, date, notification previews, and handles
    the swipe-up-to-unlock gesture.
    """

    MAX_NOTIFICATIONS = 4

    def __init__(self):
        self.locked = True
        self.notifications: list[LockScreenNotification] = []

        # Animation state
        self._swipe_progress = 0.0    # 0=locked, 1=unlocked
        self._clock_opacity = 1.0
        self._hint_pulse = 0.0        # Pulsing opacity for "swipe up" hint

        # Load theme
        try:
            from ui.theme import get_theme
            self._theme = get_theme()
        except ImportError:
            self._theme = None

    def get_time_display(self) -> dict:
        """Get formatted time and date for display."""
        now = time.localtime()
        return {
            "time": time.strftime("%H:%M", now),
            "weekday": time.strftime("%A", now),
            "date": time.strftime("%B %d", now),
        }

    def add_notification(self, notification: LockScreenNotification):
        """Add a notification preview to the lock screen."""
        # Group by app - increment count if same app
        for existing in self.notifications:
            if existing.app_name == notification.app_name:
                existing.count += 1
                existing.title = notification.title
                existing.body = notification.body
                existing.timestamp = notification.timestamp
                return
        if len(self.notifications) >= self.MAX_NOTIFICATIONS:
            self.notifications.pop(0)
        self.notifications.append(notification)

    def clear_notifications(self):
        """Clear all lock screen notification previews."""
        self.notifications.clear()

    def handle_swipe(self, progress: float):
        """
        Handle swipe-up gesture progress.

        Args:
            progress: 0.0 (bottom) to 1.0 (fully swiped up)
        """
        self._swipe_progress = max(0.0, min(1.0, progress))
        # Fade clock as user swipes
        self._clock_opacity = 1.0 - (self._swipe_progress * 0.6)

    def attempt_unlock(self) -> bool:
        """Attempt to unlock. Returns True if swipe threshold met."""
        if self._swipe_progress > 0.4:
            self.locked = False
            logger.info("Lock screen unlocked")
            return True
        # Snap back
        self._swipe_progress = 0.0
        self._clock_opacity = 1.0
        return False

    def lock(self):
        """Re-lock the screen."""
        self.locked = True
        self._swipe_progress = 0.0
        self._clock_opacity = 1.0
        logger.info("Lock screen locked")

    def get_render_data(self) -> dict:
        """Return all data needed to render the lock screen."""
        theme = self._theme
        colors = theme.colors if theme else None
        typo = theme.typography if theme else None
        spacing = theme.spacing if theme else None
        effects = theme.effects if theme else None
        anim = theme.animation if theme else None
        layout = theme.layout if theme else None

        time_display = self.get_time_display()

        return {
            "locked": self.locked,
            "swipe_progress": self._swipe_progress,
            "background": {
                "gradient": {
                    "start": colors.navy if colors else "#1A1A2E",
                    "end": colors.charcoal if colors else "#0F3460",
                    "angle": 180,
                },
            },
            "clock": {
                "time": time_display["time"],
                "weekday": time_display["weekday"],
                "date": time_display["date"],
                "opacity": self._clock_opacity,
                "time_style": {
                    "size": typo.display_large_size if typo else 34.0,
                    "weight": typo.display_large_weight if typo else 700,
                    "tracking": typo.display_large_tracking if typo else 0.37,
                    "color": colors.claude_cream if colors else "#FAF6F1",
                },
                "date_style": {
                    "size": typo.title_medium_size if typo else 20.0,
                    "weight": typo.title_medium_weight if typo else 600,
                    "color": colors.text_secondary if colors else "#5A5A72",
                },
                "y_offset": (layout.screen_height // 4) if layout else 585,
            },
            "notifications": [
                {
                    "app_name": n.app_name,
                    "title": n.title,
                    "body": n.body[:80],
                    "count": n.count,
                    "style": {
                        "background": colors.glass_background if colors else "rgba(255,255,255,0.72)",
                        "blur_radius": effects.glass_blur_thin if effects else 10.0,
                        "border_color": colors.glass_border if colors else "rgba(255,255,255,0.3)",
                        "radius": spacing.notification_radius if spacing else 16,
                        "title_size": typo.notification_title_size if typo else 15.0,
                        "title_weight": typo.notification_title_weight if typo else 600,
                        "body_size": typo.notification_body_size if typo else 13.0,
                        "app_size": typo.notification_app_size if typo else 11.0,
                    },
                }
                for n in self.notifications
            ],
            "unlock_hint": {
                "text": "Swipe up to unlock",
                "color": colors.text_tertiary if colors else "#8E8E9E",
                "size": typo.caption_size if typo else 12.0,
                "indicator_width": layout.home_indicator_width if layout else 134,
                "indicator_height": layout.home_indicator_height if layout else 5,
                "indicator_color": colors.claude_terracotta if colors else "#D4A574",
                "y_position": (layout.screen_height - 120) if layout else 2220,
                "pulse_opacity": self._hint_pulse,
            },
            "animation": {
                "unlock_spring_response": anim.spring_snappy_response if anim else 0.25,
                "unlock_spring_damping": anim.spring_snappy_damping if anim else 0.86,
                "clock_fade_duration": anim.duration_normal if anim else 0.25,
            },
        }
