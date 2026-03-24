"""
Claude-OS Design System

A unified theme blending Claude's warm, intelligent aesthetic with Apple's
design principles — clean typography, frosted glass, spring animations,
generous spacing, and subtle depth.

Design Language:
    - Claude: Warm terracotta/coral accents, cream backgrounds, approachable intelligence
    - Apple: Precision typography, depth via blur/shadow, spring-based motion, minimalism

All UI components reference this module for consistent visual identity.
"""

from dataclasses import dataclass, field
from enum import Enum, auto
from typing import Tuple


# ---------------------------------------------------------------------------
# Color Palette
# ---------------------------------------------------------------------------

@dataclass(frozen=True)
class Color:
    """RGBA color (0-255 per channel)."""
    r: int
    g: int
    b: int
    a: int = 255

    @property
    def hex(self) -> str:
        """Return #RRGGBB hex string."""
        return f"#{self.r:02X}{self.g:02X}{self.b:02X}"

    @property
    def rgba(self) -> Tuple[int, int, int, int]:
        return (self.r, self.g, self.b, self.a)

    @property
    def rgba_f(self) -> Tuple[float, float, float, float]:
        """Normalized 0.0-1.0 floats (for Cairo/OpenGL)."""
        return (self.r / 255, self.g / 255, self.b / 255, self.a / 255)

    def with_alpha(self, alpha: int) -> "Color":
        """Return a copy with a different alpha value."""
        return Color(self.r, self.g, self.b, alpha)


class ColorPalette:
    """Claude-OS color palette — warm, refined, and accessible."""

    # --- Brand: Claude ---
    CLAUDE_TERRACOTTA = Color(217, 119, 87)     # #D97757  Primary accent
    CLAUDE_CORAL = Color(228, 147, 120)          # #E49378  Lighter accent
    CLAUDE_CREAM = Color(250, 243, 232)          # #FAF3E8  Light background
    CLAUDE_WARM_WHITE = Color(255, 251, 245)     # #FFFBF5  Card/surface bg
    CLAUDE_SAND = Color(237, 226, 209)           # #EDE2D1  Subtle dividers
    CLAUDE_BROWN = Color(139, 111, 92)           # #8B6F5C  Secondary text
    CLAUDE_DEEP = Color(45, 43, 40)              # #2D2B28  Primary text (light)

    # --- Neutrals ---
    WHITE = Color(255, 255, 255)
    BLACK = Color(0, 0, 0)
    GRAY_50 = Color(249, 250, 251)
    GRAY_100 = Color(243, 244, 246)
    GRAY_200 = Color(229, 231, 235)
    GRAY_300 = Color(209, 213, 219)
    GRAY_400 = Color(156, 163, 175)
    GRAY_500 = Color(107, 114, 128)
    GRAY_600 = Color(75, 85, 99)
    GRAY_700 = Color(55, 65, 81)
    GRAY_800 = Color(31, 41, 55)
    GRAY_900 = Color(17, 24, 39)

    # --- Dark mode surfaces ---
    DARK_BG = Color(28, 27, 31)                  # #1C1B1F
    DARK_SURFACE = Color(44, 42, 48)             # #2C2A30
    DARK_ELEVATED = Color(58, 56, 62)            # #3A383E
    DARK_CARD = Color(50, 48, 54)                # #323036

    # --- Semantic ---
    SUCCESS = Color(52, 199, 89)                 # iOS green
    WARNING = Color(255, 159, 10)                # iOS orange
    ERROR = Color(255, 69, 58)                   # iOS red
    INFO = Color(90, 200, 250)                   # iOS teal

    # --- Frosted glass ---
    GLASS_LIGHT = Color(255, 255, 255, 178)      # 70% white
    GLASS_DARK = Color(28, 27, 31, 204)          # 80% dark


# ---------------------------------------------------------------------------
# Typography
# ---------------------------------------------------------------------------

@dataclass(frozen=True)
class FontWeight:
    """Font weight constants (matching CSS/Apple naming)."""
    ULTRALIGHT: int = 100
    THIN: int = 200
    LIGHT: int = 300
    REGULAR: int = 400
    MEDIUM: int = 500
    SEMIBOLD: int = 600
    BOLD: int = 700
    HEAVY: int = 800
    BLACK: int = 900


@dataclass(frozen=True)
class TypeStyle:
    """A complete typography specification."""
    family: str
    size: float         # Points
    weight: int         # FontWeight value
    line_height: float  # Multiplier (e.g. 1.4)
    letter_spacing: float = 0.0  # Points (tracking)

    @property
    def line_height_px(self) -> float:
        """Absolute line height in points."""
        return self.size * self.line_height


