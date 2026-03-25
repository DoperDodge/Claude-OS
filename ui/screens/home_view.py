"""
Home screen view — Claude chat interface.

The primary screen after unlocking. Shows a chat conversation
with Claude, text input bar, and quick action suggestions.
"""

import time
from dataclasses import dataclass, field

from ui.widgets.base import Container, Size, Widget, TouchEvent, TouchAction
from ui.widgets.text import Label, TextInput
from ui.widgets.buttons import Button, IconButton
from ui.widgets.layout import VStack, HStack, Spacer, Padding
from ui.widgets.scrolling import ScrollView


@dataclass
class ChatMessage:
    """A single chat message."""
    text: str
    is_user: bool
    timestamp: float = 0.0

    def __post_init__(self):
        if not self.timestamp:
            self.timestamp = time.time()


class MessageBubble(Container):
    """A single chat message bubble."""

    def __init__(self, message: ChatMessage):
        super().__init__()
        self.message = message
        self._build()

    def _build(self):
        theme = self.theme
        colors = theme.colors if theme else None
        spacing = theme.spacing if theme else None
        layout_m = theme.layout if theme else None

        is_user = self.message.is_user
        max_w_ratio = layout_m.chat_bubble_max_width_ratio if layout_m else 0.78
        radius = layout_m.chat_bubble_radius if layout_m else 18

        if is_user:
            bg = colors.accent if colors else "#D4A574"
            fg = colors.text_on_accent if colors else "#FFFFFF"
        else:
            bg = colors.surface if colors else "#FFFFFF"
            fg = colors.text_primary if colors else "#1A1A2E"

        self.background = bg
        self.corner_radius = radius

        label = Label(
            text=self.message.text,
            font_size=16.0,
            color=fg,
        )
        self.add(Padding(child=label, all=12))

    def measure(self, max_width, max_height):
        theme = self.theme
        layout_m = theme.layout if theme else None
        ratio = layout_m.chat_bubble_max_width_ratio if layout_m else 0.78
        bubble_max = int(max_width * ratio)
        if self.children:
            size = self.children[0].measure(bubble_max, max_height)
            return Size(min(size.width, bubble_max), size.height)
        return Size(100, 40)


class HomeView(Container):
    """
    Full-screen Claude chat home screen.

    Shows message history in a scroll view, with a text input
    bar pinned to the bottom. Typing indicator shows when
    Claude is responding.
    """

    def __init__(self, width: int, height: int, status_bar_h: int = 54):
        super().__init__()
        self._screen_w = width
        self._screen_h = height
        self._status_bar_h = status_bar_h
        self.messages: list[ChatMessage] = []
        self.typing_indicator = False
        self.input_text = ""

        self._scroll = None
        self._input_field = None
        self._typing_label = None
        self._msg_container = None

        self._build()
        self._add_welcome_messages()

    def _add_welcome_messages(self):
        """Add initial Claude greeting."""
        self.messages.append(ChatMessage(
            text="Hello! I'm Claude, your AI assistant. How can I help you today?",
            is_user=False,
        ))

    def _build(self):
        theme = self.theme
        colors = theme.colors if theme else None
        spacing = theme.spacing if theme else None

        root = VStack(
            background=colors.background if colors else "#FAF6F1",
        )

        # Chat messages area (scrollable)
        self._scroll = ScrollView()
        self._msg_container = VStack(
            spacing=spacing.sm if spacing else 8,
            padding=spacing.page_margin if spacing else 16,
        )
        self._scroll.add(self._msg_container)
        root.add(self._scroll)

        # Typing indicator
        self._typing_label = Label(
            text="Claude is typing...",
            font_size=13.0,
            color=colors.text_tertiary if colors else "#8E8E9E",
        )
        self._typing_label.visible = False
        root.add(Padding(child=self._typing_label, left=16, bottom=4))

        # Input bar
        input_bar = HStack(
            spacing=spacing.sm if spacing else 8,
            padding=spacing.sm if spacing else 8,
            background=colors.surface if colors else "#FFFFFF",
        )

        self._input_field = TextInput(
            placeholder="Message Claude...",
            font_size=17.0,
            height=44,
            corner_radius=22,
        )
        input_bar.add(self._input_field)

        send_btn = IconButton(
            icon=">",
            size=44,
            bg_color=colors.accent if colors else "#D4A574",
            icon_color="#FFFFFF",
            icon_size=20.0,
        )
        input_bar.add(send_btn)

        root.add(input_bar)

        self.add(root)

    def update(self):
        """Rebuild message list from current messages."""
        if not self._msg_container:
            return

        self._msg_container.children.clear()

        for msg in self.messages:
            bubble = MessageBubble(msg)
            if msg.is_user:
                # Right-align user messages
                row = HStack()
                row.add(Spacer())
                row.add(bubble)
                self._msg_container.add(row)
            else:
                # Left-align Claude messages
                row = HStack()
                row.add(bubble)
                row.add(Spacer())
                self._msg_container.add(row)

        # Typing indicator
        if self._typing_label:
            self._typing_label.visible = self.typing_indicator

    def add_message(self, text: str, is_user: bool):
        """Add a message and refresh the view."""
        self.messages.append(ChatMessage(text=text, is_user=is_user))
        self.update()

    def measure(self, max_width, max_height):
        return Size(self._screen_w, max_height)

    def layout(self, x, y, width, height):
        super().layout(x, y, width, height)
        if self.children:
            self.children[0].layout(x, y, width, height)
