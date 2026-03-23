"""
Claude-OS Settings App

System settings organized in sections:
    - WiFi: scan, connect, forget networks
    - Display: brightness, dark mode
    - Sound: volume, ringtone, notifications
    - About: device info, OS version, storage

Each section is a scrollable list of setting rows.
"""

from dataclasses import dataclass, field
from typing import Callable

from theme import Colors, Typography, Spacing, Radius, Color
from widget import Widget, Size, EdgeInsets, Align, Direction, Event, EventType
from widgets import Container, Label, ScrollView, Spacer, Divider


@dataclass
class SettingItem:
    """A single setting entry."""
    key: str
    label: str
    value: str = ""
    item_type: str = "text"  # "text", "toggle", "slider", "action"
    enabled: bool = True
    on_change: Callable = None


class SettingRow(Widget):
    """A row displaying a setting with label and value."""

    HEIGHT = 48

    def __init__(self, item: SettingItem, on_tap: Callable = None):
        super().__init__()
        self.item = item
        self.min_height = self.HEIGHT
        self._on_tap = on_tap
        self.padding = EdgeInsets.symmetric(horizontal=Spacing.LG,
                                            vertical=Spacing.SM)

    def measure(self, max_w: int, max_h: int) -> Size:
        return Size(max_w, self.HEIGHT)

    def draw_content(self, buf: bytearray, buf_w: int, buf_h: int,
                     abs_x: int, abs_y: int):
        from widget import _blit_text
        from font import FontRenderer
        font = FontRenderer()

        # Label (left)
        color = Colors.TEXT_PRIMARY if self.item.enabled else Colors.TEXT_DISABLED
        rt = font.render_text(self.item.label, Typography.BODY_MEDIUM, color)
        if rt.data:
            ty = abs_y + (self.HEIGHT - rt.height) // 2
            _blit_text(buf, buf_w, buf_h,
                       abs_x + self.padding.left, ty,
                       rt.data, rt.width, rt.height, rt.stride)

        # Value (right)
        if self.item.value:
            val_color = Colors.TEXT_SECONDARY
            if self.item.item_type == "toggle":
                val_color = Colors.PRIMARY if self.item.value == "On" else Colors.TEXT_DISABLED
            rt = font.render_text(self.item.value, Typography.BODY_MEDIUM, val_color)
            if rt.data:
                ty = abs_y + (self.HEIGHT - rt.height) // 2
                tx = abs_x + self.width - self.padding.right - rt.width
                _blit_text(buf, buf_w, buf_h, tx, ty,
                           rt.data, rt.width, rt.height, rt.stride)


class SettingsSection(Widget):
    """A group of settings under a header."""

    def __init__(self, title: str, items: list[SettingItem] = None):
        super().__init__()
        self.title = title
        self.items = items or []

    def build(self, on_item_tap: Callable = None) -> Container:
        """Build the section widget tree."""
        section = Container(direction=Direction.VERTICAL)

        # Header
        header = Label(
            self.title,
            style=Typography.LABEL_LARGE,
            color=Colors.PRIMARY,
        )
        header.padding = EdgeInsets.symmetric(horizontal=Spacing.LG,
                                               vertical=Spacing.SM)
        section.add_child(header)

        # Items
        for item in self.items:
            row = SettingRow(item, on_tap=lambda i=item: on_item_tap(i) if on_item_tap else None)
            section.add_child(row)
            section.add_child(Divider())

        return section


class SettingsApp(Widget):
    """
    Settings application.

    Displays a scrollable list of setting sections.
    """

    def __init__(self, on_setting_change: Callable = None):
        super().__init__()
        self.background = Colors.BACKGROUND
        self._on_setting_change = on_setting_change

        # Settings data
        self._sections = self._default_sections()
        self._build_ui()

    def _default_sections(self) -> list[SettingsSection]:
        return [
            SettingsSection("WiFi", [
                SettingItem("wifi_enabled", "WiFi", "On", "toggle"),
                SettingItem("wifi_network", "Network", "Claude-Net"),
                SettingItem("wifi_ip", "IP Address", "192.168.1.100"),
            ]),
            SettingsSection("Display", [
                SettingItem("brightness", "Brightness", "80%", "slider"),
                SettingItem("dark_mode", "Dark Mode", "On", "toggle"),
                SettingItem("font_size", "Font Size", "Medium"),
                SettingItem("auto_brightness", "Auto Brightness", "Off", "toggle"),
            ]),
            SettingsSection("Sound", [
                SettingItem("volume", "Volume", "70%", "slider"),
                SettingItem("notification_sound", "Notification", "Default"),
                SettingItem("vibration", "Vibration", "On", "toggle"),
            ]),
            SettingsSection("About", [
                SettingItem("device_name", "Device Name", "Claude Phone"),
                SettingItem("os_version", "OS Version", "Claude-OS 0.1.0"),
                SettingItem("kernel", "Kernel", "Linux 6.6.20"),
                SettingItem("storage_used", "Storage", "1.2 GB / 8 GB"),
                SettingItem("memory", "Memory", "512 MB"),
            ]),
        ]

    def _build_ui(self):
        self.clear_children()

        root = Container(direction=Direction.VERTICAL)
        self.add_child(root)

        # Title bar
        title_bar = Container(direction=Direction.HORIZONTAL,
                              cross_align=Align.CENTER)
        title_bar.min_height = 48
        title_bar.background = Colors.SURFACE
        title_bar.padding = EdgeInsets.symmetric(horizontal=Spacing.LG)
        title_bar.add_child(Label(
            "Settings",
            style=Typography.HEADLINE_MEDIUM,
            color=Colors.TEXT_PRIMARY,
        ))
        root.add_child(title_bar)

        # Scrollable sections
        scroll = ScrollView()
        scroll.flex = 1
        root.add_child(scroll)

        content = Container(direction=Direction.VERTICAL, gap=Spacing.MD)
        content.padding = EdgeInsets.symmetric(vertical=Spacing.SM)
        scroll.add_child(content)

        for section in self._sections:
            content.add_child(section.build(on_item_tap=self._on_item_tap))

    def _on_item_tap(self, item: SettingItem):
        """Handle tapping a setting row."""
        if item.item_type == "toggle":
            item.value = "Off" if item.value == "On" else "On"
            self._build_ui()
            self.mark_dirty()

        if self._on_setting_change:
            self._on_setting_change(item.key, item.value)

    # --- Public API ---

    def get_setting(self, key: str) -> str:
        for section in self._sections:
            for item in section.items:
                if item.key == key:
                    return item.value
        return ""

    def set_setting(self, key: str, value: str):
        for section in self._sections:
            for item in section.items:
                if item.key == key:
                    item.value = value
                    self._build_ui()
                    self.mark_dirty()
                    return

    @property
    def section_count(self) -> int:
        return len(self._sections)

    @property
    def setting_count(self) -> int:
        return sum(len(s.items) for s in self._sections)
