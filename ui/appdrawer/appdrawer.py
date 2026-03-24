"""
Claude-OS App Drawer

A frosted glass app drawer that slides up from the bottom of the screen,
displaying installed apps in a grid with a search bar at the top.

Design:
    ┌──────────────────────────────────┐
    │ ▓▓▓▓▓▓▓▓ Frosted Glass ▓▓▓▓▓▓▓ │
    │                                  │
    │  ┌─────────────────────────┐     │
    │  │ 🔍  Search apps...      │     │  ← Search bar (frosted pill)
    │  └─────────────────────────┘     │
    │                                  │
    │   ┌────┐  ┌────┐  ┌────┐  ┌────┐│
    │   │ 💬 │  │ ⚙️ │  │ 📁 │  │ 🌐 ││  ← App grid (4 columns)
    │   │Chat│  │Set.│  │File│  │Web ││
    │   └────┘  └────┘  └────┘  └────┘│
    │                                  │
    │   ┌────┐  ┌────┐  ┌────┐  ┌────┐│
    │   │ 💻 │  │ 📷 │  │ 📅 │  │ 🎵 ││
    │   │Term│  │Cam.│  │Cal.│  │Mus.││
    │   └────┘  └────┘  └────┘  └────┘│
    │                                  │
    │         ─────────                │  ← Drag handle
    └──────────────────────────────────┘

Animations:
    - Drawer slides up with spring (bouncy, stiffness 200)
    - App icons stagger-scale-in from bottom (0.02s each)
    - Search bar slides down from top
    - App launch: icon zooms to fill screen with spring
    - App long-press: icons enter jiggle mode (like iOS)
    - Dismiss: spring-animate down
"""

import logging
import time
from dataclasses import dataclass, field

logger = logging.getLogger("appdrawer")


# ---------------------------------------------------------------------------
# App Data
# ---------------------------------------------------------------------------

@dataclass
class AppInfo:
    """Information about an installed app."""
    app_id: str
    name: str
    icon: str              # Icon name or path
    category: str = ""     # "system", "utility", "social", etc.
    version: str = ""
    is_system: bool = False
    notification_badge: int = 0
    last_used: float = 0.0


# Default system apps
SYSTEM_APPS = [
    AppInfo("claude-chat", "Claude", "claude_icon", "system", is_system=True),
    AppInfo("settings", "Settings", "settings_icon", "system", is_system=True),
    AppInfo("files", "Files", "files_icon", "system", is_system=True),
    AppInfo("browser", "Browser", "browser_icon", "system", is_system=True),
    AppInfo("terminal", "Terminal", "terminal_icon", "utility", is_system=True),
    AppInfo("camera", "Camera", "camera_icon", "system", is_system=True),
    AppInfo("calendar", "Calendar", "calendar_icon", "system", is_system=True),
    AppInfo("music", "Music", "music_icon", "media", is_system=True),
    AppInfo("gallery", "Gallery", "gallery_icon", "media", is_system=True),
    AppInfo("contacts", "Contacts", "contacts_icon", "system", is_system=True),
    AppInfo("clock", "Clock", "clock_icon", "utility", is_system=True),
    AppInfo("calculator", "Calculator", "calculator_icon", "utility",
            is_system=True),
]


# ---------------------------------------------------------------------------
# App Drawer
# ---------------------------------------------------------------------------

