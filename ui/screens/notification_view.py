"""
Notification panel view — pull-down shade with quick settings.

Shows quick settings toggles, brightness slider, and notification
cards. Pulled down from the top of the screen.
"""

import time

from ui.widgets.base import Container, Size, Widget, TouchEvent, TouchAction
from ui.widgets.text import Label
from ui.widgets.buttons import Button
from ui.widgets.layout import VStack, HStack, Spacer, Padding
from ui.widgets.scrolling import ScrollView


class QuickSettingToggle(Container):
    """A single quick setting toggle (pill-shaped)."""

    def __init__(self, label: str, icon: str = "", enabled: bool = False,
                 subtitle: str = "", on_toggle=None):
        super().__init__()
        self.label_text = label
        self.icon = icon
        self.enabled = enabled
        self.subtitle = subtitle
        self._on_toggle = on_toggle
        self._build()

    def _build(self):
        theme = self.theme
        colors = theme.colors if theme else None
        spacing = theme.spacing if theme else None

        if self.enabled:
            self.background = colors.accent if colors else "#D4A574"
            fg = colors.text_on_accent if colors else "#FFFFFF"
        else:
            self.background = colors.surface_secondary if colors else "#F5EDE4"
            fg = colors.text_primary if colors else "#1A1A2E"

        self.corner_radius = spacing.radius_lg if spacing else 16

        content = VStack(spacing=2)
        content.add(Label(
            text=self.label_text,
            font_size=12.0,
            weight="bold",
            color=fg,
            align="center",
        ))
        if self.subtitle:
            content.add(Label(
                text=self.subtitle,
                font_size=10.0,
                color=fg,
                align="center",
            ))
        self.add(Padding(child=content, all=8))

    def measure(self, max_width, max_height):
        return Size(max(max_width, 80), 64)

    def handle_touch(self, event: TouchEvent) -> bool:
        if event.action == TouchAction.UP:
            self.enabled = not self.enabled
            if self._on_toggle:
                self._on_toggle(self.enabled)
            self.children.clear()
            self._build()
            return True
        return False


class BrightnessSlider(Container):
    """A simple horizontal brightness slider."""

    def __init__(self, value: int = 80, on_change=None):
        super().__init__()
        self.value = value
        self._on_change = on_change
        self._build()

    def _build(self):
        theme = self.theme
        colors = theme.colors if theme else None

        self.background = colors.surface_tertiary if colors else "#EDE3D8"
        self.corner_radius = 8

    def measure(self, max_width, max_height):
        return Size(max_width, 36)

    def render(self, ctx):
        if not self.visible:
            return

        ctx.save()
        x, y = self.bounds.x, self.bounds.y
        w, h = self.bounds.width, self.bounds.height

        # Track background
        theme = self.theme
        colors = theme.colors if theme else None
        track_color = colors.surface_tertiary if colors else "#EDE3D8"
        r, g, b, a = self._parse_color(track_color)
        self._rounded_rect(ctx, x, y, w, h, 8)
        ctx.set_source_rgba(r, g, b, a)
        ctx.fill()

        # Fill
        fill_w = int(w * self.value / 100)
        fill_color = colors.claude_terracotta if colors else "#D4A574"
        r, g, b, a = self._parse_color(fill_color)
        self._rounded_rect(ctx, x, y, fill_w, h, 8)
        ctx.set_source_rgba(r, g, b, a)
        ctx.fill()

        # Label
        label_color = colors.text_secondary if colors else "#5A5A72"
        r, g, b, a = self._parse_color(label_color)
        ctx.set_source_rgba(r, g, b, a)
        ctx.set_font_size(11.0)
        ctx.move_to(x + 8, y + h / 2 + 4)
        ctx.show_text(f"Brightness {self.value}%")

        ctx.restore()


class NotificationCard(Container):
    """A single notification card."""

    def __init__(self, app_name: str, title: str, body: str,
                 time_ago: str = "", on_dismiss=None):
        super().__init__()
        self.app_name = app_name
        self.title_text = title
        self.body_text = body
        self.time_ago = time_ago
        self._on_dismiss = on_dismiss
        self._build()

    def _build(self):
        theme = self.theme
        colors = theme.colors if theme else None
        spacing = theme.spacing if theme else None

        self.background = colors.glass_background if colors else "rgba(255,255,255,0.72)"
        self.corner_radius = spacing.notification_radius if spacing else 16

        content = VStack(spacing=4)

        # Header: app name + time
        header = HStack(spacing=0)
        header.add(Label(
            text=self.app_name,
            font_size=11.0,
            weight="bold",
            color=colors.text_tertiary if colors else "#8E8E9E",
        ))
        header.add(Spacer())
        if self.time_ago:
            header.add(Label(
                text=self.time_ago,
                font_size=11.0,
                color=colors.text_tertiary if colors else "#8E8E9E",
            ))
        content.add(header)

        # Title
        content.add(Label(
            text=self.title_text,
            font_size=15.0,
            weight="bold",
            color=colors.text_primary if colors else "#1A1A2E",
        ))

        # Body
        if self.body_text:
            content.add(Label(
                text=self.body_text[:120],
                font_size=13.0,
                color=colors.text_secondary if colors else "#5A5A72",
                max_lines=2,
            ))

        self.add(Padding(child=content, all=spacing.card_padding if spacing else 16))

    def measure(self, max_width, max_height):
        if self.children:
            size = self.children[0].measure(max_width, max_height)
            return Size(max_width, size.height)
        return Size(max_width, 80)


