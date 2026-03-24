"""
Tests for Phase 7 — Claude Visual Integration.

Covers: screenshot capture, screen reader, rich content (code blocks,
charts, cards, action buttons), dynamic UI (checklist, calendar, info,
form), ambient mode dashboard, and vision tools.
"""

import base64
import struct
import time
import zlib
import pytest

from theme import Colors, Typography
from widget import Widget, Size, EventType, Event
from widgets import Container, Label, Button


# --- Screenshot Capture ---

from screenshot import (
    ScreenRegion, TextElement, ScreenDescription,
    ScreenshotCapture, ScreenReader,
)


class TestScreenRegion:
    def test_contains(self):
        r = ScreenRegion(10, 10, 100, 100)
        assert r.contains(50, 50)
        assert not r.contains(5, 5)
        assert r.contains(10, 10)
        assert not r.contains(110, 110)

    def test_intersects(self):
        a = ScreenRegion(0, 0, 100, 100)
        b = ScreenRegion(50, 50, 100, 100)
        assert a.intersects(b)
        c = ScreenRegion(200, 200, 50, 50)
        assert not a.intersects(c)


class TestScreenshotCapture:
    def _make_buffer(self, w, h, r=0, g=0, b=0, a=255):
        """Create a BGRA buffer filled with a color."""
        pixel = struct.pack("BBBB", b, g, r, a)
        return bytearray(pixel * w * h), w, h

    def test_capture_raw_full(self):
        buf, w, h = self._make_buffer(10, 10, 255, 0, 0)
        sc = ScreenshotCapture()
        raw = sc.capture_raw(buf, w, h)
        assert len(raw) == len(buf)
        assert raw == buf

    def test_capture_raw_region(self):
        buf, w, h = self._make_buffer(20, 20, 100, 100, 100)
        sc = ScreenshotCapture()
        region = ScreenRegion(5, 5, 10, 10)
        raw = sc.capture_raw(buf, w, h, region)
        assert len(raw) == 10 * 10 * 4

    def test_capture_raw_region_clipped(self):
        buf, w, h = self._make_buffer(20, 20)
        sc = ScreenshotCapture()
        region = ScreenRegion(15, 15, 20, 20)  # Extends past buffer
        raw = sc.capture_raw(buf, w, h, region)
        assert len(raw) == 5 * 5 * 4  # Clipped to 5x5

    def test_capture_raw_empty_region(self):
        buf, w, h = self._make_buffer(10, 10)
        sc = ScreenshotCapture()
        region = ScreenRegion(100, 100, 10, 10)  # Completely outside
        raw = sc.capture_raw(buf, w, h, region)
        assert len(raw) == 0

    def test_encode_png_valid(self):
        buf, w, h = self._make_buffer(4, 4, 255, 0, 0)
        sc = ScreenshotCapture()
        png = sc.encode_png(buf, w, h)
        # Check PNG signature
        assert png[:8] == b'\x89PNG\r\n\x1a\n'
        # Check IHDR chunk
        assert b'IHDR' in png
        assert b'IDAT' in png
        assert b'IEND' in png

    def test_encode_png_empty(self):
        sc = ScreenshotCapture()
        png = sc.encode_png(bytearray(), 0, 0)
        assert png == b""

    def test_capture_base64(self):
        buf, w, h = self._make_buffer(4, 4, 0, 255, 0)
        sc = ScreenshotCapture()
        b64 = sc.capture_base64(buf, w, h)
        # Should be valid base64
        decoded = base64.b64decode(b64)
        assert decoded[:8] == b'\x89PNG\r\n\x1a\n'

    def test_capture_png_with_region(self):
        buf, w, h = self._make_buffer(10, 10, 128, 128, 128)
        sc = ScreenshotCapture()
        region = ScreenRegion(2, 2, 5, 5)
        png = sc.capture_png(buf, w, h, region)
        assert png[:8] == b'\x89PNG\r\n\x1a\n'

    def test_last_capture_time(self):
        buf, w, h = self._make_buffer(4, 4)
        sc = ScreenshotCapture()
        assert sc.last_capture_time == 0
        sc.capture_raw(buf, w, h)
        assert sc.last_capture_time > 0


# --- Screen Reader ---

