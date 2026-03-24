"""
Claude-OS Rich Content Renderer

Renders rich content blocks within the chat interface:
    - Code blocks with syntax highlighting (keyword-based)
    - Data charts (bar chart, simple line indicators)
    - Interactive cards (WiFi picker, file browser, etc.)
    - Action buttons that trigger callbacks

These widgets are designed to be embedded directly in the chat
message flow alongside regular text bubbles.
"""

from dataclasses import dataclass, field
from enum import Enum, auto
from typing import Callable

from theme import Colors, Typography, Spacing, Radius, Color, FontStyle
from widget import (
    Widget, Size, EdgeInsets, Align, Direction, Event, EventType,
    _fill_rect, _blit_text,
)
from widgets import Container, Label, Button, ScrollView, Divider
from font import FontRenderer

_font = FontRenderer()


# --- Syntax Highlighting ---

# Simple keyword-based highlighting for common languages
KEYWORDS = {
    "python": {"def", "class", "import", "from", "return", "if", "else", "elif",
               "for", "while", "try", "except", "with", "as", "in", "not", "and",
               "or", "True", "False", "None", "self", "yield", "async", "await",
               "lambda", "pass", "break", "continue", "raise", "finally"},
    "javascript": {"function", "const", "let", "var", "return", "if", "else",
                    "for", "while", "class", "import", "export", "from", "new",
                    "this", "true", "false", "null", "undefined", "async", "await",
                    "try", "catch", "throw", "typeof", "instanceof"},
    "generic": {"if", "else", "for", "while", "return", "class", "function",
                "import", "true", "false", "null", "def", "let", "const", "var"},
}


class TokenType(Enum):
    PLAIN = auto()
    KEYWORD = auto()
    STRING = auto()
    COMMENT = auto()
    NUMBER = auto()


@dataclass
class Token:
    text: str
    token_type: TokenType


def tokenize_code(code: str, language: str = "generic") -> list[Token]:
    """
    Simple tokenizer for syntax highlighting.

    Not a full parser — just enough to highlight keywords, strings,
    comments, and numbers.
    """
    keywords = KEYWORDS.get(language, KEYWORDS["generic"])
    tokens = []
    i = 0
    line = code

    while i < len(line):
        ch = line[i]

        # String literals
        if ch in ('"', "'"):
            quote = ch
            j = i + 1
            while j < len(line) and line[j] != quote:
                if line[j] == '\\':
                    j += 1
                j += 1
            j = min(j + 1, len(line))
            tokens.append(Token(line[i:j], TokenType.STRING))
            i = j
            continue

        # Comments (# or //)
        if ch == '#' or (ch == '/' and i + 1 < len(line) and line[i + 1] == '/'):
            tokens.append(Token(line[i:], TokenType.COMMENT))
            i = len(line)
            continue

        # Numbers
        if ch.isdigit():
            j = i
            while j < len(line) and (line[j].isdigit() or line[j] == '.'):
                j += 1
            tokens.append(Token(line[i:j], TokenType.NUMBER))
            i = j
            continue

        # Words (identifiers / keywords)
        if ch.isalpha() or ch == '_':
            j = i
            while j < len(line) and (line[j].isalnum() or line[j] == '_'):
                j += 1
            word = line[i:j]
            if word in keywords:
                tokens.append(Token(word, TokenType.KEYWORD))
            else:
                tokens.append(Token(word, TokenType.PLAIN))
            i = j
            continue

        # Whitespace and symbols
        tokens.append(Token(ch, TokenType.PLAIN))
        i += 1

    return tokens


# Token type → color
SYNTAX_COLORS = {
    TokenType.PLAIN: Colors.TEXT_PRIMARY,
    TokenType.KEYWORD: Color(197, 134, 192),     # Purple
    TokenType.STRING: Color(152, 195, 121),       # Green
    TokenType.COMMENT: Color(92, 99, 112),        # Gray
    TokenType.NUMBER: Color(209, 154, 102),       # Orange
}


# --- Code Block Widget ---

