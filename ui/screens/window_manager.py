"""
Claude-OS Window Manager

Ties the app lifecycle to the visual compositor. Each running app gets
a "window" — a widget subtree rendered as a compositor surface.

Responsibilities:
    - Map app_id → window (widget tree + surface)
    - Track which window is foreground (visible, receives input)
    - App switching: bring a window to foreground, suspend the old one
    - Recent apps list for the task switcher
    - Gesture routing: swipe-up → recent apps, swipe-right → back

Architecture:
    AppManager (process lifecycle)
        ↕  events
    WindowManager (visual lifecycle)
        ↕  surfaces
    Compositor (rendering)

Window states mirror app states:
    FOREGROUND — visible, receives input
    BACKGROUND — hidden, app may be running or suspended
    CLOSING    — being removed (animation, then destroy)
"""

import logging
import time
from dataclasses import dataclass, field
from enum import Enum, auto
from typing import Callable

from theme import Colors, Typography, Spacing, Radius, Color
from widget import Widget, Size, EdgeInsets, Align, Direction, Event, EventType
from widgets import Container, Label, ScrollView, Spacer

logger = logging.getLogger("window_manager")


class WindowState(Enum):
    FOREGROUND = auto()
    BACKGROUND = auto()
    CLOSING = auto()


@dataclass
class Window:
    """A managed application window."""
    app_id: str
    name: str
    state: WindowState = WindowState.BACKGROUND
    widget: Widget | None = None  # Root widget of the app's UI
    created_at: float = 0
    last_focused: float = 0
    thumbnail: bytearray | None = None  # Last-captured thumbnail
    thumb_width: int = 0
    thumb_height: int = 0

    def __post_init__(self):
        if not self.created_at:
            self.created_at = time.time()
        if not self.last_focused:
            self.last_focused = time.time()


class WindowManager:
    """
    Manages application windows and their visual state.

    Works alongside the AppManager — when an app is launched, the
    WindowManager creates a window for it. When foregrounded, its
    widget tree is rendered by the compositor.
    """

    MAX_RECENT = 10

    def __init__(self):
        self._windows: dict[str, Window] = {}
        self._foreground_id: str | None = None
        self._recent_order: list[str] = []  # Most recent first

        # Callbacks
        self._on_foreground_change: Callable | None = None
        self._on_window_created: Callable | None = None
        self._on_window_destroyed: Callable | None = None

    def set_callbacks(self, on_foreground_change=None,
                      on_window_created=None, on_window_destroyed=None):
        self._on_foreground_change = on_foreground_change
        self._on_window_created = on_window_created
        self._on_window_destroyed = on_window_destroyed

    # --- Window Lifecycle ---

    def create_window(self, app_id: str, name: str,
                      widget: Widget = None) -> Window:
        """Create a new window for an app."""
        if app_id in self._windows:
            return self._windows[app_id]

        window = Window(app_id=app_id, name=name, widget=widget)
        self._windows[app_id] = window

        if self._on_window_created:
            self._on_window_created(window)

        logger.info("Window created: %s (%s)", name, app_id)
        return window

    def destroy_window(self, app_id: str):
        """Destroy a window (app is being killed)."""
        window = self._windows.pop(app_id, None)
        if not window:
            return

        window.state = WindowState.CLOSING

        # Remove from recent
        if app_id in self._recent_order:
            self._recent_order.remove(app_id)

        # If this was foreground, switch to next
        if self._foreground_id == app_id:
            self._foreground_id = None
            if self._recent_order:
                self.focus_window(self._recent_order[0])

        if self._on_window_destroyed:
            self._on_window_destroyed(window)

        logger.info("Window destroyed: %s", app_id)

    def focus_window(self, app_id: str) -> bool:
        """Bring a window to the foreground."""
        window = self._windows.get(app_id)
        if not window:
            return False

        old_fg = self._foreground_id

        # Background the current foreground
        if old_fg and old_fg != app_id:
            old_window = self._windows.get(old_fg)
            if old_window:
                old_window.state = WindowState.BACKGROUND

        # Foreground the new window
        window.state = WindowState.FOREGROUND
        window.last_focused = time.time()
        self._foreground_id = app_id

        # Update recent order
        if app_id in self._recent_order:
            self._recent_order.remove(app_id)
        self._recent_order.insert(0, app_id)
        self._recent_order = self._recent_order[:self.MAX_RECENT]

        if self._on_foreground_change and old_fg != app_id:
            self._on_foreground_change(old_fg, app_id)

        logger.info("Focused: %s", app_id)
        return True

    def switch_to_previous(self) -> str | None:
        """Switch to the previous app (Alt-Tab behavior)."""
        if len(self._recent_order) < 2:
            return None
        prev_id = self._recent_order[1]
        self.focus_window(prev_id)
        return prev_id

    def go_home(self) -> bool:
        """Switch to the home app (Claude chat)."""
        return self.focus_window("claude-chat")

    # --- Queries ---

    @property
    def foreground_window(self) -> Window | None:
        if self._foreground_id:
            return self._windows.get(self._foreground_id)
        return None

    @property
    def foreground_id(self) -> str | None:
        return self._foreground_id

    @property
    def foreground_widget(self) -> Widget | None:
        w = self.foreground_window
        return w.widget if w else None

    def get_window(self, app_id: str) -> Window | None:
        return self._windows.get(app_id)

    def get_all_windows(self) -> list[Window]:
        return list(self._windows.values())

    def get_recent_windows(self) -> list[Window]:
        """Get windows in most-recently-focused order."""
        result = []
        for app_id in self._recent_order:
            w = self._windows.get(app_id)
            if w:
                result.append(w)
        return result

    @property
    def window_count(self) -> int:
        return len(self._windows)

    # --- Thumbnail Capture ---

    def capture_thumbnail(self, app_id: str, buf: bytearray,
                          width: int, height: int):
        """Store a thumbnail for an app (captured before backgrounding)."""
        window = self._windows.get(app_id)
        if window:
            window.thumbnail = buf
            window.thumb_width = width
            window.thumb_height = height

    def get_status(self) -> dict:
        return {
            "foreground": self._foreground_id,
            "windows": {
                app_id: {
                    "name": w.name,
                    "state": w.state.name,
                    "has_widget": w.widget is not None,
                }
                for app_id, w in self._windows.items()
            },
            "recent": self._recent_order,
        }
