"""
Keyboard view — on-screen QWERTY keyboard.

Renders the virtual keyboard with key rows, suggestion bar,
and layer switching (lowercase/uppercase/numbers/symbols).
"""

from ui.widgets.base import Container, Size, Widget, TouchEvent, TouchAction
from ui.widgets.text import Label
from ui.widgets.layout import VStack, HStack, Spacer, Padding
from ui.keyboard.keyboard import KeyboardLayer, Key, LAYOUTS


class KeyWidget(Container):
    """A single keyboard key rendered as a rounded rectangle."""

    def __init__(self, key: Key, unit_width: float, row_height: int,
                 on_press=None):
        super().__init__()
        self._key = key
        self._unit_width = unit_width
        self._row_height = row_height
        self._on_press = on_press
        self._pressed = False
        self._build()

    def _build(self):
        theme = self.theme
        colors = theme.colors if theme else None
        spacing = theme.spacing if theme else None

        if self._key.special:
            self.background = colors.key_special_background if colors else "#E8D5C4"
        else:
            self.background = colors.key_background if colors else "#FFFFFF"

        self.corner_radius = spacing.key_radius if spacing else 8

        font_size = 16.0 if self._key.special else 23.0
        label = Label(
            text=self._key.label,
            font_size=font_size,
            color=colors.key_text if colors else "#1A1A2E",
            align="center",
        )
        self.add(Padding(child=label, top=4, bottom=4))

    def measure(self, max_width, max_height):
        theme = self.theme
        spacing = theme.spacing if theme else None
        margin = spacing.key_margin if spacing else 3
        w = int(self._key.width * self._unit_width) - margin * 2
        h = self._row_height - margin * 2
        return Size(max(w, 10), max(h, 10))

    def handle_touch(self, event: TouchEvent) -> bool:
        if event.action == TouchAction.DOWN:
            self._pressed = True
            theme = self.theme
            colors = theme.colors if theme else None
            self.background = colors.key_pressed if colors else "#D4A574"
            return True
        elif event.action == TouchAction.UP:
            if self._pressed and self._on_press:
                self._on_press(self._key)
            self._pressed = False
            theme = self.theme
            colors = theme.colors if theme else None
            if self._key.special:
                self.background = colors.key_special_background if colors else "#E8D5C4"
            else:
                self.background = colors.key_background if colors else "#FFFFFF"
            return True
        return False


class SuggestionBar(Container):
    """Prediction/suggestion bar above the keyboard."""

    def __init__(self, suggestions: list[str] = None, height: int = 44):
        super().__init__()
        self._suggestions = suggestions or []
        self._bar_h = height
        self._on_suggestion = None
        self._build()

    def _build(self):
        theme = self.theme
        colors = theme.colors if theme else None

        self.background = colors.suggestion_background if colors else "rgba(232,213,196,0.6)"

        row = HStack(spacing=0)
        for s in self._suggestions:
            row.add(Spacer())
            row.add(Label(
                text=s,
                font_size=15.0,
                color=colors.suggestion_text if colors else "#1A1A2E",
                align="center",
            ))
        if self._suggestions:
            row.add(Spacer())
        self.add(row)

    def update(self, suggestions: list[str]):
        self._suggestions = suggestions
        self.children.clear()
        self._build()

    def measure(self, max_width, max_height):
        return Size(max_width, self._bar_h)


class KeyboardView(Container):
    """
    Full on-screen keyboard widget.

    Shows suggestion bar at top, then QWERTY key rows.
    Supports layer switching (lowercase/uppercase/numbers/symbols).
    """

    def __init__(self, width: int, height: int = 291):
        super().__init__()
        self._kb_w = width
        self._kb_h = height
        self.layer = KeyboardLayer.LOWERCASE
        self.suggestions: list[str] = []
        self.visible = False

        # Callbacks
        self._on_key = None
        self._on_special = None

        self._suggestion_bar = None
        self._keys_container = None

        self._build()

    def _build(self):
        theme = self.theme
        colors = theme.colors if theme else None
        layout_m = theme.layout if theme else None

        suggestion_h = layout_m.keyboard_suggestion_bar_height if layout_m else 44
        key_area_h = self._kb_h - suggestion_h

        self.background = colors.surface_secondary if colors else "#F5EDE4"

        root = VStack(spacing=0)

        # Suggestion bar
        self._suggestion_bar = SuggestionBar(
            suggestions=self.suggestions,
            height=suggestion_h,
        )
        root.add(self._suggestion_bar)

        # Key rows
        self._keys_container = VStack(spacing=0)
        self._rebuild_keys(key_area_h)
        root.add(self._keys_container)

        self.add(root)

    def _rebuild_keys(self, key_area_h: int):
        """Rebuild the key grid for the current layer."""
        if self._keys_container is None:
            return
        self._keys_container.children.clear()

        layout_keys = LAYOUTS.get(self.layer, LAYOUTS[KeyboardLayer.LOWERCASE])
        row_count = len(layout_keys)
        row_height = key_area_h // row_count if row_count > 0 else 50

        for row_keys in layout_keys:
            total_width_units = sum(k.width for k in row_keys)
            unit_width = self._kb_w / total_width_units if total_width_units > 0 else 40

            row = HStack(spacing=0)
            for key in row_keys:
                kw = KeyWidget(
                    key=key,
                    unit_width=unit_width,
                    row_height=row_height,
                    on_press=self._handle_key_press,
                )
                row.add(kw)
            self._keys_container.add(row)

    def _handle_key_press(self, key: Key):
        """Handle a key press from a KeyWidget."""
        if key.special:
            if key.code == "shift":
                if self.layer == KeyboardLayer.LOWERCASE:
                    self.set_layer(KeyboardLayer.UPPERCASE)
                else:
                    self.set_layer(KeyboardLayer.LOWERCASE)
            elif key.code == "numbers":
                self.set_layer(KeyboardLayer.NUMBERS)
            elif key.code == "symbols":
                self.set_layer(KeyboardLayer.SYMBOLS)
            elif key.code == "letters":
                self.set_layer(KeyboardLayer.LOWERCASE)
            elif key.code in ("backspace", "enter"):
                if self._on_special:
                    self._on_special(key.code)
        else:
            if self._on_key:
                self._on_key(key.code)
            if self.layer == KeyboardLayer.UPPERCASE:
                self.set_layer(KeyboardLayer.LOWERCASE)

    def set_layer(self, layer: KeyboardLayer):
        """Switch keyboard layer and rebuild keys."""
        self.layer = layer
        theme = self.theme
        layout_m = theme.layout if theme else None
        suggestion_h = layout_m.keyboard_suggestion_bar_height if layout_m else 44
        key_area_h = self._kb_h - suggestion_h
        self._rebuild_keys(key_area_h)

    def set_key_handler(self, on_key, on_special=None):
        """Set callbacks for key presses."""
        self._on_key = on_key
        self._on_special = on_special

    def update_suggestions(self, suggestions: list[str]):
        """Update the suggestion bar."""
        self.suggestions = suggestions[:3]
        if self._suggestion_bar:
            self._suggestion_bar.update(self.suggestions)

    def measure(self, max_width, max_height):
        return Size(self._kb_w, self._kb_h)

    def layout(self, x, y, width, height):
        super().layout(x, y, width, height)
        if self.children:
            self.children[0].layout(x, y, width, height)
