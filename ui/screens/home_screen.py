"""
Claude-OS Home Screen — Claude Chat Interface

The primary screen: a full-screen chat interface with Claude.

Layout:
    ┌──────────────────────────────┐
    │         Status Bar           │
    ├──────────────────────────────┤
    │  ┌────────────────────┐      │
    │  │ Claude              │      │  ← Claude message (left)
    │  │ Hello! How can I   │      │
    │  │ help you today?    │      │
    │  └────────────────────┘      │
    │      ┌────────────────────┐  │
    │      │ Tell me about     │  │  ← User message (right)
    │      │ the weather       │  │
    │      └────────────────────┘  │
    │  ┌────────────────────┐      │
    │  │ ···                 │      │  ← Typing indicator
    │  └────────────────────┘      │
    ├──────────────────────────────┤
    │ [Message Claude...]   🎤 ⏎  │  ← Input bar
    └──────────────────────────────┘
"""

import time
from dataclasses import dataclass, field
from enum import Enum, auto
from typing import Callable

from theme import Colors, Typography, Spacing, Radius, Color
from widget import (
    Widget, Size, EdgeInsets, Align, Direction, Event, EventType,
    _fill_rect, _blit_text,
)
from widgets import Container, Label, ScrollView, Spacer
from font import FontRenderer

_font = FontRenderer()


class MessageRole(Enum):
    USER = auto()
    CLAUDE = auto()
    SYSTEM = auto()


@dataclass
class ChatMessage:
    """A single message in the conversation."""
    role: MessageRole
    text: str
    timestamp: float = 0
    id: int = 0

    def __post_init__(self):
        if not self.timestamp:
            self.timestamp = time.time()


class MessageBubble(Widget):
    """
    A chat message bubble with word-wrapped text.

    User messages: right-aligned, primary color background
    Claude messages: left-aligned, surface color background
    """

    MAX_WIDTH_RATIO = 0.78  # Max bubble width as fraction of screen

    def __init__(self, message: ChatMessage, screen_width: int = 320):
        super().__init__()
        self.message = message
        self._screen_width = screen_width
        self._max_bubble_w = int(screen_width * self.MAX_WIDTH_RATIO)

        if message.role == MessageRole.USER:
            self.background = Colors.PRIMARY
            self._text_color = Colors.TEXT_ON_PRIMARY
            self._align = Align.END
        elif message.role == MessageRole.CLAUDE:
            self.background = Colors.SURFACE_CONTAINER
            self._text_color = Colors.TEXT_PRIMARY
            self._align = Align.START
        else:
            self.background = None
            self._text_color = Colors.TEXT_DISABLED
            self._align = Align.CENTER

        self.corner_radius = Radius.LG
        self.padding = EdgeInsets.all(Spacing.SM)

        self._rendered = None

    def measure(self, max_w: int, max_h: int) -> Size:
        bubble_max = min(self._max_bubble_w, max_w - Spacing.LG * 2)
        content_max = bubble_max - self.padding.horizontal

        # Measure wrapped text
        self._rendered = _font.render_wrapped(
            self.message.text,
            Typography.BODY_MEDIUM,
            self._text_color,
            content_max,
        )

        w = min(self._rendered.width + self.padding.horizontal, bubble_max)
        h = self._rendered.height + self.padding.vertical

        # Add role label height for Claude messages
        if self.message.role == MessageRole.CLAUDE:
            h += Typography.LABEL_SMALL.line_height + 2

        return Size(w, h + Spacing.XS)  # +XS for inter-bubble spacing

    def draw_content(self, buf: bytearray, buf_w: int, buf_h: int,
                     abs_x: int, abs_y: int):
        if not self._rendered or not self._rendered.data:
            return

        ty = abs_y + self.padding.top

        # Draw role label for Claude
        if self.message.role == MessageRole.CLAUDE:
            role_rt = _font.render_text("Claude", Typography.LABEL_SMALL,
                                        Colors.PRIMARY_LIGHT)
            if role_rt.data:
                _blit_text(buf, buf_w, buf_h,
                           abs_x + self.padding.left, ty,
                           role_rt.data, role_rt.width, role_rt.height,
                           role_rt.stride)
            ty += Typography.LABEL_SMALL.line_height + 2

        # Draw message text
        _blit_text(buf, buf_w, buf_h,
                   abs_x + self.padding.left, ty,
                   self._rendered.data, self._rendered.width,
                   self._rendered.height, self._rendered.stride)

    def layout(self, x: int, y: int, width: int, height: int):
        """Override layout to handle alignment."""
        if self._align == Align.END:
            # Right-align user messages
            parent_w = self._screen_width
            desired = self.measure(parent_w, 0x7FFFFFFF)
            x = parent_w - desired.width - Spacing.SM
            width = desired.width
        elif self._align == Align.START:
            x = Spacing.SM
            desired = self.measure(self._screen_width, 0x7FFFFFFF)
            width = desired.width

        super().layout(x, y, width, height)


