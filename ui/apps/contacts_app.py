"""
Claude-OS Contacts & Dialer (Placeholder)

Placeholder UI for future telephony support. Shows a contact list
and a dial pad.
"""

from dataclasses import dataclass, field
from typing import Callable

from theme import Colors, Typography, Spacing, Radius, Color
from widget import Widget, Size, EdgeInsets, Align, Direction, Event, EventType
from widgets import Container, Label, ScrollView, Spacer, Divider


@dataclass
class Contact:
    """A contact entry."""
    name: str
    phone: str = ""
    email: str = ""
    avatar_char: str = ""

    def __post_init__(self):
        if not self.avatar_char and self.name:
            self.avatar_char = self.name[0].upper()


class ContactRow(Widget):
    """A single contact list row."""

    HEIGHT = 52

    def __init__(self, contact: Contact, on_tap: Callable = None):
        super().__init__()
        self.contact = contact
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

        # Avatar circle
        avatar_size = 36
        ax = abs_x + self.padding.left
        ay = abs_y + (self.HEIGHT - avatar_size) // 2
        _fill_rect(buf, buf_w, buf_h, ax, ay, avatar_size, avatar_size,
                   Colors.PRIMARY.with_alpha(60))
        rt = font.render_text(self.contact.avatar_char,
                               Typography.HEADLINE_SMALL,
                               Colors.PRIMARY)
        if rt.data:
            _blit_text(buf, buf_w, buf_h,
                       ax + (avatar_size - rt.width) // 2,
                       ay + (avatar_size - rt.height) // 2,
                       rt.data, rt.width, rt.height, rt.stride)

        # Name
        name_x = ax + avatar_size + Spacing.SM
        rt = font.render_text(self.contact.name[:20],
                               Typography.BODY_MEDIUM,
                               Colors.TEXT_PRIMARY)
        if rt.data:
            ty = abs_y + (self.HEIGHT - rt.height) // 2 - 6
            _blit_text(buf, buf_w, buf_h, name_x, ty,
                       rt.data, rt.width, rt.height, rt.stride)

        # Phone
        if self.contact.phone:
            rt = font.render_text(self.contact.phone,
                                   Typography.BODY_SMALL,
                                   Colors.TEXT_SECONDARY)
            if rt.data:
                ty = abs_y + (self.HEIGHT - rt.height) // 2 + 8
                _blit_text(buf, buf_w, buf_h, name_x, ty,
                           rt.data, rt.width, rt.height, rt.stride)


class ContactsApp(Widget):
    """
    Contacts and dialer application.
    """

    def __init__(self, on_call: Callable = None):
        super().__init__()
        self.background = Colors.BACKGROUND
        self._on_call = on_call
        self._contacts: list[Contact] = []
        self._dial_input = ""

        # Sample contacts
        self._contacts = [
            Contact("Alice", "+1 555-0101", "alice@example.com"),
            Contact("Bob", "+1 555-0102", "bob@example.com"),
            Contact("Claude", "+1 555-0103", "claude@anthropic.com"),
            Contact("Diana", "+1 555-0104"),
            Contact("Eve", "+1 555-0105"),
        ]

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
        title_bar.add_child(Label(
            "Contacts",
            style=Typography.HEADLINE_MEDIUM,
            color=Colors.TEXT_PRIMARY,
        ))
        root.add_child(title_bar)

        # Contact list
        scroll = ScrollView()
        scroll.flex = 1
        root.add_child(scroll)

        contact_list = Container(direction=Direction.VERTICAL)
        scroll.add_child(contact_list)

        for contact in sorted(self._contacts, key=lambda c: c.name):
            row = ContactRow(contact, on_tap=lambda c=contact: self._on_contact_tap(c))
            contact_list.add_child(row)
            contact_list.add_child(Divider())

        if not self._contacts:
            contact_list.add_child(Label(
                "No contacts",
                style=Typography.BODY_MEDIUM,
                color=Colors.TEXT_DISABLED,
                align=Align.CENTER,
            ))

    def _on_contact_tap(self, contact: Contact):
        if self._on_call and contact.phone:
            self._on_call(contact.phone)

    # --- Public API ---

    def add_contact(self, contact: Contact):
        self._contacts.append(contact)
        self._build_ui()
        self.mark_dirty()

    def remove_contact(self, name: str):
        self._contacts = [c for c in self._contacts if c.name != name]
        self._build_ui()
        self.mark_dirty()

    def find_contact(self, name: str) -> Contact | None:
        for c in self._contacts:
            if c.name == name:
                return c
        return None

    @property
    def contact_count(self) -> int:
        return len(self._contacts)
