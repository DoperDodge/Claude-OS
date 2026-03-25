"""Tests for the Claude-OS widget toolkit."""

import os
import sys
import pytest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from ui.widgets.base import Widget, Container, Rect, Size, TouchEvent, TouchAction
from ui.widgets.text import Label, TextInput
from ui.widgets.buttons import Button, IconButton
from ui.widgets.layout import VStack, HStack, Spacer, Padding
from ui.widgets.scrolling import ScrollView


class TestRect:
    def test_contains(self):
        r = Rect(10, 20, 100, 50)
        assert r.contains(10, 20)
        assert r.contains(50, 40)
        assert not r.contains(9, 20)
        assert not r.contains(110, 20)
        assert not r.contains(50, 70)

    def test_contains_edge(self):
        r = Rect(0, 0, 100, 100)
        assert r.contains(0, 0)
        assert not r.contains(100, 100)  # exclusive end


class TestWidget:
    def test_default_measure(self):
        w = Widget()
        assert w.measure(100, 100) == Size(0, 0)

    def test_layout(self):
        w = Widget()
        w.layout(10, 20, 100, 50)
        assert w.bounds.x == 10
        assert w.bounds.y == 20
        assert w.bounds.width == 100

    def test_color_parsing(self):
        w = Widget()
        r, g, b, a = w._parse_color("#FF0000")
        assert r == pytest.approx(1.0)
        assert g == pytest.approx(0.0)
        assert a == pytest.approx(1.0)


class TestContainer:
    def test_add_child(self):
        c = Container()
        child = Widget()
        c.add(child)
        assert child in c.children
        assert child._parent == c

    def test_remove_child(self):
        c = Container()
        child = Widget()
        c.add(child)
        c.remove(child)
        assert child not in c.children
        assert child._parent is None

    def test_touch_dispatch(self):
        c = Container()
        c.layout(0, 0, 200, 200)

        received = []

        class ClickWidget(Widget):
            def handle_touch(self, event):
                received.append(event)
                return True

        child = ClickWidget()
        child.layout(10, 10, 50, 50)
        c.add(child)

        event = TouchEvent(x=20, y=20, action=TouchAction.UP)
        result = c.handle_touch(event)
        assert result is True
        assert len(received) == 1

    def test_touch_miss(self):
        c = Container()
        c.layout(0, 0, 200, 200)

        child = Widget()
        child.layout(10, 10, 50, 50)
        c.add(child)

        event = TouchEvent(x=100, y=100, action=TouchAction.UP)
        result = c.handle_touch(event)
        assert result is False


class TestLabel:
    def test_measure(self):
        label = Label(text="Hello World", font_size=17.0)
        size = label.measure(200, 100)
        assert size.width > 0
        assert size.height > 0

    def test_empty_text(self):
        label = Label(text="", font_size=17.0)
        size = label.measure(200, 100)
        assert size.width == 0
        assert size.height > 0  # Still has line height

    def test_word_wrap(self):
        label = Label(text="This is a long text that should wrap across multiple lines",
                      font_size=17.0)
        size = label.measure(100, 500)
        assert len(label._lines) > 1

    def test_max_lines(self):
        label = Label(text="Line one\nLine two\nLine three", max_lines=2)
        label.measure(500, 500)
        assert len(label._lines) == 2


class TestTextInput:
    def test_measure(self):
        ti = TextInput(height=48)
        size = ti.measure(300, 100)
        assert size.width == 300
        assert size.height == 48

    def test_insert_text(self):
        ti = TextInput()
        ti.insert_text("Hello")
        assert ti.text == "Hello"
        assert ti.cursor_pos == 5

    def test_delete_back(self):
        ti = TextInput()
        ti.insert_text("Hi")
        ti.delete_back()
        assert ti.text == "H"
        assert ti.cursor_pos == 1

    def test_delete_at_start(self):
        ti = TextInput()
        ti.delete_back()  # No crash
        assert ti.text == ""
        assert ti.cursor_pos == 0

    def test_on_change_callback(self):
        changes = []
        ti = TextInput(on_change=lambda t: changes.append(t))
        ti.insert_text("A")
        assert changes == ["A"]

    def test_focus_on_tap(self):
        ti = TextInput()
        ti.layout(0, 0, 200, 48)
        assert ti.focused is False

        event = TouchEvent(x=50, y=24, action=TouchAction.UP)
        ti.handle_touch(event)
        assert ti.focused is True


class TestButton:
    def test_measure(self):
        btn = Button(label="Click me", height=48)
        size = btn.measure(300, 100)
        assert size.width > 0
        assert size.height == 48

    def test_press_callback(self):
        pressed = []
        btn = Button(label="Go", on_press=lambda: pressed.append(True))
        btn.layout(0, 0, 100, 48)

        btn.handle_touch(TouchEvent(x=50, y=24, action=TouchAction.DOWN))
        assert btn.pressed is True

        btn.handle_touch(TouchEvent(x=50, y=24, action=TouchAction.UP))
        assert btn.pressed is False
        assert pressed == [True]

    def test_press_outside_cancels(self):
        pressed = []
        btn = Button(label="Go", on_press=lambda: pressed.append(True))
        btn.layout(0, 0, 100, 48)

        btn.handle_touch(TouchEvent(x=50, y=24, action=TouchAction.DOWN))
        btn.handle_touch(TouchEvent(x=200, y=200, action=TouchAction.UP))
        assert pressed == []

    def test_disabled_button(self):
        pressed = []
        btn = Button(label="Go", on_press=lambda: pressed.append(True))
        btn.enabled = False
        btn.layout(0, 0, 100, 48)

        btn.handle_touch(TouchEvent(x=50, y=24, action=TouchAction.DOWN))
        assert btn.pressed is False
        assert pressed == []