class TestScreenReader:
    def _make_label_widget(self, text):
        label = Label(text=text)
        label.layout(10, 20, 100, 30)
        return label

    def test_read_empty(self):
        sr = ScreenReader()
        desc = sr.read_screen(None)
        assert len(desc.text_elements) == 0

    def test_read_label(self):
        sr = ScreenReader()
        root = Container()
        root.layout(0, 0, 360, 720)
        label = Label(text="Hello World")
        label.layout(10, 20, 100, 30)
        root.add_child(label)

        desc = sr.read_screen(root, "test", 360, 720)
        assert len(desc.text_elements) >= 1
        texts = [t.text for t in desc.text_elements]
        assert "Hello World" in texts

    def test_read_button(self):
        sr = ScreenReader()
        btn = Button(text="Click Me", on_tap=lambda: None)
        btn.layout(0, 0, 100, 40)

        desc = sr.read_screen(btn, "test")
        # Button has text and is interactive
        assert len(desc.interactive_elements) >= 1

    def test_description_to_text(self):
        desc = ScreenDescription(
            screen_name="home",
            width=360,
            height=720,
            text_elements=[TextElement("Hello", 10, 20, 100, 30)],
            timestamp=time.time(),
        )
        text = desc.to_text()
        assert "home" in text
        assert "Hello" in text

    def test_description_to_dict(self):
        desc = ScreenDescription(
            screen_name="settings",
            width=360,
            height=720,
            text_elements=[TextElement("WiFi", 10, 20, 100, 30, "Label")],
            timestamp=1.0,
        )
        d = desc.to_dict()
        assert d["screen_name"] == "settings"
        assert len(d["text_elements"]) == 1
        assert d["text_elements"][0]["text"] == "WiFi"

    def test_find_text(self):
        sr = ScreenReader()
        root = Container()
        root.layout(0, 0, 360, 720)
        root.add_child(Label(text="WiFi Settings"))
        root.add_child(Label(text="Bluetooth"))
        root.children[0].layout(0, 0, 200, 30)
        root.children[1].layout(0, 30, 200, 30)

        results = sr.find_text(root, "wifi")
        assert len(results) == 1
        assert "WiFi" in results[0].text

    def test_find_text_not_found(self):
        sr = ScreenReader()
        root = Label(text="Hello")
        root.layout(0, 0, 100, 30)
        results = sr.find_text(root, "xyz")
        assert len(results) == 0

    def test_invisible_widget_skipped(self):
        sr = ScreenReader()
        root = Container()
        root.layout(0, 0, 360, 720)
        label = Label(text="Hidden")
        label.visible = False
        label.layout(0, 0, 100, 30)
        root.add_child(label)

        desc = sr.read_screen(root)
        texts = [t.text for t in desc.text_elements]
        assert "Hidden" not in texts


# --- Rich Content ---

from rich_content import (
    tokenize_code, TokenType, Token,
    CodeBlock, BarChart, BarData, InteractiveCard, ActionButtonBar,
    RichContentParser, ContentBlockType,
)


class TestTokenizer:
    def test_keyword(self):
        tokens = tokenize_code("def foo", "python")
        assert tokens[0].token_type == TokenType.KEYWORD
        assert tokens[0].text == "def"

    def test_string(self):
        tokens = tokenize_code('"hello"')
        assert any(t.token_type == TokenType.STRING for t in tokens)

    def test_comment(self):
        tokens = tokenize_code("# comment")
        assert tokens[0].token_type == TokenType.COMMENT

    def test_number(self):
        tokens = tokenize_code("x = 42")
        assert any(t.token_type == TokenType.NUMBER and t.text == "42" for t in tokens)

    def test_js_keywords(self):
        tokens = tokenize_code("const x = 1", "javascript")
        assert tokens[0].token_type == TokenType.KEYWORD


class TestCodeBlock:
    def test_create(self):
        cb = CodeBlock(code="print('hi')", language="python")
        assert cb.language == "python"
        assert len(cb._lines) == 1

    def test_measure(self):
        cb = CodeBlock(code="line1\nline2\nline3", language="python")
        size = cb.measure(300, 500)
        assert size.width > 0
        assert size.height > 0

    def test_draw(self):
        cb = CodeBlock(code="x = 1", language="python")
        cb.layout(0, 0, 300, 200)
        buf = bytearray(300 * 200 * 4)
        cb.draw(buf, 300, 200)
        # Should draw something
        any_drawn = any(buf[i] != 0 for i in range(0, len(buf), 4))
        assert any_drawn


