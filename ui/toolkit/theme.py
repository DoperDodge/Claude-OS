"""
Claude-OS UI Theme

Defines colors, spacing, typography, and styling constants for the
entire UI. All widgets reference the theme rather than hardcoding
visual properties, enabling consistent styling and future theming.

Design language: clean, modern mobile OS inspired by Material Design 3
with Claude's warm orange accent palette.
"""

from dataclasses import dataclass, field


@dataclass(frozen=True)
class Color:
    """RGBA color (0-255 per channel)."""
    r: int
    g: int
    b: int
    a: int = 255

    def with_alpha(self, a: int) -> "Color":
        return Color(self.r, self.g, self.b, a)

    def blend(self, other: "Color", t: float) -> "Color":
        """Blend toward another color. t=0 is self, t=1 is other."""
        inv = 1 - t
        return Color(
            int(self.r * inv + other.r * t),
            int(self.g * inv + other.g * t),
            int(self.b * inv + other.b * t),
            int(self.a * inv + other.a * t),
        )

    @property
    def bgra(self) -> tuple[int, int, int, int]:
        """Return as BGRA tuple (for pixel buffer format)."""
        return (self.b, self.g, self.r, self.a)

    @property
    def hex(self) -> str:
        return f"#{self.r:02x}{self.g:02x}{self.b:02x}"


# --- Color Palette ---

class Colors:
    """Color palette for the OS theme."""

    # Primary (Claude orange)
    PRIMARY = Color(217, 119, 52)
    PRIMARY_LIGHT = Color(240, 160, 100)
    PRIMARY_DARK = Color(180, 90, 30)

    # Surface colors
    BACKGROUND = Color(10, 10, 20)
    SURFACE = Color(24, 24, 36)
    SURFACE_DIM = Color(18, 18, 28)
    SURFACE_BRIGHT = Color(38, 38, 52)
    SURFACE_CONTAINER = Color(30, 30, 44)

    # Text colors
    TEXT_PRIMARY = Color(240, 240, 245)
    TEXT_SECONDARY = Color(180, 180, 195)
    TEXT_DISABLED = Color(100, 100, 115)
    TEXT_ON_PRIMARY = Color(255, 255, 255)

    # Accent colors
    SUCCESS = Color(76, 175, 80)
    WARNING = Color(255, 193, 7)
    ERROR = Color(244, 67, 54)
    INFO = Color(33, 150, 243)

    # Interactive states
    RIPPLE = Color(255, 255, 255, 30)
    HOVER = Color(255, 255, 255, 10)
    PRESSED = Color(255, 255, 255, 20)
    FOCUSED = Color(217, 119, 52, 40)

    # Borders & dividers
    BORDER = Color(60, 60, 75)
    DIVIDER = Color(45, 45, 60)

    # Transparent
    TRANSPARENT = Color(0, 0, 0, 0)
    WHITE = Color(255, 255, 255)
    BLACK = Color(0, 0, 0)


# --- Spacing ---

class Spacing:
    """Spacing constants (logical pixels)."""
    NONE = 0
    XS = 4
    SM = 8
    MD = 12
    LG = 16
    XL = 24
    XXL = 32
    XXXL = 48

    # Component-specific
    BUTTON_PADDING_H = 24
    BUTTON_PADDING_V = 12
    INPUT_PADDING_H = 16
    INPUT_PADDING_V = 12
    CARD_PADDING = 16
    STATUS_BAR_HEIGHT = 48
    KEYBOARD_HEIGHT = 300


# --- Typography ---

@dataclass(frozen=True)
class FontStyle:
    """Font style specification."""
    size: int       # Pixel height
    weight: str     # "regular", "bold", "light"
    spacing: int    # Letter spacing in pixels (0 = normal)

    @property
    def line_height(self) -> int:
        """Line height (roughly 1.4x font size)."""
        return int(self.size * 1.4)


class Typography:
    """Typography scale."""

    # Display (large headers)
    DISPLAY_LARGE = FontStyle(size=32, weight="regular", spacing=0)
    DISPLAY_MEDIUM = FontStyle(size=28, weight="regular", spacing=0)

    # Headline
    HEADLINE_LARGE = FontStyle(size=24, weight="bold", spacing=0)
    HEADLINE_MEDIUM = FontStyle(size=20, weight="bold", spacing=0)
    HEADLINE_SMALL = FontStyle(size=18, weight="bold", spacing=0)

    # Title
    TITLE_LARGE = FontStyle(size=18, weight="bold", spacing=0)
    TITLE_MEDIUM = FontStyle(size=16, weight="bold", spacing=0)

    # Body
    BODY_LARGE = FontStyle(size=16, weight="regular", spacing=0)
    BODY_MEDIUM = FontStyle(size=14, weight="regular", spacing=0)
    BODY_SMALL = FontStyle(size=12, weight="regular", spacing=0)

    # Label
    LABEL_LARGE = FontStyle(size=14, weight="bold", spacing=1)
    LABEL_MEDIUM = FontStyle(size=12, weight="bold", spacing=1)
    LABEL_SMALL = FontStyle(size=10, weight="bold", spacing=1)


# --- Corner Radius ---

class Radius:
    """Corner radius constants."""
    NONE = 0
    SM = 4
    MD = 8
    LG = 12
    XL = 16
    FULL = 9999  # Fully rounded (pill shape)


# --- Composite Theme ---

@dataclass
class Theme:
    """Complete theme combining all style tokens."""
    colors: type = Colors
    spacing: type = Spacing
    typography: type = Typography
    radius: type = Radius

    # Animation
    anim_duration_fast: int = 100   # ms
    anim_duration_normal: int = 200
    anim_duration_slow: int = 350

    # Shadows (future — for elevated surfaces)
    elevation_low: int = 2
    elevation_medium: int = 4
    elevation_high: int = 8


# Singleton default theme
default_theme = Theme()
