"""
Claude-OS Notification Panel

Slides down from the top when the user swipes down from the status bar.

Layout:
    ┌──────────────────────────────┐
    │         Status Bar           │
    ├──────────────────────────────┤
    │  Quick Settings              │
    │  [WiFi] [BT] [Bright] [Vol] │
    ├──────────────────────────────┤
    │  ┌────────────────────────┐  │
    │  │ Claude    now          │  │  ← Notification card
    │  │ Your timer is done     │  │
    │  └────────────────────────┘  │
    │  ┌────────────────────────┐  │
    │  │ System    5m ago       │  │
    │  │ Update available       │  │
    │  └────────────────────────┘  │
    │                              │
    └──────────────────────────────┘
"""

import time
from dataclasses import dataclass, field
from typing import Callable

from theme import Colors, Typography, Spacing, Radius, Color
from widget import Widget, Size, EdgeInsets, Align, Direction, Event, EventType
from widgets import Container, Label, ScrollView, Spacer, Divider


@dataclass
class Notification:
    """A system notification."""
    id: int
    app_name: str
    title: str
    body: str
    timestamp: float = 0
    icon: str = ""
    read: bool = False
    dismissible: bool = True

    def __post_init__(self):
        if not self.timestamp:
            self.timestamp = time.time()

    def time_ago(self) -> str:
        delta = time.time() - self.timestamp
        if delta < 60:
            return "now"
        elif delta < 3600:
            return f"{int(delta / 60)}m ago"
        elif delta < 86400:
            return f"{int(delta / 3600)}h ago"
        return f"{int(delta / 86400)}d ago"


@dataclass
class QuickSetting:
    """A quick settings toggle."""
    name: str
    icon: str  # ASCII icon
    enabled: bool = False
    on_toggle: Callable = None


class QuickSettingsBar(Widget):
    """Row of quick setting toggles."""

    def __init__(self):
        super().__init__()
        self.background = Colors.SURFACE
        self.padding = EdgeInsets.all(Spacing.SM)

        self._settings: list[QuickSetting] = [
            QuickSetting("WiFi", "W", enabled=True),
            QuickSetting("Bluetooth", "B", enabled=False),
            QuickSetting("Brightness", "*", enabled=True),
            QuickSetting("Volume", "V", enabled=True),
            QuickSetting("DND", "D", enabled=False),
        ]

        self._build_ui()

    def _build_ui(self):
        self.clear_children()
        row = Container(direction=Direction.HORIZONTAL,
                        gap=Spacing.SM, cross_align=Align.CENTER)
        self.add_child(row)

        for setting in self._settings:
            tile = Container(direction=Direction.VERTICAL,
                             cross_align=Align.CENTER, gap=2)
            tile.min_width = 52
            tile.min_height = 52
            tile.background = (Colors.PRIMARY.with_alpha(40) if setting.enabled
                               else Colors.SURFACE_CONTAINER)
            tile.corner_radius = Radius.LG
            tile.padding = EdgeInsets.all(Spacing.XS)

            icon_color = Colors.PRIMARY if setting.enabled else Colors.TEXT_DISABLED
            icon = Label(setting.icon, style=Typography.HEADLINE_SMALL,
                         color=icon_color, align=Align.CENTER)
            tile.add_child(icon)

            name = Label(setting.name[:4], style=Typography.LABEL_SMALL,
                         color=Colors.TEXT_SECONDARY, align=Align.CENTER)
            tile.add_child(name)

            tile.on_tap(lambda s=setting: self._toggle(s))
            row.add_child(tile)

    def _toggle(self, setting: QuickSetting):
        setting.enabled = not setting.enabled
        if setting.on_toggle:
            setting.on_toggle(setting.enabled)
        self._build_ui()
        self.mark_dirty()

    def measure(self, max_w: int, max_h: int) -> Size:
        return Size(max_w, 76)

    def set_toggle(self, name: str, enabled: bool):
        for s in self._settings:
            if s.name == name:
                s.enabled = enabled
                self._build_ui()
                self.mark_dirty()
                return

    def get_setting(self, name: str) -> QuickSetting | None:
        for s in self._settings:
            if s.name == name:
                return s
        return None


