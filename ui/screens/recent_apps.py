"""
Claude-OS Recent Apps View

A horizontal scrollable card carousel showing recent app thumbnails.
Swipe to browse, tap to switch, swipe up on a card to close.

Layout:
    ┌──────────────────────────────┐
    │         Recent Apps          │
    ├──────────────────────────────┤
    │  ┌──────┐  ┌──────┐  ┌────  │
    │  │ Chat │  │ Set. │  │ Br   │
    │  │      │  │      │  │      │
    │  │      │  │      │  │      │
    │  │      │  │      │  │      │
    │  └──────┘  └──────┘  └────  │
    │  Claude    Settings   Brow  │
    │                              │
    │     No more recent apps      │
    └──────────────────────────────┘
"""

from typing import Callable

from theme import Colors, Typography, Spacing, Radius, Color
from widget import (
    Widget, Size, EdgeInsets, Align, Direction, Event, EventType,
    _fill_rect,
)
from widgets import Container, Label, Spacer
from font import FontRenderer

_font = FontRenderer()


class AppCard(Widget):
    """A single recent app card with thumbnail preview."""

    CARD_WIDTH = 140
    CARD_HEIGHT = 200

    def __init__(self, app_id: str, name: str,
                 thumbnail: bytearray = None,
                 thumb_w: int = 0, thumb_h: int = 0,
                 on_select: Callable = None,
                 on_close: Callable = None):
        super().__init__()
        self.app_id = app_id
        self.name = name
        self.thumbnail = thumbnail
        self.thumb_w = thumb_w
        self.thumb_h = thumb_h
        self.background = Colors.SURFACE_CONTAINER
        self.corner_radius = Radius.LG
        self.padding = EdgeInsets.all(Spacing.XS)

        self._on_select = on_select
        self._on_close = on_close
        self._on_tap = lambda: self._select()
        self._swipe_start_y = 0
        self._swiping = False

    def _select(self):
        if self._on_select:
            self._on_select(self.app_id)

    def measure(self, max_w: int, max_h: int) -> Size:
        return Size(self.CARD_WIDTH, self.CARD_HEIGHT)

    def draw_content(self, buf: bytearray, buf_w: int, buf_h: int,
                     abs_x: int, abs_y: int):
        # Thumbnail area
        thumb_area_h = self.CARD_HEIGHT - 32
        if self.thumbnail:
            from widget import _blit_text
            _blit_text(buf, buf_w, buf_h,
                       abs_x + self.padding.left,
                       abs_y + self.padding.top,
                       self.thumbnail, self.thumb_w, self.thumb_h,
                       self.thumb_w * 4)
        else:
            # Placeholder
            _fill_rect(buf, buf_w, buf_h,
                       abs_x + self.padding.left,
                       abs_y + self.padding.top,
                       self.CARD_WIDTH - self.padding.horizontal,
                       thumb_area_h,
                       Colors.SURFACE_BRIGHT)

            # App initial
            if self.name:
                rt = _font.render_text(
                    self.name[0].upper(),
                    Typography.DISPLAY_LARGE,
                    Colors.TEXT_DISABLED,
                )
                if rt.data:
                    from widget import _blit_text
                    tx = abs_x + (self.CARD_WIDTH - rt.width) // 2
                    ty = abs_y + (thumb_area_h - rt.height) // 2
                    _blit_text(buf, buf_w, buf_h, tx, ty,
                               rt.data, rt.width, rt.height, rt.stride)

        # App name below
        rt = _font.render_text(
            self.name[:12],
            Typography.LABEL_MEDIUM,
            Colors.TEXT_PRIMARY,
        )
        if rt.data:
            from widget import _blit_text
            tx = abs_x + (self.CARD_WIDTH - rt.width) // 2
            ty = abs_y + self.CARD_HEIGHT - 24
            _blit_text(buf, buf_w, buf_h, tx, ty,
                       rt.data, rt.width, rt.height, rt.stride)

    def _handle_event(self, event_type: EventType, x: int, y: int,
                      key_code: int) -> bool:
        if event_type == EventType.TOUCH_DOWN:
            self._swiping = True
            self._swipe_start_y = y
            return True
        elif event_type == EventType.TOUCH_UP and self._swiping:
            self._swiping = False
            dy = self._swipe_start_y - y
            if dy > 80 and self._on_close:
                # Swipe up to close
                self._on_close(self.app_id)
                return True
            elif abs(dy) < 20:
                # Tap to select
                self._select()
                return True
        return False


class RecentAppsView(Widget):
    """
    Horizontally scrollable recent apps carousel.
    """

    def __init__(self, on_select: Callable = None,
                 on_close: Callable = None,
                 on_dismiss: Callable = None):
        super().__init__()
        self.background = Colors.BACKGROUND
        self._on_select = on_select
        self._on_close = on_close
        self._on_dismiss = on_dismiss  # Tap empty area to dismiss
        self._cards: list[AppCard] = []
        self._visible = False
        self._scroll_x = 0

    def set_recent_apps(self, apps: list[dict]):
        """
        Update the recent apps list.

        Args:
            apps: List of dicts with keys:
                  app_id, name, thumbnail (optional), thumb_w, thumb_h
        """
        self._cards.clear()
        self.clear_children()

        root = Container(direction=Direction.VERTICAL,
                         cross_align=Align.CENTER)
        root.padding = EdgeInsets.all(Spacing.LG)
        self.add_child(root)

        # Title
        root.add_child(Label(
            "Recent Apps",
            style=Typography.LABEL_LARGE,
            color=Colors.TEXT_SECONDARY,
            align=Align.CENTER,
        ))

        top_space = Spacer()
        top_space.flex = 1
        root.add_child(top_space)

        # Card row
        card_row = Container(direction=Direction.HORIZONTAL,
                             gap=Spacing.MD, cross_align=Align.CENTER)
        root.add_child(card_row)

        for app_data in apps:
            card = AppCard(
                app_id=app_data["app_id"],
                name=app_data["name"],
                thumbnail=app_data.get("thumbnail"),
                thumb_w=app_data.get("thumb_w", 0),
                thumb_h=app_data.get("thumb_h", 0),
                on_select=self._on_select,
                on_close=self._on_close,
            )
            card_row.add_child(card)
            self._cards.append(card)

        if not apps:
            card_row.add_child(Label(
                "No recent apps",
                style=Typography.BODY_MEDIUM,
                color=Colors.TEXT_DISABLED,
                align=Align.CENTER,
            ))

        bottom_space = Spacer()
        bottom_space.flex = 2
        root.add_child(bottom_space)

        self.mark_dirty()

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

    @property
    def card_count(self) -> int:
        return len(self._cards)
