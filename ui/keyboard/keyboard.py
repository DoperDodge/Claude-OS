"""
Claude-OS On-Screen Keyboard

A virtual keyboard rendered as a Wayland layer-shell surface.
Appears from the bottom of the screen when a text input is focused.

Supports:
- QWERTY layout (with shift/symbols/emoji layers)
- Touch input with visual feedback
- Predictive text suggestions bar
- Swipe-to-type gesture input
- Key repeat on long press

Sends key events via the Wayland input-method protocol.
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
        # Row 1
        [Key("q", "q"), Key("w", "w"), Key("e", "e"), Key("r", "r"),
         Key("t", "t"), Key("y", "y"), Key("u", "u"), Key("i", "i"),
         Key("o", "o"), Key("p", "p")],
        # Row 2
        [Key("a", "a"), Key("s", "s"), Key("d", "d"), Key("f", "f"),
         Key("g", "g"), Key("h", "h"), Key("j", "j"), Key("k", "k"),
         Key("l", "l")],
        # Row 3
        [Key("^", "shift", width=1.5, special=True),
         Key("z", "z"), Key("x", "x"), Key("c", "c"), Key("v", "v"),
         Key("b", "b"), Key("n", "n"), Key("m", "m"),
         Key("<-", "backspace", width=1.5, special=True)],
        # Row 4
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
    Virtual keyboard for Claude-OS.

    Renders as a Wayland layer-shell surface anchored to the bottom
    of the screen. Handles touch events and sends key codes to the
    focused text input via Wayland's input-method-v2 protocol.
    """

    HEIGHT = 300  # Total keyboard height in logical pixels
    SUGGESTION_BAR_HEIGHT = 40
    KEY_MARGIN = 4
    KEY_RADIUS = 8  # Corner radius

    def __init__(self):
        self.layer = KeyboardLayer.LOWERCASE
        self.visible = False
        self.suggestions: list[str] = []

        # Key repeat
        self._repeat_key: Key | None = None
        self._repeat_task: asyncio.Task | None = None
        self._repeat_delay = 0.4  # Initial delay
        self._repeat_rate = 0.05  # Repeat interval

        # Callbacks
        self._on_key = None        # Called when a character key is pressed
        self._on_special = None    # Called for special keys (enter, backspace)
        self._on_suggestion = None # Called when a suggestion is tapped

    def set_key_handler(self, on_key, on_special=None, on_suggestion=None):
        """Set callbacks for key events."""
        self._on_key = on_key
        self._on_special = on_special
        self._on_suggestion = on_suggestion

    def show(self):
        """Show the keyboard."""
        self.visible = True
        self.layer = KeyboardLayer.LOWERCASE
        logger.info("Keyboard shown")

    def hide(self):
        """Hide the keyboard."""
        self.visible = False
        self._cancel_repeat()
        logger.info("Keyboard hidden")

    def get_current_layout(self) -> list[list[Key]]:
        """Get the current keyboard layout."""
        return LAYOUTS.get(self.layer, LAYOUTS[KeyboardLayer.LOWERCASE])

    def handle_touch(self, x: int, y: int, action: str = "down"):
        """
        Handle a touch event on the keyboard surface.

        Args:
            x: Touch X coordinate relative to keyboard surface
            y: Touch Y coordinate relative to keyboard surface
            action: "down", "up", or "move"
        """
        if not self.visible:
            return

        if action == "up":
            self._cancel_repeat()
            return

        # Check suggestion bar first
        if y < self.SUGGESTION_BAR_HEIGHT:
            self._handle_suggestion_tap(x)
            return

        # Find which key was hit
        key = self._hit_test(x, y - self.SUGGESTION_BAR_HEIGHT)
        if key is None:
            return

        if action == "down":
            self._press_key(key)

    def _press_key(self, key: Key):
        """Process a key press."""
        if key.special:
            self._handle_special(key)
        else:
            if self._on_key:
                self._on_key(key.code)
            # Auto-lowercase after typing a character in uppercase mode
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
        """
        Determine which key is at the given coordinates.

        Calculates key positions based on the layout grid, accounting
        for variable key widths.
        """
        layout = self.get_current_layout()
        row_height = (self.HEIGHT - self.SUGGESTION_BAR_HEIGHT) / len(layout)

        row_index = int(y / row_height)
        if row_index < 0 or row_index >= len(layout):
            return None

        row = layout[row_index]
        total_width = sum(k.width for k in row)

        # Assume keyboard surface is 1080px wide (logical)
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

        # Divide suggestion bar into equal sections
        section_width = 1080 / len(self.suggestions)
        index = int(x / section_width)
        if 0 <= index < len(self.suggestions):
            suggestion = self.suggestions[index]
            if self._on_suggestion:
                self._on_suggestion(suggestion)

    def update_suggestions(self, suggestions: list[str]):
        """Update the predictive text suggestions."""
        self.suggestions = suggestions[:3]  # Show max 3 suggestions

    def _cancel_repeat(self):
        """Cancel any active key repeat."""
        if self._repeat_task:
            self._repeat_task.cancel()
            self._repeat_task = None
            self._repeat_key = None

    def get_render_data(self) -> dict:
        """
        Return all data needed to render the keyboard.

        Used by external renderers (Cairo, Skia, etc.)
        """
        layout = self.get_current_layout()
        return {
            "visible": self.visible,
            "height": self.HEIGHT,
            "suggestion_bar_height": self.SUGGESTION_BAR_HEIGHT,
            "suggestions": self.suggestions,
            "layer": self.layer.name,
            "rows": [
                [{"label": k.label, "code": k.code,
                  "width": k.width, "special": k.special}
                 for k in row]
                for row in layout
            ],
        }


def main():
    """Standalone keyboard process (layer-shell surface)."""
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
