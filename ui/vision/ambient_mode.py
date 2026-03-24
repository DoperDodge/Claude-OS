"""
Claude-OS Ambient Mode

A glanceable dashboard shown when the phone is idle.
Displays useful information at a glance without requiring interaction.

Widgets:
    - Clock (large digital display)
    - Weather summary
    - Next reminder/event
    - Recent notification count
    - Inspirational quote or tip

The dashboard updates periodically and transitions smoothly
between content sections.
"""

import time
from dataclasses import dataclass, field
from typing import Callable

from theme import Colors, Typography, Spacing, Radius, Color
from widget import (
    Widget, Size, EdgeInsets, Align, Direction, Event, EventType,
    _fill_rect, _blit_text,
)
from widgets import Container, Label, Spacer
from font import FontRenderer

_font = FontRenderer()


@dataclass
class WeatherData:
    """Weather information for the ambient display."""
    temperature: int = 72
    condition: str = "Sunny"
    high: int = 78
    low: int = 65
    location: str = ""


@dataclass
class ReminderData:
    """Upcoming reminder or event."""
    title: str = ""
    time_str: str = ""
    is_soon: bool = False


@dataclass
class AmbientState:
    """Current state of the ambient display."""
    weather: WeatherData = field(default_factory=WeatherData)
    next_reminder: ReminderData | None = None
    notification_count: int = 0
    quote: str = ""
    battery_percent: int = 100
    is_charging: bool = False


class AmbientClockWidget(Widget):
    """Large digital clock for the ambient display."""

    def __init__(self):
        super().__init__()
        self._time_str = "00:00"
        self._date_str = ""

    def update(self, time_str: str = None, date_str: str = None):
        if time_str is not None:
            self._time_str = time_str
        if date_str is not None:
            self._date_str = date_str
        self.mark_dirty()

    def measure(self, max_w: int, max_h: int) -> Size:
        return Size(max_w, 100)

    def draw_content(self, buf: bytearray, buf_w: int, buf_h: int,
                     abs_x: int, abs_y: int):
        # Large time
        time_rt = _font.render_text(
            self._time_str, Typography.DISPLAY_LARGE, Colors.TEXT_PRIMARY)
        if time_rt.data:
            tx = abs_x + (self.width - time_rt.width) // 2
            _blit_text(buf, buf_w, buf_h, tx, abs_y + 10,
                       time_rt.data, time_rt.width, time_rt.height,
                       time_rt.stride)

        # Date below
        if self._date_str:
            date_rt = _font.render_text(
                self._date_str, Typography.BODY_MEDIUM, Colors.TEXT_SECONDARY)
            if date_rt.data:
                dx = abs_x + (self.width - date_rt.width) // 2
                _blit_text(buf, buf_w, buf_h, dx, abs_y + 65,
                           date_rt.data, date_rt.width, date_rt.height,
                           date_rt.stride)


class WeatherWidget(Widget):
    """Weather summary card for ambient display."""

    def __init__(self):
        super().__init__()
        self.background = Colors.SURFACE_CONTAINER
        self.corner_radius = Radius.LG
        self.padding = EdgeInsets.all(Spacing.MD)
        self._weather = WeatherData()

    def update(self, weather: WeatherData):
        self._weather = weather
        self.mark_dirty()

    def measure(self, max_w: int, max_h: int) -> Size:
        return Size(max(self.min_width, min(max_w, max_w)), 80)

    def draw_content(self, buf: bytearray, buf_w: int, buf_h: int,
                     abs_x: int, abs_y: int):
        y = abs_y + self.padding.top
        left = abs_x + self.padding.left

        # Temperature (large)
        temp = f"{self._weather.temperature}F"
        temp_rt = _font.render_text(temp, Typography.HEADLINE_LARGE,
                                    Colors.TEXT_PRIMARY)
        if temp_rt.data:
            _blit_text(buf, buf_w, buf_h, left, y,
                       temp_rt.data, temp_rt.width, temp_rt.height,
                       temp_rt.stride)

        # Condition (next to temp)
        cond_rt = _font.render_text(
            self._weather.condition, Typography.BODY_MEDIUM,
            Colors.TEXT_SECONDARY)
        if cond_rt.data:
            cx = left + 90
            _blit_text(buf, buf_w, buf_h, cx, y + 4,
                       cond_rt.data, cond_rt.width, cond_rt.height,
                       cond_rt.stride)

        # High/Low
        hl = f"H:{self._weather.high} L:{self._weather.low}"
        hl_rt = _font.render_text(hl, Typography.BODY_SMALL,
                                  Colors.TEXT_DISABLED)
        if hl_rt.data:
            cx = left + 90
            _blit_text(buf, buf_w, buf_h, cx, y + 24,
                       hl_rt.data, hl_rt.width, hl_rt.height,
                       hl_rt.stride)

        # Location
        if self._weather.location:
            loc_rt = _font.render_text(
                self._weather.location, Typography.LABEL_SMALL,
                Colors.TEXT_DISABLED)
            if loc_rt.data:
                lx = abs_x + self.width - self.padding.right - loc_rt.width
                _blit_text(buf, buf_w, buf_h, lx, y,
                           loc_rt.data, loc_rt.width, loc_rt.height,
                           loc_rt.stride)


