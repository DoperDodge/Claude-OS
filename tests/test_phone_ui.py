"""
Tests for Phase 4 — Phone UI Shell.

Covers: lock screen, status bar, keyboard, home screen (chat),
notification panel, and app drawer.
"""

import time
import pytest
from theme import Colors, Typography
from widget import Widget, Event, EventType, Align, Direction

# --- 4a: Lock Screen ---

from lock_screen import LockScreen, LockScreenNotification


class TestLockScreen:
    def test_create(self):
        ls = LockScreen()
        assert ls.is_locked is True

    def test_update_time(self):
        ls = LockScreen()
        ls.update_time("14:30", "Tuesday, March 23")
        assert ls._time_str == "14:30"
        assert ls._date_str == "Tuesday, March 23"

    def test_swipe_to_unlock_no_pin(self):
        unlocked = []
        ls = LockScreen(on_unlock=lambda: unlocked.append(True))
        ls.layout(0, 0, 320, 480)

        # Simulate swipe up
        ls._handle_event(EventType.TOUCH_DOWN, 160, 400, 0)
        ls._handle_event(EventType.TOUCH_MOVE, 160, 200, 0)
        ls._handle_event(EventType.TOUCH_UP, 160, 200, 0)

        assert ls.is_locked is False
        assert len(unlocked) == 1

    def test_swipe_too_short_stays_locked(self):
        ls = LockScreen()
        ls.layout(0, 0, 320, 480)

        ls._handle_event(EventType.TOUCH_DOWN, 160, 400, 0)
        ls._handle_event(EventType.TOUCH_UP, 160, 380, 0)

        assert ls.is_locked is True

    def test_pin_required(self):
        ls = LockScreen(pin_required=True)
        ls.set_pin("1234")
        ls.layout(0, 0, 320, 480)

        # Swipe up should show PIN screen, not unlock
        ls._handle_event(EventType.TOUCH_DOWN, 160, 400, 0)
        ls._handle_event(EventType.TOUCH_MOVE, 160, 200, 0)
        ls._handle_event(EventType.TOUCH_UP, 160, 200, 0)

        assert ls.is_locked is True
        assert ls._show_pin is True

    def test_correct_pin_unlocks(self):
        unlocked = []
        ls = LockScreen(on_unlock=lambda: unlocked.append(True))
        ls.set_pin("1234")
        ls._show_pin = True
        ls._build_pin_ui()

        for digit in "1234":
            ls._on_pin_key(digit)

        assert ls.is_locked is False
        assert len(unlocked) == 1

    def test_wrong_pin_shows_error(self):
        ls = LockScreen()
        ls.set_pin("1234")
        ls._show_pin = True
        ls._build_pin_ui()

        for digit in "0000":
            ls._on_pin_key(digit)

        assert ls.is_locked is True
        assert ls._pin_error is True
        assert ls._pin_input == ""  # Reset after wrong PIN

    def test_pin_backspace(self):
        ls = LockScreen()
        ls.set_pin("1234")
        ls._show_pin = True

        ls._on_pin_key("1")
        ls._on_pin_key("2")
        ls._on_pin_key("<")
        assert ls._pin_input == "1"

    def test_add_notification(self):
        ls = LockScreen()
        ls.layout(0, 0, 320, 480)
        ls.add_notification(LockScreenNotification(
            app_name="Claude", title="New message",
            body="Hello there!",
        ))
        assert len(ls._notifications) == 1

    def test_clear_notifications(self):
        ls = LockScreen()
        ls.add_notification(LockScreenNotification("A", "B", "C"))
        ls.clear_notifications()
        assert len(ls._notifications) == 0

    def test_lock_resets_state(self):
        ls = LockScreen()
        ls._locked = False
        ls.lock()
        assert ls.is_locked is True
        assert ls._show_pin is False

    def test_draw(self):
        ls = LockScreen()
        ls.layout(0, 0, 320, 480)
        buf = bytearray(320 * 480 * 4)
        ls.draw(buf, 320, 480)
        has_content = any(buf[i] > 0 for i in range(0, len(buf)))
        assert has_content


# --- 4c: Status Bar ---

from status_bar_widget import StatusBarWidget


