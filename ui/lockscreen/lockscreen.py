"""
Claude-OS Lock Screen

A beautiful, minimalist lock screen blending Claude's warmth with
Apple's precision. Features a large, light-weighted clock, subtle
date, notification previews, and a smooth unlock gesture.

Design:
    ┌──────────────────────────────────┐
    │                                  │
    │                                  │
    │           9:41                   │  ← Large clock (76pt, ultralight)
    │      Tuesday, March 24           │  ← Date (17pt, medium)
    │                                  │
    │     ┌────────────────────┐       │
    │     │ 📨 2 new messages  │       │  ← Notification previews
    │     └────────────────────┘       │
    │     ┌────────────────────┐       │
    │     │ 🔋 Battery at 20%  │       │
    │     └────────────────────┘       │
    │                                  │
    │                                  │
    │         ─────────                │  ← Swipe up indicator
    │                                  │
    └──────────────────────────────────┘

Background:
    - Warm gradient: cream (#FAF3E8) to soft coral (#E49378) at 15% opacity
    - Subtle depth effect: clock floats with parallax on gyroscope
    - Time-of-day adaptive: warmer tones at golden hour

Animations:
    - Clock: spring fade-in on wake (0.6s, gentle spring)
    - Date: staggered fade-in (0.1s delay after clock)
    - Notifications: slide up with spring, staggered
    - Unlock: swipe up → scale(0.9) + fade + blur of lock content
    - Home indicator: gentle pulse animation
"""

import logging
import time
from dataclasses import dataclass, field
from enum import Enum, auto

logger = logging.getLogger("lockscreen")


class LockScreenState(Enum):
    """Lock screen display state."""
    LOCKED = auto()        # Full lock screen visible
    UNLOCKING = auto()     # Swipe-up in progress
    PIN_ENTRY = auto()     # PIN/password input
    UNLOCKED = auto()      # Dismissed


@dataclass
class LockNotification:
    """A notification preview shown on the lock screen."""
    app_id: str
    app_name: str
    title: str
    body: str
    timestamp: float
    icon: str = ""
    count: int = 1       # Badge count (grouped notifications)


@dataclass
class LockScreenData:
    """All data needed to render the lock screen."""
    # Clock
    time_str: str = ""
    date_str: str = ""

    # Notifications (max 4 on lock screen)
    notifications: list[LockNotification] = field(default_factory=list)

    # State
    state: LockScreenState = LockScreenState.LOCKED
    unlock_progress: float = 0.0   # 0.0 = locked, 1.0 = fully swiped

    # Background
    wallpaper_path: str = ""
    gradient_start: str = "#FAF3E8"   # Cream
    gradient_end: str = "#E49378"     # Soft coral (15% opacity layer)

    # PIN entry
    pin_dots: int = 0
    pin_max: int = 6
    pin_error: bool = False


