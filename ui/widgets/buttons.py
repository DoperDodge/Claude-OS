"""
Button widgets for Claude-OS.

Supports themed buttons with press feedback, icons, and callbacks.
"""

from __future__ import annotations

from typing import Callable

from ui.widgets.base import Widget, Size, Rect, TouchEvent, TouchAction


class Button(Widget):
    """
    A pressable button with label text.

    Renders a rounded rectangle with centered text. Shows visual
    feedback (color change) when pressed.
    """

    def __init__(self, label: str = "", on_press: Callable | None = None,
                 style: str = "primary", height: int = 48,
                 corner_radius: int = 12, font_size: float = 17.0):
        super().__init__()
        self.label = label
        self.on_press = on_press
        self.style = style  # "primary", "secondary", "text"
        self.preferred_height = height
        self.corner_radius = corner_radius
        self.font_size = font_size
        self.pressed = False
        self.enabled = True

    def measure(self, max_width: int, max_height: int) -> Size:
        # Estimate text width + padding
        char_width = self.font_size * 0.6
        text_width = int(len(self.label) * char_width)
        padding = 32
        width = min(max_width, max(text_width + padding * 2, 88))
        return Size(width, min(self.preferred_height, max_height))

    def render(self, ctx):
        """Render the button."""
        if not self.visible:
            return

        theme = self.theme
        colors = theme.colors if theme else None
        b = self.bounds

        ctx.save()

        # Determine colors based on style and state
        if self.style == "primary":
            bg = colors.accent if colors else "#D4A574"
            fg = colors.text_on_accent if colors else "#FFFFFF"
            if self.pressed:
                bg = colors.claude_terracotta_dark if colors else "#B8875A"
        elif self.style == "secondary":
            bg = colors.surface_secondary if colors else "#F5EDE4"
            fg = colors.text_primary if colors else "#1A1A2E"
            if self.pressed:
                bg = colors.surface_tertiary if colors else "#EDE3D8"
        else:  # "text"
            bg = None
            fg = colors.accent if colors else "#D4A574"
            if self.pressed:
                fg = colors.claude_terracotta_dark if colors else "#B8875A"

        if not self.enabled:
            fg = colors.text_tertiary if colors else "#8E8E9E"
            bg = colors.surface_secondary if colors else "#F5EDE4" if bg else None

        # Background
        if bg:
            r, g, b_c, a = self._parse_color(bg)
            self._rounded_rect(ctx, b.x, b.y, b.width, b.height, self.corner_radius)
            ctx.set_source_rgba(r, g, b_c, a)
            ctx.fill()

        # Label
        if self.label:
            try:
                import cairo as _cairo
                weight = _cairo.FONT_WEIGHT_BOLD if self.style == "primary" else _cairo.FONT_WEIGHT_NORMAL
                ctx.select_font_face("sans-serif", _cairo.FONT_SLANT_NORMAL, weight)
            except ImportError:
                pass

            ctx.set_font_size(self.font_size)

            r, g, b_c, a = self._parse_color(fg)
            ctx.set_source_rgba(r, g, b_c, a)

            extents = ctx.text_extents(self.label)
            text_x = b.x + (b.width - extents.width) / 2
            text_y = b.y + (b.height + extents.height) / 2
            ctx.move_to(text_x, text_y)
            ctx.show_text(self.label)

        ctx.restore()

    def handle_touch(self, event: TouchEvent) -> bool:
        """Handle press/release."""
        if not self.enabled:
            return False

        if not self.bounds.contains(event.x, event.y):
            if self.pressed:
                self.pressed = False
            return False

        if event.action == TouchAction.DOWN:
            self.pressed = True
            return True
        elif event.action == TouchAction.UP:
            if self.pressed:
                self.pressed = False
                if self.on_press:
                    self.on_press()
                return True

        return False


class IconButton(Widget):
    """
    A circular icon button (e.g., for action bars, FABs).

    Renders a circle with a text glyph as the icon (until real
    icon rendering is available).
    """

    def __init__(self, icon: str = "", on_press: Callable | None = None,
                 size: int = 44, bg_color: str | None = None,
                 icon_color: str | None = None, icon_size: float = 20.0):
        super().__init__()
        self.icon = icon  # Single char or emoji as placeholder
        self.on_press = on_press
        self.preferred_size = size
        self.bg_color = bg_color
        self.icon_color = icon_color
        self.icon_size = icon_size
        self.pressed = False

    def measure(self, max_width: int, max_height: int) -> Size:
        s = min(self.preferred_size, max_width, max_height)
        return Size(s, s)

    def render(self, ctx):
        if not self.visible:
            return

        import math
        theme = self.theme
        colors = theme.colors if theme else None
        b = self.bounds
        cx = b.x + b.width / 2
        cy = b.y + b.height / 2
        radius = min(b.width, b.height) / 2

        ctx.save()

        # Circle background
        bg = self.bg_color or (colors.surface_secondary if colors else "#F5EDE4")
        if self.pressed:
            bg = colors.surface_tertiary if colors else "#EDE3D8"

        r, g, b_c, a = self._parse_color(bg)
        ctx.arc(cx, cy, radius, 0, 2 * math.pi)
        ctx.set_source_rgba(r, g, b_c, a)
        ctx.fill()

        # Icon (text glyph)
        if self.icon:
            fg = self.icon_color or (colors.text_primary if colors else "#1A1A2E")
            r, g, b_c, a = self._parse_color(fg)
            ctx.set_source_rgba(r, g, b_c, a)

            try:
                import cairo as _cairo
                ctx.select_font_face("sans-serif", _cairo.FONT_SLANT_NORMAL,
                                    _cairo.FONT_WEIGHT_NORMAL)
            except ImportError:
                pass
            ctx.set_font_size(self.icon_size)

            extents = ctx.text_extents(self.icon)
            ctx.move_to(cx - extents.width / 2, cy + extents.height / 2)
            ctx.show_text(self.icon)

        ctx.restore()

    def handle_touch(self, event: TouchEvent) -> bool:
        if not self.bounds.contains(event.x, event.y):
            if self.pressed:
                self.pressed = False
            return False

        if event.action == TouchAction.DOWN:
            self.pressed = True
            return True
        elif event.action == TouchAction.UP and self.pressed:
            self.pressed = False
            if self.on_press:
                self.on_press()
            return True
        return False