class ReminderWidget(Widget):
    """Displays the next upcoming reminder/event."""

    def __init__(self):
        super().__init__()
        self.background = Colors.SURFACE_CONTAINER
        self.corner_radius = Radius.LG
        self.padding = EdgeInsets.all(Spacing.MD)
        self._reminder: ReminderData | None = None

    def update(self, reminder: ReminderData | None):
        self._reminder = reminder
        self.mark_dirty()

    @property
    def has_reminder(self) -> bool:
        return self._reminder is not None and bool(self._reminder.title)

    def measure(self, max_w: int, max_h: int) -> Size:
        return Size(max(self.min_width, min(max_w, max_w)), 56)

    def draw_content(self, buf: bytearray, buf_w: int, buf_h: int,
                     abs_x: int, abs_y: int):
        if not self._reminder:
            return

        y = abs_y + self.padding.top
        left = abs_x + self.padding.left

        # "Next:" label
        label_color = Colors.WARNING if self._reminder.is_soon else Colors.TEXT_DISABLED
        label_rt = _font.render_text("Next:", Typography.LABEL_SMALL, label_color)
        if label_rt.data:
            _blit_text(buf, buf_w, buf_h, left, y,
                       label_rt.data, label_rt.width, label_rt.height,
                       label_rt.stride)

        # Title
        title_rt = _font.render_text(
            self._reminder.title, Typography.BODY_MEDIUM, Colors.TEXT_PRIMARY)
        if title_rt.data:
            _blit_text(buf, buf_w, buf_h, left, y + 18,
                       title_rt.data, title_rt.width, title_rt.height,
                       title_rt.stride)

        # Time
        if self._reminder.time_str:
            time_rt = _font.render_text(
                self._reminder.time_str, Typography.BODY_MEDIUM,
                Colors.PRIMARY_LIGHT)
            if time_rt.data:
                tx = abs_x + self.width - self.padding.right - time_rt.width
                _blit_text(buf, buf_w, buf_h, tx, y + 18,
                           time_rt.data, time_rt.width, time_rt.height,
                           time_rt.stride)


class QuoteWidget(Widget):
    """Displays an inspirational quote or tip."""

    def __init__(self):
        super().__init__()
        self._quote = ""
        self.padding = EdgeInsets.symmetric(horizontal=Spacing.LG, vertical=Spacing.SM)

    def update(self, quote: str):
        self._quote = quote
        self.mark_dirty()

    def measure(self, max_w: int, max_h: int) -> Size:
        if not self._quote:
            return Size(max_w, 0)
        rt = _font.render_wrapped(
            self._quote, Typography.BODY_SMALL, Colors.TEXT_DISABLED,
            max_w - self.padding.horizontal)
        return Size(max_w, rt.height + self.padding.vertical)

    def draw_content(self, buf: bytearray, buf_w: int, buf_h: int,
                     abs_x: int, abs_y: int):
        if not self._quote:
            return
        rt = _font.render_wrapped(
            self._quote, Typography.BODY_SMALL, Colors.TEXT_DISABLED,
            self.content_width)
        if rt.data:
            tx = abs_x + self.padding.left
            ty = abs_y + self.padding.top
            _blit_text(buf, buf_w, buf_h, tx, ty,
                       rt.data, rt.width, rt.height, rt.stride)


