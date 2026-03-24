"""
Claude-OS Design System — Core Theme Definition

Merges Claude's warm, approachable identity with Apple's spatial design
philosophy. All UI components reference these tokens for consistent rendering.

Color Philosophy:
    - Claude Terracotta (#D4A574) and Sand (#E8D5C4) as signature warmth
    - Deep Navy (#1A1A2E) and Charcoal (#16213E) for grounding depth
    - Soft whites and creams for breathing room
    - Accent gradients that feel alive without being garish

Motion Philosophy:
    - Spring-based physics (iOS-caliber) for natural momentum
    - Micro-interactions at 120fps-ready timings
    - Respect reduce-motion preferences by collapsing to crossfades

Spatial Philosophy:
    - 8pt grid for all spacing
    - Layered glassmorphism: background → content → overlays
    - Corner radii follow Apple's superellipse (squircle) convention
"""

import logging
from dataclasses import dataclass, field
from enum import Enum, auto

logger = logging.getLogger("theme")


class ThemeMode(Enum):
    """Available theme modes."""
    LIGHT = auto()
    DARK = auto()
    HIGH_CONTRAST = auto()


# ---------------------------------------------------------------------------
# Color Palettes
# ---------------------------------------------------------------------------

@dataclass(frozen=True)
class ColorPalette:
    """Base color palette — all RGBA hex strings."""

    # -- Claude Signature --
    claude_terracotta: str = "#D4A574"
    claude_terracotta_light: str = "#E8C9A8"
    claude_terracotta_dark: str = "#B8875A"
    claude_sand: str = "#E8D5C4"
    claude_sand_light: str = "#F5EDE4"
    claude_cream: str = "#FAF6F1"

    # -- Primary Surface --
    background: str = "#FAF6F1"
    surface: str = "#FFFFFF"
    surface_secondary: str = "#F5EDE4"
    surface_tertiary: str = "#EDE3D8"

    # -- Depth & Navy --
    navy: str = "#1A1A2E"
    navy_light: str = "#16213E"
    charcoal: str = "#0F3460"

    # -- Text --
    text_primary: str = "#1A1A2E"
    text_secondary: str = "#5A5A72"
    text_tertiary: str = "#8E8E9E"
    text_on_accent: str = "#FFFFFF"
    text_on_surface: str = "#1A1A2E"

    # -- Accent --
    accent: str = "#D4A574"
    accent_secondary: str = "#E8967D"
    accent_gradient_start: str = "#D4A574"
    accent_gradient_end: str = "#E8967D"

    # -- Semantic --
    success: str = "#34C759"
    warning: str = "#FF9F0A"
    error: str = "#FF3B30"
    info: str = "#5AC8FA"

    # -- System --
    separator: str = "#E0D6CC"
    overlay: str = "rgba(26, 26, 46, 0.4)"
    glass_background: str = "rgba(255, 255, 255, 0.72)"
    glass_border: str = "rgba(255, 255, 255, 0.3)"

    # -- Notification Priority --
    notification_low: str = "#8E8E9E"
    notification_normal: str = "#5AC8FA"
    notification_high: str = "#FF9F0A"
    notification_urgent: str = "#FF3B30"

    # -- Keyboard --
    key_background: str = "#FFFFFF"
    key_special_background: str = "#E8D5C4"
    key_pressed: str = "#D4A574"
    key_text: str = "#1A1A2E"
    key_shadow: str = "rgba(0, 0, 0, 0.08)"
    suggestion_background: str = "rgba(232, 213, 196, 0.6)"
    suggestion_text: str = "#1A1A2E"
    suggestion_divider: str = "rgba(212, 165, 116, 0.3)"

    # -- Status Bar --
    statusbar_background: str = "rgba(250, 246, 241, 0.85)"
    statusbar_text: str = "#1A1A2E"
    statusbar_icon: str = "#5A5A72"
    battery_good: str = "#34C759"
    battery_low: str = "#FF9F0A"
    battery_critical: str = "#FF3B30"
    battery_charging: str = "#D4A574"