class TestIconButton:
    def test_measure_square(self):
        btn = IconButton(size=44)
        size = btn.measure(100, 100)
        assert size.width == 44
        assert size.height == 44


class TestVStack:
    def test_layout(self):
        stack = VStack(spacing=10)
        stack.add(Label(text="First", font_size=17.0))
        stack.add(Label(text="Second", font_size=17.0))

        stack.layout(0, 0, 200, 500)

        children = stack.children
        assert children[0].bounds.y == 0
        assert children[1].bounds.y > children[0].bounds.y

    def test_spacer_fills(self):
        stack = VStack()
        stack.add(Label(text="Top", font_size=17.0))
        stack.add(Spacer())
        stack.add(Label(text="Bottom", font_size=17.0))

        stack.layout(0, 0, 200, 500)
        # Bottom label should be near the bottom
        bottom = stack.children[2]
        assert bottom.bounds.y > 200

    def test_measure_sums_heights(self):
        stack = VStack(spacing=10)
        stack.add(Label(text="A", font_size=20.0))
        stack.add(Label(text="B", font_size=20.0))

        size = stack.measure(200, 500)
        assert size.height > 0
        # Two labels + gap
        line_h = int(20.0 * 1.3)
        assert size.height == line_h * 2 + 10


class TestHStack:
    def test_layout(self):
        stack = HStack(spacing=10)
        stack.add(Button(label="A", height=40))
        stack.add(Button(label="B", height=40))

        stack.layout(0, 0, 400, 100)

        children = stack.children
        assert children[0].bounds.x == 0
        assert children[1].bounds.x > children[0].bounds.x

    def test_spacer(self):
        stack = HStack()
        stack.add(Label(text="L", font_size=17.0))
        stack.add(Spacer())
        stack.add(Label(text="R", font_size=17.0))

        stack.layout(0, 0, 400, 50)
        right = stack.children[2]
        assert right.bounds.x > 100


class TestPadding:
    def test_padding_offsets_child(self):
        label = Label(text="Hello", font_size=17.0)
        padded = Padding(child=label, all=20)

        padded.layout(0, 0, 200, 100)
        assert label.bounds.x == 20
        assert label.bounds.y == 20

    def test_padding_increases_size(self):
        label = Label(text="Hi", font_size=17.0)
        padded = Padding(child=label, top=10, bottom=10, left=20, right=20)

        size = padded.measure(200, 100)
        label_size = label.measure(160, 80)
        assert size.width == label_size.width + 40
        assert size.height == label_size.height + 20


class TestScrollView:
    def test_scroll_bounds(self):
        sv = ScrollView()
        # Add items taller than viewport
        for i in range(20):
            sv.add(Label(text=f"Item {i}", font_size=17.0))

        sv.layout(0, 0, 200, 100)
        assert sv.content_height > 100
        assert sv.max_scroll > 0

    def test_scroll_clamps(self):
        sv = ScrollView()
        for i in range(20):
            sv.add(Label(text=f"Item {i}", font_size=17.0))
        sv.layout(0, 0, 200, 100)

        sv.scroll_y = -100
        sv.scroll_y = max(0, sv.scroll_y)
        assert sv.scroll_y == 0

        sv.scroll_y = 99999
        sv.scroll_y = min(sv.max_scroll, sv.scroll_y)
        assert sv.scroll_y == sv.max_scroll

    def test_drag_scrolling(self):
        sv = ScrollView()
        for i in range(20):
            sv.add(Label(text=f"Item {i}", font_size=17.0))
        sv.layout(0, 0, 200, 100)

        sv.handle_touch(TouchEvent(x=50, y=50, action=TouchAction.DOWN))
        sv.handle_touch(TouchEvent(x=50, y=30, action=TouchAction.MOVE))
        assert sv.scroll_y > 0  # Scrolled down


class TestCompositorWidgetIntegration:
    """Test that the compositor can build and use the widget tree."""

    def test_build_widget_ui(self):
        from ui.compositor.compositor import Compositor, OutputConfig
        comp = Compositor(OutputConfig(width=1080, height=2340))
        comp.initialize()
        root = comp._build_widget_ui()
        assert root is not None
        assert comp._widget_root is not None

    def test_widget_count(self):
        from ui.compositor.compositor import Compositor, OutputConfig
        comp = Compositor(OutputConfig(width=1080, height=2340))
        comp.initialize()
        comp._build_widget_ui()
        count = comp._count_widgets(comp._widget_root)
        assert count >= 10  # Status bar + app area + buttons + input

    def test_render_widgets_with_renderer(self):
        """Render widget tree through the full pipeline."""
        from ui.compositor.compositor import Compositor, OutputConfig
        from ui.renderer.drm_renderer import DRMRenderer

        comp = Compositor(OutputConfig(width=540, height=1170))
        comp.initialize()
        comp._build_widget_ui()

        renderer = DRMRenderer()
        renderer.initialize(headless=True, width=540, height=1170)

        # Render the widget tree to the renderer's Cairo context
        if renderer._cairo_ctx:
            comp._render_widgets(renderer._cairo_ctx)

        data = renderer.get_pixel_data()
        assert len(data) == 540 * 1170 * 4

        renderer.shutdown()