class TypingIndicator(Widget):
    """Animated "..." typing indicator shown while Claude is responding."""

    def __init__(self):
        super().__init__()
        self.background = Colors.SURFACE_CONTAINER
        self.corner_radius = Radius.LG
        self.padding = EdgeInsets.all(Spacing.SM)
        self._frame = 0

    def measure(self, max_w: int, max_h: int) -> Size:
        return Size(80, Typography.BODY_MEDIUM.line_height + self.padding.vertical)

    def draw_content(self, buf: bytearray, buf_w: int, buf_h: int,
                     abs_x: int, abs_y: int):
        # Draw animated dots
        dots = "." * ((self._frame % 3) + 1)
        self._frame += 1
        rt = _font.render_text(dots, Typography.BODY_MEDIUM, Colors.TEXT_SECONDARY)
        if rt.data:
            _blit_text(buf, buf_w, buf_h,
                       abs_x + self.padding.left,
                       abs_y + self.padding.top,
                       rt.data, rt.width, rt.height, rt.stride)


class InputBar(Widget):
    """
    Text input bar at the bottom of the chat screen.

    Contains: text field, mic button, send button.
    """

    HEIGHT = 52

    def __init__(self, on_send: Callable = None,
                 on_mic: Callable = None,
                 on_focus: Callable = None):
        super().__init__()
        self.background = Colors.SURFACE
        self.min_height = self.HEIGHT
        self.padding = EdgeInsets.symmetric(horizontal=Spacing.SM,
                                            vertical=Spacing.XS)

        self._text = ""
        self._placeholder = "Message Claude..."
        self._on_send = on_send
        self._on_mic = on_mic
        self._on_focus = on_focus
        self._focused = False

    @property
    def text(self) -> str:
        return self._text

    @text.setter
    def text(self, value: str):
        self._text = value
        self.mark_dirty()

    def append_char(self, ch: str):
        """Append a character (from keyboard widget)."""
        if ch == "BACKSPACE":
            self._text = self._text[:-1]
        else:
            self._text += ch
        self.mark_dirty()

    def clear(self) -> str:
        """Clear input and return the text."""
        text = self._text
        self._text = ""
        self.mark_dirty()
        return text

    def send(self):
        """Send the current message."""
        text = self._text.strip()
        if text and self._on_send:
            self._on_send(text)
            self._text = ""
            self.mark_dirty()

    def measure(self, max_w: int, max_h: int) -> Size:
        return Size(max_w, self.HEIGHT)

    def draw_content(self, buf: bytearray, buf_w: int, buf_h: int,
                     abs_x: int, abs_y: int):
        # Draw text field background
        field_x = abs_x + self.padding.left
        field_y = abs_y + self.padding.top
        field_w = self.content_width - 80  # Leave room for buttons
        field_h = self.content_height
        _fill_rect(buf, buf_w, buf_h,
                   field_x, field_y, field_w, field_h,
                   Colors.SURFACE_CONTAINER)

        # Draw text or placeholder
        display = self._text or self._placeholder
        color = Colors.TEXT_PRIMARY if self._text else Colors.TEXT_DISABLED
        rt = _font.render_text(display[:40], Typography.BODY_MEDIUM, color)
        if rt.data:
            tx = field_x + Spacing.SM
            ty = field_y + (field_h - rt.height) // 2
            _blit_text(buf, buf_w, buf_h, tx, ty,
                       rt.data, rt.width, rt.height, rt.stride)

        # Mic button area
        mic_x = field_x + field_w + Spacing.SM
        mic_rt = _font.render_text("MIC", Typography.LABEL_SMALL, Colors.TEXT_SECONDARY)
        if mic_rt.data:
            _blit_text(buf, buf_w, buf_h,
                       mic_x, field_y + (field_h - mic_rt.height) // 2,
                       mic_rt.data, mic_rt.width, mic_rt.height, mic_rt.stride)

        # Send button
        send_x = mic_x + 40
        send_color = Colors.PRIMARY if self._text else Colors.TEXT_DISABLED
        send_rt = _font.render_text("->", Typography.LABEL_LARGE, send_color)
        if send_rt.data:
            _blit_text(buf, buf_w, buf_h,
                       send_x, field_y + (field_h - send_rt.height) // 2,
                       send_rt.data, send_rt.width, send_rt.height,
                       send_rt.stride)

    def _handle_event(self, event_type: EventType, x: int, y: int,
                      key_code: int) -> bool:
        if event_type == EventType.TOUCH_DOWN:
            # Check if tap is on send button area
            send_area_x = self.width - 50
            if x >= send_area_x and self._text.strip():
                self.send()
                return True
            # Check mic button
            mic_area_x = self.width - 90
            if x >= mic_area_x and x < send_area_x:
                if self._on_mic:
                    self._on_mic()
                return True
            # Tap on text field — focus
            self._focused = True
            if self._on_focus:
                self._on_focus()
            return True
        return False


