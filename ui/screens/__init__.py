"""
Claude-OS Screen Views

Widget-based views for each phone UI screen. Each view consumes
the state from its corresponding component module and builds
a widget tree for rendering.

Screens:
    - LockScreenView: Clock, date, notifications, swipe-to-unlock
    - HomeView: Claude chat interface with message bubbles
    - StatusBarView: Time, battery, WiFi, Dynamic Island
    - KeyboardView: QWERTY keyboard with layer switching
    - NotificationView: Pull-down shade with quick settings
    - AppDrawerView: Full-screen app grid with search
"""

from ui.screens.lock_screen_view import LockScreenView
from ui.screens.home_view import HomeView
from ui.screens.status_bar_view import StatusBarView
from ui.screens.keyboard_view import KeyboardView
from ui.screens.notification_view import NotificationView
from ui.screens.app_drawer_view import AppDrawerView

__all__ = [
    "LockScreenView",
    "HomeView",
    "StatusBarView",
    "KeyboardView",
    "NotificationView",
    "AppDrawerView",
]
