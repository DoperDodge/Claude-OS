"""
Claude-OS On-Screen Keyboard

A themed virtual keyboard rendered as a Wayland layer-shell surface.
Appears from the bottom with spring animation when a text input is focused.

Visual Design:
    ┌──────────────────────────────────────────────────┐
    │  [hello]    [help]    [hey]                      │  <- Suggestion bar
    ├──────────────────────────────────────────────────┤
    │  q  w  e  r  t  y  u  i  o  p                   │  <- Rows with rounded keys
    │   a  s  d  f  g  h  j  k  l                      │     Key press: scale + color
    │  [^]  z  x  c  v  b  n  m  [<-]                  │     Special: sand background
    │  [123] [,] [        space        ] [.] [->]       │
    └──────────────────────────────────────────────────┘

Uses theme tokens for: key colors, shadows, corner radii, suggestion bar
styling, press animations, and spring-based show/hide transitions.
"""

import asyncio
import logging
import time
from dataclasses import dataclass
from enum import Enum, auto

logger = logging.getLogger("keyboard")


class KeyboardLayer(Enum):
    """Active keyboard layout layer."""
    LOWERCASE = auto()
    UPPERCASE = auto()
    NUMBERS = auto()
    SYMBOLS = auto()
    EMOJI = auto()


@dataclass
class Key:
    """A single key on the keyboard."""
    label: str           # Display text
    code: str            # Key code to send
    width: float = 1.0   # Width multiplier (1.0 = standard key width)
    special: bool = False  # True for modifier keys (shift, backspace, etc.)


# Standard QWERTY layouts
LAYOUTS = {
    KeyboardLayer.LOWERCASE: [
        [Key("q", "q"), Key("w", "w"), Key("e", "e"), Key("r", "r"),
         Key("t", "t"), Key("y", "y"), Key("u", "u"), Key("i", "i"),
         Key("o", "o"), Key("p", "p")],
        [Key("a", "a"), Key("s", "s"), Key("d", "d"), Key("f", "f"),
         Key("g", "g"), Key("h", "h"), Key("j", "j"), Key("k", "k"),
         Key("l", "l")],
        [Key("^", "shift", width=1.5, special=True),
         Key("z", "z"), Key("x", "x"), Key("c", "c"), Key("v", "v"),
         Key("b", "b"), Key("n", "n"), Key("m", "m"),
         Key("<-", "backspace", width=1.5, special=True)],
        [Key("123", "numbers", width=1.5, special=True),
         Key(",", ","),
         Key(" ", "space", width=5.0),
         Key(".", "."),
         Key("->", "enter", width=1.5, special=True)],
    ],
    KeyboardLayer.UPPERCASE: [
        [Key("Q", "Q"), Key("W", "W"), Key("E", "E"), Key("R", "R"),
         Key("T", "T"), Key("Y", "Y"), Key("U", "U"), Key("I", "I"),
         Key("O", "O"), Key("P", "P")],
        [Key("A", "A"), Key("S", "S"), Key("D", "D"), Key("F", "F"),
         Key("G", "G"), Key("H", "H"), Key("J", "J"), Key("K", "K"),
         Key("L", "L")],
        [Key("v", "shift", width=1.5, special=True),
         Key("Z", "Z"), Key("X", "X"), Key("C", "C"), Key("V", "V"),
         Key("B", "B"), Key("N", "N"), Key("M", "M"),
         Key("<-", "backspace", width=1.5, special=True)],
        [Key("123", "numbers", width=1.5, special=True),
         Key(",", ","),
         Key(" ", "space", width=5.0),
         Key(".", "."),
         Key("->", "enter", width=1.5, special=True)],
    ],
    KeyboardLayer.NUMBERS: [
        [Key("1", "1"), Key("2", "2"), Key("3", "3"), Key("4", "4"),
         Key("5", "5"), Key("6", "6"), Key("7", "7"), Key("8", "8"),
         Key("9", "9"), Key("0", "0")],
        [Key("@", "@"), Key("#", "#"), Key("$", "$"), Key("_", "_"),
         Key("&", "&"), Key("-", "-"), Key("+", "+"), Key("(", "("),
         Key(")", ")")],
        [Key("#+=", "symbols", width=1.5, special=True),
         Key("*", "*"), Key('"', '"'), Key("'", "'"), Key(":", ":"),
         Key(";", ";"), Key("!", "!"), Key("?", "?"),
         Key("<-", "backspace", width=1.5, special=True)],
        [Key("abc", "letters", width=1.5, special=True),
         Key(",", ","),
         Key(" ", "space", width=5.0),
         Key(".", "."),
         Key("->", "enter", width=1.5, special=True)],
    ],
    KeyboardLayer.SYMBOLS: [
        [Key("~", "~"), Key("`", "`"), Key("|", "|"), Key("*", "*"),
         Key("^", "^"), Key("{", "{"), Key("}", "}"), Key("[", "["),
         Key("]", "]"), Key("\\", "\\")],
        [Key("<", "<"), Key(">", ">"), Key("=", "="), Key("/", "/"),
         Key("%", "%"), Key("€", "€"), Key("£", "£"), Key("¥", "¥"),
         Key("•", "•")],
        [Key("123", "numbers", width=1.5, special=True),
         Key("©", "©"), Key("®", "®"), Key("™", "™"), Key("°", "°"),
         Key("¶", "¶"), Key("§", "§"), Key("…", "…"),
         Key("<-", "backspace", width=1.5, special=True)],
        [Key("abc", "letters", width=1.5, special=True),
         Key(",", ","),
         Key(" ", "space", width=5.0),
         Key(".", "."),
         Key("->", "enter", width=1.5, special=True)],
    ],
}


