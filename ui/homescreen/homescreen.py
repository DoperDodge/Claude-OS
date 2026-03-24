"""
Claude-OS Home Screen

The main screen users see after unlocking. Features:
- App icon grid (4 columns) with Apple-style squircle icons
- Dock at the bottom with pinned apps
- Wallpaper with subtle parallax effect
- Page indicator dots for multiple pages
- Quick-access Claude AI button (floating action)

Visual Design:
    ┌──────────────────────────────────┐
    │  [Status Bar]                    │
    ├──────────────────────────────────┤
    │                                  │
    │  [Claude] [Phone] [Msgs] [Cam]  │  <- App grid (4 cols)
    │  [Music]  [Maps]  [Mail] [Web]  │     Squircle icons + labels
    │  [Files]  [Notes] [Cal]  [Set]  │
    │  [Clock]  [Calc]  [Rec]  [Pod]  │
    │                                  │
    │          o  O  o  o              │  <- Page indicators
    │                                  │
    │  ┌──────────────────────────┐    │
    │  │ [Phone][Claude][Msgs][Cam]│   │  <- Glassmorphic dock
    │  └──────────────────────────┘    │
    │        ────────────              │  <- Home indicator
    └──────────────────────────────────┘
"""

import logging
from dataclasses import dataclass, field
from enum import Enum, auto

logger = logging.getLogger("homescreen")


@dataclass
class AppIcon:
    """An app icon on the home screen."""
    app_id: str
    name: str
    icon: str = ""          # Icon path or emoji placeholder
    badge_count: int = 0
    color: str = ""         # Background color for the icon


@dataclass
class HomeScreenPage:
    """A single page of the app grid."""
    apps: list[AppIcon] = field(default_factory=list)