class CodeBlock(Widget):
    """
    Renders a code block with syntax highlighting.

    Features:
        - Keyword highlighting for Python, JavaScript, generic code
        - Dark background with monospace-style font
        - Language label in top-right corner
        - Line numbers on the left
    """

    LINE_HEIGHT = 16
    LEFT_MARGIN = 32  # Space for line numbers

    def __init__(self, code: str = "", language: str = "generic"):
        super().__init__()
        self.code = code
        self.language = language
        self.background = Color(30, 30, 46)
        self.corner_radius = Radius.MD
        self.padding = EdgeInsets.all(Spacing.SM)
        self._lines = code.split('\n') if code else []

    def measure(self, max_w: int, max_h: int) -> Size:
        line_count = max(1, len(self._lines))
        h = (line_count * self.LINE_HEIGHT + self.padding.vertical +
             Typography.LABEL_SMALL.line_height + 4)  # +lang label
        return Size(
            max(self.min_width, min(max_w, max_w)),
            max(self.min_height, min(h, max_h)),
        )

    def draw_content(self, buf: bytearray, buf_w: int, buf_h: int,
                     abs_x: int, abs_y: int):
        # Language label
        if self.language:
            lang_rt = _font.render_text(
                self.language, Typography.LABEL_SMALL,
                Colors.TEXT_DISABLED,
            )
            if lang_rt.data:
                lx = abs_x + self.width - lang_rt.width - self.padding.right
                _blit_text(buf, buf_w, buf_h,
                           lx, abs_y + self.padding.top,
                           lang_rt.data, lang_rt.width, lang_rt.height,
                           lang_rt.stride)

        # Code lines with syntax highlighting
        code_style = FontStyle(size=12, weight="regular", spacing=0)
        y = abs_y + self.padding.top + Typography.LABEL_SMALL.line_height + 4

        for i, line in enumerate(self._lines):
            # Line number
            ln_text = f"{i + 1:3d}"
            ln_rt = _font.render_text(ln_text, code_style, Colors.TEXT_DISABLED)
            if ln_rt.data:
                _blit_text(buf, buf_w, buf_h,
                           abs_x + self.padding.left, y,
                           ln_rt.data, ln_rt.width, ln_rt.height,
                           ln_rt.stride)

            # Tokenize and render with colors
            tokens = tokenize_code(line, self.language)
            tx = abs_x + self.padding.left + self.LEFT_MARGIN

            for token in tokens:
                color = SYNTAX_COLORS.get(token.token_type, Colors.TEXT_PRIMARY)
                rt = _font.render_text(token.text, code_style, color)
                if rt.data:
                    _blit_text(buf, buf_w, buf_h,
                               tx, y, rt.data, rt.width, rt.height,
                               rt.stride)
                    tx += rt.width

            y += self.LINE_HEIGHT


# --- Bar Chart Widget ---

@dataclass
class BarData:
    """A single bar in a bar chart."""
    label: str
    value: float
    color: Color = None


class BarChart(Widget):
    """
    Simple horizontal bar chart for displaying data inline.

    Good for: battery status, storage usage, WiFi signal comparison.
    """

    BAR_HEIGHT = 20
    BAR_GAP = 6
    LABEL_WIDTH = 60

    def __init__(self, title: str = "", bars: list[BarData] = None):
        super().__init__()
        self.title = title
        self.bars = bars or []
        self.background = Colors.SURFACE_CONTAINER
        self.corner_radius = Radius.MD
        self.padding = EdgeInsets.all(Spacing.SM)
        self.max_value: float = 0  # Auto-computed if 0

    def measure(self, max_w: int, max_h: int) -> Size:
        title_h = Typography.LABEL_MEDIUM.line_height + 4 if self.title else 0
        bars_h = len(self.bars) * (self.BAR_HEIGHT + self.BAR_GAP)
        h = title_h + bars_h + self.padding.vertical
        return Size(max(self.min_width, min(max_w, max_w)),
                    max(self.min_height, min(h, max_h)))

    def draw_content(self, buf: bytearray, buf_w: int, buf_h: int,
                     abs_x: int, abs_y: int):
        y = abs_y + self.padding.top

        # Title
        if self.title:
            rt = _font.render_text(self.title, Typography.LABEL_MEDIUM,
                                   Colors.TEXT_PRIMARY)
            if rt.data:
                _blit_text(buf, buf_w, buf_h,
                           abs_x + self.padding.left, y,
                           rt.data, rt.width, rt.height, rt.stride)
            y += Typography.LABEL_MEDIUM.line_height + 4

        # Compute max
        max_val = self.max_value or max((b.value for b in self.bars), default=1)
        bar_area_w = self.content_width - self.LABEL_WIDTH - 10

        for bar in self.bars:
            # Label
            rt = _font.render_text(bar.label[:8], Typography.BODY_SMALL,
                                   Colors.TEXT_SECONDARY)
            if rt.data:
                _blit_text(buf, buf_w, buf_h,
                           abs_x + self.padding.left, y + 2,
                           rt.data, rt.width, rt.height, rt.stride)

            # Bar
            bar_x = abs_x + self.padding.left + self.LABEL_WIDTH
            ratio = min(1.0, bar.value / max_val) if max_val > 0 else 0
            bar_w = max(2, int(bar_area_w * ratio))
            color = bar.color or Colors.PRIMARY
            _fill_rect(buf, buf_w, buf_h,
                       bar_x, y, bar_w, self.BAR_HEIGHT, color)

            # Value label
            val_text = f"{bar.value:.0f}"
            val_rt = _font.render_text(val_text, Typography.LABEL_SMALL,
                                       Colors.TEXT_SECONDARY)
            if val_rt.data:
                _blit_text(buf, buf_w, buf_h,
                           bar_x + bar_w + 4, y + 3,
                           val_rt.data, val_rt.width, val_rt.height,
                           val_rt.stride)

            y += self.BAR_HEIGHT + self.BAR_GAP