class OnScreenKeyboard:
    """
    Themed virtual keyboard for Claude-OS.

    Renders as a Wayland layer-shell surface anchored to the bottom.
    All visual properties come from the design system tokens.
    """

    def __init__(self):
        self.layer = KeyboardLayer.LOWERCASE
        self.visible = False
        self.suggestions: list[str] = []

        # Load theme
        try:
            from ui.theme import get_theme
            self._theme = get_theme()
        except ImportError:
            self._theme = None

        # Key repeat
        self._repeat_key: Key | None = None
        self._repeat_task: asyncio.Task | None = None
        self._repeat_delay = 0.4
        self._repeat_rate = 0.05

        # Animation state
        self._show_progress = 0.0  # 0=hidden, 1=fully shown
        self._pressed_key_code: str | None = None

        # Callbacks
        self._on_key = None
        self._on_special = None
        self._on_suggestion = None

    @property
    def height(self) -> int:
        if self._theme:
            return self._theme.layout.keyboard_height
        return 291

    @property
    def suggestion_bar_height(self) -> int:
        if self._theme:
            return self._theme.layout.keyboard_suggestion_bar_height
        return 44

    def set_key_handler(self, on_key, on_special=None, on_suggestion=None):
        """Set callbacks for key events."""
        self._on_key = on_key
        self._on_special = on_special
        self._on_suggestion = on_suggestion

    def show(self):
        """Show the keyboard with spring animation."""
        self.visible = True
        self.layer = KeyboardLayer.LOWERCASE
        self._show_progress = 1.0
        logger.info("Keyboard shown")

    def hide(self):
        """Hide the keyboard with ease-out animation."""
        self.visible = False
        self._show_progress = 0.0
        self._cancel_repeat()
        logger.info("Keyboard hidden")

    def get_current_layout(self) -> list[list[Key]]:
        """Get the current keyboard layout."""
        return LAYOUTS.get(self.layer, LAYOUTS[KeyboardLayer.LOWERCASE])

    def handle_touch(self, x: int, y: int, action: str = "down"):
        """Handle a touch event on the keyboard surface."""
        if not self.visible:
            return

        if action == "up":
            self._pressed_key_code = None
            self._cancel_repeat()
            return

        # Check suggestion bar first
        if y < self.suggestion_bar_height:
            self._handle_suggestion_tap(x)
            return

        # Find which key was hit
        key = self._hit_test(x, y - self.suggestion_bar_height)
        if key is None:
            return

        if action == "down":
            self._pressed_key_code = key.code
            self._press_key(key)

    def _press_key(self, key: Key):
        """Process a key press."""
        if key.special:
            self._handle_special(key)
        else:
            if self._on_key:
                self._on_key(key.code)
            if self.layer == KeyboardLayer.UPPERCASE:
                self.layer = KeyboardLayer.LOWERCASE

    def _handle_special(self, key: Key):
        """Handle special key actions."""
        if key.code == "shift":
            if self.layer == KeyboardLayer.LOWERCASE:
                self.layer = KeyboardLayer.UPPERCASE
            else:
                self.layer = KeyboardLayer.LOWERCASE
        elif key.code == "numbers":
            self.layer = KeyboardLayer.NUMBERS
        elif key.code == "symbols":
            self.layer = KeyboardLayer.SYMBOLS
        elif key.code == "letters":
            self.layer = KeyboardLayer.LOWERCASE
        elif key.code in ("backspace", "enter"):
            if self._on_special:
                self._on_special(key.code)

    def _hit_test(self, x: int, y: int) -> Key | None:
        """Determine which key is at the given coordinates."""
        layout = self.get_current_layout()
        key_area_height = self.height - self.suggestion_bar_height
        row_height = key_area_height / len(layout)

        row_index = int(y / row_height)
        if row_index < 0 or row_index >= len(layout):
            return None

        row = layout[row_index]
        total_width = sum(k.width for k in row)
        keyboard_width = 1080
        unit_width = keyboard_width / total_width

        current_x = 0
        for key in row:
            key_width = key.width * unit_width
            if current_x <= x < current_x + key_width:
                return key
            current_x += key_width

        return None

    def _handle_suggestion_tap(self, x: int):
        """Handle tap on the suggestion bar."""
        if not self.suggestions:
            return
        section_width = 1080 / len(self.suggestions)
        index = int(x / section_width)
        if 0 <= index < len(self.suggestions):
            suggestion = self.suggestions[index]
            if self._on_suggestion:
                self._on_suggestion(suggestion)

    def update_suggestions(self, suggestions: list[str]):
        """Update the predictive text suggestions."""
        self.suggestions = suggestions[:3]

    def _cancel_repeat(self):
        """Cancel any active key repeat."""
        if self._repeat_task:
            self._repeat_task.cancel()
            self._repeat_task = None
            self._repeat_key = None

    def get_render_data(self) -> dict:
        """Return themed render data for external renderers."""
        theme = self._theme
        colors = theme.colors if theme else None
        typo = theme.typography if theme else None
        spacing = theme.spacing if theme else None
        effects = theme.effects if theme else None
        anim = theme.animation if theme else None

        layout = self.get_current_layout()

        return {
            "visible": self.visible,
            "height": self.height,
            "show_progress": self._show_progress,
            "layer": self.layer.name,
            "suggestion_bar": {
                "height": self.suggestion_bar_height,
                "suggestions": self.suggestions,
                "background": colors.suggestion_background if colors else "rgba(232,213,196,0.6)",
                "text_color": colors.suggestion_text if colors else "#1A1A2E",
                "divider_color": colors.suggestion_divider if colors else "rgba(212,165,116,0.3)",
                "text_size": typo.suggestion_size if typo else 15.0,
                "text_weight": typo.suggestion_weight if typo else 500,
                "radius": spacing.suggestion_radius if spacing else 12,
            },
            "keys": {
                "rows": [
                    [{"label": k.label, "code": k.code,
                      "width": k.width, "special": k.special,
                      "pressed": k.code == self._pressed_key_code}
                     for k in row]
                    for row in layout
                ],
                "background": colors.key_background if colors else "#FFFFFF",
                "special_background": colors.key_special_background if colors else "#E8D5C4",
                "pressed_color": colors.key_pressed if colors else "#D4A574",
                "text_color": colors.key_text if colors else "#1A1A2E",
                "shadow": {
                    "offset": effects.key_shadow_offset if effects else (0, 1, 1, 0),
                    "opacity": effects.key_shadow_opacity if effects else 0.15,
                },
                "radius": spacing.key_radius if spacing else 8,
                "margin": spacing.key_margin if spacing else 3,
                "label_size": typo.key_label_size if typo else 23.0,
                "label_weight": typo.key_label_weight if typo else 400,
                "special_label_size": typo.key_special_label_size if typo else 16.0,
                "special_label_weight": typo.key_special_label_weight if typo else 500,
            },
            "animation": {
                "show_duration": anim.keyboard_show_duration if anim else 0.35,
                "show_curve": anim.keyboard_show_curve if anim else (0.16, 1.0, 0.3, 1.0),
                "hide_duration": anim.keyboard_hide_duration if anim else 0.28,
                "hide_curve": anim.keyboard_hide_curve if anim else (0.42, 0.0, 0.58, 1.0),
                "key_press_scale": anim.key_press_scale if anim else 0.92,
                "key_press_duration": anim.key_press_duration if anim else 0.08,
            },
        }


def main():
    """Standalone keyboard process."""
    logging.basicConfig(level=logging.INFO)
    keyboard = OnScreenKeyboard()

    def on_key(code):
        print(code, end="", flush=True)

    def on_special(code):
        if code == "enter":
            print()
        elif code == "backspace":
            print("\b \b", end="", flush=True)

    keyboard.set_key_handler(on_key, on_special)
    keyboard.show()

    logger.info("On-screen keyboard ready")
    logger.info("Layout: %s", keyboard.layer.name)
    logger.info("Keys per row: %s",
                [len(r) for r in keyboard.get_current_layout()])


if __name__ == "__main__":
    main()
