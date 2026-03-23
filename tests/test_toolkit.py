"""
Tests for the UI toolkit — theme, font, widgets, layout, and events.
"""

import struct
import pytest
from theme import Color, Colors, FontStyle, Typography, Spacing, Radius, default_theme
from font import FontRenderer, RenderedText, FONT_8X8, BASE_GLYPH_WIDTH, BASE_GLYPH_HEIGHT
from widget import (
    Widget, Size, EdgeInsets, Align, Direction,
    Event, EventType, _fill_rect, _draw_border,
)
from widgets import (
    Container, Label, Button, TextInput, ScrollView,
    Spacer, Divider, Image,
)


# --- Theme Tests ---

class TestColor:
    def test_create(self):
        c = Color(255, 128, 0)
        assert c.r == 255
        assert c.g == 128
        assert c.b == 0
        assert c.a == 255

    def test_with_alpha(self):
        c = Color(255, 0, 0).with_alpha(128)
        assert c.a == 128
        assert c.r == 255

    def test_blend(self):
        c1 = Color(0, 0, 0)
        c2 = Color(255, 255, 255)
        mid = c1.blend(c2, 0.5)
        assert mid.r == 127
        assert mid.g == 127

    def test_bgra(self):
        c = Color(255, 128, 64)
        assert c.bgra == (64, 128, 255, 255)

    def test_hex(self):
        c = Color(255, 128, 0)
        assert c.hex == "#ff8000"


class TestTheme:
    def test_default_theme_exists(self):
        assert default_theme is not None
        assert default_theme.colors is Colors

    def test_spacing_values(self):
        assert Spacing.SM < Spacing.MD < Spacing.LG

    def test_typography_line_height(self):
        assert Typography.BODY_MEDIUM.line_height > Typography.BODY_MEDIUM.size

    def test_font_style_frozen(self):
        with pytest.raises(AttributeError):
            Typography.BODY_MEDIUM.size = 99


# --- Font Renderer Tests ---

class TestFontRenderer:
    def setup_method(self):
        self.font = FontRenderer()

    def test_render_empty(self):
        rt = self.font.render_text("", Typography.BODY_MEDIUM, Colors.WHITE)
        assert rt.width == 0

    def test_render_single_char(self):
        rt = self.font.render_text("A", Typography.BODY_MEDIUM, Colors.WHITE)
        assert rt.width > 0
        assert rt.height > 0
        assert len(rt.data) == rt.stride * rt.height

    def test_render_has_pixels(self):
        rt = self.font.render_text("X", FontStyle(size=8, weight="regular", spacing=0),
                                   Color(255, 255, 255))
        # At 1x scale, 'X' should have some non-zero pixels
        has_pixel = any(rt.data[i + 3] > 0 for i in range(0, len(rt.data), 4))
        assert has_pixel

    def test_render_width_scales_with_text(self):
        rt1 = self.font.render_text("A", Typography.BODY_MEDIUM, Colors.WHITE)
        rt3 = self.font.render_text("ABC", Typography.BODY_MEDIUM, Colors.WHITE)
        assert rt3.width > rt1.width

    def test_measure_text(self):
        w, h = self.font.measure_text("Hello", Typography.BODY_MEDIUM)
        assert w > 0
        assert h > 0

    def test_measure_empty(self):
        w, h = self.font.measure_text("", Typography.BODY_MEDIUM)
        assert w == 0

    def test_word_wrap(self):
        rt = self.font.render_wrapped(
            "Hello World Wrap", Typography.BODY_MEDIUM, Colors.WHITE, 80,
        )
        assert rt.height > Typography.BODY_MEDIUM.line_height

    def test_font_covers_ascii(self):
        for code in range(0x20, 0x7F):
            ch = chr(code)
            rt = self.font.render_text(ch, Typography.BODY_MEDIUM, Colors.WHITE)
            assert rt.width > 0


# --- Widget Base Tests ---