@dataclass(frozen=True)
class DarkPalette(ColorPalette):
    """Dark mode — deep navy surfaces with warm accent glow."""

    background: str = "#0D0D1A"
    surface: str = "#1A1A2E"
    surface_secondary: str = "#16213E"
    surface_tertiary: str = "#1E2A4A"

    text_primary: str = "#F5EDE4"
    text_secondary: str = "#B8B8CC"
    text_tertiary: str = "#7A7A8E"
    text_on_surface: str = "#F5EDE4"

    separator: str = "#2A2A3E"
    overlay: str = "rgba(0, 0, 0, 0.6)"
    glass_background: str = "rgba(26, 26, 46, 0.72)"
    glass_border: str = "rgba(255, 255, 255, 0.08)"

    key_background: str = "#2A2A3E"
    key_special_background: str = "#1E2A4A"
    key_pressed: str = "#D4A574"
    key_text: str = "#F5EDE4"
    key_shadow: str = "rgba(0, 0, 0, 0.3)"
    suggestion_background: str = "rgba(26, 26, 46, 0.8)"
    suggestion_text: str = "#E8D5C4"
    suggestion_divider: str = "rgba(212, 165, 116, 0.2)"

    statusbar_background: str = "rgba(13, 13, 26, 0.85)"
    statusbar_text: str = "#F5EDE4"
    statusbar_icon: str = "#B8B8CC"

    notification_low: str = "#7A7A8E"


# Alias for external import
LightPalette = ColorPalette


@dataclass(frozen=True)
class HighContrastPalette(ColorPalette):
    """High contrast mode for accessibility."""

    background: str = "#000000"
    surface: str = "#1A1A1A"
    surface_secondary: str = "#2A2A2A"
    surface_tertiary: str = "#3A3A3A"

    text_primary: str = "#FFFFFF"
    text_secondary: str = "#E0E0E0"
    text_tertiary: str = "#C0C0C0"
    text_on_surface: str = "#FFFFFF"
    text_on_accent: str = "#000000"

    accent: str = "#FFB366"
    accent_secondary: str = "#FF8A65"
    separator: str = "#FFFFFF"
    overlay: str = "rgba(0, 0, 0, 0.85)"
    glass_background: str = "rgba(0, 0, 0, 0.9)"
    glass_border: str = "rgba(255, 255, 255, 0.5)"

    key_background: str = "#2A2A2A"
    key_special_background: str = "#3A3A3A"
    key_pressed: str = "#FFB366"
    key_text: str = "#FFFFFF"
    key_shadow: str = "rgba(0, 0, 0, 0.5)"
    suggestion_background: str = "rgba(0, 0, 0, 0.9)"
    suggestion_text: str = "#FFFFFF"
    suggestion_divider: str = "rgba(255, 255, 255, 0.5)"

    statusbar_background: str = "rgba(0, 0, 0, 0.95)"
    statusbar_text: str = "#FFFFFF"
    statusbar_icon: str = "#FFFFFF"


# ---------------------------------------------------------------------------
# Typography
# ---------------------------------------------------------------------------

@dataclass(frozen=True)
class Typography:
    """
    Type scale following Apple's Dynamic Type with Claude-OS character.

    All sizes in logical points (scaled by display factor).
    Weights follow CSS convention: 400=regular, 500=medium, 600=semibold, 700=bold.
    """

    # -- Font Families --
    font_family: str = "Inter"
    font_family_display: str = "Inter"
    font_family_mono: str = "SF Mono"

    # -- Display (large headers, welcome screens) --
    display_large_size: float = 34.0
    display_large_weight: int = 700
    display_large_tracking: float = 0.37  # letter-spacing in pt
    display_large_leading: float = 41.0   # line-height in pt

    display_medium_size: float = 28.0
    display_medium_weight: int = 700
    display_medium_tracking: float = 0.36
    display_medium_leading: float = 34.0

    # -- Title --
    title_large_size: float = 22.0
    title_large_weight: int = 700
    title_large_tracking: float = 0.35
    title_large_leading: float = 28.0

    title_medium_size: float = 20.0
    title_medium_weight: int = 600
    title_medium_tracking: float = 0.38
    title_medium_leading: float = 25.0

    title_small_size: float = 17.0
    title_small_weight: int = 600
    title_small_tracking: float = -0.41
    title_small_leading: float = 22.0

    # -- Body --
    body_large_size: float = 17.0
    body_large_weight: int = 400
    body_large_tracking: float = -0.41
    body_large_leading: float = 22.0

    body_medium_size: float = 15.0
    body_medium_weight: int = 400
    body_medium_tracking: float = -0.24
    body_medium_leading: float = 20.0

    body_small_size: float = 13.0
    body_small_weight: int = 400
    body_small_tracking: float = -0.08
    body_small_leading: float = 18.0

    # -- Caption & Label --
    caption_size: float = 12.0
    caption_weight: int = 400
    caption_tracking: float = 0.0
    caption_leading: float = 16.0

    label_size: float = 11.0
    label_weight: int = 500
    label_tracking: float = 0.06
    label_leading: float = 13.0

    # -- Keyboard Keys --
    key_label_size: float = 23.0
    key_label_weight: int = 400
    key_special_label_size: float = 16.0
    key_special_label_weight: int = 500
    suggestion_size: float = 15.0
    suggestion_weight: int = 500

    # -- Status Bar --
    statusbar_time_size: float = 15.0
    statusbar_time_weight: int = 600
    statusbar_label_size: float = 12.0
    statusbar_label_weight: int = 500

    # -- Chat --
    chat_message_size: float = 16.0
    chat_message_weight: int = 400
    chat_message_leading: float = 22.0
    chat_sender_size: float = 13.0
    chat_sender_weight: int = 600

    # -- Notification --
    notification_title_size: float = 15.0
    notification_title_weight: int = 600
    notification_body_size: float = 13.0
    notification_body_weight: int = 400
    notification_app_size: float = 11.0
    notification_app_weight: int = 500


