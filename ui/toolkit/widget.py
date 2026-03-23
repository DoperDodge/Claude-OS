"""
Claude-OS Widget Base

The foundation of the UI toolkit. Every visual element on screen is a Widget.
Widgets form a tree — each widget has a parent and zero or more children.

Responsibilities:
    - Layout: Measure desired size, then position children within bounds
    - Drawing: Render self to a pixel buffer, then draw children on top
    - Events: Receive touch/key events, propagate through the tree
    - Hit testing: Determine which widget a touch point lands on

Layout model (simplified CSS box model):
    ┌─────────── margin ───────────┐
    │ ┌──────── border ──────────┐ │
    │ │ ┌────── padding ───────┐ │ │
    │ │ │                      │ │ │
    │ │ │     content area     │ │ │
    │ │ │                      │ │ │
    │ │ └──────────────────────┘ │ │
    │ └──────────────────────────┘ │
    └──────────────────────────────┘
"""

import struct
from dataclasses import dataclass, field
from enum import Enum, auto
from typing import Callable

from theme import Color, Colors, Spacing, default_theme


# --- Events ---

class EventType(Enum):
    TOUCH_DOWN = auto()
    TOUCH_UP = auto()
    TOUCH_MOVE = auto()
    KEY_DOWN = auto()
    KEY_UP = auto()
    FOCUS_IN = auto()
    FOCUS_OUT = auto()


@dataclass
class Event:
    """UI event propagated through the widget tree."""
    type: EventType
    x: int = 0
    y: int = 0
    key_code: int = 0
    consumed: bool = False

    def consume(self):
        """Mark this event as handled (stops propagation)."""
        self.consumed = True


# --- Layout ---

class Align(Enum):
    START = auto()
    CENTER = auto()
    END = auto()


class Direction(Enum):
    HORIZONTAL = auto()
    VERTICAL = auto()


@dataclass
class EdgeInsets:
    """Spacing on all four sides."""
    top: int = 0
    right: int = 0
    bottom: int = 0
    left: int = 0

    @classmethod
    def all(cls, value: int) -> "EdgeInsets":
        return cls(value, value, value, value)

    @classmethod
    def symmetric(cls, horizontal: int = 0, vertical: int = 0) -> "EdgeInsets":
        return cls(vertical, horizontal, vertical, horizontal)

    @property
    def horizontal(self) -> int:
        return self.left + self.right

    @property
    def vertical(self) -> int:
        return self.top + self.bottom


@dataclass
class Size:
    """Widget dimensions."""
    width: int = 0
    height: int = 0


# --- Base Widget ---