class TestWidget:
    def test_create(self):
        w = Widget()
        assert w.x == 0
        assert w.y == 0
        assert w.visible is True

    def test_add_child(self):
        parent = Widget()
        child = Widget()
        parent.add_child(child)
        assert child in parent.children
        assert child.parent is parent

    def test_remove_child(self):
        parent = Widget()
        child = Widget()
        parent.add_child(child)
        parent.remove_child(child)
        assert child not in parent.children
        assert child.parent is None

    def test_clear_children(self):
        parent = Widget()
        for _ in range(3):
            parent.add_child(Widget())
        parent.clear_children()
        assert len(parent.children) == 0

    def test_layout(self):
        w = Widget()
        w.layout(10, 20, 100, 50)
        assert w.x == 10
        assert w.y == 20
        assert w.width == 100
        assert w.height == 50

    def test_hit_test(self):
        w = Widget()
        w.layout(0, 0, 100, 100)
        assert w.hit_test(50, 50) is True
        assert w.hit_test(150, 50) is False
        assert w.hit_test(-1, 50) is False

    def test_content_size_with_padding(self):
        w = Widget()
        w.padding = EdgeInsets.all(10)
        w.layout(0, 0, 100, 100)
        assert w.content_width == 80
        assert w.content_height == 80

    def test_draw_background(self):
        w = Widget()
        w.background = Color(255, 0, 0)
        w.layout(0, 0, 4, 4)
        buf = bytearray(4 * 4 * 4)
        w.draw(buf, 4, 4)
        # Check first pixel is red (BGRA)
        assert buf[0:4] == bytes([0, 0, 255, 255])

    def test_invisible_not_drawn(self):
        w = Widget()
        w.background = Color(255, 0, 0)
        w.visible = False
        w.layout(0, 0, 4, 4)
        buf = bytearray(4 * 4 * 4)
        w.draw(buf, 4, 4)
        assert buf[0:4] == bytes([0, 0, 0, 0])

    def test_on_tap_callback(self):
        tapped = []
        w = Widget()
        w.on_tap(lambda: tapped.append(True))
        w.layout(0, 0, 100, 100)

        # Touch down then up
        w.on_event(Event(type=EventType.TOUCH_DOWN, x=50, y=50))
        w.on_event(Event(type=EventType.TOUCH_UP, x=50, y=50))
        assert len(tapped) == 1

    def test_event_not_consumed_outside(self):
        w = Widget()
        w.layout(0, 0, 100, 100)
        event = Event(type=EventType.TOUCH_DOWN, x=200, y=200)
        result = w.on_event(event)
        assert result is False


class TestEdgeInsets:
    def test_all(self):
        ei = EdgeInsets.all(10)
        assert ei.top == ei.right == ei.bottom == ei.left == 10

    def test_symmetric(self):
        ei = EdgeInsets.symmetric(horizontal=20, vertical=10)
        assert ei.left == ei.right == 20
        assert ei.top == ei.bottom == 10

    def test_horizontal_vertical(self):
        ei = EdgeInsets(10, 20, 30, 40)
        assert ei.horizontal == 60  # left + right
        assert ei.vertical == 40   # top + bottom


# --- Container Tests ---

class TestContainer:
    def test_vertical_layout(self):
        c = Container(direction=Direction.VERTICAL)
        c1 = Widget()
        c1.min_height = 30
        c2 = Widget()
        c2.min_height = 40
        c.add_child(c1)
        c.add_child(c2)
        c.layout(0, 0, 100, 200)
        assert c1.y == 0
        assert c2.y == 30

    def test_horizontal_layout(self):
        c = Container(direction=Direction.HORIZONTAL)
        c1 = Widget()
        c1.min_width = 30
        c2 = Widget()
        c2.min_width = 50
        c.add_child(c1)
        c.add_child(c2)
        c.layout(0, 0, 200, 100)
        assert c1.x == 0
        assert c2.x == 30

    def test_gap(self):
        c = Container(direction=Direction.VERTICAL, gap=10)
        c1 = Widget()
        c1.min_height = 20
        c2 = Widget()
        c2.min_height = 20
        c.add_child(c1)
        c.add_child(c2)
        c.layout(0, 0, 100, 200)
        assert c2.y == 30  # 20 + 10 gap

    def test_flex_children(self):
        c = Container(direction=Direction.VERTICAL)
        c1 = Widget()
        c1.flex = 1
        c2 = Widget()
        c2.flex = 1
        c.add_child(c1)
        c.add_child(c2)
        c.layout(0, 0, 100, 200)
        # Each child should get ~100px (200 / 2 flex)
        assert c1.height == 100
        assert c2.height == 100

    def test_cross_align_center(self):
        c = Container(direction=Direction.VERTICAL, cross_align=Align.CENTER)
        child = Widget()
        child.min_width = 40
        child.min_height = 20
        c.add_child(child)
        c.layout(0, 0, 100, 100)
        assert child.x == 30  # (100 - 40) / 2

    def test_measure(self):
        c = Container(direction=Direction.VERTICAL, gap=5)
        c1 = Widget()
        c1.min_width = 80
        c1.min_height = 30
        c2 = Widget()
        c2.min_width = 60
        c2.min_height = 40
        c.add_child(c1)
        c.add_child(c2)
        size = c.measure(200, 200)
        assert size.width == 80  # max child width
        assert size.height == 75  # 30 + 5 + 40


