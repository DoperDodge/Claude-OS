"""
Text widgets: Label and TextInput.

Uses Cairo's toy text API for font rendering. For production use,
Pango integration would provide proper text shaping, line breaking,
and RTL support.
"""

from __future__ import annotations

import time
from typing import Callable

from ui.widgets.base import Widget, Size, Rect, TouchEvent, TouchAction


class Label(Widget):
    """
    Single or multi-line text label.

    Renders text with theme-aware font, size, color, and alignment.
    """

    def __init__(self, text: str = "", font_size: float = 17.0,
                 color: str | None = None, weight: str = "normal",
                 align: str = "left", max_lines: int = 0):
        super().__init__()
        self.text = text
        self.font_size = font_size
        self.color = color  # None = use theme text_primary
        self.weight = weight  # "normal" or "bold"
        self.align = align  # "left", "center", "right"
        self.max_lines = max_lines  # 0 = unlimited

        # Cached measurements
        self._measured_width = 0
        self._measured_height = 0
        self._lines: list[str] = []

    def measure(self, max_width: int, max_height: int) -> Size:
        """Measure text to determine required size."""
        if not self.text:
            return Size(0, int(self.font_size * 1.3))

        # Estimate line height
        line_height = int(self.font_size * 1.3)

        # Simple word-wrap calculation
        self._lines = self._wrap_text(self.text, max_width)
        if self.max_lines > 0:
            self._lines = self._lines[:self.max_lines]

        self._measured_height = len(self._lines) * line_height
        # Width is the longest line (estimated at ~0.6 * font_size per char)
        char_width = self.font_size * 0.6
        self._measured_width = min(
            max_width,
            max(int(len(line) * char_width) for line in self._lines) if self._lines else 0
        )

        return Size(self._measured_width, self._measured_height)

    def _wrap_text(self, text: str, max_width: int) -> list[str]:
        """Simple word-wrap. Returns list of lines."""
        if max_width <= 0:
            return [text]

        char_width = self.font_size * 0.6
        chars_per_line = max(1, int(max_width / char_width))

        lines = []
        for paragraph in text.split("\n"):
            if not paragraph:
                lines.append("")
                continue

            words = paragraph.split()
            current_line = ""
            for word in words:
                test = f"{current_line} {word}".strip()
                if len(test) <= chars_per_line:
                    current_line = test
                else:
                    if current_line:
                        lines.append(current_line)
                    current_line = word
            if current_line:
                lines.append(current_line)

        return lines or [""]

    def render(self, ctx):
        """Render text using Cairo."""
        if not self.visible or not self.text:
            return

        theme = self.theme
        colors = theme.colors if theme else None

        # Set font
        try:
            import cairo as _cairo
            font_weight = (_cairo.FONT_WEIGHT_BOLD if self.weight == "bold"
                          else _cairo.FONT_WEIGHT_NORMAL)
            ctx.select_font_face("sans-serif", _cairo.FONT_SLANT_NORMAL, font_weight)
        except ImportError:
            pass

        ctx.set_font_size(self.font_size)

        # Set color
        color_str = self.color or (colors.text_primary if colors else "#1A1A2E")
        r, g, b, a = self._parse_color(color_str)
        ctx.set_source_rgba(r, g, b, a * self.opacity)

        line_height = int(self.font_size * 1.3)
        lines = self._lines if self._lines else [self.text]

        for i, line in enumerate(lines):
            if not line:
                continue

            y = self.bounds.y + (i + 1) * line_height - int(self.font_size * 0.2)

            if self.align == "center":
                extents = ctx.text_extents(line)
                x = self.bounds.x + (self.bounds.width - extents.width) / 2
            elif self.align == "right":
                extents = ctx.text_extents(line)
                x = self.bounds.x + self.bounds.width - extents.width
            else:
                x = self.bounds.x

            ctx.move_to(x, y)
            ctx.show_text(line)