class Widget:
    """
    Base class for all UI elements.

    Subclasses override:
        - measure(): Return desired Size given constraints
        - layout(): Position children within allocated bounds
        - draw(): Render pixels to a buffer
        - on_event(): Handle input events
    """

    def __init__(self):
        # Tree structure
        self.parent: Widget | None = None
        self.children: list[Widget] = []

        # Position (set by parent's layout)
        self.x: int = 0
        self.y: int = 0

        # Size (set after measure/layout)
        self.width: int = 0
        self.height: int = 0

        # Constraints from parent
        self.min_width: int = 0
        self.min_height: int = 0
        self.max_width: int = 0x7FFFFFFF
        self.max_height: int = 0x7FFFFFFF

        # Styling
        self.padding = EdgeInsets()
        self.margin = EdgeInsets()
        self.background: Color | None = None
        self.border_color: Color | None = None
        self.border_width: int = 0
        self.corner_radius: int = 0
        self.visible: bool = True
        self.opacity: float = 1.0

        # Flex layout
        self.flex: int = 0  # 0 = fixed, >0 = flex weight

        # Event handlers
        self._on_tap: Callable | None = None
        self._on_long_press: Callable | None = None
        self._event_handlers: dict[EventType, list[Callable]] = {}

        # State
        self._pressed = False
        self._focused = False
        self._dirty = True

    # --- Tree ---

    def add_child(self, child: "Widget") -> "Widget":
        """Add a child widget. Returns self for chaining."""
        child.parent = self
        self.children.append(child)
        self.mark_dirty()
        return self

    def remove_child(self, child: "Widget"):
        """Remove a child widget."""
        if child in self.children:
            self.children.remove(child)
            child.parent = None
            self.mark_dirty()

    def clear_children(self):
        """Remove all children."""
        for child in self.children:
            child.parent = None
        self.children.clear()
        self.mark_dirty()

    # --- Measurement ---

    def measure(self, max_w: int, max_h: int) -> Size:
        """
        Calculate desired size given constraints.

        Default: just big enough for padding. Subclasses override.
        """
        w = self.padding.horizontal
        h = self.padding.vertical
        return Size(
            max(self.min_width, min(w, max_w)),
            max(self.min_height, min(h, max_h)),
        )

    # --- Layout ---

    def layout(self, x: int, y: int, width: int, height: int):
        """
        Position this widget and lay out children.

        Called by the parent after measure(). Sets absolute position
        and size, then positions children within the content area.
        """
        self.x = x
        self.y = y
        self.width = max(0, width)
        self.height = max(0, height)
        self._layout_children()

    def _layout_children(self):
        """Default child layout — stack at content origin. Override in subclasses."""
        cx = self.padding.left
        cy = self.padding.top
        cw = self.content_width
        ch = self.content_height

        for child in self.children:
            if not child.visible:
                continue
            size = child.measure(cw, ch)
            child.layout(cx, cy, size.width, size.height)

    @property
    def content_width(self) -> int:
        """Width available for content (excluding padding)."""
        return max(0, self.width - self.padding.horizontal)

    @property
    def content_height(self) -> int:
        """Height available for content (excluding padding)."""
        return max(0, self.height - self.padding.vertical)

    # --- Drawing ---

    def draw(self, buf: bytearray, buf_w: int, buf_h: int,
             ox: int = 0, oy: int = 0):
        """
        Draw this widget and children into a pixel buffer.

        Args:
            buf: BGRA pixel buffer
            buf_w: Buffer width in pixels
            buf_h: Buffer height in pixels
            ox, oy: Offset from buffer origin to this widget's parent
        """
        if not self.visible:
            return

        abs_x = ox + self.x
        abs_y = oy + self.y

        # Draw background
        if self.background:
            _fill_rect(buf, buf_w, buf_h,
                       abs_x, abs_y, self.width, self.height,
                       self.background)

        # Draw border
        if self.border_color and self.border_width > 0:
            _draw_border(buf, buf_w, buf_h,
                         abs_x, abs_y, self.width, self.height,
                         self.border_color, self.border_width)

        # Draw pressed overlay
        if self._pressed:
            _fill_rect(buf, buf_w, buf_h,
                       abs_x, abs_y, self.width, self.height,
                       Colors.PRESSED)

        # Draw self content (subclass)
        self.draw_content(buf, buf_w, buf_h, abs_x, abs_y)

        # Draw children
        for child in self.children:
            child.draw(buf, buf_w, buf_h, abs_x, abs_y)

        self._dirty = False

    def draw_content(self, buf: bytearray, buf_w: int, buf_h: int,
                     abs_x: int, abs_y: int):
        """Draw widget-specific content. Override in subclasses."""
        pass

    # --- Events ---

    def on_event(self, event: Event) -> bool:
        """
        Handle an input event. Returns True if consumed.

        Default: propagate to children via hit testing.
        """
        if not self.visible or event.consumed:
            return False

        # Convert to local coordinates
        local_x = event.x - self.x
        local_y = event.y - self.y

        # Check if point is within bounds
        if not self.hit_test(local_x, local_y):
            if event.type == EventType.TOUCH_UP and self._pressed:
                self._pressed = False
                self.mark_dirty()
            return False

        # Propagate to children (front to back)
        child_event = Event(
            type=event.type,
            x=local_x, y=local_y,
            key_code=event.key_code,
        )

        for child in reversed(self.children):
            if child.on_event(child_event):
                event.consume()
                return True

        # Handle locally
        handled = self._handle_event(event.type, local_x, local_y,
                                      event.key_code)

        # Fire registered handlers
        for handler in self._event_handlers.get(event.type, []):
            handler(event)
            handled = True

        if handled:
            event.consume()
        return handled

    def _handle_event(self, event_type: EventType, x: int, y: int,
                      key_code: int) -> bool:
        """Internal event handling. Override for custom behavior."""
        if event_type == EventType.TOUCH_DOWN:
            self._pressed = True
            self.mark_dirty()
            return self._on_tap is not None

        elif event_type == EventType.TOUCH_UP:
            was_pressed = self._pressed
            self._pressed = False
            self.mark_dirty()
            if was_pressed and self._on_tap:
                self._on_tap()
                return True
            return False

        return False

    def hit_test(self, local_x: int, local_y: int) -> bool:
        """Test if a point (in parent coordinates) is within this widget."""
        return (0 <= local_x < self.width and
                0 <= local_y < self.height)

    def on(self, event_type: EventType, handler: Callable) -> "Widget":
        """Register an event handler. Returns self for chaining."""
        self._event_handlers.setdefault(event_type, []).append(handler)
        return self

    def on_tap(self, handler: Callable) -> "Widget":
        """Set tap handler. Returns self for chaining."""
        self._on_tap = handler
        return self

    # --- State ---

    def mark_dirty(self):
        """Mark this widget as needing redraw."""
        self._dirty = True

    @property
    def is_dirty(self) -> bool:
        if self._dirty:
            return True
        return any(c.is_dirty for c in self.children)

    @property
    def absolute_x(self) -> int:
        """Absolute X position in screen coordinates."""
        x = self.x
        p = self.parent
        while p:
            x += p.x
            p = p.parent
        return x

    @property
    def absolute_y(self) -> int:
        """Absolute Y position in screen coordinates."""
        y = self.y
        p = self.parent
        while p:
            y += p.y
            p = p.parent
        return y