# --- Label Tests ---

class TestLabel:
    def test_create(self):
        lbl = Label("Hello")
        assert lbl.text == "Hello"

    def test_measure(self):
        lbl = Label("Hello")
        size = lbl.measure(500, 500)
        assert size.width > 0
        assert size.height > 0

    def test_draw(self):
        lbl = Label("Hi", color=Colors.WHITE)
        lbl.layout(0, 0, 100, 30)
        buf = bytearray(100 * 30 * 4)
        lbl.draw(buf, 100, 30)
        # Should have some non-zero pixels (the text)
        has_pixel = any(buf[i] > 0 for i in range(0, len(buf), 4))
        assert has_pixel

    def test_align_center(self):
        lbl = Label("A", align=Align.CENTER)
        lbl.layout(0, 0, 200, 30)
        # Just verify it doesn't crash
        buf = bytearray(200 * 30 * 4)
        lbl.draw(buf, 200, 30)

    def test_wrap(self):
        lbl = Label("Hello World This Is A Long Text", wrap=True)
        size = lbl.measure(80, 500)
        # Should need multiple lines
        assert size.height > Typography.BODY_MEDIUM.line_height


# --- Button Tests ---

class TestButton:
    def test_create(self):
        btn = Button("Click Me")
        assert btn.text == "Click Me"

    def test_has_padding(self):
        btn = Button("OK")
        size = btn.measure(300, 100)
        text_w, _ = FontRenderer().measure_text("OK", btn.text_style)
        assert size.width > text_w  # Has padding

    def test_tap_callback(self):
        tapped = []
        btn = Button("Tap", on_tap=lambda: tapped.append(True))
        btn.layout(0, 0, 100, 40)
        btn.on_event(Event(type=EventType.TOUCH_DOWN, x=50, y=20))
        btn.on_event(Event(type=EventType.TOUCH_UP, x=50, y=20))
        assert len(tapped) == 1

    def test_draw(self):
        btn = Button("Go")
        btn.layout(0, 0, 80, 40)
        buf = bytearray(80 * 40 * 4)
        btn.draw(buf, 80, 40)
        # Background should be drawn (primary color)
        has_color = any(buf[i + 2] > 100 for i in range(0, len(buf), 4))
        assert has_color


# --- TextInput Tests ---

class TestTextInput:
    def test_create(self):
        ti = TextInput(placeholder="Type here...")
        assert ti.text == ""
        assert ti.placeholder == "Type here..."

    def test_type_character(self):
        ti = TextInput()
        ti._focused = True
        ti._on_key(30)  # 'a'
        assert ti.text == "a"
        assert ti.cursor_pos == 1

    def test_backspace(self):
        ti = TextInput(text="abc")
        ti._focused = True
        ti._on_key(14)  # Backspace
        assert ti.text == "ab"
        assert ti.cursor_pos == 2

    def test_submit_callback(self):
        submitted = []
        ti = TextInput(text="hello", on_submit=lambda t: submitted.append(t))
        ti._focused = True
        ti._on_key(28)  # Enter
        assert "hello" in submitted

    def test_change_callback(self):
        changes = []
        ti = TextInput(on_change=lambda t: changes.append(t))
        ti._focused = True
        ti._on_key(30)  # 'a'
        assert len(changes) == 1

    def test_focus_on_tap(self):
        ti = TextInput()
        ti.layout(0, 0, 200, 40)
        ti.on_event(Event(type=EventType.TOUCH_DOWN, x=50, y=20))
        assert ti._focused is True


# --- ScrollView Tests ---

class TestScrollView:
    def test_create(self):
        sv = ScrollView()
        assert sv.scroll_y == 0

    def test_scroll_clamps(self):
        sv = ScrollView()
        lbl = Label("A")
        lbl.min_height = 500
        sv.add_child(lbl)
        sv.layout(0, 0, 100, 200)
        assert sv.max_scroll == 500 - 200

    def test_drag_scrolls(self):
        sv = ScrollView()
        child = Widget()
        child.min_height = 500
        sv.add_child(child)
        sv.layout(0, 0, 100, 200)

        sv._handle_event(EventType.TOUCH_DOWN, 50, 100, 0)
        sv._handle_event(EventType.TOUCH_MOVE, 50, 50, 0)
        assert sv.scroll_y > 0


