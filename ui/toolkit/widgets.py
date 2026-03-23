"""
Claude-OS Core Widgets

Built on the Widget base class, these are the building blocks for all
UI screens in the OS:

    Container  — Flex layout container (horizontal or vertical)
    Label      — Text display
    Button     — Tappable button with label
    TextInput  — Editable text field
    ScrollView — Scrollable container for overflow content
    Spacer     — Flexible empty space (for layout)
    Divider    — Horizontal or vertical line separator
    Image      — Pixel buffer display
"""

from typing import Callable

from font import FontRenderer, RenderedText
from theme import (
    Color, Colors, FontStyle, Spacing, Typography, Radius, default_theme,
)
from widget import (
    Widget, Size, EdgeInsets, Align, Direction, Event, EventType,
    _fill_rect, _blit_text,
)

# Shared font renderer
_font = FontRenderer()


# --- Container ---

class Container(Widget):
    """
    Flex layout container.

    Arranges children in a row (horizontal) or column (vertical).
    Supports flex sizing — children with flex > 0 share remaining
    space proportionally.
    """

    def __init__(self, direction: Direction = Direction.VERTICAL,
                 align: Align = Align.START,
                 cross_align: Align = Align.START,
                 gap: int = 0):
        super().__init__()
        self.direction = direction
        self.align = align
        self.cross_align = cross_align
        self.gap = gap

    def measure(self, max_w: int, max_h: int) -> Size:
        total_main = 0
        max_cross = 0
        visible = [c for c in self.children if c.visible]

        for child in visible:
            size = child.measure(max_w, max_h)
            if self.direction == Direction.VERTICAL:
                total_main += size.height
                max_cross = max(max_cross, size.width)
            else:
                total_main += size.width
                max_cross = max(max_cross, size.height)

        if visible:
            total_main += self.gap * (len(visible) - 1)

        p = self.padding
        if self.direction == Direction.VERTICAL:
            w = max_cross + p.horizontal
            h = total_main + p.vertical
        else:
            w = total_main + p.horizontal
            h = max_cross + p.vertical

        return Size(
            max(self.min_width, min(w, max_w)),
            max(self.min_height, min(h, max_h)),
        )

    def _layout_children(self):
        visible = [c for c in self.children if c.visible]
        if not visible:
            return

        cw = self.content_width
        ch = self.content_height
        is_vert = self.direction == Direction.VERTICAL
        main_size = ch if is_vert else cw
        cross_size = cw if is_vert else ch

        # Measure fixed children and count flex
        total_fixed = 0
        total_flex = 0
        measurements = []

        for child in visible:
            size = child.measure(cw, ch)
            measurements.append(size)
            if child.flex > 0:
                total_flex += child.flex
            else:
                total_fixed += (size.height if is_vert else size.width)

        gap_total = self.gap * (len(visible) - 1)
        remaining = max(0, main_size - total_fixed - gap_total)

        # Position children
        pos = self.padding.top if is_vert else self.padding.left
        cross_start = self.padding.left if is_vert else self.padding.top

        for i, child in enumerate(visible):
            size = measurements[i]

            # Determine main axis size
            if child.flex > 0:
                main = int(remaining * child.flex / total_flex) if total_flex else 0
            else:
                main = size.height if is_vert else size.width

            # Determine cross axis size and alignment
            cross = size.width if is_vert else size.height
            cross_offset = cross_start
            if self.cross_align == Align.CENTER:
                cross_offset += (cross_size - cross) // 2
            elif self.cross_align == Align.END:
                cross_offset += cross_size - cross

            if is_vert:
                child.layout(cross_offset, pos, cross, main)
            else:
                child.layout(pos, cross_offset, main, cross)

            pos += main + self.gap


# --- Label ---

