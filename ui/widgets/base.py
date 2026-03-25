"""
Base widget classes for the Claude-OS UI toolkit.

All widgets follow a measure → layout → render cycle:
  1. measure(max_w, max_h) → returns desired Size
  2. layout(x, y, w, h)  → positions the widget in absolute coords
  3. render(ctx)          → draws to a Cairo context
  4. handle_touch(event)  → processes touch input, returns True if consumed
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from enum import Enum, auto
from typing import Callable

logger = logging.getLogger("widgets")


@dataclass
class Size:
    """A width/height pair."""
    width: int = 0
    height: int = 0


@dataclass
class Rect:
    """An axis-aligned rectangle."""
    x: int = 0
    y: int = 0
    width: int = 0
    height: int = 0

    def contains(self, px: int, py: int) -> bool:
        return (self.x <= px < self.x + self.width and
                self.y <= py < self.y + self.height)


class TouchAction(Enum):
    DOWN = auto()
    MOVE = auto()
    UP = auto()


@dataclass
class TouchEvent:
    """A touch/click event."""
    x: int
    y: int
    action: TouchAction
    touch_id: int = 0


class Widget:
    """
    Base class for all UI elements.

    Subclasses must implement:
      - measure(max_w, max_h) -> Size
      - render(ctx) -> None

    Optionally override:
      - handle_touch(event) -> bool
    """

    def __init__(self):
        self.bounds = Rect()
        self.visible = True
        self.opacity = 1.0
        self._parent: Widget | None = None
        self._dirty = True  # needs re-render

        # Theme (lazy-loaded)
        self._theme = None

    @property
    def theme(self):
        if self._theme is None:
            try:
                from ui.theme import get_theme
                self._theme = get_theme()
            except ImportError:
                pass
        return self._theme

    def measure(self, max_width: int, max_height: int) -> Size:
        """Return the desired size given maximum constraints."""
        return Size(0, 0)

    def layout(self, x: int, y: int, width: int, height: int):
        """Position this widget at absolute coordinates."""
        self.bounds = Rect(x, y, width, height)

    def render(self, ctx):
        """Draw this widget to a Cairo context."""
        pass

    def handle_touch(self, event: TouchEvent) -> bool:
        """Process a touch event. Return True if consumed."""
        return False

    def invalidate(self):
        """Mark this widget as needing re-render."""
        self._dirty = True

    def _parse_color(self, color_str: str) -> tuple:
        """Parse hex color to (r, g, b, a) floats."""
        c = color_str.lstrip("#")
        if len(c) == 6:
            r, g, b = int(c[0:2], 16), int(c[2:4], 16), int(c[4:6], 16)
            return r / 255.0, g / 255.0, b / 255.0, 1.0
        elif len(c) == 8:
            r, g, b, a = int(c[0:2], 16), int(c[2:4], 16), int(c[4:6], 16), int(c[6:8], 16)
            return r / 255.0, g / 255.0, b / 255.0, a / 255.0
        return 0.0, 0.0, 0.0, 1.0

    def _rounded_rect(self, ctx, x, y, w, h, r):
        """Draw a rounded rectangle path on the Cairo context."""
        import math
        if r <= 0:
            ctx.rectangle(x, y, w, h)
            return
        r = min(r, w / 2, h / 2)
        ctx.new_sub_path()
        ctx.arc(x + w - r, y + r, r, -math.pi / 2, 0)
        ctx.arc(x + w - r, y + h - r, r, 0, math.pi / 2)
        ctx.arc(x + r, y + h - r, r, math.pi / 2, math.pi)
        ctx.arc(x + r, y + r, r, math.pi, 3 * math.pi / 2)
        ctx.close_path()


class Container(Widget):
    """
    A widget that holds child widgets.

    Draws an optional background, then renders children in order.
    Touch events are dispatched to children in reverse order
    (top-most first).
    """

    def __init__(self, background: str | None = None,
                 corner_radius: int = 0,
                 padding: int = 0):
        super().__init__()
        self.children: list[Widget] = []
        self.background = background
        self.corner_radius = corner_radius
        self.padding = padding

    def add(self, child: Widget) -> Widget:
        """Add a child widget. Returns the child for chaining."""
        child._parent = self
        self.children.append(child)
        return child

    def remove(self, child: Widget):
        """Remove a child widget."""
        if child in self.children:
            self.children.remove(child)
            child._parent = None

    def measure(self, max_width: int, max_height: int) -> Size:
        """Default: use full available space."""
        return Size(max_width, max_height)

    def layout(self, x: int, y: int, width: int, height: int):
        """Layout self and all children."""
        super().layout(x, y, width, height)
        p = self.padding
        for child in self.children:
            child_size = child.measure(width - 2 * p, height - 2 * p)
            child.layout(x + p, y + p, child_size.width, child_size.height)

    def render(self, ctx):
        """Render background then children."""
        if not self.visible:
            return

        ctx.save()

        # Apply opacity
        if self.opacity < 1.0:
            ctx.push_group()

        # Draw background
        if self.background:
            r, g, b, a = self._parse_color(self.background)
            self._rounded_rect(ctx, self.bounds.x, self.bounds.y,
                              self.bounds.width, self.bounds.height,
                              self.corner_radius)
            ctx.set_source_rgba(r, g, b, a)
            ctx.fill()

        # Clip children to bounds
        ctx.rectangle(self.bounds.x, self.bounds.y,
                     self.bounds.width, self.bounds.height)
        ctx.clip()

        # Render children
        for child in self.children:
            if child.visible:
                child.render(ctx)

        if self.opacity < 1.0:
            ctx.pop_group_to_source()
            ctx.paint_with_alpha(self.opacity)

        ctx.restore()

    def handle_touch(self, event: TouchEvent) -> bool:
        """Dispatch touch to children (reverse order = top-most first)."""
        for child in reversed(self.children):
            if child.visible and child.bounds.contains(event.x, event.y):
                if child.handle_touch(event):
                    return True
        return False