class TestStatusBarWidget:
    def test_create(self):
        sb = StatusBarWidget()
        assert sb.min_height == StatusBarWidget.HEIGHT

    def test_update_time(self):
        sb = StatusBarWidget()
        sb.update_time("15:45")
        assert sb._time_str == "15:45"

    def test_update_battery(self):
        sb = StatusBarWidget()
        sb.update_battery(42)
        assert sb._battery_pct == 42

    def test_battery_clamps(self):
        sb = StatusBarWidget()
        sb.update_battery(150)
        assert sb._battery_pct == 100
        sb.update_battery(-10)
        assert sb._battery_pct == 0

    def test_battery_charging_color(self):
        sb = StatusBarWidget()
        sb.update_battery(50, charging=True)
        assert sb._battery_label.color == Colors.SUCCESS

    def test_battery_low_color(self):
        sb = StatusBarWidget()
        sb.update_battery(10)
        assert sb._battery_label.color == Colors.ERROR

    def test_update_wifi(self):
        sb = StatusBarWidget()
        sb.update_wifi(3, connected=True)
        assert sb._wifi_strength == 3
        assert sb._wifi_connected is True

    def test_wifi_off(self):
        sb = StatusBarWidget()
        sb.update_wifi(0, connected=False)
        assert "OFF" in sb._wifi_label.text

    def test_update_notifications(self):
        sb = StatusBarWidget()
        sb.update_notifications(3)
        assert sb._notification_count == 3
        assert sb._notif_label.text == "..."

    def test_zero_notifications(self):
        sb = StatusBarWidget()
        sb.update_notifications(0)
        assert sb._notif_label.text == ""

    def test_get_state(self):
        sb = StatusBarWidget()
        sb.update_time("10:30")
        sb.update_battery(80)
        state = sb.get_state()
        assert state["time"] == "10:30"
        assert state["battery"] == 80

    def test_measure(self):
        sb = StatusBarWidget()
        size = sb.measure(320, 480)
        assert size.width == 320
        assert size.height == StatusBarWidget.HEIGHT

    def test_draw(self):
        sb = StatusBarWidget()
        sb.layout(0, 0, 320, 32)
        buf = bytearray(320 * 32 * 4)
        sb.draw(buf, 320, 32)
        has_content = any(buf[i] > 0 for i in range(0, len(buf)))
        assert has_content


# --- 4d: Keyboard ---

from keyboard_widget import KeyboardWidget, KeyboardLayer, KeyWidget, LAYOUTS


class TestKeyboardWidget:
    def test_create(self):
        kb = KeyboardWidget()
        assert kb.current_layer == KeyboardLayer.LOWERCASE

    def test_key_callback(self):
        keys = []
        kb = KeyboardWidget(on_key=lambda k: keys.append(k))
        kb._handle_key("a")
        assert "a" in keys

    def test_shift_toggles_layer(self):
        kb = KeyboardWidget()
        assert kb.current_layer == KeyboardLayer.LOWERCASE
        kb._handle_key("SHIFT")
        assert kb.current_layer == KeyboardLayer.UPPERCASE
        kb._handle_key("SHIFT")
        assert kb.current_layer == KeyboardLayer.LOWERCASE

    def test_auto_lowercase_after_char(self):
        keys = []
        kb = KeyboardWidget(on_key=lambda k: keys.append(k))
        kb._handle_key("SHIFT")
        assert kb.current_layer == KeyboardLayer.UPPERCASE
        kb._handle_key("A")
        assert kb.current_layer == KeyboardLayer.LOWERCASE

    def test_numbers_layer(self):
        kb = KeyboardWidget()
        kb._handle_key("?123")
        assert kb.current_layer == KeyboardLayer.NUMBERS

    def test_abc_returns_to_lowercase(self):
        kb = KeyboardWidget()
        kb._handle_key("?123")
        kb._handle_key("ABC")
        assert kb.current_layer == KeyboardLayer.LOWERCASE

    def test_symbols_layer(self):
        kb = KeyboardWidget()
        kb._handle_key("?123")
        kb._handle_key("#+=")
        assert kb.current_layer == KeyboardLayer.SYMBOLS

    def test_space_key(self):
        keys = []
        kb = KeyboardWidget(on_key=lambda k: keys.append(k))
        kb._handle_key("SPACE")
        assert " " in keys

    def test_backspace_key(self):
        keys = []
        kb = KeyboardWidget(on_key=lambda k: keys.append(k))
        kb._handle_key("DEL")
        assert "BACKSPACE" in keys

    def test_enter_callback(self):
        entered = []
        kb = KeyboardWidget(on_enter=lambda: entered.append(True))
        kb._handle_key("ENTER")
        assert len(entered) == 1

    def test_measure(self):
        kb = KeyboardWidget()
        size = kb.measure(320, 480)
        assert size.width == 320
        assert size.height == KeyboardWidget.HEIGHT

    def test_layouts_have_all_layers(self):
        for layer in KeyboardLayer:
            assert layer in LAYOUTS
            assert len(LAYOUTS[layer]) == 4  # 4 rows

    def test_key_widget(self):
        pressed = []
        kw = KeyWidget("A", on_press=lambda: pressed.append(True))
        size = kw.measure(200, 200)
        assert size.width == 32
        assert size.height == 42


# --- 4b: Home Screen ---

from home_screen import (
    HomeScreen, ChatMessage, MessageRole, MessageBubble,
    TypingIndicator, InputBar,
)