class AmbientDashboard(Widget):
    """
    The complete ambient mode dashboard.

    Composites all ambient widgets into a single view.
    Provides an update API for the system to push new data.
    """

    def __init__(self, on_tap_to_wake: Callable = None):
        super().__init__()
        self.background = Colors.BACKGROUND
        self.on_tap_to_wake = on_tap_to_wake
        self._state = AmbientState()
        self._active = False

        # Sub-widgets
        self._clock = AmbientClockWidget()
        self._weather = WeatherWidget()
        self._reminder = ReminderWidget()
        self._quote = QuoteWidget()

    def activate(self):
        """Enter ambient mode."""
        self._active = True
        self.update_time()
        self.mark_dirty()

    def deactivate(self):
        """Exit ambient mode."""
        self._active = False

    @property
    def is_active(self) -> bool:
        return self._active

    def update_time(self):
        """Update the clock display."""
        now = time.localtime()
        time_str = f"{now.tm_hour:02d}:{now.tm_min:02d}"
        days = ["Monday", "Tuesday", "Wednesday", "Thursday",
                "Friday", "Saturday", "Sunday"]
        months = ["Jan", "Feb", "Mar", "Apr", "May", "Jun",
                  "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"]
        date_str = f"{days[now.tm_wday]}, {months[now.tm_mon - 1]} {now.tm_mday}"
        self._clock.update(time_str, date_str)

    def update_state(self, state: AmbientState):
        """Update the full ambient state."""
        self._state = state
        self._weather.update(state.weather)
        if state.next_reminder:
            self._reminder.update(state.next_reminder)
        if state.quote:
            self._quote.update(state.quote)
        self.update_time()
        self.mark_dirty()

    def set_weather(self, weather: WeatherData):
        self._state.weather = weather
        self._weather.update(weather)
        self.mark_dirty()

    def set_reminder(self, reminder: ReminderData):
        self._state.next_reminder = reminder
        self._reminder.update(reminder)
        self.mark_dirty()

    def set_quote(self, quote: str):
        self._state.quote = quote
        self._quote.update(quote)
        self.mark_dirty()

    def measure(self, max_w: int, max_h: int) -> Size:
        return Size(max_w, max_h)

    def draw(self, buf: bytearray, buf_w: int, buf_h: int,
             ox: int = 0, oy: int = 0):
        if not self._active or not self.visible:
            return

        abs_x = ox + self.x
        abs_y = oy + self.y

        # Background
        _fill_rect(buf, buf_w, buf_h,
                   abs_x, abs_y, self.width, self.height,
                   Colors.BACKGROUND)

        # Layout sub-widgets vertically centered
        content_h = 100 + 8 + 80 + 8 + 56 + 8 + 40  # clock + gaps + weather + reminder + quote
        start_y = abs_y + max(40, (self.height - content_h) // 3)

        # Clock
        self._clock.layout(0, 0, self.width, 100)
        self._clock.draw(buf, buf_w, buf_h, abs_x, start_y)
        start_y += 100 + Spacing.LG

        # Weather
        margin = Spacing.LG
        self._weather.layout(margin, 0, self.width - 2 * margin, 80)
        self._weather.draw(buf, buf_w, buf_h, abs_x, start_y)
        start_y += 80 + Spacing.SM

        # Reminder
        if self._reminder.has_reminder:
            self._reminder.layout(margin, 0, self.width - 2 * margin, 56)
            self._reminder.draw(buf, buf_w, buf_h, abs_x, start_y)
            start_y += 56 + Spacing.SM

        # Quote (bottom area)
        if self._state.quote:
            self._quote.layout(0, 0, self.width, 60)
            self._quote.draw(buf, buf_w, buf_h,
                             abs_x, abs_y + self.height - 80)

        # Notification count badge
        if self._state.notification_count > 0:
            count_text = str(self._state.notification_count)
            count_rt = _font.render_text(
                count_text, Typography.LABEL_SMALL, Colors.TEXT_ON_PRIMARY)
            if count_rt.data:
                badge_w = max(20, count_rt.width + 10)
                badge_x = abs_x + self.width - badge_w - Spacing.MD
                badge_y = abs_y + Spacing.MD
                _fill_rect(buf, buf_w, buf_h,
                           badge_x, badge_y, badge_w, 20,
                           Colors.PRIMARY)
                _blit_text(buf, buf_w, buf_h,
                           badge_x + (badge_w - count_rt.width) // 2,
                           badge_y + 3,
                           count_rt.data, count_rt.width, count_rt.height,
                           count_rt.stride)

        # Battery indicator
        batt_text = f"{self._state.battery_percent}%"
        if self._state.is_charging:
            batt_text += "+"
        batt_rt = _font.render_text(
            batt_text, Typography.LABEL_SMALL, Colors.TEXT_DISABLED)
        if batt_rt.data:
            bx = abs_x + Spacing.MD
            by = abs_y + Spacing.MD
            _blit_text(buf, buf_w, buf_h, bx, by,
                       batt_rt.data, batt_rt.width, batt_rt.height,
                       batt_rt.stride)

    def _handle_event(self, event_type: EventType, x: int, y: int,
                      key_code: int) -> bool:
        if event_type == EventType.TOUCH_DOWN:
            if self.on_tap_to_wake:
                self.on_tap_to_wake()
            return True
        return False
