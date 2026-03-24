"""
Claude-OS Dynamic UI Generator

Allows Claude to create custom UI screens from structured data.
Instead of just text responses, Claude can generate interactive
views like calendars, checklists, timers, etc.

Claude returns a JSON schema describing the desired UI, and this
module renders it as a widget tree.

Supported dynamic views:
    - Checklist: Editable to-do list with checkboxes
    - Calendar: Simple month/week view with events
    - Info Panel: Key-value display (settings, device info)
    - Custom Form: Input fields with submit
"""

import time
from dataclasses import dataclass, field
from enum import Enum, auto
from typing import Callable

from theme import Colors, Typography, Spacing, Radius, Color
from widget import (
    Widget, Size, EdgeInsets, Align, Direction, Event, EventType,
    _fill_rect, _blit_text,
)
from widgets import Container, Label, Button, ScrollView, Divider, Spacer
from font import FontRenderer

_font = FontRenderer()


# --- Checklist View ---

@dataclass
class ChecklistItem:
    """A single checklist item."""
    text: str
    checked: bool = False
    id: int = 0


class ChecklistView(Widget):
    """
    An interactive checklist / to-do list.

    Claude can create this with: "Make a shopping list"
    Items can be checked/unchecked by tapping.
    """

    ITEM_HEIGHT = 36

    def __init__(self, title: str = "", items: list[ChecklistItem] = None,
                 on_change: Callable = None):
        super().__init__()
        self.title = title
        self.items = items or []
        self.on_change = on_change
        self.background = Colors.SURFACE_CONTAINER
        self.corner_radius = Radius.LG
        self.padding = EdgeInsets.all(Spacing.MD)
        self._next_id = 1
        for item in self.items:
            if item.id == 0:
                item.id = self._next_id
                self._next_id += 1

    def add_item(self, text: str, checked: bool = False) -> ChecklistItem:
        item = ChecklistItem(text=text, checked=checked, id=self._next_id)
        self._next_id += 1
        self.items.append(item)
        self.mark_dirty()
        return item

    def remove_item(self, item_id: int):
        self.items = [i for i in self.items if i.id != item_id]
        self.mark_dirty()

    def toggle_item(self, item_id: int):
        for item in self.items:
            if item.id == item_id:
                item.checked = not item.checked
                if self.on_change:
                    self.on_change(item)
                self.mark_dirty()
                return

    @property
    def checked_count(self) -> int:
        return sum(1 for i in self.items if i.checked)

    @property
    def total_count(self) -> int:
        return len(self.items)

    @property
    def progress(self) -> float:
        if not self.items:
            return 1.0
        return self.checked_count / self.total_count

    def measure(self, max_w: int, max_h: int) -> Size:
        title_h = Typography.TITLE_MEDIUM.line_height + 8 if self.title else 0
        progress_h = 20  # Progress bar
        items_h = len(self.items) * self.ITEM_HEIGHT
        h = title_h + progress_h + items_h + self.padding.vertical
        return Size(max(self.min_width, min(max_w, max_w)),
                    max(self.min_height, min(h, max_h)))

    def draw_content(self, buf: bytearray, buf_w: int, buf_h: int,
                     abs_x: int, abs_y: int):
        y = abs_y + self.padding.top
        left = abs_x + self.padding.left
        cw = self.content_width

        # Title + count
        if self.title:
            title_text = f"{self.title} ({self.checked_count}/{self.total_count})"
            rt = _font.render_text(title_text, Typography.TITLE_MEDIUM,
                                   Colors.TEXT_PRIMARY)
            if rt.data:
                _blit_text(buf, buf_w, buf_h, left, y,
                           rt.data, rt.width, rt.height, rt.stride)
            y += Typography.TITLE_MEDIUM.line_height + 4

        # Progress bar
        bar_h = 6
        bar_w = cw
        _fill_rect(buf, buf_w, buf_h, left, y, bar_w, bar_h,
                   Colors.SURFACE_BRIGHT)
        filled_w = int(bar_w * self.progress)
        if filled_w > 0:
            _fill_rect(buf, buf_w, buf_h, left, y, filled_w, bar_h,
                       Colors.SUCCESS)
        y += bar_h + 10

        # Items
        for item in self.items:
            # Checkbox
            box_size = 18
            box_x = left
            box_y = y + (self.ITEM_HEIGHT - box_size) // 2
            border_color = Colors.SUCCESS if item.checked else Colors.BORDER
            _fill_rect(buf, buf_w, buf_h, box_x, box_y,
                       box_size, box_size, border_color)
            _fill_rect(buf, buf_w, buf_h,
                       box_x + 2, box_y + 2,
                       box_size - 4, box_size - 4,
                       Colors.SUCCESS if item.checked else Colors.SURFACE_CONTAINER)

            if item.checked:
                # Draw checkmark as a small filled center
                _fill_rect(buf, buf_w, buf_h,
                           box_x + 4, box_y + 4,
                           box_size - 8, box_size - 8,
                           Colors.SUCCESS)

            # Text
            text_color = Colors.TEXT_DISABLED if item.checked else Colors.TEXT_PRIMARY
            text_x = left + box_size + Spacing.SM
            text_y = y + (self.ITEM_HEIGHT - Typography.BODY_MEDIUM.line_height) // 2
            rt = _font.render_text(item.text, Typography.BODY_MEDIUM, text_color)
            if rt.data:
                _blit_text(buf, buf_w, buf_h, text_x, text_y,
                           rt.data, rt.width, rt.height, rt.stride)

            y += self.ITEM_HEIGHT

    def _handle_event(self, event_type: EventType, x: int, y: int,
                      key_code: int) -> bool:
        if event_type == EventType.TOUCH_UP:
            # Determine which item was tapped
            title_h = (Typography.TITLE_MEDIUM.line_height + 8) if self.title else 0
            progress_h = 16
            items_start = self.padding.top + title_h + progress_h
            idx = (y - items_start) // self.ITEM_HEIGHT
            if 0 <= idx < len(self.items):
                self.toggle_item(self.items[idx].id)
                return True
        return False