# ---------------------------------------------------------------------------
# Spacing (8pt grid)
# ---------------------------------------------------------------------------

@dataclass(frozen=True)
class Spacing:
    """
    Spacing tokens on a strict 8pt grid.

    Apple's HIG uses 8pt multiples for layout consistency.
    Half-values (4pt) allowed for tight micro-layouts.
    """

    # -- Base Units --
    xxs: int = 2
    xs: int = 4
    sm: int = 8
    md: int = 16
    lg: int = 24
    xl: int = 32
    xxl: int = 48
    xxxl: int = 64

    # -- Semantic Spacing --
    page_margin: int = 16
    card_padding: int = 16
    section_gap: int = 24
    list_item_height: int = 44   # Apple's minimum tap target
    list_item_padding: int = 16
    icon_text_gap: int = 12

    # -- Corner Radii (Apple squircle convention) --
    radius_xs: int = 4
    radius_sm: int = 8
    radius_md: int = 12
    radius_lg: int = 16
    radius_xl: int = 20
    radius_xxl: int = 24
    radius_pill: int = 999       # Fully rounded pill
    radius_circle: int = 9999

    # -- Key-specific --
    key_radius: int = 8
    key_margin: int = 3
    suggestion_radius: int = 12

    # -- Card & Sheet --
    card_radius: int = 16
    sheet_radius: int = 20
    notification_radius: int = 16
    modal_radius: int = 24

    # -- Status Bar --
    statusbar_padding_h: int = 16
    statusbar_padding_v: int = 8
    statusbar_item_gap: int = 6
    statusbar_pill_padding_h: int = 8
    statusbar_pill_padding_v: int = 3


# ---------------------------------------------------------------------------
# Animation Curves & Timings
# ---------------------------------------------------------------------------

@dataclass(frozen=True)
class Animation:
    """
    Motion tokens — spring physics and timing curves.

    Models iOS spring animations with damping ratio and response time.
    All durations in seconds. Curves defined as cubic-bezier control points.
    """

    # -- Spring Parameters (iOS UIKit-style) --
    # response = how fast it moves, damping = how much it bounces

    spring_snappy_response: float = 0.25
    spring_snappy_damping: float = 0.86

    spring_default_response: float = 0.35
    spring_default_damping: float = 0.82

    spring_gentle_response: float = 0.55
    spring_gentle_damping: float = 0.78

    spring_bouncy_response: float = 0.40
    spring_bouncy_damping: float = 0.68

    # -- Cubic Bezier Curves --
    ease_in: tuple = (0.42, 0.0, 1.0, 1.0)
    ease_out: tuple = (0.0, 0.0, 0.58, 1.0)
    ease_in_out: tuple = (0.42, 0.0, 0.58, 1.0)
    ease_out_expo: tuple = (0.16, 1.0, 0.3, 1.0)     # Dramatic deceleration
    ease_out_back: tuple = (0.34, 1.56, 0.64, 1.0)    # Slight overshoot
    ease_in_out_quint: tuple = (0.86, 0.0, 0.07, 1.0) # Apple keyboard curve

    # -- Duration Tokens --
    duration_instant: float = 0.1
    duration_fast: float = 0.15
    duration_normal: float = 0.25
    duration_slow: float = 0.35
    duration_gentle: float = 0.5
    duration_dramatic: float = 0.7

    # -- Specific Animations --
    keyboard_show_duration: float = 0.35
    keyboard_show_curve: tuple = (0.16, 1.0, 0.3, 1.0)    # ease_out_expo
    keyboard_hide_duration: float = 0.28
    keyboard_hide_curve: tuple = (0.42, 0.0, 0.58, 1.0)    # ease_in_out

    notification_enter_duration: float = 0.45
    notification_enter_curve: tuple = (0.34, 1.56, 0.64, 1.0)  # overshoot
    notification_exit_duration: float = 0.3
    notification_exit_curve: tuple = (0.42, 0.0, 1.0, 1.0)

    statusbar_fade_duration: float = 0.2
    statusbar_fade_curve: tuple = (0.0, 0.0, 0.58, 1.0)

    app_transition_duration: float = 0.45
    app_transition_curve: tuple = (0.16, 1.0, 0.3, 1.0)

    sheet_present_duration: float = 0.5
    sheet_present_spring_damping: float = 0.82
    sheet_dismiss_duration: float = 0.35

    key_press_scale: float = 0.92        # Scale down on press
    key_press_duration: float = 0.08
    key_release_duration: float = 0.15
    key_press_curve: tuple = (0.42, 0.0, 0.58, 1.0)

    # -- Gesture Physics --
    swipe_velocity_threshold: float = 500.0   # px/s to trigger gesture
    swipe_deceleration_rate: float = 0.998     # iOS-style momentum
    rubber_band_factor: float = 0.55           # Bounce-back elasticity

    # -- Reduce Motion Fallbacks --
    reduce_motion_duration: float = 0.01
    reduce_motion_crossfade: float = 0.15