class Label(Widget):
    """Text display widget."""

    def __init__(self, text: str = "",
                 style: FontStyle = None,
                 color: Color = None,
                 align: Align = Align.START,
                 wrap: bool = False):
        super().__init__()
        self.text = text
        self.style = style or Typography.BODY_MEDIUM
        self.color = color or Colors.TEXT_PRIMARY
        self.align = align
        self.wrap = wrap
        self._rendered: RenderedText | None = None

    def measure(self, max_w: int, max_h: int) -> Size:
        if not self.text:
            return Size(self.padding.horizontal,
                        self.style.line_height + self.padding.vertical)

        if self.wrap and max_w > self.padding.horizontal:
            rt = _font.render_wrapped(
                self.text, self.style, self.color,
                max_w - self.padding.horizontal,
            )
            self._rendered = rt
        else:
            w, h = _font.measure_text(self.text, self.style)
            return Size(
                max(self.min_width, min(w + self.padding.horizontal, max_w)),
                max(self.min_height, min(h + self.padding.vertical, max_h)),
            )

        return Size(
            max(self.min_width, min(self._rendered.width + self.padding.horizontal, max_w)),
            max(self.min_height, min(self._rendered.height + self.padding.vertical, max_h)),
        )

    def draw_content(self, buf: bytearray, buf_w: int, buf_h: int,
                     abs_x: int, abs_y: int):
        if not self.text:
            return

        if self._rendered is None or self._dirty:
            if self.wrap:
                self._rendered = _font.render_wrapped(
                    self.text, self.style, self.color, self.content_width,
                )
            else:
                self._rendered = _font.render_text(
                    self.text, self.style, self.color,
                )

        rt = self._rendered
        if not rt.data:
            return

        # Horizontal alignment
        text_x = abs_x + self.padding.left
        if self.align == Align.CENTER:
            text_x += (self.content_width - rt.width) // 2
        elif self.align == Align.END:
            text_x += self.content_width - rt.width

        text_y = abs_y + self.padding.top

        _blit_text(buf, buf_w, buf_h,
                   text_x, text_y, rt.data,
                   rt.width, rt.height, rt.stride)


# --- Button ---

class Button(Widget):
    """Tappable button with a text label."""

    def __init__(self, text: str = "",
                 style: FontStyle = None,
                 color: Color = None,
                 text_color: Color = None,
                 on_tap: Callable = None):
        super().__init__()
        self.text = text
        self.text_style = style or Typography.LABEL_LARGE
        self.background = color or Colors.PRIMARY
        self.text_color = text_color or Colors.TEXT_ON_PRIMARY
        self.corner_radius = Radius.MD
        self.padding = EdgeInsets.symmetric(
            horizontal=Spacing.BUTTON_PADDING_H,
            vertical=Spacing.BUTTON_PADDING_V,
        )
        self._on_tap = on_tap
        self._label = Label(text=text, style=self.text_style,
                            color=self.text_color, align=Align.CENTER)

    def measure(self, max_w: int, max_h: int) -> Size:
        text_size = self._label.measure(max_w, max_h)
        w = text_size.width + self.padding.horizontal
        h = text_size.height + self.padding.vertical
        return Size(
            max(self.min_width, min(w, max_w)),
            max(self.min_height, min(h, max_h)),
        )

    def draw_content(self, buf: bytearray, buf_w: int, buf_h: int,
                     abs_x: int, abs_y: int):
        self._label.text = self.text
        self._label.color = self.text_color
        self._label.style = self.text_style
        self._label.width = self.content_width
        self._label.height = self.content_height

        # Center label within button
        text_size = _font.measure_text(self.text, self.text_style)
        tx = abs_x + self.padding.left + (self.content_width - text_size[0]) // 2
        ty = abs_y + self.padding.top + (self.content_height - text_size[1]) // 2

        rt = _font.render_text(self.text, self.text_style, self.text_color)
        if rt.data:
            _blit_text(buf, buf_w, buf_h,
                       tx, ty, rt.data, rt.width, rt.height, rt.stride)


# --- TextInput ---