# --- Calendar View ---

WEEKDAYS = ["Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"]
MONTHS = ["", "January", "February", "March", "April", "May", "June",
          "July", "August", "September", "October", "November", "December"]


@dataclass
class CalendarEvent:
    """An event on the calendar."""
    day: int
    title: str
    color: Color = None


class CalendarView(Widget):
    """
    Simple month calendar view.

    Shows a month grid with highlighted event days.
    """

    CELL_SIZE = 36
    HEADER_HEIGHT = 40

    def __init__(self, year: int = 2026, month: int = 1,
                 events: list[CalendarEvent] = None,
                 on_day_tap: Callable = None):
        super().__init__()
        self.year = year
        self.month = month
        self.events = events or []
        self.on_day_tap = on_day_tap
        self.today: int = 0
        self.background = Colors.SURFACE_CONTAINER
        self.corner_radius = Radius.LG
        self.padding = EdgeInsets.all(Spacing.SM)
        self._days_in_month = self._get_days_in_month()
        self._first_weekday = self._get_first_weekday()

    def _get_days_in_month(self) -> int:
        if self.month in (1, 3, 5, 7, 8, 10, 12):
            return 31
        elif self.month in (4, 6, 9, 11):
            return 30
        elif self.month == 2:
            if (self.year % 4 == 0 and self.year % 100 != 0) or self.year % 400 == 0:
                return 29
            return 28
        return 30

    def _get_first_weekday(self) -> int:
        """Get weekday of first day (0=Mon, 6=Sun). Zeller's formula."""
        y, m = self.year, self.month
        if m < 3:
            m += 12
            y -= 1
        k = y % 100
        j = y // 100
        h = (1 + (13 * (m + 1)) // 5 + k + k // 4 + j // 4 - 2 * j) % 7
        # Convert from Zeller (0=Sat) to Mon=0
        return (h + 5) % 7

    def set_month(self, year: int, month: int):
        self.year = year
        self.month = month
        self._days_in_month = self._get_days_in_month()
        self._first_weekday = self._get_first_weekday()
        self.mark_dirty()

    def _event_days(self) -> dict[int, CalendarEvent]:
        return {e.day: e for e in self.events}

    def measure(self, max_w: int, max_h: int) -> Size:
        rows = (self._first_weekday + self._days_in_month + 6) // 7
        h = (self.HEADER_HEIGHT + 24 +  # Title + weekday headers
             rows * self.CELL_SIZE + self.padding.vertical)
        w = 7 * self.CELL_SIZE + self.padding.horizontal
        return Size(max(self.min_width, min(w, max_w)),
                    max(self.min_height, min(h, max_h)))

    def draw_content(self, buf: bytearray, buf_w: int, buf_h: int,
                     abs_x: int, abs_y: int):
        y = abs_y + self.padding.top
        left = abs_x + self.padding.left
        event_days = self._event_days()

        # Month/year title
        title = f"{MONTHS[self.month]} {self.year}"
        rt = _font.render_text(title, Typography.TITLE_MEDIUM, Colors.TEXT_PRIMARY)
        if rt.data:
            _blit_text(buf, buf_w, buf_h, left, y,
                       rt.data, rt.width, rt.height, rt.stride)
        y += self.HEADER_HEIGHT

        # Weekday headers
        for i, day_name in enumerate(WEEKDAYS):
            dx = left + i * self.CELL_SIZE
            rt = _font.render_text(day_name[:2], Typography.LABEL_SMALL,
                                   Colors.TEXT_DISABLED)
            if rt.data:
                _blit_text(buf, buf_w, buf_h, dx + 8, y,
                           rt.data, rt.width, rt.height, rt.stride)
        y += 24

        # Day grid
        col = self._first_weekday
        for day in range(1, self._days_in_month + 1):
            dx = left + col * self.CELL_SIZE
            dy = y

            # Highlight today
            if day == self.today:
                _fill_rect(buf, buf_w, buf_h,
                           dx + 2, dy + 2,
                           self.CELL_SIZE - 4, self.CELL_SIZE - 4,
                           Colors.PRIMARY)

            # Event dot
            if day in event_days:
                event = event_days[day]
                dot_color = event.color or Colors.PRIMARY_LIGHT
                _fill_rect(buf, buf_w, buf_h,
                           dx + self.CELL_SIZE // 2 - 2,
                           dy + self.CELL_SIZE - 8,
                           4, 4, dot_color)

            # Day number
            text_color = Colors.TEXT_ON_PRIMARY if day == self.today else Colors.TEXT_PRIMARY
            rt = _font.render_text(str(day), Typography.BODY_SMALL, text_color)
            if rt.data:
                tx = dx + (self.CELL_SIZE - rt.width) // 2
                ty = dy + (self.CELL_SIZE - rt.height) // 2 - 2
                _blit_text(buf, buf_w, buf_h, tx, ty,
                           rt.data, rt.width, rt.height, rt.stride)

            col += 1
            if col >= 7:
                col = 0
                y += self.CELL_SIZE

    def _handle_event(self, event_type: EventType, x: int, y: int,
                      key_code: int) -> bool:
        if event_type == EventType.TOUCH_UP and self.on_day_tap:
            # Calculate which day was tapped
            header_h = self.HEADER_HEIGHT + 24 + self.padding.top
            if y < header_h:
                return False
            row = (y - header_h) // self.CELL_SIZE
            col = (x - self.padding.left) // self.CELL_SIZE
            if 0 <= col < 7:
                day_idx = row * 7 + col - self._first_weekday + 1
                if 1 <= day_idx <= self._days_in_month:
                    self.on_day_tap(day_idx)
                    return True
        return False


# --- Info Panel ---

@dataclass
class InfoRow:
    """A key-value pair for display."""
    key: str
    value: str
    icon: str = ""


class InfoPanel(Widget):
    """
    Key-value display panel for structured information.

    Used for: device info, settings summary, status displays.
    """

    ROW_HEIGHT = 32

    def __init__(self, title: str = "", rows: list[InfoRow] = None):
        super().__init__()
        self.title = title
        self.rows = rows or []
        self.background = Colors.SURFACE_CONTAINER
        self.corner_radius = Radius.LG
        self.padding = EdgeInsets.all(Spacing.MD)

    def add_row(self, key: str, value: str, icon: str = "") -> InfoRow:
        row = InfoRow(key=key, value=value, icon=icon)
        self.rows.append(row)
        self.mark_dirty()
        return row

    def set_value(self, key: str, value: str):
        for row in self.rows:
            if row.key == key:
                row.value = value
                self.mark_dirty()
                return

    def measure(self, max_w: int, max_h: int) -> Size:
        title_h = Typography.TITLE_MEDIUM.line_height + 8 if self.title else 0
        rows_h = len(self.rows) * self.ROW_HEIGHT
        h = title_h + rows_h + self.padding.vertical
        return Size(max(self.min_width, min(max_w, max_w)),
                    max(self.min_height, min(h, max_h)))

    def draw_content(self, buf: bytearray, buf_w: int, buf_h: int,
                     abs_x: int, abs_y: int):
        y = abs_y + self.padding.top
        left = abs_x + self.padding.left
        cw = self.content_width

        if self.title:
            rt = _font.render_text(self.title, Typography.TITLE_MEDIUM,
                                   Colors.TEXT_PRIMARY)
            if rt.data:
                _blit_text(buf, buf_w, buf_h, left, y,
                           rt.data, rt.width, rt.height, rt.stride)
            y += Typography.TITLE_MEDIUM.line_height + 8

        for row in self.rows:
            # Key (left-aligned)
            key_text = row.key
            if row.icon:
                key_text = f"{row.icon} {key_text}"
            krt = _font.render_text(key_text, Typography.BODY_MEDIUM,
                                    Colors.TEXT_SECONDARY)
            if krt.data:
                _blit_text(buf, buf_w, buf_h, left, y + 6,
                           krt.data, krt.width, krt.height, krt.stride)

            # Value (right-aligned)
            vrt = _font.render_text(row.value, Typography.BODY_MEDIUM,
                                    Colors.TEXT_PRIMARY)
            if vrt.data:
                vx = abs_x + self.width - self.padding.right - vrt.width
                _blit_text(buf, buf_w, buf_h, vx, y + 6,
                           vrt.data, vrt.width, vrt.height, vrt.stride)

            y += self.ROW_HEIGHT


# --- Custom Form ---

@dataclass
class FormField:
    """A form input field definition."""
    name: str
    label: str
    field_type: str = "text"  # "text", "number", "toggle"
    value: str = ""
    placeholder: str = ""


class FormView(Widget):
    """
    A dynamic form with input fields and a submit button.

    Claude can use this for: "Set a reminder", "Create a note", etc.
    """

    FIELD_HEIGHT = 44

    def __init__(self, title: str = "", fields: list[FormField] = None,
                 submit_label: str = "Submit",
                 on_submit: Callable = None):
        super().__init__()
        self.title = title
        self.fields = fields or []
        self.submit_label = submit_label
        self.on_submit = on_submit
        self.background = Colors.SURFACE_CONTAINER
        self.corner_radius = Radius.LG
        self.padding = EdgeInsets.all(Spacing.MD)

    def add_field(self, name: str, label: str, field_type: str = "text",
                  placeholder: str = "") -> FormField:
        f = FormField(name=name, label=label, field_type=field_type,
                      placeholder=placeholder)
        self.fields.append(f)
        self.mark_dirty()
        return f

    def get_values(self) -> dict[str, str]:
        return {f.name: f.value for f in self.fields}

    def set_value(self, name: str, value: str):
        for f in self.fields:
            if f.name == name:
                f.value = value
                self.mark_dirty()
                return

    def submit(self):
        if self.on_submit:
            self.on_submit(self.get_values())

    def measure(self, max_w: int, max_h: int) -> Size:
        title_h = Typography.TITLE_MEDIUM.line_height + 8 if self.title else 0
        fields_h = len(self.fields) * (self.FIELD_HEIGHT + 4)
        button_h = 44 + 8
        h = title_h + fields_h + button_h + self.padding.vertical
        return Size(max(self.min_width, min(max_w, max_w)),
                    max(self.min_height, min(h, max_h)))

    def draw_content(self, buf: bytearray, buf_w: int, buf_h: int,
                     abs_x: int, abs_y: int):
        y = abs_y + self.padding.top
        left = abs_x + self.padding.left
        cw = self.content_width

        if self.title:
            rt = _font.render_text(self.title, Typography.TITLE_MEDIUM,
                                   Colors.TEXT_PRIMARY)
            if rt.data:
                _blit_text(buf, buf_w, buf_h, left, y,
                           rt.data, rt.width, rt.height, rt.stride)
            y += Typography.TITLE_MEDIUM.line_height + 8

        for fld in self.fields:
            # Label
            lrt = _font.render_text(fld.label, Typography.LABEL_MEDIUM,
                                    Colors.TEXT_SECONDARY)
            if lrt.data:
                _blit_text(buf, buf_w, buf_h, left, y,
                           lrt.data, lrt.width, lrt.height, lrt.stride)
            y += Typography.LABEL_MEDIUM.line_height + 2

            # Input field background
            _fill_rect(buf, buf_w, buf_h,
                       left, y, cw, 28, Colors.SURFACE_BRIGHT)

            # Value or placeholder
            display = fld.value or fld.placeholder
            color = Colors.TEXT_PRIMARY if fld.value else Colors.TEXT_DISABLED
            vrt = _font.render_text(display, Typography.BODY_MEDIUM, color)
            if vrt.data:
                _blit_text(buf, buf_w, buf_h, left + 8, y + 4,
                           vrt.data, vrt.width, vrt.height, vrt.stride)
            y += 32

        # Submit button
        y += 8
        btn_w = min(cw, 150)
        _fill_rect(buf, buf_w, buf_h,
                   left + (cw - btn_w) // 2, y, btn_w, 36, Colors.PRIMARY)
        srt = _font.render_text(self.submit_label, Typography.LABEL_LARGE,
                                Colors.TEXT_ON_PRIMARY)
        if srt.data:
            sx = left + (cw - srt.width) // 2
            sy = y + (36 - srt.height) // 2
            _blit_text(buf, buf_w, buf_h, sx, sy,
                       srt.data, srt.width, srt.height, srt.stride)

    def _handle_event(self, event_type: EventType, x: int, y: int,
                      key_code: int) -> bool:
        if event_type == EventType.TOUCH_UP:
            # Check if submit button area was tapped
            title_h = (Typography.TITLE_MEDIUM.line_height + 8) if self.title else 0
            fields_h = len(self.fields) * (self.FIELD_HEIGHT + 4)
            btn_y = self.padding.top + title_h + fields_h + 8
            if y >= btn_y and y <= btn_y + 36:
                self.submit()
                return True
        return False


# --- Dynamic View Builder ---

class DynamicViewBuilder:
    """
    Builds widget trees from JSON-like data structures.

    Claude returns a view spec as part of its response, and this
    builder turns it into a renderable widget.

    Supported view types:
        - "checklist": {title, items: [{text, checked}]}
        - "calendar": {year, month, events: [{day, title}], today}
        - "info": {title, rows: [{key, value}]}
        - "form": {title, fields: [{name, label, type}], submit_label}
    """

    def build(self, spec: dict, callbacks: dict = None) -> Widget | None:
        """
        Build a widget from a view specification.

        Args:
            spec: View specification dict with "type" key
            callbacks: Optional callbacks dict (e.g., {"on_submit": fn})

        Returns:
            A Widget instance, or None if spec is invalid.
        """
        callbacks = callbacks or {}
        view_type = spec.get("type", "")

        if view_type == "checklist":
            return self._build_checklist(spec, callbacks)
        elif view_type == "calendar":
            return self._build_calendar(spec, callbacks)
        elif view_type == "info":
            return self._build_info(spec)
        elif view_type == "form":
            return self._build_form(spec, callbacks)

        return None

    def _build_checklist(self, spec: dict, callbacks: dict) -> ChecklistView:
        items = [
            ChecklistItem(text=i.get("text", ""), checked=i.get("checked", False))
            for i in spec.get("items", [])
        ]
        return ChecklistView(
            title=spec.get("title", ""),
            items=items,
            on_change=callbacks.get("on_change"),
        )

    def _build_calendar(self, spec: dict, callbacks: dict) -> CalendarView:
        events = [
            CalendarEvent(
                day=e.get("day", 1),
                title=e.get("title", ""),
            )
            for e in spec.get("events", [])
        ]
        cal = CalendarView(
            year=spec.get("year", 2026),
            month=spec.get("month", 1),
            events=events,
            on_day_tap=callbacks.get("on_day_tap"),
        )
        cal.today = spec.get("today", 0)
        return cal

    def _build_info(self, spec: dict) -> InfoPanel:
        rows = [
            InfoRow(key=r.get("key", ""), value=r.get("value", ""),
                    icon=r.get("icon", ""))
            for r in spec.get("rows", [])
        ]
        return InfoPanel(title=spec.get("title", ""), rows=rows)

    def _build_form(self, spec: dict, callbacks: dict) -> FormView:
        fields = [
            FormField(
                name=f.get("name", ""),
                label=f.get("label", ""),
                field_type=f.get("type", "text"),
                placeholder=f.get("placeholder", ""),
            )
            for f in spec.get("fields", [])
        ]
        return FormView(
            title=spec.get("title", ""),
            fields=fields,
            submit_label=spec.get("submit_label", "Submit"),
            on_submit=callbacks.get("on_submit"),
        )