class HomeScreen:
    """
    Claude-OS home screen with themed app grid and dock.

    Supports multiple pages of apps with swipe navigation,
    a glassmorphic dock, and a floating Claude AI button.
    """

    def __init__(self):
        self.pages: list[HomeScreenPage] = []
        self.dock_apps: list[AppIcon] = []
        self.current_page: int = 0

        # Load theme
        try:
            from ui.theme import get_theme
            self._theme = get_theme()
        except ImportError:
            self._theme = None

        # Set up default apps
        self._setup_default_apps()

    def _setup_default_apps(self):
        """Initialize with default system apps."""
        default_apps = [
            AppIcon("com.claude.assistant", "Claude", color="#D4A574"),
            AppIcon("com.claude.phone", "Phone", color="#34C759"),
            AppIcon("com.claude.messages", "Messages", color="#5AC8FA"),
            AppIcon("com.claude.camera", "Camera", color="#5A5A72"),
            AppIcon("com.claude.music", "Music", color="#E8967D"),
            AppIcon("com.claude.maps", "Maps", color="#0F3460"),
            AppIcon("com.claude.mail", "Mail", color="#5AC8FA"),
            AppIcon("com.claude.browser", "Browser", color="#16213E"),
            AppIcon("com.claude.files", "Files", color="#D4A574"),
            AppIcon("com.claude.notes", "Notes", color="#E8D5C4"),
            AppIcon("com.claude.calendar", "Calendar", color="#FF3B30"),
            AppIcon("com.claude.settings", "Settings", color="#8E8E9E"),
            AppIcon("com.claude.clock", "Clock", color="#1A1A2E"),
            AppIcon("com.claude.calculator", "Calculator", color="#5A5A72"),
            AppIcon("com.claude.recorder", "Recorder", color="#FF9F0A"),
            AppIcon("com.claude.podcasts", "Podcasts", color="#E8967D"),
        ]

        layout = self._theme.layout if self._theme else None
        cols = layout.app_grid_columns if layout else 4
        per_page = cols * 4  # 4 rows per page

        # Distribute into pages
        for i in range(0, len(default_apps), per_page):
            page = HomeScreenPage(apps=default_apps[i:i + per_page])
            self.pages.append(page)

        # Dock apps (always visible at bottom)
        self.dock_apps = [
            AppIcon("com.claude.phone", "Phone", color="#34C759"),
            AppIcon("com.claude.assistant", "Claude", color="#D4A574"),
            AppIcon("com.claude.messages", "Messages", color="#5AC8FA"),
            AppIcon("com.claude.camera", "Camera", color="#5A5A72"),
        ]

    def set_page(self, index: int):
        """Switch to a specific page."""
        if 0 <= index < len(self.pages):
            self.current_page = index

    def next_page(self):
        """Navigate to the next page."""
        if self.current_page < len(self.pages) - 1:
            self.current_page += 1

    def prev_page(self):
        """Navigate to the previous page."""
        if self.current_page > 0:
            self.current_page -= 1

    def update_badge(self, app_id: str, count: int):
        """Update the badge count for an app."""
        for page in self.pages:
            for app in page.apps:
                if app.app_id == app_id:
                    app.badge_count = count
        for app in self.dock_apps:
            if app.app_id == app_id:
                app.badge_count = count

    def get_app_at_position(self, col: int, row: int) -> AppIcon | None:
        """Get the app at a grid position on the current page."""
        if self.current_page >= len(self.pages):
            return None
        page = self.pages[self.current_page]
        layout = self._theme.layout if self._theme else None
        cols = layout.app_grid_columns if layout else 4
        index = row * cols + col
        if 0 <= index < len(page.apps):
            return page.apps[index]
        return None

    def get_render_data(self) -> dict:
        """Return all data needed to render the home screen."""
        theme = self._theme
        colors = theme.colors if theme else None
        typo = theme.typography if theme else None
        spacing = theme.spacing if theme else None
        effects = theme.effects if theme else None
        layout = theme.layout if theme else None

        current_apps = []
        if self.current_page < len(self.pages):
            current_apps = self.pages[self.current_page].apps

        cols = layout.app_grid_columns if layout else 4
        icon_size = layout.app_icon_size if layout else 60
        icon_radius = layout.app_icon_radius if layout else 14
        row_height = layout.app_grid_row_height if layout else 100
        label_margin = layout.app_label_margin_top if layout else 6

        return {
            "background": {
                "color": colors.background if colors else "#FAF6F1",
            },
            "grid": {
                "columns": cols,
                "row_height": row_height,
                "icon_size": icon_size,
                "icon_radius": icon_radius,
                "label_margin": label_margin,
                "margin_top": (layout.safe_area_top + 20) if layout else 74,
                "margin_horizontal": spacing.page_margin if spacing else 16,
                "apps": [
                    {
                        "app_id": app.app_id,
                        "name": app.name,
                        "icon": app.icon,
                        "color": app.color,
                        "badge_count": app.badge_count,
                        "badge_color": colors.error if colors else "#FF3B30",
                        "badge_text_color": colors.text_on_accent if colors else "#FFFFFF",
                    }
                    for app in current_apps
                ],
                "label_style": {
                    "size": typo.caption_size if typo else 12.0,
                    "weight": typo.caption_weight if typo else 400,
                    "color": colors.text_primary if colors else "#1A1A2E",
                },
            },
            "page_indicator": {
                "current": self.current_page,
                "total": len(self.pages),
                "dot_size": layout.onboarding_page_indicator_size if layout else 8,
                "dot_gap": layout.onboarding_page_indicator_gap if layout else 8,
                "active_width": layout.onboarding_page_indicator_active_width if layout else 24,
                "color": colors.claude_terracotta if colors else "#D4A574",
                "inactive_color": colors.separator if colors else "#E0D6CC",
            },
            "dock": {
                "apps": [
                    {
                        "app_id": app.app_id,
                        "name": app.name,
                        "icon": app.icon,
                        "color": app.color,
                        "badge_count": app.badge_count,
                    }
                    for app in self.dock_apps
                ],
                "background": colors.glass_background if colors else "rgba(255,255,255,0.72)",
                "blur_radius": effects.glass_blur_regular if effects else 20.0,
                "border_color": colors.glass_border if colors else "rgba(255,255,255,0.3)",
                "radius": spacing.sheet_radius if spacing else 20,
                "height": 96,
                "icon_size": icon_size,
                "icon_radius": icon_radius,
                "margin_bottom": (layout.safe_area_bottom + 8) if layout else 42,
                "margin_horizontal": spacing.page_margin if spacing else 16,
                "shadow": {
                    "offset": effects.shadow_lg if effects else (0, 8, 24, -2),
                    "opacity": effects.shadow_lg_opacity if effects else 0.16,
                },
            },
            "claude_fab": {
                "size": 56,
                "color": colors.claude_terracotta if colors else "#D4A574",
                "icon_color": colors.text_on_accent if colors else "#FFFFFF",
                "shadow": {
                    "offset": effects.shadow_md if effects else (0, 4, 12, 0),
                    "opacity": effects.shadow_md_opacity if effects else 0.12,
                },
                "radius": 28,
            },
        }
