"""
Claude-OS Design System

A unified design language blending Claude's warm, intelligent aesthetic with
Apple's precision and clarity. Every pixel, color, and motion curve is
intentional — creating an OS that feels both deeply human and effortlessly
polished.

Design Principles:
    1. Warmth & Intelligence — Claude's terracotta and sand tones convey
       approachability; deep navy grounds the interface with sophistication.
    2. Clarity & Depth — Apple-inspired layered glassmorphism creates spatial
       hierarchy without clutter.
    3. Fluid Motion — Spring-based animations with Apple-caliber timing curves
       make every interaction feel alive.
    4. Accessible by Default — High contrast ratios, scalable type, and
       reduce-motion support baked into every token.
"""

from ui.theme.theme import (
    ClaudeOSTheme,
    ColorPalette,
    DarkPalette,
    LightPalette,
    HighContrastPalette,
    Typography,
    Spacing,
    Animation,
    Effects,
    Iconography,
    LayoutMetrics,
    get_theme,
    set_theme_mode,
    ThemeMode,
)

__all__ = [
    "ClaudeOSTheme",
    "ColorPalette",
    "DarkPalette",
    "LightPalette",
    "HighContrastPalette",
    "Typography",
    "Spacing",
    "Animation",
    "Effects",
    "Iconography",
    "LayoutMetrics",
    "get_theme",
    "set_theme_mode",
    "ThemeMode",
]
