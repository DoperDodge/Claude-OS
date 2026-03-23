"""
Claude-OS File Manager

Browse files and directories. Shows:
    - Directory listing with icons and file sizes
    - Navigation (back, up, home)
    - File type icons (folder, text, image, etc.)
    - Storage usage

Layout:
    ┌──────────────────────────────┐
    │  <- Files   /home/user       │
    ├──────────────────────────────┤
    │  [D] Documents          ->   │
    │  [D] Downloads          ->   │
    │  [F] notes.txt      1.2 KB  │
    │  [F] photo.jpg      3.4 MB  │
    │                              │
    └──────────────────────────────┘
"""

import os
from dataclasses import dataclass
from typing import Callable

from theme import Colors, Typography, Spacing, Radius, Color
from widget import Widget, Size, EdgeInsets, Align, Direction, Event, EventType
from widgets import Container, Label, ScrollView, Spacer, Divider


@dataclass
class FileEntry:
    """A file or directory entry."""
    name: str
    path: str
    is_dir: bool
    size: int = 0
    icon: str = ""

    @property
    def size_str(self) -> str:
        if self.is_dir:
            return ""
        if self.size < 1024:
            return f"{self.size} B"
        elif self.size < 1024 * 1024:
            return f"{self.size / 1024:.1f} KB"
        elif self.size < 1024 * 1024 * 1024:
            return f"{self.size / (1024 * 1024):.1f} MB"
        return f"{self.size / (1024 * 1024 * 1024):.1f} GB"

    @property
    def type_icon(self) -> str:
        if self.is_dir:
            return "D"
        ext = os.path.splitext(self.name)[1].lower()
        icons = {
            ".txt": "T", ".md": "T", ".log": "T",
            ".py": "#", ".js": "#", ".c": "#", ".h": "#",
            ".jpg": "I", ".png": "I", ".gif": "I",
            ".mp3": "M", ".wav": "M", ".ogg": "M",
            ".mp4": "V", ".mkv": "V",
            ".zip": "Z", ".tar": "Z", ".gz": "Z",
            ".json": "J", ".xml": "J",
        }
        return icons.get(ext, "F")


class FileRow(Widget):
    """A single file/directory row."""

    HEIGHT = 44

    def __init__(self, entry: FileEntry, on_tap: Callable = None):
        super().__init__()
        self.entry = entry
        self._on_tap = on_tap
        self.min_height = self.HEIGHT
        self.padding = EdgeInsets.symmetric(horizontal=Spacing.LG,
                                            vertical=Spacing.XS)

    def measure(self, max_w: int, max_h: int) -> Size:
        return Size(max_w, self.HEIGHT)

    def draw_content(self, buf: bytearray, buf_w: int, buf_h: int,
                     abs_x: int, abs_y: int):
        from font import FontRenderer
        from widget import _blit_text, _fill_rect
        font = FontRenderer()

        # Type icon
        icon_color = Colors.PRIMARY if self.entry.is_dir else Colors.TEXT_SECONDARY
        rt = font.render_text(
            f"[{self.entry.type_icon}]",
            Typography.LABEL_MEDIUM, icon_color,
        )
        if rt.data:
            ty = abs_y + (self.HEIGHT - rt.height) // 2
            _blit_text(buf, buf_w, buf_h,
                       abs_x + self.padding.left, ty,
                       rt.data, rt.width, rt.height, rt.stride)

        # File name
        name_x = abs_x + self.padding.left + 40
        rt = font.render_text(
            self.entry.name[:24],
            Typography.BODY_MEDIUM, Colors.TEXT_PRIMARY,
        )
        if rt.data:
            ty = abs_y + (self.HEIGHT - rt.height) // 2
            _blit_text(buf, buf_w, buf_h, name_x, ty,
                       rt.data, rt.width, rt.height, rt.stride)

        # Size or arrow
        right_text = "->" if self.entry.is_dir else self.entry.size_str
        rt = font.render_text(
            right_text,
            Typography.LABEL_SMALL, Colors.TEXT_DISABLED,
        )
        if rt.data:
            ty = abs_y + (self.HEIGHT - rt.height) // 2
            tx = abs_x + self.width - self.padding.right - rt.width
            _blit_text(buf, buf_w, buf_h, tx, ty,
                       rt.data, rt.width, rt.height, rt.stride)