class NotificationCard(Widget):
    """A single notification card."""

    def __init__(self, notification: Notification,
                 on_tap: Callable = None,
                 on_dismiss: Callable = None):
        super().__init__()
        self.notification = notification
        self.background = Colors.SURFACE_CONTAINER
        self.corner_radius = Radius.MD
        self.padding = EdgeInsets.all(Spacing.SM)
        self._on_tap_callback = on_tap
        self._on_dismiss = on_dismiss
        self._on_tap = on_tap

        # Swipe-to-dismiss tracking
        self._swipe_x = 0
        self._swiping = False

        self._build_ui()

    def _build_ui(self):
        self.clear_children()

        col = Container(direction=Direction.VERTICAL, gap=2)
        self.add_child(col)

        # Header: app name + timestamp
        header = Container(direction=Direction.HORIZONTAL)
        header.add_child(Label(
            self.notification.app_name,
            style=Typography.LABEL_SMALL,
            color=Colors.PRIMARY_LIGHT,
        ))
        header.add_child(Spacer())
        header.add_child(Label(
            self.notification.time_ago(),
            style=Typography.LABEL_SMALL,
            color=Colors.TEXT_DISABLED,
        ))
        col.add_child(header)

        # Title
        col.add_child(Label(
            self.notification.title,
            style=Typography.LABEL_MEDIUM,
            color=Colors.TEXT_PRIMARY,
        ))

        # Body
        if self.notification.body:
            col.add_child(Label(
                self.notification.body[:80],
                style=Typography.BODY_SMALL,
                color=Colors.TEXT_SECONDARY,
                wrap=True,
            ))

    def measure(self, max_w: int, max_h: int) -> Size:
        h = Spacing.SM * 2  # padding
        h += Typography.LABEL_SMALL.line_height  # header
        h += Typography.LABEL_MEDIUM.line_height  # title
        if self.notification.body:
            h += Typography.BODY_SMALL.line_height  # body
        h += 4  # gaps
        return Size(max_w - Spacing.MD * 2, max(h, 50))

    def _handle_event(self, event_type: EventType, x: int, y: int,
                      key_code: int) -> bool:
        if event_type == EventType.TOUCH_DOWN:
            self._swiping = True
            self._swipe_x = x
            return True
        elif event_type == EventType.TOUCH_UP and self._swiping:
            self._swiping = False
            dx = x - self._swipe_x
            if abs(dx) > 100 and self._on_dismiss:
                self._on_dismiss(self.notification)
                return True
            elif self._on_tap_callback:
                self._on_tap_callback(self.notification)
                return True
        return False


class NotificationPanel(Widget):
    """
    Full notification panel with quick settings and notification list.
    """

    def __init__(self, on_notification_tap: Callable = None):
        super().__init__()
        self.background = Colors.BACKGROUND
        self._notifications: list[Notification] = []
        self._next_id = 1
        self._on_notification_tap = on_notification_tap
        self._visible = False

        self._build_ui()

    def _build_ui(self):
        self.clear_children()

        root = Container(direction=Direction.VERTICAL, gap=Spacing.SM)
        root.padding = EdgeInsets.all(Spacing.SM)
        self.add_child(root)

        # Quick settings
        self._quick_settings = QuickSettingsBar()
        root.add_child(self._quick_settings)

        # Divider
        root.add_child(Divider())

        # Notifications header
        header = Container(direction=Direction.HORIZONTAL)
        header.add_child(Label(
            "Notifications",
            style=Typography.LABEL_LARGE,
            color=Colors.TEXT_SECONDARY,
        ))
        header.add_child(Spacer())
        clear_btn = Label(
            "Clear all",
            style=Typography.LABEL_SMALL,
            color=Colors.PRIMARY,
        )
        clear_btn.on_tap(lambda: self.clear_all())
        header.add_child(clear_btn)
        root.add_child(header)

        # Notification list
        self._notif_scroll = ScrollView()
        self._notif_scroll.flex = 1
        self._notif_list = Container(direction=Direction.VERTICAL,
                                      gap=Spacing.SM)
        self._notif_scroll.add_child(self._notif_list)
        root.add_child(self._notif_scroll)

        # Rebuild notification cards
        self._rebuild_cards()

    def _rebuild_cards(self):
        self._notif_list.clear_children()
        for notif in reversed(self._notifications):  # Newest first
            card = NotificationCard(
                notif,
                on_tap=self._on_notification_tap,
                on_dismiss=lambda n: self.dismiss(n.id),
            )
            self._notif_list.add_child(card)

        if not self._notifications:
            self._notif_list.add_child(Label(
                "No notifications",
                style=Typography.BODY_MEDIUM,
                color=Colors.TEXT_DISABLED,
                align=Align.CENTER,
            ))
        self.mark_dirty()

    # --- Public API ---

    def add_notification(self, app_name: str, title: str,
                         body: str = "") -> Notification:
        notif = Notification(
            id=self._next_id, app_name=app_name,
            title=title, body=body,
        )
        self._next_id += 1
        self._notifications.append(notif)
        self._rebuild_cards()
        return notif

    def dismiss(self, notif_id: int):
        self._notifications = [n for n in self._notifications if n.id != notif_id]
        self._rebuild_cards()

    def clear_all(self):
        self._notifications.clear()
        self._rebuild_cards()

    @property
    def notification_count(self) -> int:
        return len(self._notifications)

    @property
    def unread_count(self) -> int:
        return sum(1 for n in self._notifications if not n.read)

    def show(self):
        self._visible = True
        self.visible = True
        self.mark_dirty()

    def hide(self):
        self._visible = False
        self.visible = False
        self.mark_dirty()

    @property
    def is_visible(self) -> bool:
        return self._visible
