"""
Claude-OS App Drawer

Slides up from the bottom of the home screen. Shows a grid of
installed app icons with labels.

Layout:
    ┌──────────────────────────────┐
    │  ─── drag handle ───         │
    ├──────────────────────────────┤
    │  [Claude]  [Settings]  [Web] │
    │  [Files]   [Clock]    [Calc] │
    │  [Notes]   [Camera]   [Map]  │
    │                              │
    └──────────────────────────────┘
"""

from dataclasses import dataclass
from typing import Callable

from theme import Colors, Typography, Spacing, Radius, Color
from widget import Widget, Size, EdgeInsets, Align, Direction, Event, EventType, _fill_rect
from widgets import Container, Label, ScrollView, Spacer
from font import FontRenderer

_font = FontRenderer()


@dataclass
class AppInfo:
    """An installed application."""
    app_id: str
    name: str
    icon_char: str = ""  # Single character icon (ASCII fallback)
    icon_color: Color = None
    installed: bool = True


class AppIcon(Widget):
    """A single app icon with label."""

    ICON_SIZE = 48
    TOTAL_HEIGHT = 80

    def __init__(self, app: AppInfo, on_launch: Callable = None):
        super().__init__()
        self.app = app
        self._on_launch = on_launch
        self._on_tap = lambda: self._launch()
        self.min_width = 72
        self.min_height = self.TOTAL_HEIGHT

    def _launch(self):
        if self._on_launch:
            self._on_launch(self.app)

    def measure(self, max_w: int, max_h: int) -> Size:
        return Size(self.min_width, self.TOTAL_HEIGHT)

    def draw_content(self, buf: bytearray, buf_w: int, buf_h: int,
                     abs_x: int, abs_y: int):
        # Draw icon circle
        icon_x = abs_x + (self.width - self.ICON_SIZE) // 2
        icon_y = abs_y + 4
        icon_color = self.app.icon_color or Colors.SURFACE_BRIGHT
        _fill_rect(buf, buf_w, buf_h,
                   icon_x, icon_y, self.ICON_SIZE, self.ICON_SIZE,
                   icon_color)

        # Draw icon character centered in the circle
        if self.app.icon_char:
            rt = _font.render_text(self.app.icon_char,
                                   Typography.HEADLINE_MEDIUM,
                                   Colors.TEXT_ON_PRIMARY)
            if rt.data:
                from widget import _blit_text
                tx = icon_x + (self.ICON_SIZE - rt.width) // 2
                ty = icon_y + (self.ICON_SIZE - rt.height) // 2
                _blit_text(buf, buf_w, buf_h, tx, ty,
                           rt.data, rt.width, rt.height, rt.stride)

        # Draw label below icon
        rt = _font.render_text(self.app.name[:8],
                               Typography.LABEL_SMALL,
                               Colors.TEXT_SECONDARY)
        if rt.data:
            from widget import _blit_text
            tx = abs_x + (self.width - rt.width) // 2
            ty = icon_y + self.ICON_SIZE + 6
            _blit_text(buf, buf_w, buf_h, tx, ty,
                       rt.data, rt.width, rt.height, rt.stride)


class AppDrawer(Widget):
    """
    App drawer showing a grid of installed apps.
    """

    COLUMNS = 4
    DRAG_HANDLE_HEIGHT = 24

    def __init__(self, on_launch: Callable = None):
        super().__init__()
        self.background = Colors.SURFACE
        self.corner_radius = Radius.XL
        self._on_launch = on_launch
        self._visible = False
        self._apps: list[AppInfo] = []

        # Default apps
        self._apps = [
            AppInfo("claude-chat", "Claude", "C", Colors.PRIMARY),
            AppInfo("settings", "Settings", "S", Colors.SURFACE_BRIGHT),
            AppInfo("browser", "Browser", "B", Color(33, 150, 243)),
            AppInfo("files", "Files", "F", Color(255, 193, 7)),
            AppInfo("clock", "Clock", "T", Color(156, 39, 176)),
            AppInfo("calculator", "Calc", "#", Color(0, 150, 136)),
            AppInfo("notes", "Notes", "N", Color(255, 152, 0)),
            AppInfo("camera", "Camera", "O", Color(233, 30, 99)),
        ]

        self._build_ui()

    def _build_ui(self):
        self.clear_children()

        root = Container(direction=Direction.VERTICAL)
        root.padding = EdgeInsets(top=Spacing.XS, right=Spacing.SM,
                                   bottom=Spacing.MD, left=Spacing.SM)
        self.add_child(root)

        # Drag handle
        handle = Widget()
        handle.min_height = self.DRAG_HANDLE_HEIGHT
        handle.min_width = 40
        handle.background = Colors.BORDER
        handle.corner_radius = Radius.FULL
        root.add_child(handle)

        # Scrollable grid
        self._scroll = ScrollView()
        self._scroll.flex = 1
        root.add_child(self._scroll)

        grid = Container(direction=Direction.VERTICAL,
                         gap=Spacing.SM)
        self._scroll.add_child(grid)

        # Build rows
        for i in range(0, len(self._apps), self.COLUMNS):
            row_apps = self._apps[i:i + self.COLUMNS]
            row = Container(direction=Direction.HORIZONTAL,
                            gap=Spacing.XS, cross_align=Align.START)

            for app in row_apps:
                icon = AppIcon(app, on_launch=self._on_launch)
                row.add_child(icon)

            # Pad row if less than COLUMNS
            while len(row.children) < self.COLUMNS:
                filler = Widget()
                filler.min_width = 72
                filler.min_height = AppIcon.TOTAL_HEIGHT
                row.add_child(filler)

            grid.add_child(row)

    # --- Public API ---

    def add_app(self, app: AppInfo):
        self._apps.append(app)
        self._build_ui()
        self.mark_dirty()

    def remove_app(self, app_id: str):
        self._apps = [a for a in self._apps if a.app_id != app_id]
        self._build_ui()
        self.mark_dirty()

    def get_app(self, app_id: str) -> AppInfo | None:
        for a in self._apps:
            if a.app_id == app_id:
                return a
        return None

    @property
    def app_count(self) -> int:
        return len(self._apps)

    def show(self):
        self._visible = True
        self.visible = True
        self.mark_dirty()

    def hide(self):
        self._visible = False
        self.visible = False
        self.mark_dirty()

    @property
    def is_visible(self) -> bool:
        return self._visible
