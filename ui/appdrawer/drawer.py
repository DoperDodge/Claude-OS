"""
Claude-OS App Drawer

A full-screen app drawer that slides up from the home screen.
Shows all installed apps in an alphabetically sorted grid with
a search bar at the top.

Visual Design:
    ┌──────────────────────────────────────┐
    │  [Status Bar]                        │
    ├──────────────────────────────────────┤
    │                                      │
    │    ─────────────────                 │  <- Drag handle
    │                                      │
    │  ┌────────────────────────────────┐  │
    │  │  Search apps...               │  │  <- Search bar (rounded pill)
    │  └────────────────────────────────┘  │
    │                                      │
    │  A                                   │  <- Alphabetical section header
    │  [Alarm] [Assist] [Audio]            │
    │                                      │
    │  B                                   │
    │  [Browser] [Budget]                  │
    │                                      │
    │  C                                   │
    │  [Calc] [Calendar] [Camera] [Claude] │
    │                                      │
    │  ...                                 │
    └──────────────────────────────────────┘
"""

import logging
from dataclasses import dataclass, field

logger = logging.getLogger("appdrawer")


@dataclass
class DrawerApp:
    """An app entry in the app drawer."""
    app_id: str
    name: str
    icon: str = ""
    color: str = ""
    category: str = ""