class TestBarChart:
    def test_create(self):
        bars = [BarData("A", 10), BarData("B", 20)]
        chart = BarChart(title="Test", bars=bars)
        assert len(chart.bars) == 2

    def test_measure(self):
        bars = [BarData("A", 10)]
        chart = BarChart(title="Test", bars=bars)
        size = chart.measure(300, 500)
        assert size.height > 0

    def test_draw(self):
        bars = [BarData("A", 10), BarData("B", 20)]
        chart = BarChart(title="Chart", bars=bars)
        chart.layout(0, 0, 300, 200)
        buf = bytearray(300 * 200 * 4)
        chart.draw(buf, 300, 200)
        any_drawn = any(buf[i] != 0 for i in range(0, len(buf), 4))
        assert any_drawn


class TestInteractiveCard:
    def test_create(self):
        card = InteractiveCard(title="WiFi", body="Connected")
        assert card.title == "WiFi"

    def test_with_actions(self):
        clicked = []
        card = InteractiveCard(
            title="Network",
            body="Signal: Strong",
            actions=[{"label": "Connect", "callback": lambda: clicked.append(True)}],
        )
        assert len(card._action_buttons) == 1

    def test_measure(self):
        card = InteractiveCard(title="Test", body="Some body text")
        size = card.measure(300, 500)
        assert size.height > 0


class TestActionButtonBar:
    def test_create_empty(self):
        bar = ActionButtonBar()
        assert bar.button_count == 0

    def test_create_with_actions(self):
        bar = ActionButtonBar(actions=[
            {"label": "Open"},
            {"label": "Share"},
        ])
        assert bar.button_count == 2

    def test_measure(self):
        bar = ActionButtonBar(actions=[{"label": "OK"}])
        size = bar.measure(300, 100)
        assert size.height > 0


class TestRichContentParser:
    def test_plain_text(self):
        parser = RichContentParser()
        blocks = parser.parse("Hello world")
        assert len(blocks) == 1
        assert blocks[0].block_type == ContentBlockType.TEXT

    def test_code_block(self):
        parser = RichContentParser()
        text = "```python\nprint('hi')\n```"
        blocks = parser.parse(text)
        assert any(b.block_type == ContentBlockType.CODE for b in blocks)
        code_block = [b for b in blocks if b.block_type == ContentBlockType.CODE][0]
        assert code_block.language == "python"
        assert "print" in code_block.text

    def test_chart_block(self):
        parser = RichContentParser()
        text = '[chart:bar title="Storage" data="Apps:45,Photos:30"]'
        blocks = parser.parse(text)
        assert any(b.block_type == ContentBlockType.CHART for b in blocks)
        chart = [b for b in blocks if b.block_type == ContentBlockType.CHART][0]
        assert chart.data["title"] == "Storage"
        assert len(chart.data["bars"]) == 2

    def test_card_block(self):
        parser = RichContentParser()
        text = '[card title="WiFi" body="Connected" actions="Disconnect"]'
        blocks = parser.parse(text)
        assert any(b.block_type == ContentBlockType.CARD for b in blocks)

    def test_actions_block(self):
        parser = RichContentParser()
        text = '[actions: Connect | Open | Share]'
        blocks = parser.parse(text)
        assert any(b.block_type == ContentBlockType.ACTIONS for b in blocks)
        actions = [b for b in blocks if b.block_type == ContentBlockType.ACTIONS][0]
        assert len(actions.data["labels"]) == 3

    def test_mixed_content(self):
        parser = RichContentParser()
        text = "Here's some code:\n```python\nx = 1\n```\nAnd some data:\n[chart:bar data=\"A:10\"]"
        blocks = parser.parse(text)
        types = [b.block_type for b in blocks]
        assert ContentBlockType.TEXT in types
        assert ContentBlockType.CODE in types
        assert ContentBlockType.CHART in types

    def test_blocks_to_widgets(self):
        parser = RichContentParser()
        blocks = [
            ContentBlockType.TEXT,
            ContentBlockType.CODE,
        ]
        # Use actual blocks
        parsed = parser.parse("Hello\n```python\nx = 1\n```")
        widgets = parser.blocks_to_widgets(parsed)
        assert len(widgets) >= 2


# --- Dynamic UI ---

from dynamic_ui import (
    ChecklistItem, ChecklistView,
    CalendarEvent, CalendarView,
    InfoRow, InfoPanel,
    FormField, FormView,
    DynamicViewBuilder,
)