class LockScreen:
    """
    Claude-OS lock screen.

    Renders as a fullscreen Wayland surface on top of everything.
    Uses parallax depth for the clock and staggered spring animations
    for notification cards.

    Visual specs:
    - Clock: 76pt, ultralight/thin weight, centered, Claude deep text
    - Date: 17pt, medium weight, centered below clock
    - Notification cards: frosted glass (16px radius, warm tint)
    - Swipe indicator: 134×5px rounded bar, subtle pulse
    - PIN entry: 6 dots, fill animation on each digit
    """

    MAX_NOTIFICATIONS = 4
    SWIPE_UNLOCK_THRESHOLD = 0.4  # 40% of screen height to unlock

    def __init__(self):
        self.data = LockScreenData()
        self._pin_buffer: str = ""
        self._pin_hash: str | None = None  # Stored PIN hash
        self._on_unlock = None
        self._on_pin_attempt = None
        self._wake_time: float = 0.0

    def wake(self):
        """Called when the display turns on — triggers entrance animations."""
        self._wake_time = time.monotonic()
        self.data.state = LockScreenState.LOCKED
        self.data.unlock_progress = 0.0
        self._update_clock()
        logger.info("Lock screen woke")

    def _update_clock(self):
        """Update the lock screen clock and date."""
        now = time.localtime()
        self.data.time_str = time.strftime("%H:%M", now)
        self.data.date_str = time.strftime("%A, %B %d", now)

    def set_unlock_handler(self, handler):
        """Set callback for successful unlock."""
        self._on_unlock = handler

    def set_pin(self, pin_hash: str):
        """Set the stored PIN hash for verification."""
        self._pin_hash = pin_hash

    # --- Notifications ---

    def add_notification(self, notification: LockNotification):
        """Add a notification to the lock screen."""
        self.data.notifications.insert(0, notification)
        # Cap at max
        if len(self.data.notifications) > self.MAX_NOTIFICATIONS:
            self.data.notifications = self.data.notifications[:self.MAX_NOTIFICATIONS]
        logger.info("Lock screen notification: %s", notification.title)

    def clear_notifications(self):
        """Clear all lock screen notifications."""
        self.data.notifications.clear()

    # --- Gesture Handling ---

    def handle_swipe_progress(self, progress: float):
        """
        Handle ongoing swipe-up gesture.

        Args:
            progress: 0.0 (bottom) to 1.0 (fully swiped)

        As the user swipes up:
        - Lock content scales down (1.0 → 0.9)
        - Lock content fades out (1.0 → 0.0)
        - Lock content blurs (0 → 10px)
        """
        self.data.unlock_progress = max(0.0, min(1.0, progress))
        if self.data.state == LockScreenState.LOCKED:
            self.data.state = LockScreenState.UNLOCKING

    def handle_swipe_end(self, progress: float):
        """
        Handle swipe-up gesture completion.

        If progress exceeds threshold, proceed to unlock.
        Otherwise, spring-animate back to locked position.
        """
        if progress >= self.SWIPE_UNLOCK_THRESHOLD:
            if self._pin_hash:
                # Require PIN
                self.data.state = LockScreenState.PIN_ENTRY
                self.data.pin_dots = 0
                self._pin_buffer = ""
            else:
                # No PIN set — unlock immediately
                self._unlock()
        else:
            # Snap back to locked
            self.data.state = LockScreenState.LOCKED
            self.data.unlock_progress = 0.0

    # --- PIN Entry ---

    def enter_pin_digit(self, digit: str):
        """Enter a single PIN digit."""
        if self.data.state != LockScreenState.PIN_ENTRY:
            return
        if len(self._pin_buffer) >= self.data.pin_max:
            return

        self._pin_buffer += digit
        self.data.pin_dots = len(self._pin_buffer)

        # Auto-verify when full
        if len(self._pin_buffer) == self.data.pin_max:
            self._verify_pin()

    def delete_pin_digit(self):
        """Delete the last PIN digit."""
        if self._pin_buffer:
            self._pin_buffer = self._pin_buffer[:-1]
            self.data.pin_dots = len(self._pin_buffer)

    def _verify_pin(self):
        """Verify the entered PIN."""
        # In production, compare hashes
        import hashlib
        entered_hash = hashlib.sha256(self._pin_buffer.encode()).hexdigest()

        if entered_hash == self._pin_hash:
            self._unlock()
        else:
            # Wrong PIN — shake animation + reset
            self.data.pin_error = True
            self._pin_buffer = ""
            self.data.pin_dots = 0
            logger.warning("Incorrect PIN attempt")

    def _unlock(self):
        """Complete the unlock sequence."""
        self.data.state = LockScreenState.UNLOCKED
        self.data.unlock_progress = 1.0
        if self._on_unlock:
            self._on_unlock()
        logger.info("Lock screen unlocked")

    # --- Rendering ---

    def get_render_data(self) -> dict:
        """
        Return all data needed to render the lock screen.

        Includes animation timing, visual states, and layout specs.
        """
        elapsed = time.monotonic() - self._wake_time if self._wake_time else 0
        self._update_clock()

        return {
            "state": self.data.state.name,
            "time_str": self.data.time_str,
            "date_str": self.data.date_str,
            "unlock_progress": self.data.unlock_progress,
            "notifications": [
                {
                    "app_name": n.app_name,
                    "title": n.title,
                    "body": n.body[:80],
                    "icon": n.icon,
                    "count": n.count,
                    "timestamp": n.timestamp,
                }
                for n in self.data.notifications
            ],
            "pin": {
                "active": self.data.state == LockScreenState.PIN_ENTRY,
                "dots": self.data.pin_dots,
                "max": self.data.pin_max,
                "error": self.data.pin_error,
            },
            # Animation data
            "animation": {
                "elapsed_since_wake": elapsed,
                "clock_opacity": min(1.0, elapsed / 0.6) if elapsed < 0.6 else 1.0,
                "date_opacity": min(1.0, max(0.0, (elapsed - 0.1) / 0.5)),
                # Content transforms during swipe unlock
                "content_scale": 1.0 - (self.data.unlock_progress * 0.1),
                "content_opacity": 1.0 - self.data.unlock_progress,
                "content_blur": self.data.unlock_progress * 10.0,
            },
            # Style
            "style": {
                "clock": {"size": 76, "weight": 200, "font": "rounded"},
                "date": {"size": 17, "weight": 500},
                "background": {
                    "gradient_start": self.data.gradient_start,
                    "gradient_end": self.data.gradient_end,
                    "wallpaper": self.data.wallpaper_path,
                },
                "home_indicator": {
                    "width": 134,
                    "height": 5,
                    "radius": 2.5,
                    "bottom_offset": 8,
                    "pulse": True,
                },
                "notification_card": {
                    "radius": 16,
                    "blur": 12,
                    "padding": 14,
                },
            },
        }