class TextInput(Widget):
    """Editable text field."""

    def __init__(self, placeholder: str = "",
                 text: str = "",
                 on_change: Callable = None,
                 on_submit: Callable = None):
        super().__init__()
        self.text = text
        self.placeholder = placeholder
        self.cursor_pos: int = len(text)
        self.text_style = Typography.BODY_MEDIUM
        self.text_color = Colors.TEXT_PRIMARY
        self.placeholder_color = Colors.TEXT_DISABLED
        self.background = Colors.SURFACE_CONTAINER
        self.border_color = Colors.BORDER
        self.border_width = 1
        self.corner_radius = Radius.MD
        self.padding = EdgeInsets.symmetric(
            horizontal=Spacing.INPUT_PADDING_H,
            vertical=Spacing.INPUT_PADDING_V,
        )

        self._on_change = on_change
        self._on_submit = on_submit
        self._cursor_visible = False

    def measure(self, max_w: int, max_h: int) -> Size:
        h = self.text_style.line_height + self.padding.vertical
        return Size(
            max(self.min_width, min(max_w, 300)),
            max(self.min_height, h),
        )

    def draw_content(self, buf: bytearray, buf_w: int, buf_h: int,
                     abs_x: int, abs_y: int):
        display_text = self.text or self.placeholder
        color = self.text_color if self.text else self.placeholder_color

        rt = _font.render_text(display_text, self.text_style, color)
        if rt.data:
            tx = abs_x + self.padding.left
            ty = abs_y + self.padding.top
            _blit_text(buf, buf_w, buf_h,
                       tx, ty, rt.data, rt.width, rt.height, rt.stride)

        # Draw cursor
        if self._focused and self._cursor_visible:
            cursor_x = abs_x + self.padding.left
            if self.text:
                before = self.text[:self.cursor_pos]
                cw, _ = _font.measure_text(before, self.text_style)
                cursor_x += cw
            cursor_y = abs_y + self.padding.top
            _fill_rect(buf, buf_w, buf_h,
                       cursor_x, cursor_y, 2,
                       self.text_style.line_height,
                       Colors.TEXT_PRIMARY)

    def _handle_event(self, event_type: EventType, x: int, y: int,
                      key_code: int) -> bool:
        if event_type == EventType.TOUCH_DOWN:
            self._focused = True
            self._cursor_visible = True
            self.mark_dirty()
            return True

        if event_type == EventType.KEY_DOWN and self._focused:
            self._on_key(key_code)
            return True

        return super()._handle_event(event_type, x, y, key_code)

    def _on_key(self, key_code: int):
        """Handle keyboard input."""
        if key_code == 14:  # Backspace
            if self.cursor_pos > 0:
                self.text = (self.text[:self.cursor_pos - 1] +
                             self.text[self.cursor_pos:])
                self.cursor_pos -= 1
        elif key_code == 28:  # Enter
            if self._on_submit:
                self._on_submit(self.text)
        elif 2 <= key_code <= 127:
            # Basic ASCII — real implementation would use keymap
            ch = self._keycode_to_char(key_code)
            if ch:
                self.text = (self.text[:self.cursor_pos] + ch +
                             self.text[self.cursor_pos:])
                self.cursor_pos += 1

        if self._on_change:
            self._on_change(self.text)
        self.mark_dirty()

    @staticmethod
    def _keycode_to_char(key_code: int) -> str:
        """Simple keycode to character mapping (US QWERTY)."""
        keymap = {
            2: '1', 3: '2', 4: '3', 5: '4', 6: '5',
            7: '6', 8: '7', 9: '8', 10: '9', 11: '0',
            16: 'q', 17: 'w', 18: 'e', 19: 'r', 20: 't',
            21: 'y', 22: 'u', 23: 'i', 24: 'o', 25: 'p',
            30: 'a', 31: 's', 32: 'd', 33: 'f', 34: 'g',
            35: 'h', 36: 'j', 37: 'k', 38: 'l',
            44: 'z', 45: 'x', 46: 'c', 47: 'v', 48: 'b',
            49: 'n', 50: 'm',
            57: ' ',  # Space
        }
        return keymap.get(key_code, "")


# --- ScrollView ---