class HomeScreen(Widget):
    """
    Claude chat home screen.

    Manages the conversation, message display, and input.
    """

    def __init__(self, on_send_message: Callable = None):
        super().__init__()
        self.background = Colors.BACKGROUND

        self._messages: list[ChatMessage] = []
        self._next_msg_id = 1
        self._typing = False
        self._on_send_message = on_send_message

        # Build UI
        self._build_ui()

    def _build_ui(self):
        self.clear_children()

        root = Container(direction=Direction.VERTICAL)
        self.add_child(root)

        # Chat scroll area
        self._scroll = ScrollView()
        self._scroll.flex = 1
        self._scroll.background = Colors.BACKGROUND
        root.add_child(self._scroll)

        # Message container inside scroll
        self._msg_container = Container(
            direction=Direction.VERTICAL,
            gap=Spacing.XS,
        )
        self._msg_container.padding = EdgeInsets.symmetric(
            vertical=Spacing.SM,
        )
        self._scroll.add_child(self._msg_container)

        # Input bar
        self._input_bar = InputBar(on_send=self._on_send)
        root.add_child(self._input_bar)

    def _on_send(self, text: str):
        """Handle sending a user message."""
        self.add_message(MessageRole.USER, text)
        if self._on_send_message:
            self._on_send_message(text)

    # --- Public API ---

    def add_message(self, role: MessageRole, text: str) -> ChatMessage:
        """Add a message to the conversation."""
        msg = ChatMessage(role=role, text=text, id=self._next_msg_id)
        self._next_msg_id += 1
        self._messages.append(msg)

        # Create bubble widget
        bubble = MessageBubble(msg, screen_width=self.width or 320)
        self._msg_container.add_child(bubble)

        # Auto-scroll to bottom
        self._auto_scroll()
        self.mark_dirty()
        return msg

    def set_typing(self, typing: bool):
        """Show or hide the typing indicator."""
        if typing == self._typing:
            return
        self._typing = typing

        if typing:
            self._typing_indicator = TypingIndicator()
            self._msg_container.add_child(self._typing_indicator)
        elif hasattr(self, '_typing_indicator'):
            self._msg_container.remove_child(self._typing_indicator)

        self._auto_scroll()
        self.mark_dirty()

    def clear_chat(self):
        """Clear all messages."""
        self._messages.clear()
        self._msg_container.clear_children()
        self._next_msg_id = 1
        self.mark_dirty()

    @property
    def input_bar(self) -> InputBar:
        return self._input_bar

    @property
    def messages(self) -> list[ChatMessage]:
        return list(self._messages)

    @property
    def message_count(self) -> int:
        return len(self._messages)

    def _auto_scroll(self):
        """Scroll to the bottom of the chat."""
        if self._scroll._content_height > self._scroll.height:
            self._scroll.scroll_y = self._scroll.max_scroll
