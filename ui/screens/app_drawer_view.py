"""
App drawer view — full-screen app grid with search.

Slides up from the home screen. Shows all installed apps
sorted alphabetically with section headers.
"""

from ui.widgets.base import Container, Size, Widget
from ui.widgets.text import Label, TextInput
from ui.widgets.layout import VStack, HStack, Spacer, Padding
from ui.widgets.scrolling import ScrollView


class AppIconWidget(Container):
    """An app icon with label — colored rounded square + name."""

    def __init__(self, name: str, color: str = "#D4A574",
                 icon_size: int = 60, icon_radius: int = 14):
        super().__init__()
        self.app_name = name
        self.app_color = color
        self._icon_size = icon_size
        self._icon_radius = icon_radius
        self._build()

    def _build(self):
        theme = self.theme
        colors = theme.colors if theme else None

        content = VStack(spacing=6)

        # Icon square
        icon_box = Container(
            background=self.app_color,
            corner_radius=self._icon_radius,
        )
        # Add first letter as icon placeholder
        icon_label = Label(
            text=self.app_name[0].upper() if self.app_name else "?",
            font_size=24.0,
            weight="bold",
            color="#FFFFFF",
            align="center",
        )
        icon_box.add(Padding(child=icon_label, all=10))
        content.add(icon_box)

        # App name
        content.add(Label(
            text=self.app_name,
            font_size=12.0,
            color=colors.text_primary if colors else "#1A1A2E",
            align="center",
            max_lines=1,
        ))

        self.add(content)

    def measure(self, max_width, max_height):
        label_h = 16  # approximate label height
        return Size(self._icon_size + 8, self._icon_size + 6 + label_h + 8)


class AppDrawerView(Container):
    """
    Full-screen app drawer with search and alphabetical grid.

    Shows a drag handle, search bar, and scrollable grid of
    app icons grouped by first letter.
    """

    def __init__(self, width: int, height: int, status_bar_h: int = 54):
        super().__init__()
        self._screen_w = width
        self._screen_h = height
        self._status_bar_h = status_bar_h
        self.slide_progress = 0.0  # 0=hidden, 1=fully shown

        # Data
        self.apps: list[dict] = []
        self.search_query = ""

        self._search_input = None
        self._scroll = None
        self._grid_container = None

        self._setup_default_apps()
        self._build()

    def _setup_default_apps(self):
        """Initialize with system apps."""
        self.apps = [
            {"name": "Claude", "color": "#D4A574"},
            {"name": "Phone", "color": "#34C759"},
            {"name": "Messages", "color": "#5AC8FA"},
            {"name": "Camera", "color": "#5A5A72"},
            {"name": "Music", "color": "#E8967D"},
            {"name": "Maps", "color": "#0F3460"},
            {"name": "Mail", "color": "#5AC8FA"},
            {"name": "Browser", "color": "#16213E"},
            {"name": "Files", "color": "#D4A574"},
            {"name": "Notes", "color": "#E8D5C4"},
            {"name": "Calendar", "color": "#FF3B30"},
            {"name": "Settings", "color": "#8E8E9E"},
            {"name": "Clock", "color": "#1A1A2E"},
            {"name": "Calculator", "color": "#5A5A72"},
            {"name": "Recorder", "color": "#FF9F0A"},
            {"name": "Podcasts", "color": "#E8967D"},
            {"name": "Weather", "color": "#5AC8FA"},
            {"name": "Gallery", "color": "#D4A574"},
            {"name": "Terminal", "color": "#1A1A2E"},
            {"name": "Contacts", "color": "#34C759"},
        ]
        self.apps.sort(key=lambda a: a["name"].lower())

    def _build(self):
        theme = self.theme
        colors = theme.colors if theme else None
        spacing = theme.spacing if theme else None
        layout_m = theme.layout if theme else None

        root = VStack(
            spacing=spacing.md if spacing else 16,
            padding=spacing.page_margin if spacing else 16,
            background=colors.background if colors else "#FAF6F1",
        )

        # Drag handle
        handle_container = HStack()
        handle_container.add(Spacer())
        handle = Container(
            background=colors.separator if colors else "#E0D6CC",
            corner_radius=2,
        )
        root.add(Padding(child=handle_container, top=12, bottom=4))

        # Search bar
        self._search_input = TextInput(
            placeholder="Search apps...",
            font_size=15.0,
            height=44,
            corner_radius=spacing.radius_pill if spacing else 999,
        )
        root.add(self._search_input)

        # Scrollable app grid
        self._scroll = ScrollView()
        self._grid_container = VStack(
            spacing=spacing.sm if spacing else 8,
        )
        self._scroll.add(self._grid_container)
        root.add(self._scroll)

        self.add(root)

        # Build initial grid
        self._rebuild_grid()

    def _get_filtered_apps(self) -> list[dict]:
        if not self.search_query:
            return self.apps
        q = self.search_query.lower()
        return [a for a in self.apps if q in a["name"].lower()]

    def _get_sections(self) -> dict:
        """Group apps by first letter."""
        sections = {}
        for app in self._get_filtered_apps():
            letter = app["name"][0].upper()
            if letter not in sections:
                sections[letter] = []
            sections[letter].append(app)
        return dict(sorted(sections.items()))

    def _rebuild_grid(self):
        """Rebuild the app grid from current data."""
        if not self._grid_container:
            return
        self._grid_container.children.clear()

        theme = self.theme
        colors = theme.colors if theme else None
        layout_m = theme.layout if theme else None
        cols = layout_m.app_grid_columns if layout_m else 4
        icon_size = layout_m.app_icon_size if layout_m else 60
        icon_radius = layout_m.app_icon_radius if layout_m else 14

        sections = self._get_sections()

        for letter, apps in sections.items():
            # Section header
            self._grid_container.add(Label(
                text=letter,
                font_size=17.0,
                weight="bold",
                color=colors.text_tertiary if colors else "#8E8E9E",
            ))

            # App rows
            for i in range(0, len(apps), cols):
                row = HStack(spacing=8)
                for app in apps[i:i + cols]:
                    icon = AppIconWidget(
                        name=app["name"],
                        color=app.get("color", "#D4A574"),
                        icon_size=icon_size,
                        icon_radius=icon_radius,
                    )
                    row.add(icon)
                # Fill remaining columns with spacers
                remaining = cols - len(apps[i:i + cols])
                for _ in range(remaining):
                    row.add(Spacer())
                self._grid_container.add(row)

    def update(self):
        """Refresh the grid after search or app changes."""
        self._rebuild_grid()

    def set_search(self, query: str):
        """Update search and rebuild grid."""
        self.search_query = query
        self._rebuild_grid()

    def measure(self, max_width, max_height):
        return Size(self._screen_w, self._screen_h - self._status_bar_h)

    def layout(self, x, y, width, height):
        super().layout(x, y, width, height)
        if self.children:
            self.children[0].layout(x, y, width, height)