# --- Spacer Tests ---

class TestSpacer:
    def test_has_flex(self):
        sp = Spacer()
        assert sp.flex == 1

    def test_measures_zero(self):
        sp = Spacer()
        size = sp.measure(100, 100)
        assert size.width == 0
        assert size.height == 0

    def test_spacer_in_container(self):
        c = Container(direction=Direction.VERTICAL)
        top = Widget()
        top.min_height = 20
        c.add_child(top)
        c.add_child(Spacer())
        bottom = Widget()
        bottom.min_height = 20
        c.add_child(bottom)
        c.layout(0, 0, 100, 200)
        # Spacer should push bottom to near the end
        assert bottom.y == 180  # 200 - 20


# --- Divider Tests ---

class TestDivider:
    def test_horizontal(self):
        d = Divider(direction=Direction.HORIZONTAL, thickness=2)
        size = d.measure(200, 200)
        assert size.width == 200
        assert size.height == 2

    def test_vertical(self):
        d = Divider(direction=Direction.VERTICAL, thickness=1)
        size = d.measure(200, 200)
        assert size.width == 1
        assert size.height == 200

    def test_draws_line(self):
        d = Divider(color=Color(255, 255, 255))
        d.layout(0, 0, 10, 1)
        buf = bytearray(10 * 2 * 4)
        d.draw(buf, 10, 2)
        # First row should have white pixels
        assert buf[2] == 255  # R channel in BGRA


# --- Pixel Helper Tests ---

class TestPixelHelpers:
    def test_fill_rect(self):
        buf = bytearray(10 * 10 * 4)
        _fill_rect(buf, 10, 10, 2, 2, 3, 3, Color(255, 0, 0))
        offset = (2 * 10 + 2) * 4
        assert buf[offset + 2] == 255  # R

    def test_fill_rect_clips(self):
        buf = bytearray(10 * 10 * 4)
        # Should not crash when drawing outside bounds
        _fill_rect(buf, 10, 10, -5, -5, 20, 20, Color(128, 128, 128))

    def test_draw_border(self):
        buf = bytearray(20 * 20 * 4)
        _draw_border(buf, 20, 20, 2, 2, 16, 16, Color(255, 255, 255), 1)
        # Top-left of border should be white
        offset = (2 * 20 + 2) * 4
        assert buf[offset + 2] == 255
        # Center should be empty
        center = (10 * 20 + 10) * 4
        assert buf[center] == 0


# --- Integration Tests ---

class TestWidgetTree:
    def test_nested_containers(self):
        root = Container(direction=Direction.VERTICAL)
        root.background = Colors.BACKGROUND

        header = Container(direction=Direction.HORIZONTAL)
        header.min_height = 48
        header.add_child(Label("Title", style=Typography.HEADLINE_MEDIUM))
        header.add_child(Spacer())

        body = Container(direction=Direction.VERTICAL, gap=8)
        body.flex = 1
        body.add_child(Label("Body text"))
        body.add_child(Button("Action"))

        root.add_child(header)
        root.add_child(body)

        root.layout(0, 0, 320, 480)

        buf = bytearray(320 * 480 * 4)
        root.draw(buf, 320, 480)

        # Should have drawn something
        has_content = any(buf[i] > 0 for i in range(0, len(buf)))
        assert has_content

    def test_event_propagation(self):
        root = Container(direction=Direction.VERTICAL)
        root.layout(0, 0, 200, 200)

        tapped = []
        btn = Button("Test", on_tap=lambda: tapped.append(True))
        root.add_child(btn)
        root._layout_children()

        # Tap the button area
        event = Event(type=EventType.TOUCH_DOWN, x=30, y=10)
        root.on_event(event)
        event = Event(type=EventType.TOUCH_UP, x=30, y=10)
        root.on_event(event)
        assert len(tapped) == 1

    def test_scrollview_with_content(self):
        sv = ScrollView()
        for i in range(20):
            lbl = Label(f"Item {i}")
            lbl.min_height = 30
            sv.add_child(lbl)
        sv.layout(0, 0, 200, 100)

        buf = bytearray(200 * 100 * 4)
        sv.draw(buf, 200, 100)

        assert sv._content_height == 600  # 20 * 30
        assert sv.max_scroll == 500  # 600 - 100