class TextInput(Widget):
    """
    Single-line text input field with cursor.

    Renders a rounded rectangle with text, cursor blink,
    and placeholder text when empty.
    """

    def __init__(self, placeholder: str = "", font_size: float = 17.0,
                 height: int = 48, corner_radius: int = 24,
                 on_change: Callable[[str], None] | None = None,
                 on_submit: Callable[[str], None] | None = None,
                 on_focus: Callable[[bool], None] | None = None):
        super().__init__()
        self.text = ""
        self.placeholder = placeholder
        self.font_size = font_size
        self.preferred_height = height
        self.corner_radius = corner_radius
        self.focused = False
        self.cursor_pos = 0

        # Callbacks
        self.on_change = on_change
        self.on_submit = on_submit
        self.on_focus = on_focus

        # Cursor blink
        self._cursor_visible = True
        self._cursor_blink_time = 0.0
        self._cursor_blink_rate = 0.53  # seconds

    def measure(self, max_width: int, max_height: int) -> Size:
        return Size(max_width, min(self.preferred_height, max_height))

    def insert_text(self, text: str):
        """Insert text at cursor position."""
        self.text = self.text[:self.cursor_pos] + text + self.text[self.cursor_pos:]
        self.cursor_pos += len(text)
        if self.on_change:
            self.on_change(self.text)

    def delete_back(self):
        """Delete character before cursor."""
        if self.cursor_pos > 0:
            self.text = self.text[:self.cursor_pos - 1] + self.text[self.cursor_pos:]
            self.cursor_pos -= 1
            if self.on_change:
                self.on_change(self.text)

    def submit(self):
        """Submit the current text."""
        if self.on_submit:
            self.on_submit(self.text)

    def render(self, ctx):
        """Render the text input field."""
        if not self.visible:
            return

        theme = self.theme
        colors = theme.colors if theme else None
        spacing = theme.spacing if theme else None

        b = self.bounds
        ctx.save()

        # Background
        bg_color = colors.surface if colors else "#FFFFFF"
        border_color = (colors.accent if self.focused else colors.separator) if colors else "#E0D6CC"

        r, g, b_c, a = self._parse_color(bg_color)
        self._rounded_rect(ctx, b.x, b.y, b.width, b.height, self.corner_radius)
        ctx.set_source_rgba(r, g, b_c, a)
        ctx.fill_preserve()

        # Border
        r, g, b_c, a = self._parse_color(border_color)
        ctx.set_source_rgba(r, g, b_c, a)
        ctx.set_line_width(2 if self.focused else 1)
        ctx.stroke()

        # Text area with padding
        pad_x = spacing.md if spacing else 16
        text_x = b.x + pad_x
        text_y = b.y + b.height / 2 + self.font_size * 0.35

        try:
            import cairo as _cairo
            ctx.select_font_face("sans-serif", _cairo.FONT_SLANT_NORMAL,
                                _cairo.FONT_WEIGHT_NORMAL)
        except ImportError:
            pass
        ctx.set_font_size(self.font_size)

        if self.text:
            # Render actual text
            color_str = colors.text_primary if colors else "#1A1A2E"
            r, g, b_c, a = self._parse_color(color_str)
            ctx.set_source_rgba(r, g, b_c, a)
            ctx.move_to(text_x, text_y)
            ctx.show_text(self.text)

            # Cursor
            if self.focused and self._should_show_cursor():
                # Measure text up to cursor
                before_cursor = self.text[:self.cursor_pos]
                extents = ctx.text_extents(before_cursor)
                cursor_x = text_x + extents.x_advance
                cursor_y_top = b.y + (b.height - self.font_size) / 2
                cursor_y_bot = cursor_y_top + self.font_size + 4

                color_str = colors.accent if colors else "#D4A574"
                r, g, b_c, a = self._parse_color(color_str)
                ctx.set_source_rgba(r, g, b_c, a)
                ctx.set_line_width(2)
                ctx.move_to(cursor_x, cursor_y_top)
                ctx.line_to(cursor_x, cursor_y_bot)
                ctx.stroke()
        else:
            # Placeholder text
            color_str = colors.text_tertiary if colors else "#8E8E9E"
            r, g, b_c, a = self._parse_color(color_str)
            ctx.set_source_rgba(r, g, b_c, a)
            ctx.move_to(text_x, text_y)
            ctx.show_text(self.placeholder)

            # Cursor at start when focused
            if self.focused and self._should_show_cursor():
                cursor_y_top = b.y + (b.height - self.font_size) / 2
                cursor_y_bot = cursor_y_top + self.font_size + 4
                color_str = colors.accent if colors else "#D4A574"
                r, g, b_c, a = self._parse_color(color_str)
                ctx.set_source_rgba(r, g, b_c, a)
                ctx.set_line_width(2)
                ctx.move_to(text_x, cursor_y_top)
                ctx.line_to(text_x, cursor_y_bot)
                ctx.stroke()

        ctx.restore()

    def _should_show_cursor(self) -> bool:
        """Blink cursor on/off."""
        now = time.monotonic()
        cycle = (now % (self._cursor_blink_rate * 2))
        return cycle < self._cursor_blink_rate

    def handle_touch(self, event: TouchEvent) -> bool:
        """Focus on tap."""
        if event.action == TouchAction.UP and self.bounds.contains(event.x, event.y):
            if not self.focused:
                self.focused = True
                self.cursor_pos = len(self.text)
                if self.on_focus:
                    self.on_focus(True)
            return True
        return False