class ScrollView(Widget):
    """
    Scrollable container.

    Clips children to its bounds and offsets them by scroll_y.
    Touch drag scrolls vertically.
    """

    def __init__(self):
        super().__init__()
        self.scroll_y: int = 0
        self.scroll_x: int = 0
        self._content_height: int = 0
        self._dragging = False
        self._drag_start_y = 0
        self._drag_start_scroll = 0

    def measure(self, max_w: int, max_h: int) -> Size:
        # ScrollView takes all available space
        return Size(max_w, max_h)

    def _layout_children(self):
        """Layout children in a vertical stack, measuring total content height."""
        cw = self.content_width
        y = 0

        for child in self.children:
            if not child.visible:
                continue
            size = child.measure(cw, 0x7FFFFFFF)
            child.layout(self.padding.left, y, size.width, size.height)
            y += size.height

        self._content_height = y

    def draw(self, buf: bytearray, buf_w: int, buf_h: int,
             ox: int = 0, oy: int = 0):
        if not self.visible:
            return

        abs_x = ox + self.x
        abs_y = oy + self.y

        # Draw background
        if self.background:
            _fill_rect(buf, buf_w, buf_h,
                       abs_x, abs_y, self.width, self.height,
                       self.background)

        # Draw children with scroll offset (clip to bounds)
        for child in self.children:
            child_abs_y = abs_y + child.y - self.scroll_y
            # Skip if completely outside viewport
            if child_abs_y + child.height < abs_y:
                continue
            if child_abs_y >= abs_y + self.height:
                continue
            child.draw(buf, buf_w, buf_h,
                       abs_x, abs_y - self.scroll_y)

        # Draw scrollbar if content overflows
        if self._content_height > self.height:
            self._draw_scrollbar(buf, buf_w, buf_h, abs_x, abs_y)

    def _draw_scrollbar(self, buf: bytearray, buf_w: int, buf_h: int,
                        abs_x: int, abs_y: int):
        bar_w = 4
        bar_x = abs_x + self.width - bar_w - 2
        ratio = self.height / self._content_height
        bar_h = max(20, int(self.height * ratio))
        max_scroll = self._content_height - self.height
        if max_scroll > 0:
            bar_y = abs_y + int(self.scroll_y / max_scroll * (self.height - bar_h))
        else:
            bar_y = abs_y
        _fill_rect(buf, buf_w, buf_h,
                   bar_x, bar_y, bar_w, bar_h,
                   Colors.TEXT_DISABLED.with_alpha(80))

    def _handle_event(self, event_type: EventType, x: int, y: int,
                      key_code: int) -> bool:
        if event_type == EventType.TOUCH_DOWN:
            self._dragging = True
            self._drag_start_y = y
            self._drag_start_scroll = self.scroll_y
            return True

        elif event_type == EventType.TOUCH_MOVE and self._dragging:
            dy = self._drag_start_y - y
            max_scroll = max(0, self._content_height - self.height)
            self.scroll_y = max(0, min(max_scroll,
                                        self._drag_start_scroll + dy))
            self.mark_dirty()
            return True

        elif event_type == EventType.TOUCH_UP:
            self._dragging = False
            return False

        return False

    @property
    def max_scroll(self) -> int:
        return max(0, self._content_height - self.height)


# --- Spacer ---

class Spacer(Widget):
    """Flexible empty space. Use with flex to push items apart."""

    def __init__(self, flex: int = 1):
        super().__init__()
        self.flex = flex

    def measure(self, max_w: int, max_h: int) -> Size:
        return Size(0, 0)


# --- Divider ---

class Divider(Widget):
    """Thin horizontal or vertical separator line."""

    def __init__(self, direction: Direction = Direction.HORIZONTAL,
                 color: Color = None, thickness: int = 1):
        super().__init__()
        self.direction = direction
        self.line_color = color or Colors.DIVIDER
        self.thickness = thickness

    def measure(self, max_w: int, max_h: int) -> Size:
        if self.direction == Direction.HORIZONTAL:
            return Size(max_w, self.thickness)
        return Size(self.thickness, max_h)

    def draw_content(self, buf: bytearray, buf_w: int, buf_h: int,
                     abs_x: int, abs_y: int):
        _fill_rect(buf, buf_w, buf_h,
                   abs_x, abs_y, self.width, self.height,
                   self.line_color)


# --- Image ---

class Image(Widget):
    """Displays a raw BGRA pixel buffer."""

    def __init__(self, data: bytearray = None,
                 img_width: int = 0, img_height: int = 0):
        super().__init__()
        self.img_data = data
        self.img_width = img_width
        self.img_height = img_height

    def measure(self, max_w: int, max_h: int) -> Size:
        return Size(
            min(self.img_width + self.padding.horizontal, max_w),
            min(self.img_height + self.padding.vertical, max_h),
        )

    def draw_content(self, buf: bytearray, buf_w: int, buf_h: int,
                     abs_x: int, abs_y: int):
        if not self.img_data:
            return
        stride = self.img_width * 4
        _blit_text(buf, buf_w, buf_h,
                   abs_x + self.padding.left,
                   abs_y + self.padding.top,
                   self.img_data, self.img_width, self.img_height, stride)