# --- Pixel Drawing Helpers ---

def _fill_rect(buf: bytearray, buf_w: int, buf_h: int,
               x: int, y: int, w: int, h: int, color: Color):
    """Fill a rectangle in the pixel buffer."""
    x0 = max(0, x)
    y0 = max(0, y)
    x1 = min(buf_w, x + w)
    y1 = min(buf_h, y + h)
    if x0 >= x1 or y0 >= y1:
        return

    b, g, r, a = color.bgra
    if a == 0:
        return

    pixel = struct.pack("BBBB", b, g, r, a)
    row_w = x1 - x0

    if a == 255:
        row_data = pixel * row_w
        for row in range(y0, y1):
            offset = (row * buf_w + x0) * 4
            buf[offset:offset + len(row_data)] = row_data
    else:
        # Alpha blending
        alpha = a / 255.0
        inv_alpha = 1.0 - alpha
        for row in range(y0, y1):
            for col in range(x0, x1):
                offset = (row * buf_w + col) * 4
                if offset + 3 >= len(buf):
                    continue
                db = buf[offset]
                dg = buf[offset + 1]
                dr = buf[offset + 2]
                buf[offset] = int(db * inv_alpha + b * alpha)
                buf[offset + 1] = int(dg * inv_alpha + g * alpha)
                buf[offset + 2] = int(dr * inv_alpha + r * alpha)
                buf[offset + 3] = 255


def _draw_border(buf: bytearray, buf_w: int, buf_h: int,
                 x: int, y: int, w: int, h: int,
                 color: Color, thickness: int):
    """Draw a rectangular border."""
    # Top
    _fill_rect(buf, buf_w, buf_h, x, y, w, thickness, color)
    # Bottom
    _fill_rect(buf, buf_w, buf_h, x, y + h - thickness, w, thickness, color)
    # Left
    _fill_rect(buf, buf_w, buf_h, x, y, thickness, h, color)
    # Right
    _fill_rect(buf, buf_w, buf_h, x + w - thickness, y, thickness, h, color)


def _blit_text(buf: bytearray, buf_w: int, buf_h: int,
               x: int, y: int, text_data: bytearray,
               text_w: int, text_h: int, text_stride: int):
    """Blit rendered text onto the widget buffer (alpha-aware)."""
    for row in range(text_h):
        screen_y = y + row
        if screen_y < 0 or screen_y >= buf_h:
            continue
        for col in range(text_w):
            screen_x = x + col
            if screen_x < 0 or screen_x >= buf_w:
                continue

            src_offset = row * text_stride + col * 4
            if src_offset + 3 >= len(text_data):
                continue
            sa = text_data[src_offset + 3]
            if sa == 0:
                continue

            dst_offset = (screen_y * buf_w + screen_x) * 4
            if dst_offset + 3 >= len(buf):
                continue

            if sa == 255:
                buf[dst_offset:dst_offset + 4] = text_data[src_offset:src_offset + 4]
            else:
                alpha = sa / 255.0
                inv = 1.0 - alpha
                buf[dst_offset] = int(buf[dst_offset] * inv + text_data[src_offset] * alpha)
                buf[dst_offset + 1] = int(buf[dst_offset + 1] * inv + text_data[src_offset + 1] * alpha)
                buf[dst_offset + 2] = int(buf[dst_offset + 2] * inv + text_data[src_offset + 2] * alpha)
                buf[dst_offset + 3] = 255
