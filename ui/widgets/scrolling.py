"""
ScrollView widget — vertically scrollable container.

Clips children to a viewport and tracks scroll offset via
touch drag gestures.
"""

from __future__ import annotations

import time

from ui.widgets.base import Widget, Container, Size, Rect, TouchEvent, TouchAction


class ScrollView(Container):
    """
    Vertical scroll container.

    Wraps content that may be taller than the viewport. Touch drag
    scrolls the content. Momentum scrolling decelerates after release.
    """

    def __init__(self, background: str | None = None,
                 corner_radius: int = 0):
        super().__init__(background=background, corner_radius=corner_radius)
        self.scroll_y = 0.0
        self.content_height = 0
        self._velocity_y = 0.0
        self._last_touch_y = 0
        self._last_touch_time = 0.0
        self._dragging = False
        self._deceleration = 0.95

    @property
    def max_scroll(self) -> int:
        return max(0, self.content_height - self.bounds.height)

    def measure(self, max_width: int, max_height: int) -> Size:
        return Size(max_width, max_height)

    def layout(self, x: int, y: int, width: int, height: int):
        """Layout children in a tall column, then set viewport."""
        self.bounds = Rect(x, y, width, height)

        # Layout children sequentially to get total content height
        cur_y = 0
        for child in self.children:
            child_size = child.measure(width, 100000)  # large max height
            child.layout(x, y + cur_y - int(self.scroll_y), width, child_size.height)
            cur_y += child_size.height

        self.content_height = cur_y

    def render(self, ctx):
        """Render with clipping to viewport."""
        if not self.visible:
            return

        ctx.save()

        # Background
        if self.background:
            r, g, b, a = self._parse_color(self.background)
            self._rounded_rect(ctx, self.bounds.x, self.bounds.y,
                              self.bounds.width, self.bounds.height,
                              self.corner_radius)
            ctx.set_source_rgba(r, g, b, a)
            ctx.fill()

        # Clip to viewport
        ctx.rectangle(self.bounds.x, self.bounds.y,
                     self.bounds.width, self.bounds.height)
        ctx.clip()

        # Render visible children
        for child in self.children:
            # Skip children fully outside viewport
            if (child.bounds.y + child.bounds.height < self.bounds.y or
                    child.bounds.y > self.bounds.y + self.bounds.height):
                continue
            if child.visible:
                child.render(ctx)

        # Scroll indicator (thin bar on right side)
        if self.content_height > self.bounds.height:
            self._render_scroll_indicator(ctx)

        ctx.restore()

    def _render_scroll_indicator(self, ctx):
        """Draw a thin scroll position indicator."""
        viewport_h = self.bounds.height
        ratio = viewport_h / self.content_height
        indicator_h = max(30, int(viewport_h * ratio))
        scroll_ratio = self.scroll_y / max(1, self.max_scroll)
        indicator_y = self.bounds.y + int(scroll_ratio * (viewport_h - indicator_h))
        indicator_x = self.bounds.x + self.bounds.width - 4

        ctx.set_source_rgba(0.0, 0.0, 0.0, 0.2)
        self._rounded_rect(ctx, indicator_x, indicator_y, 3, indicator_h, 2)
        ctx.fill()

    def handle_touch(self, event: TouchEvent) -> bool:
        """Handle drag scrolling."""
        if not self.bounds.contains(event.x, event.y) and event.action != TouchAction.UP:
            return False

        if event.action == TouchAction.DOWN:
            self._dragging = True
            self._velocity_y = 0.0
            self._last_touch_y = event.y
            self._last_touch_time = time.monotonic()
            return True

        elif event.action == TouchAction.MOVE and self._dragging:
            dy = self._last_touch_y - event.y
            now = time.monotonic()
            dt = now - self._last_touch_time
            if dt > 0:
                self._velocity_y = dy / dt

            self.scroll_y = max(0, min(self.max_scroll, self.scroll_y + dy))
            self._last_touch_y = event.y
            self._last_touch_time = now
            return True

        elif event.action == TouchAction.UP:
            self._dragging = False
            # Let children handle taps if no significant scroll happened
            if abs(self._velocity_y) < 50:
                return super().handle_touch(event)
            return True

        return False

    def update_momentum(self):
        """Called each frame to apply momentum scrolling after touch release."""
        if self._dragging or abs(self._velocity_y) < 1.0:
            self._velocity_y = 0.0
            return

        # Apply velocity
        dt = 1.0 / 30  # assume 30fps
        self.scroll_y += self._velocity_y * dt
        self.scroll_y = max(0, min(self.max_scroll, self.scroll_y))

        # Decelerate
        self._velocity_y *= self._deceleration