# ---------------------------------------------------------------------------
# Visual Effects
# ---------------------------------------------------------------------------

@dataclass(frozen=True)
class Effects:
    """
    Visual effects — glassmorphism, shadows, vibrancy.

    Gaussian blur values in logical pixels. Shadow offsets as (x, y, blur, spread).
    """

    # -- Glassmorphism --
    glass_blur_regular: float = 20.0
    glass_blur_thick: float = 40.0
    glass_blur_thin: float = 10.0
    glass_saturation: float = 1.8        # Color saturation boost behind glass

    # -- Shadows (Apple-style layered) --
    shadow_sm: tuple = (0, 1, 3, 0)       # (x, y, blur, spread)
    shadow_sm_opacity: float = 0.08
    shadow_md: tuple = (0, 4, 12, 0)
    shadow_md_opacity: float = 0.12
    shadow_lg: tuple = (0, 8, 24, -2)
    shadow_lg_opacity: float = 0.16
    shadow_xl: tuple = (0, 16, 48, -4)
    shadow_xl_opacity: float = 0.20

    # -- Key Shadows --
    key_shadow_offset: tuple = (0, 1, 1, 0)
    key_shadow_opacity: float = 0.15
    key_pressed_shadow_offset: tuple = (0, 0, 0, 0)
    key_pressed_shadow_opacity: float = 0.0

    # -- Notification Shadow --
    notification_shadow: tuple = (0, 8, 24, -4)
    notification_shadow_opacity: float = 0.18

    # -- Vibrancy --
    vibrancy_light: float = 0.72        # Alpha for light vibrancy
    vibrancy_dark: float = 0.60
    vibrancy_ultra_thin: float = 0.4

    # -- Gradient Angles (degrees) --
    accent_gradient_angle: float = 135.0
    background_gradient_angle: float = 180.0

    # -- Haptic Feedback Intensities --
    haptic_light: float = 0.3
    haptic_medium: float = 0.6
    haptic_heavy: float = 1.0
    haptic_selection: float = 0.15       # Subtle tick for selections


# ---------------------------------------------------------------------------
# Iconography
# ---------------------------------------------------------------------------

@dataclass(frozen=True)
class Iconography:
    """
    Icon sizing and style tokens.

    Uses SF Symbols-style sizing with optical balance.
    """

    # -- Sizes --
    icon_xs: int = 12
    icon_sm: int = 16
    icon_md: int = 20
    icon_lg: int = 24
    icon_xl: int = 28
    icon_xxl: int = 32
    icon_display: int = 48

    # -- Status Bar Icons --
    statusbar_icon_size: int = 16
    statusbar_battery_width: int = 25
    statusbar_battery_height: int = 12

    # -- Notification Icons --
    notification_icon_size: int = 20
    notification_app_icon_size: int = 36

    # -- Weight (stroke width for line icons) --
    icon_weight_thin: float = 1.0
    icon_weight_regular: float = 1.5
    icon_weight_medium: float = 2.0
    icon_weight_bold: float = 2.5


# ---------------------------------------------------------------------------
# Layout Metrics
# ---------------------------------------------------------------------------

