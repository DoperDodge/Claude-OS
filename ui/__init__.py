"""
Claude-OS UI Layer

The complete visual interface for Claude-OS, built on a unified design system.
All components reference theme tokens for consistent, polished rendering.

Components:
    - theme:         Design tokens (colors, typography, spacing, animation, effects)
    - compositor:    Wayland compositor with scene-graph rendering
    - statusbar:     Glassmorphic status bar with Dynamic Island
    - keyboard:      Themed on-screen keyboard with spring animations
    - lockscreen:    Lock screen with clock, notifications, swipe-to-unlock
    - homescreen:    App grid with dock and page navigation
    - notifications: Pull-down panel with quick settings and notification cards
    - appdrawer:     Full-screen alphabetical app drawer with search

Usage:
    from ui.theme import get_theme, set_theme_mode, ThemeMode
    from ui.compositor import Compositor, OutputConfig
    from ui.lockscreen import LockScreen
    from ui.homescreen import HomeScreen
    from ui.notifications import NotificationPanel
    from ui.appdrawer import AppDrawer
"""