class TestHomeScreen:
    def test_create(self):
        hs = HomeScreen()
        assert hs.message_count == 0

    def test_add_user_message(self):
        hs = HomeScreen()
        hs.layout(0, 0, 320, 480)
        msg = hs.add_message(MessageRole.USER, "Hello!")
        assert msg.role == MessageRole.USER
        assert msg.text == "Hello!"
        assert hs.message_count == 1

    def test_add_claude_message(self):
        hs = HomeScreen()
        hs.layout(0, 0, 320, 480)
        msg = hs.add_message(MessageRole.CLAUDE, "Hi! How can I help?")
        assert msg.role == MessageRole.CLAUDE

    def test_conversation_flow(self):
        hs = HomeScreen()
        hs.layout(0, 0, 320, 480)
        hs.add_message(MessageRole.USER, "What's the weather?")
        hs.add_message(MessageRole.CLAUDE, "I don't have weather access yet.")
        assert hs.message_count == 2

    def test_send_callback(self):
        sent = []
        hs = HomeScreen(on_send_message=lambda t: sent.append(t))
        hs.layout(0, 0, 320, 480)
        hs._on_send("Hello")
        assert "Hello" in sent
        assert hs.message_count == 1

    def test_typing_indicator(self):
        hs = HomeScreen()
        hs.layout(0, 0, 320, 480)
        hs.set_typing(True)
        assert hs._typing is True
        hs.set_typing(False)
        assert hs._typing is False

    def test_clear_chat(self):
        hs = HomeScreen()
        hs.layout(0, 0, 320, 480)
        hs.add_message(MessageRole.USER, "Test")
        hs.clear_chat()
        assert hs.message_count == 0

    def test_input_bar_text(self):
        hs = HomeScreen()
        hs.input_bar.text = "Hello"
        assert hs.input_bar.text == "Hello"

    def test_input_bar_append(self):
        hs = HomeScreen()
        hs.input_bar.append_char("H")
        hs.input_bar.append_char("i")
        assert hs.input_bar.text == "Hi"

    def test_input_bar_backspace(self):
        hs = HomeScreen()
        hs.input_bar.text = "Hello"
        hs.input_bar.append_char("BACKSPACE")
        assert hs.input_bar.text == "Hell"

    def test_input_bar_clear(self):
        hs = HomeScreen()
        hs.input_bar.text = "Hello"
        result = hs.input_bar.clear()
        assert result == "Hello"
        assert hs.input_bar.text == ""

    def test_draw(self):
        hs = HomeScreen()
        hs.layout(0, 0, 320, 480)
        hs.add_message(MessageRole.CLAUDE, "Welcome!")
        buf = bytearray(320 * 480 * 4)
        hs.draw(buf, 320, 480)
        has_content = any(buf[i] > 0 for i in range(0, len(buf)))
        assert has_content


class TestMessageBubble:
    def test_user_bubble_right_aligned(self):
        msg = ChatMessage(role=MessageRole.USER, text="Hello")
        bubble = MessageBubble(msg, screen_width=320)
        assert bubble._align == Align.END
        assert bubble.background == Colors.PRIMARY

    def test_claude_bubble_left_aligned(self):
        msg = ChatMessage(role=MessageRole.CLAUDE, text="Hi!")
        bubble = MessageBubble(msg, screen_width=320)
        assert bubble._align == Align.START
        assert bubble.background == Colors.SURFACE_CONTAINER

    def test_measure(self):
        msg = ChatMessage(role=MessageRole.USER, text="Test message")
        bubble = MessageBubble(msg, screen_width=320)
        size = bubble.measure(320, 500)
        assert size.width > 0
        assert size.height > 0


class TestTypingIndicator:
    def test_create(self):
        ti = TypingIndicator()
        size = ti.measure(320, 100)
        assert size.width == 80


class TestInputBar:
    def test_create(self):
        bar = InputBar()
        assert bar.text == ""

    def test_send(self):
        sent = []
        bar = InputBar(on_send=lambda t: sent.append(t))
        bar.text = "Hello"
        bar.send()
        assert "Hello" in sent
        assert bar.text == ""

    def test_send_empty_does_nothing(self):
        sent = []
        bar = InputBar(on_send=lambda t: sent.append(t))
        bar.text = "   "
        bar.send()
        assert len(sent) == 0


# --- 4e: Notification Panel ---

from notification_panel import (
    NotificationPanel, Notification, NotificationCard,
    QuickSettingsBar, QuickSetting,
)