class Typography:
    """
    Type scale inspired by Apple's SF system — clear hierarchy,
    optimized for mobile readability.

    Uses system fonts with fallbacks:
    - Primary: "SF Pro Display" (or Noto Sans for Linux builds)
    - Mono: "SF Mono" (or Noto Sans Mono)
    """

    FONT_FAMILY = "SF Pro Display, Noto Sans, Helvetica Neue, sans-serif"
    FONT_FAMILY_MONO = "SF Mono, Noto Sans Mono, Menlo, monospace"
    FONT_FAMILY_ROUNDED = "SF Pro Rounded, Noto Sans, sans-serif"

    # --- Display ---
    LARGE_TITLE = TypeStyle(FONT_FAMILY, 34, 700, 1.2, -0.4)
    TITLE_1 = TypeStyle(FONT_FAMILY, 28, 700, 1.2, 0.36)
    TITLE_2 = TypeStyle(FONT_FAMILY, 22, 700, 1.3, 0.35)
    TITLE_3 = TypeStyle(FONT_FAMILY, 20, 600, 1.3, 0.38)

    # --- Body ---
    HEADLINE = TypeStyle(FONT_FAMILY, 17, 600, 1.4, -0.4)
    BODY = TypeStyle(FONT_FAMILY, 17, 400, 1.4, -0.4)
    BODY_BOLD = TypeStyle(FONT_FAMILY, 17, 600, 1.4, -0.4)
    CALLOUT = TypeStyle(FONT_FAMILY, 16, 400, 1.4, -0.3)
    SUBHEADLINE = TypeStyle(FONT_FAMILY, 15, 400, 1.35, -0.2)
    FOOTNOTE = TypeStyle(FONT_FAMILY, 13, 400, 1.35, -0.1)
    CAPTION_1 = TypeStyle(FONT_FAMILY, 12, 400, 1.3, 0.0)
    CAPTION_2 = TypeStyle(FONT_FAMILY, 11, 400, 1.3, 0.1)

    # --- Special ---
    CLOCK_LARGE = TypeStyle(FONT_FAMILY_ROUNDED, 76, 200, 1.0, -2.0)
    CLOCK_MEDIUM = TypeStyle(FONT_FAMILY_ROUNDED, 48, 300, 1.0, -1.0)
    STATUS_BAR = TypeStyle(FONT_FAMILY, 14, 600, 1.0, 0.0)
    KEYBOARD_KEY = TypeStyle(FONT_FAMILY, 22, 400, 1.0, 0.2)
    KEYBOARD_SPECIAL = TypeStyle(FONT_FAMILY, 14, 500, 1.0, 0.1)
    CHAT_BUBBLE = TypeStyle(FONT_FAMILY, 16, 400, 1.45, -0.2)
    CODE_BLOCK = TypeStyle(FONT_FAMILY_MONO, 14, 400, 1.5, 0.0)


# ---------------------------------------------------------------------------
# Spacing & Layout
# ---------------------------------------------------------------------------

class Spacing:
    """Consistent spacing scale (multiples of 4px base unit)."""

    XXXS = 2
    XXS = 4
    XS = 8
    SM = 12
    MD = 16
    LG = 20
    XL = 24
    XXL = 32
    XXXL = 40
    XXXXL = 48

    # Named aliases for common use
    PADDING_SCREEN = 20       # Screen edge padding
    PADDING_CARD = 16         # Card internal padding
    PADDING_CELL = 12         # List cell padding
    GAP_ELEMENTS = 8          # Between sibling elements
    GAP_SECTIONS = 24         # Between content sections


class Layout:
    """Layout constants for the mobile form factor."""

    # Screen
    SCREEN_WIDTH = 1080       # Logical pixels (before scale)
    SCREEN_HEIGHT = 2340

    # Status bar
    STATUS_BAR_HEIGHT = 54    # Slightly taller for modern feel
    STATUS_BAR_NOTCH_WIDTH = 220   # Dynamic Island-style pill width
    STATUS_BAR_NOTCH_HEIGHT = 36
    STATUS_BAR_NOTCH_RADIUS = 18

    # Navigation
    HOME_INDICATOR_HEIGHT = 34
    HOME_INDICATOR_WIDTH = 134
    HOME_INDICATOR_RADIUS = 5

    # Keyboard
    KEYBOARD_HEIGHT = 300
    KEYBOARD_SUGGESTION_HEIGHT = 44
    KEYBOARD_KEY_HEIGHT = 42
    KEYBOARD_KEY_RADIUS = 8
    KEYBOARD_KEY_MARGIN = 6

    # Cards & Surfaces
    CARD_RADIUS = 16
    CARD_RADIUS_LG = 22
    CARD_RADIUS_SM = 12
    SHEET_RADIUS = 24         # Bottom sheets / modal sheets
    BUTTON_RADIUS = 12
    BUTTON_RADIUS_PILL = 999  # Fully rounded
    INPUT_RADIUS = 12

    # Chat
    CHAT_BUBBLE_RADIUS = 20
    CHAT_BUBBLE_TAIL_RADIUS = 4
    CHAT_INPUT_HEIGHT = 52
    CHAT_MAX_BUBBLE_WIDTH = 0.78  # 78% of screen width

    # Notification panel
    NOTIFICATION_CARD_RADIUS = 16
    QUICK_SETTINGS_TILE_SIZE = 64
    QUICK_SETTINGS_TILE_RADIUS = 16