@dataclass(frozen=True)
class LayoutMetrics:
    """
    Screen layout metrics for the mobile form factor.

    All values in logical pixels (before display scale factor).
    """

    # -- Screen --
    screen_width: int = 1080
    screen_height: int = 2340
    display_scale: float = 2.0

    # -- Status Bar --
    statusbar_height: int = 54          # Slightly taller for pill-style indicators
    statusbar_notch_width: int = 162    # Dynamic Island-style width
    statusbar_notch_height: int = 37
    statusbar_notch_radius: int = 19

    # -- Keyboard --
    keyboard_height: int = 291          # Apple iOS keyboard height equivalent
    keyboard_suggestion_bar_height: int = 44  # Match tap target height
    keyboard_row_count: int = 4
    keyboard_bottom_safe_area: int = 0  # Home indicator safe area

    # -- Navigation --
    home_indicator_width: int = 134
    home_indicator_height: int = 5
    home_indicator_radius: int = 3
    home_indicator_bottom_margin: int = 8

    # -- Notification Banner --
    notification_banner_height: int = 80
    notification_banner_margin: int = 8

    # -- App Content Area --
    safe_area_top: int = 54             # = statusbar_height
    safe_area_bottom: int = 34          # Home indicator area

    # -- Chat --
    chat_input_height: int = 48
    chat_input_radius: int = 24
    chat_bubble_max_width_ratio: float = 0.78   # % of screen width
    chat_bubble_radius: int = 18
    chat_bubble_tail_radius: int = 4

    # -- App Drawer --
    app_icon_size: int = 60
    app_icon_radius: int = 14           # Apple squircle
    app_grid_columns: int = 4
    app_grid_row_height: int = 100
    app_label_margin_top: int = 6

    # -- Onboarding --
    onboarding_illustration_size: int = 200
    onboarding_page_indicator_size: int = 8
    onboarding_page_indicator_gap: int = 8
    onboarding_page_indicator_active_width: int = 24


# ---------------------------------------------------------------------------
# Assembled Theme
# ---------------------------------------------------------------------------

@dataclass
class ClaudeOSTheme:
    """Complete theme instance with all design tokens."""
    mode: ThemeMode = ThemeMode.LIGHT
    colors: ColorPalette = field(default_factory=ColorPalette)
    typography: Typography = field(default_factory=Typography)
    spacing: Spacing = field(default_factory=Spacing)
    animation: Animation = field(default_factory=Animation)
    effects: Effects = field(default_factory=Effects)
    icons: Iconography = field(default_factory=Iconography)
    layout: LayoutMetrics = field(default_factory=LayoutMetrics)

    def to_dict(self) -> dict:
        """Serialize the full theme for external renderers."""
        from dataclasses import asdict
        return {
            "mode": self.mode.name.lower(),
            "colors": asdict(self.colors),
            "typography": asdict(self.typography),
            "spacing": asdict(self.spacing),
            "animation": asdict(self.animation),
            "effects": asdict(self.effects),
            "icons": asdict(self.icons),
            "layout": asdict(self.layout),
        }


# ---------------------------------------------------------------------------
# Global Theme State
# ---------------------------------------------------------------------------

_current_theme: ClaudeOSTheme | None = None


def get_theme(mode: ThemeMode = None) -> ClaudeOSTheme:
    """Get the current theme instance, optionally for a specific mode."""
    global _current_theme

    if mode is not None:
        return _build_theme(mode)

    if _current_theme is None:
        _current_theme = _build_theme(ThemeMode.LIGHT)

    return _current_theme


def set_theme_mode(mode: ThemeMode) -> ClaudeOSTheme:
    """Switch the global theme mode. Returns the new theme."""
    global _current_theme
    _current_theme = _build_theme(mode)
    logger.info("Theme mode set to: %s", mode.name)
    return _current_theme


def _build_theme(mode: ThemeMode) -> ClaudeOSTheme:
    """Build a theme for the given mode."""
    palette_map = {
        ThemeMode.LIGHT: ColorPalette,
        ThemeMode.DARK: DarkPalette,
        ThemeMode.HIGH_CONTRAST: HighContrastPalette,
    }
    palette_cls = palette_map.get(mode, ColorPalette)

    return ClaudeOSTheme(
        mode=mode,
        colors=palette_cls(),
        typography=Typography(),
        spacing=Spacing(),
        animation=Animation(),
        effects=Effects(),
        icons=Iconography(),
        layout=LayoutMetrics(),
    )
