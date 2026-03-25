"""
Status bar view — system indicators at the top of the screen.

Renders the status bar with clock, Dynamic Island notch,
battery indicator, WiFi signal, and notification badge.
"""

import time

from ui.widgets.base import Container, Size, Widget
from ui.widgets.text import Label
from ui.widgets.layout import VStack, HStack, Spacer, Padding


class BatteryIcon(Widget):
    """A simple battery level indicator."""

    def __init__(self, level: int = 100, charging: bool = False,
                 color: str = "#34C759", width: int = 25, height: int = 12):
        super().__init__()
        self._level = level
        self._charging = charging
        self._color = color
        self._icon_w = width
        self._icon_h = height

    def measure(self, max_width, max_height):
        return Size(self._icon_w + 3, self._icon_h)

    def render(self, ctx):
        if not self.visible:
            return
        x, y = self.bounds.x, self.bounds.y
        w, h = self._icon_w, self._icon_h

        ctx.save()
        # Battery outline
        r, g, b, a = self._parse_color("#8E8E9E")
        ctx.set_source_rgba(r, g, b, a)
        ctx.set_line_width(1.0)
        self._rounded_rect(ctx, x, y, w, h, 2)
        ctx.stroke()

        # Battery nub
        nub_h = h // 3
        ctx.rectangle(x + w, y + (h - nub_h) // 2, 2, nub_h)
        ctx.fill()

        # Fill level
        fill_w = max(1, int((w - 4) * self._level / 100))
        r, g, b, a = self._parse_color(self._color)
        ctx.set_source_rgba(r, g, b, a)
        self._rounded_rect(ctx, x + 2, y + 2, fill_w, h - 4, 1)
        ctx.fill()

        ctx.restore()


class WifiIcon(Widget):
    """A simple WiFi signal indicator with bars."""

    def __init__(self, strength: int = 0, connected: bool = False,
                 color: str = "#5A5A72", size: int = 16):
        super().__init__()
        self._strength = strength  # 0-4
        self._connected = connected
        self._color = color
        self._size = size

    def measure(self, max_width, max_height):
        return Size(self._size, self._size)

    def render(self, ctx):
        if not self.visible:
            return
        x, y = self.bounds.x, self.bounds.y
        s = self._size

        ctx.save()
        bar_count = 4
        bar_w = max(2, s // (bar_count * 2))
        gap = bar_w
        total_w = bar_count * bar_w + (bar_count - 1) * gap

        start_x = x + (s - total_w) // 2

        for i in range(bar_count):
            bar_h = int(s * (i + 1) / bar_count * 0.8)
            bx = start_x + i * (bar_w + gap)
            by = y + s - bar_h

            if self._connected and i < self._strength:
                r, g, b, a = self._parse_color(self._color)
            else:
                r, g, b, a = self._parse_color("#D0D0D0")

            ctx.set_source_rgba(r, g, b, a)
            self._rounded_rect(ctx, bx, by, bar_w, bar_h, 1)
            ctx.fill()

        ctx.restore()


class DynamicIslandView(Container):
    """The Dynamic Island-style notch/pill in the center of the status bar."""

    def __init__(self, width: int = 162, height: int = 37, radius: int = 19):
        super().__init__()
        self._island_w = width
        self._island_h = height
        self._island_r = radius
        self.expanded = False
        self.content_type = ""
        self.title = ""

        theme = self.theme
        colors = theme.colors if theme else None
        self.background = colors.navy if colors else "#1A1A2E"
        self.corner_radius = radius

    def measure(self, max_width, max_height):
        w = self._island_w
        if self.expanded:
            w = min(int(max_width * 0.8), w * 2)
        return Size(w, self._island_h)


class StatusBarView(Container):
    """
    Full-width status bar at the top of the screen.

    Layout: [time] ... [Dynamic Island] ... [battery wifi badge]
    """

    def __init__(self, width: int, height: int = 54):
        super().__init__()
        self._bar_w = width
        self._bar_h = height

        # State
        self.time_str = time.strftime("%H:%M")
        self.battery_level = 100
        self.battery_charging = False
        self.wifi_connected = True
        self.wifi_strength = 4  # 0-4
        self.notification_count = 0

        self._time_label = None
        self._battery_icon = None
        self._wifi_icon = None
        self._badge_label = None
        self._island = None

        self._build()

    def _build(self):
        theme = self.theme
        colors = theme.colors if theme else None
        spacing = theme.spacing if theme else None
        layout_m = theme.layout if theme else None

        self.background = colors.statusbar_background if colors else "rgba(250,246,241,0.85)"

        bar = HStack(
            spacing=spacing.statusbar_item_gap if spacing else 6,
            padding=spacing.statusbar_padding_h if spacing else 16,
        )

        # Left: time
        self._time_label = Label(
            text=self.time_str,
            font_size=15.0,
            weight="bold",
            color=colors.statusbar_text if colors else "#1A1A2E",
        )
        bar.add(self._time_label)
        bar.add(Spacer())

        # Center: Dynamic Island
        self._island = DynamicIslandView(
            width=layout_m.statusbar_notch_width if layout_m else 162,
            height=layout_m.statusbar_notch_height if layout_m else 37,
            radius=layout_m.statusbar_notch_radius if layout_m else 19,
        )
        bar.add(self._island)
        bar.add(Spacer())

        # Right: battery + wifi + badge
        right = HStack(spacing=spacing.statusbar_item_gap if spacing else 6)

        self._wifi_icon = WifiIcon(
            strength=self.wifi_strength,
            connected=self.wifi_connected,
            color=colors.statusbar_icon if colors else "#5A5A72",
        )
        right.add(self._wifi_icon)

        bat_color = colors.battery_good if colors else "#34C759"
        self._battery_icon = BatteryIcon(
            level=self.battery_level,
            charging=self.battery_charging,
            color=bat_color,
        )
        right.add(self._battery_icon)

        if self.notification_count > 0:
            self._badge_label = Label(
                text=str(self.notification_count),
                font_size=10.0,
                weight="bold",
                color=colors.text_on_accent if colors else "#FFFFFF",
            )
            right.add(self._badge_label)

        bar.add(right)
        self.add(bar)

    def update(self):
        """Refresh time and indicator state."""
        self.time_str = time.strftime("%H:%M")
        if self._time_label:
            self._time_label.text = self.time_str
        if self._battery_icon:
            self._battery_icon._level = self.battery_level
            self._battery_icon._charging = self.battery_charging
        if self._wifi_icon:
            self._wifi_icon._strength = self.wifi_strength
            self._wifi_icon._connected = self.wifi_connected

    def measure(self, max_width, max_height):
        return Size(self._bar_w, self._bar_h)

    def layout(self, x, y, width, height):
        super().layout(x, y, width, height)
        if self.children:
            self.children[0].layout(x, y, width, height)