# ---------------------------------------------------------------------------
# Animation & Motion
# ---------------------------------------------------------------------------

@dataclass(frozen=True)
class SpringConfig:
    """Spring physics configuration for natural motion."""
    damping: float       # 0.0 = no damping (infinite bounce), 1.0 = critical
    stiffness: float     # Higher = snappier
    mass: float = 1.0    # Higher = more inertia

    @property
    def duration_estimate(self) -> float:
        """Approximate animation duration in seconds."""
        # Rough estimate based on spring parameters
        if self.damping >= 1.0:
            return 0.3 + (self.mass / self.stiffness) * 2
        return 0.4 + (1.0 - self.damping) * 0.6


@dataclass(frozen=True)
class EasingCurve:
    """Cubic bezier easing curve (matching CSS transition-timing-function)."""
    x1: float
    y1: float
    x2: float
    y2: float
    name: str = ""


class Animation:
    """
    Animation presets — spring physics for interactive gestures,
    bezier curves for non-interactive transitions.

    Inspired by Apple's UIKit/SwiftUI spring system.
    """

    # --- Spring Presets ---
    SPRING_SNAPPY = SpringConfig(damping=0.85, stiffness=300)
    SPRING_BOUNCY = SpringConfig(damping=0.7, stiffness=200)
    SPRING_SMOOTH = SpringConfig(damping=0.9, stiffness=180)
    SPRING_GENTLE = SpringConfig(damping=0.95, stiffness=120)
    SPRING_INTERACTIVE = SpringConfig(damping=0.86, stiffness=400)

    # --- Easing Curves ---
    EASE_IN_OUT = EasingCurve(0.42, 0.0, 0.58, 1.0, "ease-in-out")
    EASE_OUT = EasingCurve(0.0, 0.0, 0.58, 1.0, "ease-out")
    EASE_IN = EasingCurve(0.42, 0.0, 1.0, 1.0, "ease-in")
    EASE_OUT_EXPO = EasingCurve(0.16, 1.0, 0.3, 1.0, "ease-out-expo")
    EASE_OUT_BACK = EasingCurve(0.34, 1.56, 0.64, 1.0, "ease-out-back")
    EASE_IN_OUT_QUINT = EasingCurve(0.83, 0.0, 0.17, 1.0, "ease-in-out-quint")

    # --- Duration Presets (seconds) ---
    DURATION_INSTANT = 0.1
    DURATION_FAST = 0.2
    DURATION_NORMAL = 0.35
    DURATION_SLOW = 0.5
    DURATION_SHEET = 0.45
    DURATION_PAGE = 0.4

    # --- Named Animation Configs ---
    # (duration, easing_curve_or_spring)
    KEYBOARD_SHOW = (0.3, SPRING_SNAPPY)
    KEYBOARD_HIDE = (0.25, EASE_OUT)
    NOTIFICATION_SLIDE = (0.35, SPRING_SMOOTH)
    APP_LAUNCH = (0.4, SPRING_BOUNCY)
    APP_CLOSE = (0.3, EASE_IN_OUT)
    SHEET_PRESENT = (0.45, SPRING_GENTLE)
    SHEET_DISMISS = (0.35, EASE_IN_OUT)
    PAGE_TRANSITION = (0.4, EASE_IN_OUT_QUINT)
    FADE_IN = (0.2, EASE_OUT)
    FADE_OUT = (0.15, EASE_IN)
    LOCK_SCREEN_CLOCK = (0.6, SPRING_GENTLE)
    BUTTON_PRESS = (0.1, EASE_OUT)
    BUTTON_RELEASE = (0.2, SPRING_SNAPPY)
    RIPPLE = (0.5, EASE_OUT_EXPO)
    CHAT_BUBBLE_APPEAR = (0.3, SPRING_BOUNCY)
    TYPING_INDICATOR = (0.6, EASE_IN_OUT)