class AppDrawer:
    """
    Full-screen app drawer for Claude-OS.

    Shows all installed apps in an alphabetically sorted grid.
    Supports search filtering and swipe-up/down to show/hide.
    """

    def __init__(self):
        self.visible = False
        self.apps: list[DrawerApp] = []
        self.search_query: str = ""
        self._slide_progress = 0.0  # 0=hidden, 1=fully shown

        # Load theme
        try:
            from ui.theme import get_theme
            self._theme = get_theme()
        except ImportError:
            self._theme = None

        self._setup_default_apps()

    def _setup_default_apps(self):
        """Initialize with all system apps."""
        self.apps = [
            DrawerApp("com.claude.assistant", "Claude", color="#D4A574", category="AI"),
            DrawerApp("com.claude.phone", "Phone", color="#34C759", category="Communication"),
            DrawerApp("com.claude.messages", "Messages", color="#5AC8FA", category="Communication"),
            DrawerApp("com.claude.camera", "Camera", color="#5A5A72", category="Media"),
            DrawerApp("com.claude.music", "Music", color="#E8967D", category="Media"),
            DrawerApp("com.claude.maps", "Maps", color="#0F3460", category="Navigation"),
            DrawerApp("com.claude.mail", "Mail", color="#5AC8FA", category="Communication"),
            DrawerApp("com.claude.browser", "Browser", color="#16213E", category="Productivity"),
            DrawerApp("com.claude.files", "Files", color="#D4A574", category="Productivity"),
            DrawerApp("com.claude.notes", "Notes", color="#E8D5C4", category="Productivity"),
            DrawerApp("com.claude.calendar", "Calendar", color="#FF3B30", category="Productivity"),
            DrawerApp("com.claude.settings", "Settings", color="#8E8E9E", category="System"),
            DrawerApp("com.claude.clock", "Clock", color="#1A1A2E", category="Utilities"),
            DrawerApp("com.claude.calculator", "Calculator", color="#5A5A72", category="Utilities"),
            DrawerApp("com.claude.recorder", "Recorder", color="#FF9F0A", category="Media"),
            DrawerApp("com.claude.podcasts", "Podcasts", color="#E8967D", category="Media"),
            DrawerApp("com.claude.weather", "Weather", color="#5AC8FA", category="Utilities"),
            DrawerApp("com.claude.gallery", "Gallery", color="#D4A574", category="Media"),
            DrawerApp("com.claude.terminal", "Terminal", color="#1A1A2E", category="Developer"),
            DrawerApp("com.claude.contacts", "Contacts", color="#34C759", category="Communication"),
        ]
        self.apps.sort(key=lambda a: a.name.lower())

    def show(self):
        """Show the app drawer."""
        self.visible = True
        self._slide_progress = 1.0
        self.search_query = ""
        logger.info("App drawer shown")

    def hide(self):
        """Hide the app drawer."""
        self.visible = False
        self._slide_progress = 0.0
        self.search_query = ""
        logger.info("App drawer hidden")

    def set_slide_progress(self, progress: float):
        """Set slide-up progress for gesture-driven reveal."""
        self._slide_progress = max(0.0, min(1.0, progress))
        self.visible = self._slide_progress > 0.0

    def set_search(self, query: str):
        """Update the search filter."""
        self.search_query = query

    def get_filtered_apps(self) -> list[DrawerApp]:
        """Get apps filtered by search query."""
        if not self.search_query:
            return self.apps
        q = self.search_query.lower()
        return [a for a in self.apps if q in a.name.lower()]

    def get_alphabetical_sections(self) -> dict[str, list[DrawerApp]]:
        """Group filtered apps by first letter."""
        sections: dict[str, list[DrawerApp]] = {}
        for app in self.get_filtered_apps():
            letter = app.name[0].upper()
            if letter not in sections:
                sections[letter] = []
            sections[letter].append(app)
        return dict(sorted(sections.items()))

    def install_app(self, app: DrawerApp):
        """Add a new app to the drawer."""
        self.apps.append(app)
        self.apps.sort(key=lambda a: a.name.lower())

    def uninstall_app(self, app_id: str):
        """Remove an app from the drawer."""
        self.apps = [a for a in self.apps if a.app_id != app_id]

    def get_render_data(self) -> dict:
        """Return all data needed to render the app drawer."""
        theme = self._theme
        colors = theme.colors if theme else None
        typo = theme.typography if theme else None
        spacing = theme.spacing if theme else None
        effects = theme.effects if theme else None
        anim = theme.animation if theme else None
        layout = theme.layout if theme else None

        sections = self.get_alphabetical_sections()
        icon_size = layout.app_icon_size if layout else 60
        icon_radius = layout.app_icon_radius if layout else 14
        cols = layout.app_grid_columns if layout else 4

        return {
            "visible": self.visible,
            "slide_progress": self._slide_progress,
            "background": {
                "color": colors.background if colors else "#FAF6F1",
                "opacity": 0.97,
            },
            "drag_handle": {
                "width": 40,
                "height": 4,
                "radius": 2,
                "color": colors.separator if colors else "#E0D6CC",
                "margin_top": spacing.md if spacing else 16,
            },
            "search_bar": {
                "query": self.search_query,
                "placeholder": "Search apps...",
                "background": colors.surface_secondary if colors else "#F5EDE4",
                "text_color": colors.text_primary if colors else "#1A1A2E",
                "placeholder_color": colors.text_tertiary if colors else "#8E8E9E",
                "radius": spacing.radius_pill if spacing else 999,
                "height": spacing.list_item_height if spacing else 44,
                "padding_horizontal": spacing.md if spacing else 16,
                "text_size": typo.body_medium_size if typo else 15.0,
                "margin": spacing.page_margin if spacing else 16,
            },
            "grid": {
                "columns": cols,
                "icon_size": icon_size,
                "icon_radius": icon_radius,
                "row_height": layout.app_grid_row_height if layout else 100,
                "margin_horizontal": spacing.page_margin if spacing else 16,
                "sections": {
                    letter: {
                        "header": {
                            "text": letter,
                            "color": colors.text_tertiary if colors else "#8E8E9E",
                            "size": typo.title_small_size if typo else 17.0,
                            "weight": typo.title_small_weight if typo else 600,
                        },
                        "apps": [
                            {
                                "app_id": app.app_id,
                                "name": app.name,
                                "icon": app.icon,
                                "color": app.color,
                            }
                            for app in apps
                        ],
                    }
                    for letter, apps in sections.items()
                },
                "label_style": {
                    "size": typo.caption_size if typo else 12.0,
                    "weight": typo.caption_weight if typo else 400,
                    "color": colors.text_primary if colors else "#1A1A2E",
                },
            },
            "animation": {
                "show_duration": anim.sheet_present_duration if anim else 0.5,
                "show_spring_damping": anim.sheet_present_spring_damping if anim else 0.82,
                "hide_duration": anim.sheet_dismiss_duration if anim else 0.35,
            },
        }