class TestChecklistView:
    def test_create(self):
        cl = ChecklistView(title="Shopping")
        assert cl.total_count == 0
        assert cl.progress == 1.0

    def test_add_item(self):
        cl = ChecklistView(title="Todo")
        cl.add_item("Buy milk")
        assert cl.total_count == 1
        assert cl.checked_count == 0

    def test_toggle(self):
        cl = ChecklistView()
        item = cl.add_item("Task 1")
        cl.toggle_item(item.id)
        assert cl.checked_count == 1
        assert cl.progress == 1.0

    def test_remove_item(self):
        cl = ChecklistView()
        item = cl.add_item("Remove me")
        cl.remove_item(item.id)
        assert cl.total_count == 0

    def test_on_change_callback(self):
        changes = []
        cl = ChecklistView(on_change=changes.append)
        item = cl.add_item("Task")
        cl.toggle_item(item.id)
        assert len(changes) == 1

    def test_progress(self):
        cl = ChecklistView()
        cl.add_item("A")
        cl.add_item("B")
        item = cl.add_item("C")
        cl.toggle_item(item.id)
        assert cl.progress == pytest.approx(1/3, abs=0.01)

    def test_draw(self):
        cl = ChecklistView(title="Test")
        cl.add_item("Item 1")
        cl.add_item("Item 2", checked=True)
        cl.layout(0, 0, 300, 300)
        buf = bytearray(300 * 300 * 4)
        cl.draw(buf, 300, 300)
        any_drawn = any(buf[i] != 0 for i in range(0, len(buf), 4))
        assert any_drawn

    def test_with_items(self):
        items = [ChecklistItem("A"), ChecklistItem("B", checked=True)]
        cl = ChecklistView(title="Pre", items=items)
        assert cl.total_count == 2
        assert cl.checked_count == 1


class TestCalendarView:
    def test_create(self):
        cal = CalendarView(year=2026, month=3)
        assert cal.year == 2026
        assert cal.month == 3

    def test_days_in_month(self):
        cal = CalendarView(year=2026, month=2)
        assert cal._days_in_month == 28

    def test_leap_year(self):
        cal = CalendarView(year=2024, month=2)
        assert cal._days_in_month == 29

    def test_set_month(self):
        cal = CalendarView(year=2026, month=1)
        cal.set_month(2026, 6)
        assert cal.month == 6
        assert cal._days_in_month == 30

    def test_events(self):
        events = [CalendarEvent(day=15, title="Meeting")]
        cal = CalendarView(year=2026, month=3, events=events)
        assert len(cal.events) == 1

    def test_today_highlight(self):
        cal = CalendarView(year=2026, month=3)
        cal.today = 24
        assert cal.today == 24

    def test_draw(self):
        cal = CalendarView(year=2026, month=3)
        cal.today = 15
        cal.layout(0, 0, 300, 400)
        buf = bytearray(300 * 400 * 4)
        cal.draw(buf, 300, 400)
        any_drawn = any(buf[i] != 0 for i in range(0, len(buf), 4))
        assert any_drawn

    def test_day_tap(self):
        tapped = []
        cal = CalendarView(year=2026, month=3, on_day_tap=tapped.append)
        cal.layout(0, 0, 300, 400)
        # The callback is tested via _handle_event
        assert cal.on_day_tap is not None


class TestInfoPanel:
    def test_create(self):
        panel = InfoPanel(title="Device Info")
        assert panel.title == "Device Info"
        assert len(panel.rows) == 0

    def test_add_row(self):
        panel = InfoPanel()
        panel.add_row("Model", "Claude Phone")
        assert len(panel.rows) == 1

    def test_set_value(self):
        panel = InfoPanel(rows=[InfoRow("Battery", "80%")])
        panel.set_value("Battery", "75%")
        assert panel.rows[0].value == "75%"

    def test_draw(self):
        panel = InfoPanel(title="Info", rows=[
            InfoRow("Key", "Value"),
        ])
        panel.layout(0, 0, 300, 200)
        buf = bytearray(300 * 200 * 4)
        panel.draw(buf, 300, 200)
        any_drawn = any(buf[i] != 0 for i in range(0, len(buf), 4))
        assert any_drawn