class FileManagerApp(Widget):
    """
    File manager application.
    """

    def __init__(self, root_path: str = "/home",
                 on_file_open: Callable = None):
        super().__init__()
        self.background = Colors.BACKGROUND
        self._root_path = root_path
        self._current_path = root_path
        self._entries: list[FileEntry] = []
        self._on_file_open = on_file_open
        self._history: list[str] = []

        self._build_ui()

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

        back_btn = Label("<-", style=Typography.HEADLINE_SMALL,
                         color=Colors.PRIMARY)
        back_btn.on_tap(lambda: self.go_back())
        back_btn.padding = EdgeInsets.symmetric(horizontal=Spacing.SM)
        title_bar.add_child(back_btn)

        title_bar.add_child(Label(
            "Files",
            style=Typography.HEADLINE_MEDIUM,
            color=Colors.TEXT_PRIMARY,
        ))
        title_bar.add_child(Spacer())

        # Current path
        path_display = self._current_path
        if len(path_display) > 20:
            path_display = "..." + path_display[-17:]
        title_bar.add_child(Label(
            path_display,
            style=Typography.LABEL_SMALL,
            color=Colors.TEXT_SECONDARY,
        ))
        root.add_child(title_bar)

        # File list
        scroll = ScrollView()
        scroll.flex = 1
        root.add_child(scroll)

        file_list = Container(direction=Direction.VERTICAL)
        scroll.add_child(file_list)

        if not self._entries:
            file_list.add_child(Label(
                "Empty directory",
                style=Typography.BODY_MEDIUM,
                color=Colors.TEXT_DISABLED,
                align=Align.CENTER,
            ))
        else:
            for entry in self._entries:
                row = FileRow(entry, on_tap=lambda e=entry: self._on_entry_tap(e))
                file_list.add_child(row)
                file_list.add_child(Divider())

    def _on_entry_tap(self, entry: FileEntry):
        if entry.is_dir:
            self.navigate(entry.path)
        elif self._on_file_open:
            self._on_file_open(entry.path)

    # --- Public API ---

    def navigate(self, path: str):
        """Navigate to a directory."""
        self._history.append(self._current_path)
        self._current_path = path
        self._load_entries()
        self._build_ui()
        self.mark_dirty()

    def go_back(self):
        """Go to the previous directory."""
        if self._history:
            self._current_path = self._history.pop()
            self._load_entries()
            self._build_ui()
            self.mark_dirty()

    def go_home(self):
        """Navigate to root path."""
        self._history.append(self._current_path)
        self._current_path = self._root_path
        self._load_entries()
        self._build_ui()
        self.mark_dirty()

    def _load_entries(self):
        """Load directory entries from the filesystem."""
        self._entries.clear()
        try:
            for name in sorted(os.listdir(self._current_path)):
                full = os.path.join(self._current_path, name)
                is_dir = os.path.isdir(full)
                size = 0 if is_dir else os.path.getsize(full)
                self._entries.append(FileEntry(
                    name=name, path=full, is_dir=is_dir, size=size,
                ))
        except PermissionError:
            pass
        except FileNotFoundError:
            pass

    def set_entries(self, entries: list[FileEntry]):
        """Set entries directly (for testing without filesystem)."""
        self._entries = entries
        self._build_ui()
        self.mark_dirty()

    @property
    def current_path(self) -> str:
        return self._current_path

    @property
    def entry_count(self) -> int:
        return len(self._entries)
