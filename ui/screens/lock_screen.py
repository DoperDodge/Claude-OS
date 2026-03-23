"""
Claude-OS Lock Screen

The first screen users see. Shows:
    - Current time (large, centered)
    - Current date
    - Lock screen notifications (preview)
    - "Swipe up to unlock" indicator

After swipe-up, transitions to PIN entry (if set) or directly
to the home screen.

Layout:
    ┌──────────────────────────────┐
    │          Status Bar          │
    ├──────────────────────────────┤
    │                              │
    │           12:34              │  ← Large clock
    │      Monday, March 23       │  ← Date
    │                              │
    │   ┌──────────────────────┐   │
    │   │ Claude: You have 2.. │   │  ← Notification preview
    │   └──────────────────────┘   │
    │                              │
    │       ⌃ Swipe to unlock      │  ← Animated hint
    └──────────────────────────────┘
"""

import time
from dataclasses import dataclass, field

from theme import Colors, Typography, Spacing, Radius, Color
from widget import Widget, Size, EdgeInsets, Align, Direction, Event, EventType
from widgets import Container, Label, Spacer, Divider


@dataclass
class LockScreenNotification:
    """A notification shown on the lock screen."""
    app_name: str
    title: str
    body: str
    timestamp: str = ""


class LockScreen(Widget):
    """
    Lock screen with clock, date, notifications, and swipe-to-unlock.
    """

    SWIPE_UNLOCK_THRESHOLD = 150  # pixels upward to unlock

    def __init__(self, on_unlock=None, pin_required: bool = False):
        super().__init__()
        self.background = Colors.BACKGROUND

        self._on_unlock = on_unlock
        self._pin_required = pin_required
        self._locked = True
        self._show_pin = False
        self._notifications: list[LockScreenNotification] = []

        # Swipe tracking
        self._swipe_start_y = 0
        self._swiping = False
        self._swipe_offset = 0

        # Clock/date (updated externally or via update_time)
        self._time_str = "12:00"
        self._date_str = "Monday, January 1"

        # PIN entry state
        self._pin_input = ""
        self._pin_code = ""  # Expected PIN
        self._pin_error = False
        self._pin_dots = 4

        # Build widget tree
        self._build_ui()

    def _build_ui(self):
        """Construct the lock screen widget tree."""
        self.clear_children()

        # Main layout
        self._root = Container(direction=Direction.VERTICAL,
                               cross_align=Align.CENTER)
        self._root.padding = EdgeInsets.symmetric(horizontal=Spacing.XL,
                                                   vertical=Spacing.XXXL)
        self.add_child(self._root)

        # Top spacer
        top_space = Spacer()
        top_space.flex = 2
        self._root.add_child(top_space)

        # Clock
        self._clock_label = Label(
            self._time_str,
            style=Typography.DISPLAY_LARGE,
            color=Colors.TEXT_PRIMARY,
            align=Align.CENTER,
        )
        self._root.add_child(self._clock_label)

        # Date
        self._date_label = Label(
            self._date_str,
            style=Typography.BODY_LARGE,
            color=Colors.TEXT_SECONDARY,
            align=Align.CENTER,
        )
        self._root.add_child(self._date_label)

        # Notification area spacer
        notif_space = Spacer()
        notif_space.flex = 1
        self._root.add_child(notif_space)

        # Notifications container
        self._notif_container = Container(
            direction=Direction.VERTICAL, gap=Spacing.SM,
            cross_align=Align.CENTER,
        )
        self._root.add_child(self._notif_container)

        # Bottom spacer
        bottom_space = Spacer()
        bottom_space.flex = 2
        self._root.add_child(bottom_space)

        # Swipe hint
        self._swipe_hint = Label(
            "Swipe up to unlock",
            style=Typography.LABEL_MEDIUM,
            color=Colors.TEXT_DISABLED,
            align=Align.CENTER,
        )
        self._root.add_child(self._swipe_hint)

    def _build_pin_ui(self):
        """Build the PIN entry screen."""
        self.clear_children()

        root = Container(direction=Direction.VERTICAL,
                         cross_align=Align.CENTER, gap=Spacing.LG)
        root.padding = EdgeInsets.symmetric(horizontal=Spacing.XL,
                                            vertical=Spacing.XXXL)
        self.add_child(root)

        top = Spacer()
        top.flex = 2
        root.add_child(top)

        root.add_child(Label(
            "Enter PIN",
            style=Typography.HEADLINE_MEDIUM,
            color=Colors.TEXT_PRIMARY,
            align=Align.CENTER,
        ))

        # PIN dots
        self._pin_dots_label = Label(
            self._get_pin_dots_text(),
            style=Typography.DISPLAY_MEDIUM,
            color=Colors.TEXT_PRIMARY,
            align=Align.CENTER,
        )
        root.add_child(self._pin_dots_label)

        # Error message
        self._pin_error_label = Label(
            "",
            style=Typography.BODY_SMALL,
            color=Colors.ERROR,
            align=Align.CENTER,
        )
        root.add_child(self._pin_error_label)

        mid = Spacer()
        mid.flex = 1
        root.add_child(mid)

        # Number pad (3x4 grid)
        self._build_numpad(root)

        bottom = Spacer()
        bottom.flex = 1
        root.add_child(bottom)

    def _build_numpad(self, parent: Container):
        """Build the numeric keypad for PIN entry."""
        keys = [
            ["1", "2", "3"],
            ["4", "5", "6"],
            ["7", "8", "9"],
            ["", "0", "<"],
        ]

        for row_keys in keys:
            row = Container(direction=Direction.HORIZONTAL,
                            gap=Spacing.MD, cross_align=Align.CENTER)
            for key in row_keys:
                btn = Label(
                    key,
                    style=Typography.HEADLINE_LARGE,
                    color=Colors.TEXT_PRIMARY,
                    align=Align.CENTER,
                )
                btn.min_width = 64
                btn.min_height = 56
                btn.background = Colors.SURFACE_CONTAINER if key else None
                btn.corner_radius = Radius.LG
                if key:
                    btn.on_tap(lambda k=key: self._on_pin_key(k))
                row.add_child(btn)
            parent.add_child(row)

    def _get_pin_dots_text(self) -> str:
        """Get the visual PIN dots display."""
        filled = len(self._pin_input)
        return "* " * filled + "- " * (self._pin_dots - filled)

    def _on_pin_key(self, key: str):
        """Handle a PIN keypad press."""
        if key == "<":
            # Backspace
            if self._pin_input:
                self._pin_input = self._pin_input[:-1]
        elif len(self._pin_input) < self._pin_dots:
            self._pin_input += key

            # Check if PIN is complete
            if len(self._pin_input) == self._pin_dots:
                if self._pin_input == self._pin_code:
                    self._unlock()
                else:
                    self._pin_error = True
                    self._pin_input = ""

        self._update_pin_display()

    def _update_pin_display(self):
        """Update PIN dots and error message."""
        if hasattr(self, '_pin_dots_label'):
            self._pin_dots_label.text = self._get_pin_dots_text()
        if hasattr(self, '_pin_error_label'):
            self._pin_error_label.text = "Wrong PIN" if self._pin_error else ""
        self.mark_dirty()

    # --- Public API ---

    def update_time(self, time_str: str = None, date_str: str = None):
        """Update the displayed time and date."""
        if time_str:
            self._time_str = time_str
            if hasattr(self, '_clock_label'):
                self._clock_label.text = time_str
        if date_str:
            self._date_str = date_str
            if hasattr(self, '_date_label'):
                self._date_label.text = date_str
        self.mark_dirty()

    def update_time_from_system(self):
        """Update time from system clock."""
        now = time.localtime()
        self.update_time(
            time_str=time.strftime("%H:%M", now),
            date_str=time.strftime("%A, %B %d", now),
        )

    def set_pin(self, pin: str):
        """Set the unlock PIN code."""
        self._pin_code = pin
        self._pin_required = True
        self._pin_dots = len(pin)

    def add_notification(self, notification: LockScreenNotification):
        """Add a notification to the lock screen."""
        self._notifications.append(notification)
        self._rebuild_notifications()

    def clear_notifications(self):
        """Remove all lock screen notifications."""
        self._notifications.clear()
        self._rebuild_notifications()

    def lock(self):
        """Lock the screen."""
        self._locked = True
        self._show_pin = False
        self._pin_input = ""
        self._pin_error = False
        self._build_ui()
        self.mark_dirty()

    @property
    def is_locked(self) -> bool:
        return self._locked

    # --- Internal ---

    def _rebuild_notifications(self):
        """Rebuild notification preview widgets."""
        if not hasattr(self, '_notif_container'):
            return
        self._notif_container.clear_children()

        for notif in self._notifications[-3:]:  # Show last 3
            card = Container(direction=Direction.VERTICAL, gap=2)
            card.background = Colors.SURFACE_CONTAINER
            card.corner_radius = Radius.MD
            card.padding = EdgeInsets.all(Spacing.SM)
            card.min_width = 240

            header = Label(
                notif.app_name,
                style=Typography.LABEL_SMALL,
                color=Colors.TEXT_SECONDARY,
            )
            card.add_child(header)

            title = Label(
                notif.title,
                style=Typography.LABEL_MEDIUM,
                color=Colors.TEXT_PRIMARY,
            )
            card.add_child(title)

            if notif.body:
                body = Label(
                    notif.body[:60] + ("..." if len(notif.body) > 60 else ""),
                    style=Typography.BODY_SMALL,
                    color=Colors.TEXT_SECONDARY,
                )
                card.add_child(body)

            self._notif_container.add_child(card)

        self.mark_dirty()

    def _unlock(self):
        """Transition to unlocked state."""
        self._locked = False
        self._show_pin = False
        if self._on_unlock:
            self._on_unlock()

    def _handle_event(self, event_type: EventType, x: int, y: int,
                      key_code: int) -> bool:
        if not self._locked:
            return False

        if self._show_pin:
            return super()._handle_event(event_type, x, y, key_code)

        if event_type == EventType.TOUCH_DOWN:
            self._swiping = True
            self._swipe_start_y = y
            self._swipe_offset = 0
            return True

        elif event_type == EventType.TOUCH_MOVE and self._swiping:
            self._swipe_offset = self._swipe_start_y - y
            self.mark_dirty()
            return True

        elif event_type == EventType.TOUCH_UP and self._swiping:
            self._swiping = False
            if self._swipe_offset >= self.SWIPE_UNLOCK_THRESHOLD:
                if self._pin_required and self._pin_code:
                    self._show_pin = True
                    self._build_pin_ui()
                else:
                    self._unlock()
            self._swipe_offset = 0
            self.mark_dirty()
            return True

        return False