class AppDrawer:
    """
    Claude-OS app drawer.

    Renders as a fullscreen overlay with frosted glass background.
    Grid layout with search filtering and app launch animations.

    Visual specs:
    - Background: frosted glass (20px blur, warm white tint 70%)
    - Search bar: frosted pill (999px radius), 44px height
    - App grid: 4 columns, 88px icon size, 12px gap
    - Icon: rounded square (22px radius), subtle shadow
    - Label: 12pt caption below icon
    - Badge: red circle with count, top-right of icon
    - Long press: jiggle mode with delete buttons
    """

    GRID_COLUMNS = 4
    ICON_SIZE = 64
    ICON_RADIUS = 16
    ICON_GAP = 20
    SEARCH_HEIGHT = 44
    SEARCH_RADIUS = 12

    def __init__(self):
        self.visible = False
        self.offset: float = 0.0  # 0=hidden, 1=fully open
        self.apps: list[AppInfo] = list(SYSTEM_APPS)
        self.search_query: str = ""
        self.jiggle_mode: bool = False  # iOS-style jiggle for rearranging

        # Callbacks
        self._on_app_launch = None
        self._on_app_uninstall = None

    def set_handlers(self, on_app_launch=None, on_app_uninstall=None):
        """Set event callbacks."""
        self._on_app_launch = on_app_launch
        self._on_app_uninstall = on_app_uninstall

    # --- Drawer Control ---

    def show(self):
        """Show the app drawer (animated by compositor)."""
        self.visible = True
        self.offset = 1.0
        self.search_query = ""
        self.jiggle_mode = False
        logger.info("App drawer shown")

    def hide(self):
        """Hide the app drawer."""
        self.visible = False
        self.offset = 0.0
        self.jiggle_mode = False
        logger.info("App drawer hidden")

    def set_offset(self, offset: float):
        """Set drawer offset for interactive drag (0-1)."""
        self.offset = max(0.0, min(1.0, offset))

    # --- Search ---

    def search(self, query: str):
        """Filter apps by search query."""
        self.search_query = query.strip().lower()

    def get_filtered_apps(self) -> list[AppInfo]:
        """Return apps matching the current search query."""
        if not self.search_query:
            return self.apps
        return [
            app for app in self.apps
            if self.search_query in app.name.lower()
            or self.search_query in app.category.lower()
        ]

    # --- App Management ---

    def add_app(self, app: AppInfo):
        """Register a new app."""
        # Avoid duplicates
        if any(a.app_id == app.app_id for a in self.apps):
            return
        self.apps.append(app)
        logger.info("App registered: %s (%s)", app.name, app.app_id)

    def remove_app(self, app_id: str):
        """Uninstall an app (non-system only)."""
        app = next((a for a in self.apps if a.app_id == app_id), None)
        if app and not app.is_system:
            self.apps.remove(app)
            if self._on_app_uninstall:
                self._on_app_uninstall(app_id)
            logger.info("App removed: %s", app_id)

    def launch_app(self, app_id: str):
        """Launch an app."""
        app = next((a for a in self.apps if a.app_id == app_id), None)
        if app:
            app.last_used = time.time()
            if self._on_app_launch:
                self._on_app_launch(app_id)
            logger.info("Launching app: %s", app.name)

    def set_badge(self, app_id: str, count: int):
        """Set notification badge count on an app icon."""
        for app in self.apps:
            if app.app_id == app_id:
                app.notification_badge = count
                return

    def toggle_jiggle(self):
        """Toggle jiggle mode (long-press to rearrange/delete)."""
        self.jiggle_mode = not self.jiggle_mode

    # --- Rendering ---

    def get_render_data(self) -> dict:
        """
        Return all data needed to render the app drawer.

        Includes visual specs for the Claude × Apple design.
        """
        filtered = self.get_filtered_apps()

        return {
            "visible": self.visible,
            "offset": self.offset,
            "search_query": self.search_query,
            "jiggle_mode": self.jiggle_mode,
            "apps": [
                {
                    "app_id": app.app_id,
                    "name": app.name,
                    "icon": app.icon,
                    "badge": app.notification_badge,
                    "is_system": app.is_system,
                }
                for app in filtered
            ],
            "grid": {
                "columns": self.GRID_COLUMNS,
                "icon_size": self.ICON_SIZE,
                "icon_radius": self.ICON_RADIUS,
                "icon_gap": self.ICON_GAP,
                "total_rows": (len(filtered) + self.GRID_COLUMNS - 1) // self.GRID_COLUMNS,
            },
            # Style config
            "style": {
                "background": {
                    "blur_radius": 20,
                    "saturation": 1.8,
                    "tint": "warm_white_70",
                },
                "search_bar": {
                    "height": self.SEARCH_HEIGHT,
                    "radius": self.SEARCH_RADIUS,
                    "placeholder": "Search apps...",
                    "blur_radius": 12,
                },
                "icon_shadow": {
                    "offset_y": 2,
                    "blur": 8,
                    "color": "rgba(0,0,0,0.12)",
                },
                "badge": {
                    "size": 20,
                    "color": "error",
                    "text_color": "white",
                    "font_size": 11,
                },
                "animation": {
                    "icon_stagger": 0.02,
                    "spring": {"damping": 0.7, "stiffness": 200},
                    "jiggle_rotation": 2.0,    # degrees
                    "jiggle_duration": 0.15,   # seconds per cycle
                    "launch_scale_duration": 0.4,
                },
                "handle": {
                    "width": 40,
                    "height": 5,
                    "radius": 2.5,
                    "top_margin": 8,
                },
            },
        }