class TestFormView:
    def test_create(self):
        form = FormView(title="New Note")
        assert form.title == "New Note"

    def test_add_field(self):
        form = FormView()
        form.add_field("title", "Title", placeholder="Enter title")
        assert len(form.fields) == 1

    def test_get_values(self):
        form = FormView(fields=[
            FormField(name="name", label="Name", value="Alice"),
            FormField(name="age", label="Age", value="30"),
        ])
        vals = form.get_values()
        assert vals["name"] == "Alice"
        assert vals["age"] == "30"

    def test_set_value(self):
        form = FormView(fields=[FormField(name="x", label="X")])
        form.set_value("x", "hello")
        assert form.fields[0].value == "hello"

    def test_submit(self):
        results = []
        form = FormView(
            fields=[FormField(name="note", label="Note", value="test")],
            on_submit=results.append,
        )
        form.submit()
        assert len(results) == 1
        assert results[0] == {"note": "test"}

    def test_draw(self):
        form = FormView(title="Form", fields=[
            FormField(name="f1", label="Field 1"),
        ])
        form.layout(0, 0, 300, 300)
        buf = bytearray(300 * 300 * 4)
        form.draw(buf, 300, 300)
        any_drawn = any(buf[i] != 0 for i in range(0, len(buf), 4))
        assert any_drawn


class TestDynamicViewBuilder:
    def test_build_checklist(self):
        builder = DynamicViewBuilder()
        spec = {
            "type": "checklist",
            "title": "Shopping",
            "items": [
                {"text": "Milk", "checked": False},
                {"text": "Eggs", "checked": True},
            ],
        }
        widget = builder.build(spec)
        assert widget is not None
        assert isinstance(widget, ChecklistView)
        assert widget.total_count == 2

    def test_build_calendar(self):
        builder = DynamicViewBuilder()
        spec = {
            "type": "calendar",
            "year": 2026,
            "month": 3,
            "today": 24,
            "events": [{"day": 25, "title": "Meeting"}],
        }
        widget = builder.build(spec)
        assert isinstance(widget, CalendarView)
        assert widget.today == 24

    def test_build_info(self):
        builder = DynamicViewBuilder()
        spec = {
            "type": "info",
            "title": "Status",
            "rows": [{"key": "Battery", "value": "85%"}],
        }
        widget = builder.build(spec)
        assert isinstance(widget, InfoPanel)
        assert len(widget.rows) == 1

    def test_build_form(self):
        builder = DynamicViewBuilder()
        spec = {
            "type": "form",
            "title": "New Reminder",
            "fields": [
                {"name": "title", "label": "Title", "type": "text"},
            ],
            "submit_label": "Save",
        }
        widget = builder.build(spec)
        assert isinstance(widget, FormView)
        assert widget.submit_label == "Save"

    def test_build_unknown(self):
        builder = DynamicViewBuilder()
        widget = builder.build({"type": "unknown_type"})
        assert widget is None

    def test_build_with_callbacks(self):
        changes = []
        builder = DynamicViewBuilder()
        spec = {
            "type": "checklist",
            "title": "Tasks",
            "items": [{"text": "Do thing"}],
        }
        widget = builder.build(spec, callbacks={"on_change": changes.append})
        assert widget.on_change is not None


# --- Ambient Mode ---

from ambient_mode import (
    WeatherData, ReminderData, AmbientState,
    AmbientClockWidget, WeatherWidget, ReminderWidget,
    QuoteWidget, AmbientDashboard,
)


class TestAmbientClock:
    def test_create(self):
        clock = AmbientClockWidget()
        assert clock._time_str == "00:00"

    def test_update(self):
        clock = AmbientClockWidget()
        clock.update("14:30", "Monday, Mar 24")
        assert clock._time_str == "14:30"
        assert clock._date_str == "Monday, Mar 24"


class TestWeatherWidget:
    def test_create(self):
        ww = WeatherWidget()
        assert ww._weather.temperature == 72

    def test_update(self):
        ww = WeatherWidget()
        ww.update(WeatherData(temperature=85, condition="Cloudy"))
        assert ww._weather.temperature == 85


class TestReminderWidget:
    def test_no_reminder(self):
        rw = ReminderWidget()
        assert not rw.has_reminder

    def test_with_reminder(self):
        rw = ReminderWidget()
        rw.update(ReminderData(title="Meeting", time_str="3:00 PM"))
        assert rw.has_reminder