class NotificationView(Container):
    """
    Full notification panel shade.

    Shows quick settings toggles in a grid, a brightness slider,
    and scrollable notification cards.
    """

    def __init__(self, width: int, height: int, status_bar_h: int = 54):
        super().__init__()
        self._screen_w = width
        self._screen_h = height
        self._status_bar_h = status_bar_h
        self.pull_progress = 0.0  # 0=hidden, 1=fully shown

        # Data
        self.quick_settings: list[dict] = []
        self.notifications: list[dict] = []
        self.brightness = 80

        self._scroll = None
        self._brightness_slider = None
        self._notif_container = None

        self._setup_default_quick_settings()
        self._build()

    def _setup_default_quick_settings(self):
        self.quick_settings = [
            {"id": "wifi", "label": "WiFi", "enabled": True, "subtitle": "Home"},
            {"id": "bluetooth", "label": "Bluetooth", "enabled": False},
            {"id": "dnd", "label": "DND", "enabled": False},
            {"id": "flashlight", "label": "Torch", "enabled": False},
            {"id": "rotation", "label": "Rotate", "enabled": True},
            {"id": "dark_mode", "label": "Dark", "enabled": False},
        ]

    def _build(self):
        theme = self.theme
        colors = theme.colors if theme else None
        spacing = theme.spacing if theme else None

        root = VStack(
            spacing=spacing.md if spacing else 16,
            padding=spacing.page_margin if spacing else 16,
            background=colors.background if colors else "#FAF6F1",
        )

        # Quick settings grid (2 rows x 3 columns)
        for row_idx in range(0, len(self.quick_settings), 3):
            row = HStack(spacing=spacing.sm if spacing else 8)
            for qs in self.quick_settings[row_idx:row_idx + 3]:
                toggle = QuickSettingToggle(
                    label=qs["label"],
                    enabled=qs.get("enabled", False),
                    subtitle=qs.get("subtitle", ""),
                )
                row.add(toggle)
            root.add(row)

        # Brightness slider
        self._brightness_slider = BrightnessSlider(value=self.brightness)
        root.add(Padding(child=self._brightness_slider, top=8, bottom=8))

        # Notifications header
        header = HStack(spacing=0)
        header.add(Label(
            text="Notifications",
            font_size=15.0,
            weight="bold",
            color=colors.text_secondary if colors else "#5A5A72",
        ))
        header.add(Spacer())
        header.add(Label(
            text="Clear",
            font_size=13.0,
            color=colors.accent if colors else "#D4A574",
        ))
        root.add(header)

        # Notification cards (scrollable)
        self._scroll = ScrollView()
        self._notif_container = VStack(spacing=spacing.sm if spacing else 8)
        self._scroll.add(self._notif_container)
        root.add(self._scroll)

        self.add(root)

    def update(self):
        """Rebuild notification cards."""
        if not self._notif_container:
            return
        self._notif_container.children.clear()

        if not self.notifications:
            theme = self.theme
            colors = theme.colors if theme else None
            self._notif_container.add(Label(
                text="No notifications",
                font_size=15.0,
                color=colors.text_tertiary if colors else "#8E8E9E",
                align="center",
            ))
            return

        for notif in self.notifications:
            card = NotificationCard(
                app_name=notif.get("app_name", "App"),
                title=notif.get("title", ""),
                body=notif.get("body", ""),
                time_ago=notif.get("time_ago", ""),
            )
            self._notif_container.add(card)

        if self._brightness_slider:
            self._brightness_slider.value = self.brightness

    def add_notification(self, app_name: str, title: str, body: str,
                         time_ago: str = "now"):
        self.notifications.insert(0, {
            "app_name": app_name,
            "title": title,
            "body": body,
            "time_ago": time_ago,
        })
        self.update()

    def clear_notifications(self):
        self.notifications.clear()
        self.update()

    def measure(self, max_width, max_height):
        return Size(self._screen_w, self._screen_h - self._status_bar_h)

    def layout(self, x, y, width, height):
        super().layout(x, y, width, height)
        if self.children:
            self.children[0].layout(x, y, width, height)