# ---------------------------------------------------------------------------
# Shadows & Depth
# ---------------------------------------------------------------------------

@dataclass(frozen=True)
class Shadow:
    """Drop shadow definition."""
    offset_x: float
    offset_y: float
    blur_radius: float
    spread: float
    color: Color


class Shadows:
    """Layered shadow presets for depth hierarchy."""

    NONE = Shadow(0, 0, 0, 0, Color(0, 0, 0, 0))

    # Subtle elevation (cards, buttons)
    SM = Shadow(0, 1, 3, 0, Color(0, 0, 0, 20))
    # Medium elevation (floating elements, popovers)
    MD = Shadow(0, 4, 12, 0, Color(0, 0, 0, 30))
    # High elevation (modals, sheets)
    LG = Shadow(0, 8, 24, -4, Color(0, 0, 0, 40))
    # Ultra elevation (dragged elements)
    XL = Shadow(0, 16, 48, -8, Color(0, 0, 0, 50))

    # Keyboard shadow (cast upward from bottom)
    KEYBOARD = Shadow(0, -2, 16, 0, Color(0, 0, 0, 25))
    # Status bar subtle bottom edge
    STATUS_BAR = Shadow(0, 1, 4, 0, Color(0, 0, 0, 10))
    # Chat bubble shadow
    CHAT_BUBBLE = Shadow(0, 1, 4, 0, Color(0, 0, 0, 8))
    # Notification card
    NOTIFICATION = Shadow(0, 4, 16, 0, Color(0, 0, 0, 20))


# ---------------------------------------------------------------------------
# Blur / Vibrancy
# ---------------------------------------------------------------------------

@dataclass(frozen=True)
class BlurStyle:
    """Background blur configuration for frosted glass effects."""
    radius: float            # Blur radius in pixels
    saturation: float = 1.8  # Color saturation boost
    tint_color: Color = Color(255, 255, 255, 0)
    tint_opacity: float = 0.0


class Blur:
    """Blur presets for frosted glass / vibrancy effects."""

    # Light mode
    REGULAR_LIGHT = BlurStyle(radius=20, saturation=1.8,
                               tint_color=Color(255, 255, 255, 178))
    THIN_LIGHT = BlurStyle(radius=12, saturation=1.5,
                            tint_color=Color(255, 255, 255, 128))
    THICK_LIGHT = BlurStyle(radius=30, saturation=2.0,
                             tint_color=Color(255, 255, 255, 204))

    # Dark mode
    REGULAR_DARK = BlurStyle(radius=20, saturation=1.8,
                              tint_color=Color(28, 27, 31, 178))
    THIN_DARK = BlurStyle(radius=12, saturation=1.5,
                           tint_color=Color(28, 27, 31, 128))
    THICK_DARK = BlurStyle(radius=30, saturation=2.0,
                            tint_color=Color(28, 27, 31, 204))

    # Special
    STATUS_BAR = BlurStyle(radius=24, saturation=1.6,
                            tint_color=Color(255, 251, 245, 153))
    KEYBOARD_BG = BlurStyle(radius=30, saturation=1.4,
                             tint_color=Color(237, 226, 209, 178))
    NOTIFICATION = BlurStyle(radius=20, saturation=1.8,
                              tint_color=Color(255, 251, 245, 178))


# ---------------------------------------------------------------------------
# Theme Modes
# ---------------------------------------------------------------------------

class ThemeMode(Enum):
    LIGHT = auto()
    DARK = auto()


@dataclass
class ThemeColors:
    """Resolved color set for a specific theme mode."""
    # Backgrounds
    bg_primary: Color
    bg_secondary: Color
    bg_tertiary: Color
    bg_elevated: Color
    bg_grouped: Color

    # Text
    text_primary: Color
    text_secondary: Color
    text_tertiary: Color
    text_placeholder: Color

    # Accent
    accent: Color
    accent_light: Color

    # Chat bubbles
    bubble_user: Color
    bubble_user_text: Color
    bubble_assistant: Color
    bubble_assistant_text: Color

    # Status bar
    status_bar_bg: Color
    status_bar_text: Color

    # Keyboard
    keyboard_bg: Color
    keyboard_key: Color
    keyboard_key_special: Color
    keyboard_key_text: Color
    keyboard_key_text_special: Color

    # Separators / dividers
    separator: Color
    separator_opaque: Color

    # Glass
    glass_bg: Color

    # System
    success: Color
    warning: Color
    error: Color
    info: Color