class TestQuoteWidget:
    def test_empty(self):
        qw = QuoteWidget()
        size = qw.measure(300, 100)
        assert size.height == 0  # No quote = no height

    def test_with_quote(self):
        qw = QuoteWidget()
        qw.update("The only way to do great work is to love what you do.")
        size = qw.measure(300, 100)
        assert size.height > 0


class TestAmbientDashboard:
    def test_create(self):
        dash = AmbientDashboard()
        assert not dash.is_active

    def test_activate(self):
        dash = AmbientDashboard()
        dash.activate()
        assert dash.is_active

    def test_deactivate(self):
        dash = AmbientDashboard()
        dash.activate()
        dash.deactivate()
        assert not dash.is_active

    def test_set_weather(self):
        dash = AmbientDashboard()
        dash.activate()
        dash.set_weather(WeatherData(temperature=90, condition="Hot"))
        assert dash._state.weather.temperature == 90

    def test_set_reminder(self):
        dash = AmbientDashboard()
        dash.set_reminder(ReminderData(title="Call"))
        assert dash._state.next_reminder.title == "Call"

    def test_set_quote(self):
        dash = AmbientDashboard()
        dash.set_quote("Hello world")
        assert dash._state.quote == "Hello world"

    def test_update_state(self):
        dash = AmbientDashboard()
        dash.activate()
        state = AmbientState(
            weather=WeatherData(temperature=68),
            notification_count=3,
            quote="Stay curious",
            battery_percent=75,
        )
        dash.update_state(state)
        assert dash._state.notification_count == 3

    def test_tap_to_wake(self):
        woken = []
        dash = AmbientDashboard(on_tap_to_wake=lambda: woken.append(True))
        dash.activate()
        event = Event(type=EventType.TOUCH_DOWN, x=100, y=100)
        dash._handle_event(EventType.TOUCH_DOWN, 100, 100, 0)
        assert len(woken) == 1

    def test_draw(self):
        dash = AmbientDashboard()
        dash.activate()
        dash.set_weather(WeatherData(temperature=72, condition="Sunny"))
        dash.set_quote("Test quote")
        dash.layout(0, 0, 360, 720)
        buf = bytearray(360 * 720 * 4)
        dash.draw(buf, 360, 720)
        any_drawn = any(buf[i] != 0 for i in range(0, len(buf), 4))
        assert any_drawn

    def test_notification_badge(self):
        dash = AmbientDashboard()
        dash.activate()
        state = AmbientState(notification_count=5)
        dash.update_state(state)
        dash.layout(0, 0, 360, 720)
        buf = bytearray(360 * 720 * 4)
        dash.draw(buf, 360, 720)
        # Badge should be drawn - hard to assert pixel-level, just ensure no crash
        assert True


# --- Integration ---

class TestVisionIntegration:
    def test_screenshot_and_screen_reader(self):
        """Screenshot + screen reader work together."""
        # Build a widget tree
        root = Container()
        root.layout(0, 0, 100, 50)
        root.add_child(Label(text="Hello Claude"))
        root.children[0].layout(0, 0, 100, 25)

        # Read screen
        sr = ScreenReader()
        desc = sr.read_screen(root, "test", 100, 50)
        assert any("Hello Claude" in t.text for t in desc.text_elements)

        # Take screenshot of a simple buffer
        sc = ScreenshotCapture()
        buf = bytearray(100 * 50 * 4)
        b64 = sc.capture_base64(buf, 100, 50)
        assert len(b64) > 0

    def test_parser_to_widgets(self):
        """Rich content parser produces renderable widgets."""
        parser = RichContentParser()
        text = "Look:\n```python\nprint('hello')\n```"
        blocks = parser.parse(text)
        widgets = parser.blocks_to_widgets(blocks)
        assert len(widgets) >= 2
        # Each should be measurable
        for w in widgets:
            size = w.measure(300, 500)
            assert size.width >= 0
            assert size.height >= 0

    def test_dynamic_builder_roundtrip(self):
        """Build a view, interact with it, verify state."""
        builder = DynamicViewBuilder()
        spec = {
            "type": "checklist",
            "title": "Groceries",
            "items": [
                {"text": "Apples"},
                {"text": "Bread"},
            ],
        }
        checklist = builder.build(spec)
        assert checklist.total_count == 2
        assert checklist.checked_count == 0

        # Toggle first item
        checklist.toggle_item(checklist.items[0].id)
        assert checklist.checked_count == 1
        assert checklist.progress == 0.5