class TestNotificationPanel:
    def test_create(self):
        np = NotificationPanel()
        assert np.notification_count == 0

    def test_add_notification(self):
        np = NotificationPanel()
        notif = np.add_notification("Claude", "New message", "Hello!")
        assert np.notification_count == 1
        assert notif.app_name == "Claude"

    def test_dismiss_notification(self):
        np = NotificationPanel()
        notif = np.add_notification("Test", "Title", "Body")
        np.dismiss(notif.id)
        assert np.notification_count == 0

    def test_clear_all(self):
        np = NotificationPanel()
        np.add_notification("A", "1", "")
        np.add_notification("B", "2", "")
        np.clear_all()
        assert np.notification_count == 0

    def test_unread_count(self):
        np = NotificationPanel()
        np.add_notification("A", "1", "")
        np.add_notification("B", "2", "")
        assert np.unread_count == 2

    def test_show_hide(self):
        np = NotificationPanel()
        np.show()
        assert np.is_visible is True
        np.hide()
        assert np.is_visible is False

    def test_notification_tap_callback(self):
        tapped = []
        np = NotificationPanel(on_notification_tap=lambda n: tapped.append(n))
        np.add_notification("Claude", "Test", "Body")
        # The callback is set on the card widgets


class TestNotification:
    def test_create(self):
        n = Notification(id=1, app_name="Claude", title="Hello",
                         body="World")
        assert n.app_name == "Claude"
        assert n.read is False

    def test_time_ago_now(self):
        n = Notification(id=1, app_name="A", title="B", body="",
                         timestamp=time.time())
        assert n.time_ago() == "now"

    def test_time_ago_minutes(self):
        n = Notification(id=1, app_name="A", title="B", body="",
                         timestamp=time.time() - 300)
        assert "m ago" in n.time_ago()


class TestQuickSettingsBar:
    def test_create(self):
        qs = QuickSettingsBar()
        assert len(qs._settings) == 5

    def test_toggle(self):
        qs = QuickSettingsBar()
        wifi = qs.get_setting("WiFi")
        assert wifi.enabled is True
        qs.set_toggle("WiFi", False)
        wifi = qs.get_setting("WiFi")
        assert wifi.enabled is False

    def test_get_nonexistent(self):
        qs = QuickSettingsBar()
        assert qs.get_setting("Nonexistent") is None


class TestNotificationCard:
    def test_create(self):
        n = Notification(id=1, app_name="Claude", title="Hi", body="")
        card = NotificationCard(n)
        size = card.measure(300, 500)
        assert size.width > 0
        assert size.height > 0

    def test_dismiss_swipe(self):
        dismissed = []
        n = Notification(id=1, app_name="Claude", title="Hi", body="")
        card = NotificationCard(n, on_dismiss=lambda n: dismissed.append(n))
        card.layout(0, 0, 280, 60)

        card._handle_event(EventType.TOUCH_DOWN, 140, 30, 0)
        card._handle_event(EventType.TOUCH_UP, 280, 30, 0)
        assert len(dismissed) == 1


# --- 4f: App Drawer ---

from app_drawer import AppDrawer, AppInfo, AppIcon


class TestAppDrawer:
    def test_create(self):
        ad = AppDrawer()
        assert ad.app_count == 8  # Default apps

    def test_add_app(self):
        ad = AppDrawer()
        ad.add_app(AppInfo("test", "Test App", "T"))
        assert ad.app_count == 9

    def test_remove_app(self):
        ad = AppDrawer()
        ad.remove_app("calculator")
        assert ad.app_count == 7
        assert ad.get_app("calculator") is None

    def test_get_app(self):
        ad = AppDrawer()
        app = ad.get_app("claude-chat")
        assert app is not None
        assert app.name == "Claude"

    def test_show_hide(self):
        ad = AppDrawer()
        ad.show()
        assert ad.is_visible is True
        ad.hide()
        assert ad.is_visible is False

    def test_launch_callback(self):
        launched = []
        ad = AppDrawer(on_launch=lambda a: launched.append(a))
        # AppIcons have _on_launch set to the drawer's callback
        # Test the icon directly
        app = AppInfo("test", "Test", "T")
        icon = AppIcon(app, on_launch=lambda a: launched.append(a))
        icon._launch()
        assert len(launched) == 1
        assert launched[0].app_id == "test"

    def test_draw(self):
        ad = AppDrawer()
        ad.layout(0, 0, 320, 400)
        buf = bytearray(320 * 400 * 4)
        ad.draw(buf, 320, 400)
        has_content = any(buf[i] > 0 for i in range(0, len(buf)))
        assert has_content


class TestAppIcon:
    def test_create(self):
        app = AppInfo("test", "Test", "T", Colors.PRIMARY)
        icon = AppIcon(app)
        size = icon.measure(100, 100)
        assert size.width == 72
        assert size.height == AppIcon.TOTAL_HEIGHT

    def test_tap_launches(self):
        launched = []
        app = AppInfo("test", "Test", "T")
        icon = AppIcon(app, on_launch=lambda a: launched.append(a.app_id))
        icon._launch()
        assert "test" in launched
