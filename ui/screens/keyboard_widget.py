"""
Claude-OS On-Screen Keyboard Widget

A QWERTY keyboard that slides up from the bottom when a text input
is focused. Built on the UI toolkit widget system.

Layers:
    - LOWERCASE: default qwerty
    - UPPERCASE: shifted qwerty
    - NUMBERS:   numbers + common punctuation
    - SYMBOLS:   less common symbols

Layout per row:
    ┌──────────────────────────────────┐
    │  q  w  e  r  t  y  u  i  o  p   │
    │   a  s  d  f  g  h  j  k  l     │
    │ SHIFT z  x  c  v  b  n  m  DEL  │
    │ ?123    SPACE           .  ENTER │
    └──────────────────────────────────┘
"""

from enum import Enum, auto
from typing import Callable

from theme import Colors, Typography, Spacing, Radius, Color, FontStyle
from widget import Widget, Size, EdgeInsets, Align, Direction, Event, EventType, _fill_rect
from widgets import Container, Label
from font import FontRenderer

_font = FontRenderer()


class KeyboardLayer(Enum):
    LOWERCASE = auto()
    UPPERCASE = auto()
    NUMBERS = auto()
    SYMBOLS = auto()


# Key layouts per layer
LAYOUTS = {
    KeyboardLayer.LOWERCASE: [
        list("qwertyuiop"),
        list("asdfghjkl"),
        ["SHIFT"] + list("zxcvbnm") + ["DEL"],
        ["?123", ",", "SPACE", ".", "ENTER"],
    ],
    KeyboardLayer.UPPERCASE: [
        list("QWERTYUIOP"),
        list("ASDFGHJKL"),
        ["SHIFT"] + list("ZXCVBNM") + ["DEL"],
        ["?123", ",", "SPACE", ".", "ENTER"],
    ],
    KeyboardLayer.NUMBERS: [
        list("1234567890"),
        list("-/:;()$&@\""),
        ["#+="] + list(".,?!'") + ["DEL"],
        ["ABC", ",", "SPACE", ".", "ENTER"],
    ],
    KeyboardLayer.SYMBOLS: [
        list("[]{}#%^*+="),
        list("_\\|~<>$@&\""),
        ["123"] + list(".,?!'") + ["DEL"],
        ["ABC", ",", "SPACE", ".", "ENTER"],
    ],
}

# Special key widths (multiplier of standard key width)
SPECIAL_KEY_WIDTHS = {
    "SHIFT": 1.5,
    "DEL": 1.5,
    "SPACE": 4.0,
    "ENTER": 1.5,
    "?123": 1.5,
    "ABC": 1.5,
    "#+=": 1.5,
    "123": 1.5,
}


class KeyWidget(Widget):
    """A single keyboard key."""

    def __init__(self, label: str, width_mult: float = 1.0,
                 on_press: Callable = None):
        super().__init__()
        self.key_label = label
        self.width_mult = width_mult
        self.background = Colors.SURFACE_BRIGHT
        self.corner_radius = Radius.SM
        self._on_press = on_press
        self._on_tap = on_press

        # Special key styling
        if label in ("SHIFT", "DEL", "?123", "ABC", "#+=", "123"):
            self.background = Colors.SURFACE_CONTAINER
        elif label == "ENTER":
            self.background = Colors.PRIMARY
        elif label == "SPACE":
            self.background = Colors.SURFACE_CONTAINER

    def measure(self, max_w: int, max_h: int) -> Size:
        return Size(int(32 * self.width_mult), 42)

    def draw_content(self, buf: bytearray, buf_w: int, buf_h: int,
                     abs_x: int, abs_y: int):
        # Draw key label centered
        display = self.key_label
        if display == "SPACE":
            display = ""
        elif display == "DEL":
            display = "<-"
        elif display == "ENTER":
            display = "->"
        elif display == "SHIFT":
            display = "^"

        if not display:
            return

        style = Typography.LABEL_MEDIUM if len(display) > 1 else Typography.BODY_MEDIUM
        color = Colors.TEXT_ON_PRIMARY if self.key_label == "ENTER" else Colors.TEXT_PRIMARY

        tw, th = _font.measure_text(display, style)
        tx = abs_x + (self.width - tw) // 2
        ty = abs_y + (self.height - th) // 2

        rt = _font.render_text(display, style, color)
        if rt.data:
            from widget import _blit_text
            _blit_text(buf, buf_w, buf_h, tx, ty,
                       rt.data, rt.width, rt.height, rt.stride)


class KeyboardWidget(Widget):
    """
    Full on-screen QWERTY keyboard.
    """

    HEIGHT = 220

    def __init__(self, on_key: Callable = None,
                 on_enter: Callable = None,
                 on_hide: Callable = None):
        super().__init__()
        self.background = Colors.SURFACE_DIM
        self.min_height = self.HEIGHT
        self.padding = EdgeInsets(top=Spacing.XS, right=Spacing.XS,
                                  bottom=Spacing.SM, left=Spacing.XS)

        self._layer = KeyboardLayer.LOWERCASE
        self._on_key = on_key
        self._on_enter = on_enter
        self._on_hide = on_hide
        self._shift_locked = False

        self._build_keys()

    def _build_keys(self):
        """Build key widgets for the current layer."""
        self.clear_children()

        root = Container(direction=Direction.VERTICAL,
                         gap=Spacing.XS, cross_align=Align.CENTER)
        self.add_child(root)

        layout = LAYOUTS[self._layer]

        for row_keys in layout:
            row = Container(direction=Direction.HORIZONTAL,
                            gap=Spacing.XS, cross_align=Align.CENTER)

            for key_label in row_keys:
                width_mult = SPECIAL_KEY_WIDTHS.get(key_label, 1.0)
                key = KeyWidget(
                    label=key_label,
                    width_mult=width_mult,
                    on_press=lambda k=key_label: self._handle_key(k),
                )
                row.add_child(key)

            root.add_child(row)

    def _handle_key(self, key: str):
        """Process a key press."""
        if key == "SHIFT":
            if self._layer == KeyboardLayer.LOWERCASE:
                self._layer = KeyboardLayer.UPPERCASE
            elif self._layer == KeyboardLayer.UPPERCASE:
                self._layer = KeyboardLayer.LOWERCASE
            self._build_keys()
            self.mark_dirty()

        elif key == "DEL":
            if self._on_key:
                self._on_key("BACKSPACE")

        elif key == "ENTER":
            if self._on_enter:
                self._on_enter()

        elif key in ("?123", "123"):
            self._layer = KeyboardLayer.NUMBERS
            self._build_keys()
            self.mark_dirty()

        elif key == "#+=":
            self._layer = KeyboardLayer.SYMBOLS
            self._build_keys()
            self.mark_dirty()

        elif key == "ABC":
            self._layer = KeyboardLayer.LOWERCASE
            self._build_keys()
            self.mark_dirty()

        elif key == "SPACE":
            if self._on_key:
                self._on_key(" ")

        else:
            # Regular character
            if self._on_key:
                self._on_key(key)
            # Auto-lowercase after typing in uppercase (unless shift-locked)
            if (self._layer == KeyboardLayer.UPPERCASE
                    and not self._shift_locked):
                self._layer = KeyboardLayer.LOWERCASE
                self._build_keys()
                self.mark_dirty()

    def measure(self, max_w: int, max_h: int) -> Size:
        return Size(max_w, self.HEIGHT)

    @property
    def current_layer(self) -> KeyboardLayer:
        return self._layer

    def set_layer(self, layer: KeyboardLayer):
        self._layer = layer
        self._build_keys()
        self.mark_dirty()