# Pre-built light theme
LIGHT_THEME = ThemeColors(
    bg_primary=ColorPalette.CLAUDE_WARM_WHITE,
    bg_secondary=ColorPalette.CLAUDE_CREAM,
    bg_tertiary=ColorPalette.GRAY_100,
    bg_elevated=ColorPalette.WHITE,
    bg_grouped=ColorPalette.CLAUDE_CREAM,

    text_primary=ColorPalette.CLAUDE_DEEP,
    text_secondary=ColorPalette.CLAUDE_BROWN,
    text_tertiary=ColorPalette.GRAY_400,
    text_placeholder=ColorPalette.GRAY_300,

    accent=ColorPalette.CLAUDE_TERRACOTTA,
    accent_light=ColorPalette.CLAUDE_CORAL,

    bubble_user=ColorPalette.CLAUDE_TERRACOTTA,
    bubble_user_text=ColorPalette.WHITE,
    bubble_assistant=ColorPalette.WHITE,
    bubble_assistant_text=ColorPalette.CLAUDE_DEEP,

    status_bar_bg=Color(255, 251, 245, 204),
    status_bar_text=ColorPalette.CLAUDE_DEEP,

    keyboard_bg=ColorPalette.CLAUDE_SAND,
    keyboard_key=ColorPalette.WHITE,
    keyboard_key_special=Color(195, 183, 167),
    keyboard_key_text=ColorPalette.CLAUDE_DEEP,
    keyboard_key_text_special=ColorPalette.CLAUDE_DEEP,

    separator=Color(139, 111, 92, 40),
    separator_opaque=ColorPalette.CLAUDE_SAND,

    glass_bg=ColorPalette.GLASS_LIGHT,

    success=ColorPalette.SUCCESS,
    warning=ColorPalette.WARNING,
    error=ColorPalette.ERROR,
    info=ColorPalette.INFO,
)

# Pre-built dark theme
DARK_THEME = ThemeColors(
    bg_primary=ColorPalette.DARK_BG,
    bg_secondary=ColorPalette.DARK_SURFACE,
    bg_tertiary=ColorPalette.DARK_ELEVATED,
    bg_elevated=ColorPalette.DARK_CARD,
    bg_grouped=ColorPalette.DARK_SURFACE,

    text_primary=Color(245, 240, 235),
    text_secondary=Color(180, 165, 150),
    text_tertiary=ColorPalette.GRAY_500,
    text_placeholder=ColorPalette.GRAY_600,

    accent=ColorPalette.CLAUDE_CORAL,
    accent_light=ColorPalette.CLAUDE_TERRACOTTA,

    bubble_user=ColorPalette.CLAUDE_TERRACOTTA,
    bubble_user_text=ColorPalette.WHITE,
    bubble_assistant=ColorPalette.DARK_ELEVATED,
    bubble_assistant_text=Color(245, 240, 235),

    status_bar_bg=Color(28, 27, 31, 204),
    status_bar_text=Color(245, 240, 235),

    keyboard_bg=Color(44, 42, 48),
    keyboard_key=Color(72, 70, 76),
    keyboard_key_special=Color(58, 56, 62),
    keyboard_key_text=Color(245, 240, 235),
    keyboard_key_text_special=Color(220, 210, 200),

    separator=Color(255, 255, 255, 25),
    separator_opaque=ColorPalette.DARK_ELEVATED,

    glass_bg=ColorPalette.GLASS_DARK,

    success=ColorPalette.SUCCESS,
    warning=ColorPalette.WARNING,
    error=ColorPalette.ERROR,
    info=ColorPalette.INFO,
)


# ---------------------------------------------------------------------------
# Active Theme
# ---------------------------------------------------------------------------

class Theme:
    """
    Global theme accessor.

    Usage:
        from theme import Theme
        colors = Theme.colors()
        bg = colors.bg_primary
    """

    _mode: ThemeMode = ThemeMode.LIGHT

    @classmethod
    def set_mode(cls, mode: ThemeMode):
        cls._mode = mode

    @classmethod
    def mode(cls) -> ThemeMode:
        return cls._mode

    @classmethod
    def toggle(cls):
        cls._mode = (ThemeMode.DARK if cls._mode == ThemeMode.LIGHT
                      else ThemeMode.LIGHT)

    @classmethod
    def colors(cls) -> ThemeColors:
        return DARK_THEME if cls._mode == ThemeMode.DARK else LIGHT_THEME

    @classmethod
    def is_dark(cls) -> bool:
        return cls._mode == ThemeMode.DARK