# --- Interactive Card Widget ---

class InteractiveCard(Widget):
    """
    A card with a title, body content, and action buttons.

    Used for: WiFi network picker, file browser items, settings cards.
    Claude can generate these dynamically in chat responses.
    """

    def __init__(self, title: str = "", body: str = "",
                 icon: str = "", actions: list[dict] = None):
        super().__init__()
        self.title = title
        self.body = body
        self.icon = icon
        self.actions = actions or []  # [{"label": "Connect", "callback": fn}]
        self.background = Colors.SURFACE_CONTAINER
        self.corner_radius = Radius.LG
        self.padding = EdgeInsets.all(Spacing.MD)
        self._action_buttons: list[Button] = []
        self._build()

    def _build(self):
        self._action_buttons.clear()
        for action in self.actions:
            btn = Button(
                text=action.get("label", "Action"),
                on_tap=action.get("callback"),
            )
            btn.padding = EdgeInsets.symmetric(horizontal=12, vertical=6)
            self._action_buttons.append(btn)

    def measure(self, max_w: int, max_h: int) -> Size:
        h = self.padding.vertical
        if self.title:
            h += Typography.TITLE_MEDIUM.line_height + 4
        if self.body:
            # Estimate wrapped text height
            chars_per_line = max(1, (max_w - self.padding.horizontal) // 8)
            lines = max(1, len(self.body) // chars_per_line + 1)
            h += lines * Typography.BODY_MEDIUM.line_height
        if self._action_buttons:
            h += 8 + 36  # gap + button height
        return Size(max(self.min_width, min(max_w, max_w)),
                    max(self.min_height, min(h, max_h)))

    def draw_content(self, buf: bytearray, buf_w: int, buf_h: int,
                     abs_x: int, abs_y: int):
        y = abs_y + self.padding.top
        left = abs_x + self.padding.left

        # Icon + Title
        if self.title:
            title_text = self.title
            if self.icon:
                title_text = f"{self.icon} {self.title}"
            rt = _font.render_text(title_text, Typography.TITLE_MEDIUM,
                                   Colors.TEXT_PRIMARY)
            if rt.data:
                _blit_text(buf, buf_w, buf_h, left, y,
                           rt.data, rt.width, rt.height, rt.stride)
            y += Typography.TITLE_MEDIUM.line_height + 4

        # Body
        if self.body:
            body_rt = _font.render_wrapped(
                self.body, Typography.BODY_MEDIUM, Colors.TEXT_SECONDARY,
                self.content_width,
            )
            if body_rt.data:
                _blit_text(buf, buf_w, buf_h, left, y,
                           body_rt.data, body_rt.width, body_rt.height,
                           body_rt.stride)
            y += body_rt.height + 8

        # Action buttons (horizontal row)
        bx = left
        for btn in self._action_buttons:
            size = btn.measure(self.content_width, 36)
            btn.layout(0, 0, size.width, 36)
            btn.draw(buf, buf_w, buf_h, bx, y)
            bx += size.width + Spacing.SM

    def _handle_event(self, event_type: EventType, x: int, y: int,
                      key_code: int) -> bool:
        if event_type == EventType.TOUCH_UP:
            # Check if any action button was tapped
            for i, btn in enumerate(self._action_buttons):
                if i < len(self.actions):
                    cb = self.actions[i].get("callback")
                    if cb:
                        cb()
                        return True
        return False


# --- Action Button Bar ---

class ActionButtonBar(Widget):
    """
    A horizontal row of action buttons for inline chat actions.

    E.g., "Connect" | "Open" | "Share" — Claude includes these
    in responses to provide one-tap actions.
    """

    BUTTON_HEIGHT = 36

    def __init__(self, actions: list[dict] = None):
        super().__init__()
        self.actions = actions or []
        self.padding = EdgeInsets.symmetric(horizontal=Spacing.SM,
                                            vertical=Spacing.XS)
        self._buttons: list[Button] = []
        self._build()

    def _build(self):
        self._buttons.clear()
        for action in self.actions:
            btn = Button(
                text=action.get("label", ""),
                on_tap=action.get("callback"),
                color=action.get("color", Colors.PRIMARY),
            )
            btn.padding = EdgeInsets.symmetric(horizontal=16, vertical=8)
            self._buttons.append(btn)

    def measure(self, max_w: int, max_h: int) -> Size:
        h = self.BUTTON_HEIGHT + self.padding.vertical
        return Size(max(self.min_width, min(max_w, max_w)),
                    max(self.min_height, h))

    def draw_content(self, buf: bytearray, buf_w: int, buf_h: int,
                     abs_x: int, abs_y: int):
        bx = abs_x + self.padding.left
        by = abs_y + self.padding.top

        for btn in self._buttons:
            size = btn.measure(self.content_width, self.BUTTON_HEIGHT)
            btn.layout(0, 0, size.width, self.BUTTON_HEIGHT)
            btn.draw(buf, buf_w, buf_h, bx, by)
            bx += size.width + Spacing.SM

    @property
    def button_count(self) -> int:
        return len(self._buttons)


# --- Rich Content Parser ---

class ContentBlockType(Enum):
    TEXT = auto()
    CODE = auto()
    CHART = auto()
    CARD = auto()
    ACTIONS = auto()


@dataclass
class ContentBlock:
    """A parsed block of rich content."""
    block_type: ContentBlockType
    text: str = ""
    language: str = ""
    data: dict = field(default_factory=dict)


class RichContentParser:
    """
    Parses Claude's response text into rich content blocks.

    Recognizes markdown-like patterns:
        ```python
        code here
        ```
        → CodeBlock

        [chart:bar title="Storage" data="Apps:45,Photos:30,System:15"]
        → BarChart

        [card title="WiFi Network" body="Signal: Strong" actions="Connect,Forget"]
        → InteractiveCard

        [actions: Connect | Open | Share]
        → ActionButtonBar
    """

    def parse(self, text: str, action_handler: Callable = None) -> list[ContentBlock]:
        """
        Parse response text into content blocks.

        Args:
            text: Claude's response text
            action_handler: Callback for action buttons (receives label string)

        Returns:
            List of ContentBlock objects.
        """
        blocks = []
        lines = text.split('\n')
        i = 0

        while i < len(lines):
            line = lines[i]

            # Code block
            if line.strip().startswith('```'):
                lang = line.strip()[3:].strip()
                code_lines = []
                i += 1
                while i < len(lines) and not lines[i].strip().startswith('```'):
                    code_lines.append(lines[i])
                    i += 1
                blocks.append(ContentBlock(
                    block_type=ContentBlockType.CODE,
                    text='\n'.join(code_lines),
                    language=lang or "generic",
                ))
                i += 1  # Skip closing ```
                continue

            # Chart
            if line.strip().startswith('[chart:'):
                blocks.append(self._parse_chart(line.strip()))
                i += 1
                continue

            # Card
            if line.strip().startswith('[card '):
                blocks.append(self._parse_card(line.strip()))
                i += 1
                continue

            # Actions
            if line.strip().startswith('[actions:'):
                blocks.append(self._parse_actions(line.strip(), action_handler))
                i += 1
                continue

            # Regular text
            text_lines = [line]
            i += 1
            while i < len(lines):
                next_line = lines[i].strip()
                if (next_line.startswith('```') or
                    next_line.startswith('[chart:') or
                    next_line.startswith('[card ') or
                    next_line.startswith('[actions:')):
                    break
                text_lines.append(lines[i])
                i += 1

            joined = '\n'.join(text_lines).strip()
            if joined:
                blocks.append(ContentBlock(
                    block_type=ContentBlockType.TEXT,
                    text=joined,
                ))

        return blocks

    def _parse_chart(self, line: str) -> ContentBlock:
        """Parse [chart:bar title="X" data="A:1,B:2"]"""
        data = {}

        # Extract chart type
        chart_type = "bar"
        if "chart:bar" in line:
            chart_type = "bar"

        # Extract title
        title_start = line.find('title="')
        if title_start >= 0:
            title_start += 7
            title_end = line.find('"', title_start)
            if title_end > title_start:
                data["title"] = line[title_start:title_end]

        # Extract data
        data_start = line.find('data="')
        if data_start >= 0:
            data_start += 6
            data_end = line.find('"', data_start)
            if data_end > data_start:
                data["bars"] = []
                for pair in line[data_start:data_end].split(','):
                    parts = pair.split(':')
                    if len(parts) == 2:
                        data["bars"].append({
                            "label": parts[0].strip(),
                            "value": float(parts[1].strip()),
                        })

        data["chart_type"] = chart_type
        return ContentBlock(block_type=ContentBlockType.CHART, data=data)

    def _parse_card(self, line: str) -> ContentBlock:
        """Parse [card title="X" body="Y" actions="A,B"]"""
        data = {}

        for key in ("title", "body", "icon"):
            start = line.find(f'{key}="')
            if start >= 0:
                start += len(key) + 2
                end = line.find('"', start)
                if end > start:
                    data[key] = line[start:end]

        actions_start = line.find('actions="')
        if actions_start >= 0:
            actions_start += 9
            actions_end = line.find('"', actions_start)
            if actions_end > actions_start:
                data["actions"] = [
                    a.strip() for a in line[actions_start:actions_end].split(',')
                ]

        return ContentBlock(block_type=ContentBlockType.CARD, data=data)

    def _parse_actions(self, line: str, handler: Callable = None) -> ContentBlock:
        """Parse [actions: Connect | Open | Share]"""
        content = line.strip()
        if content.startswith('[actions:'):
            content = content[9:]
        if content.endswith(']'):
            content = content[:-1]

        labels = [a.strip() for a in content.split('|') if a.strip()]
        data = {"labels": labels, "handler": handler}
        return ContentBlock(block_type=ContentBlockType.ACTIONS, data=data)

    def blocks_to_widgets(self, blocks: list[ContentBlock],
                          action_handler: Callable = None) -> list[Widget]:
        """Convert parsed content blocks to renderable widgets."""
        widgets = []
        for block in blocks:
            if block.block_type == ContentBlockType.TEXT:
                label = Label(
                    text=block.text,
                    style=Typography.BODY_MEDIUM,
                    color=Colors.TEXT_PRIMARY,
                    wrap=True,
                )
                widgets.append(label)

            elif block.block_type == ContentBlockType.CODE:
                cb = CodeBlock(code=block.text, language=block.language)
                widgets.append(cb)

            elif block.block_type == ContentBlockType.CHART:
                bars = [
                    BarData(label=b["label"], value=b["value"])
                    for b in block.data.get("bars", [])
                ]
                chart = BarChart(title=block.data.get("title", ""), bars=bars)
                widgets.append(chart)

            elif block.block_type == ContentBlockType.CARD:
                actions = []
                for label in block.data.get("actions", []):
                    actions.append({
                        "label": label,
                        "callback": (lambda l=label: action_handler(l))
                        if action_handler else None,
                    })
                card = InteractiveCard(
                    title=block.data.get("title", ""),
                    body=block.data.get("body", ""),
                    icon=block.data.get("icon", ""),
                    actions=actions,
                )
                widgets.append(card)

            elif block.block_type == ContentBlockType.ACTIONS:
                actions = []
                for label in block.data.get("labels", []):
                    h = block.data.get("handler") or action_handler
                    actions.append({
                        "label": label,
                        "callback": (lambda l=label: h(l)) if h else None,
                    })
                bar = ActionButtonBar(actions=actions)
                widgets.append(bar)

        return widgets
