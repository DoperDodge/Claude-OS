"""
Claude-OS Status Bar Widget

Always-on-top bar at the top of the screen showing system status.

Layout (left to right):
    ┌─────────────────────────────────────┐
    │ 12:34    · ·    LTE  ▂▄▆█  100%  │
    │  time  notifs  cell  wifi   batt   │
    └─────────────────────────────────────┘
"""

from theme import Colors, Typography, Spacing, Color
from widget import Widget, Size, EdgeInsets, Align, Direction, Event, EventType
from widgets import Container, Label, Spacer


class StatusBarWidget(Widget):
    """
    System status bar displayed at the top of every screen.
    """

    HEIGHT = 32

    def __init__(self):
        super().__init__()
        self.background = Colors.SURFACE_DIM
        self.min_height = self.HEIGHT

        # State
        self._time_str = "12:00"
        self._battery_pct = 100
        self._battery_charging = False
        self._wifi_strength = 3  # 0-4
        self._wifi_connected = True
        self._notification_count = 0
        self._carrier = ""

        self._build_ui()

    def _build_ui(self):
        self.clear_children()

        row = Container(direction=Direction.HORIZONTAL,
                        cross_align=Align.CENTER)
        row.padding = EdgeInsets.symmetric(horizontal=Spacing.SM)
        self.add_child(row)

        # Time (left)
        self._time_label = Label(
            self._time_str,
            style=Typography.LABEL_MEDIUM,
            color=Colors.TEXT_PRIMARY,
        )
        row.add_child(self._time_label)

        # Notification dots
        self._notif_label = Label(
            "",
            style=Typography.LABEL_SMALL,
            color=Colors.PRIMARY,
        )
        self._notif_label.padding = EdgeInsets.symmetric(horizontal=Spacing.SM)
        row.add_child(self._notif_label)

        # Center spacer
        row.add_child(Spacer())

        # WiFi indicator
        self._wifi_label = Label(
            self._wifi_icon(),
            style=Typography.LABEL_SMALL,
            color=Colors.TEXT_SECONDARY,
        )
        self._wifi_label.padding = EdgeInsets.symmetric(horizontal=Spacing.XS)
        row.add_child(self._wifi_label)

        # Battery
        self._battery_label = Label(
            self._battery_text(),
            style=Typography.LABEL_SMALL,
            color=self._battery_color(),
        )
        row.add_child(self._battery_label)

    # --- Public API ---

    def update_time(self, time_str: str):
        self._time_str = time_str
        self._time_label.text = time_str
        self.mark_dirty()

    def update_battery(self, pct: int, charging: bool = False):
        self._battery_pct = max(0, min(100, pct))
        self._battery_charging = charging
        self._battery_label.text = self._battery_text()
        self._battery_label.color = self._battery_color()
        self.mark_dirty()

    def update_wifi(self, strength: int, connected: bool = True):
        self._wifi_strength = max(0, min(4, strength))
        self._wifi_connected = connected
        self._wifi_label.text = self._wifi_icon()
        self._wifi_label.color = (Colors.TEXT_PRIMARY if connected
                                   else Colors.TEXT_DISABLED)
        self.mark_dirty()

    def update_notifications(self, count: int):
        self._notification_count = count
        if count > 0:
            self._notif_label.text = "." * min(count, 5)
        else:
            self._notif_label.text = ""
        self.mark_dirty()

    # --- Display Helpers ---

    def _wifi_icon(self) -> str:
        """ASCII WiFi signal indicator."""
        if not self._wifi_connected:
            return "WiFi OFF"
        bars = ["_", ".", ":", "|"]
        active = self._wifi_strength
        return "".join(bars[i] if i < active else " " for i in range(4))

    def _battery_text(self) -> str:
        prefix = "+" if self._battery_charging else ""
        return f"{prefix}{self._battery_pct}%"

    def _battery_color(self) -> Color:
        if self._battery_charging:
            return Colors.SUCCESS
        if self._battery_pct <= 15:
            return Colors.ERROR
        if self._battery_pct <= 30:
            return Colors.WARNING
        return Colors.TEXT_SECONDARY

    def measure(self, max_w: int, max_h: int) -> Size:
        return Size(max_w, self.HEIGHT)

    def get_state(self) -> dict:
        return {
            "time": self._time_str,
            "battery": self._battery_pct,
            "charging": self._battery_charging,
            "wifi_strength": self._wifi_strength,
            "wifi_connected": self._wifi_connected,
            "notifications": self._notification_count,
        }
