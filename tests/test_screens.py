"""Tests for the Claude-OS screen views and compositor state transitions."""

import os
import sys
import time

import pytest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from ui.widgets.base import Size, TouchEvent, TouchAction


# --- Lock Screen View ---

class TestLockScreenView:
    def test_create(self):
        from ui.screens.lock_screen_view import LockScreenView
        view = LockScreenView(1080, 2340)
        assert view._screen_w == 1080
        assert view._screen_h == 2340

    def test_initial_state(self):
        from ui.screens.lock_screen_view import LockScreenView
        view = LockScreenView(1080, 2340)
        assert view.swipe_progress == 0.0
        assert view.notifications == []

    def test_measure(self):
        from ui.screens.lock_screen_view import LockScreenView
        view = LockScreenView(1080, 2340)
        size = view.measure(1080, 2340)
        assert size.width == 1080
        assert size.height == 2340

    def test_update_clock(self):
        from ui.screens.lock_screen_view import LockScreenView
        view = LockScreenView(1080, 2340)
        view.update()
        assert view._clock_label is not None
        assert ":" in view._clock_label.text

    def test_swipe_progress_opacity(self):
        from ui.screens.lock_screen_view import LockScreenView
        view = LockScreenView(1080, 2340)
        view.swipe_progress = 0.5
        view.update()
        assert view._clock_label.opacity < 1.0

    def test_notifications_display(self):
        from ui.screens.lock_screen_view import LockScreenView
        view = LockScreenView(1080, 2340)
        view.notifications = [
            {"app_name": "Claude", "title": "Hello", "body": "Test"},
        ]
        view.update()
        assert len(view._notif_container.children) == 1


# --- Home View ---

class TestHomeView:
    def test_create(self):
        from ui.screens.home_view import HomeView
        view = HomeView(1080, 2000)
        assert view._screen_w == 1080

    def test_welcome_message(self):
        from ui.screens.home_view import HomeView
        view = HomeView(1080, 2000)
        assert len(view.messages) == 1
        assert "Claude" in view.messages[0].text

    def test_add_message(self):
        from ui.screens.home_view import HomeView
        view = HomeView(1080, 2000)
        view.add_message("Hello!", is_user=True)
        assert len(view.messages) == 2
        assert view.messages[-1].is_user is True

    def test_typing_indicator(self):
        from ui.screens.home_view import HomeView
        view = HomeView(1080, 2000)
        view.typing_indicator = True
        view.update()
        assert view._typing_label.visible is True

    def test_message_bubble_measure(self):
        from ui.screens.home_view import ChatMessage, MessageBubble
        msg = ChatMessage(text="Hello world", is_user=True)
        bubble = MessageBubble(msg)
        size = bubble.measure(400, 500)
        assert size.width > 0
        assert size.height > 0


# --- Status Bar View ---

class TestStatusBarView:
    def test_create(self):
        from ui.screens.status_bar_view import StatusBarView
        view = StatusBarView(1080)
        assert view._bar_w == 1080
        assert view._bar_h == 54

    def test_measure(self):
        from ui.screens.status_bar_view import StatusBarView
        view = StatusBarView(1080, height=54)
        size = view.measure(1080, 2340)
        assert size.width == 1080
        assert size.height == 54

    def test_update_time(self):
        from ui.screens.status_bar_view import StatusBarView
        view = StatusBarView(1080)
        view.update()
        assert ":" in view.time_str

    def test_battery_icon_measure(self):
        from ui.screens.status_bar_view import BatteryIcon
        icon = BatteryIcon(level=75)
        size = icon.measure(100, 100)
        assert size.width > 0
        assert size.height > 0

    def test_wifi_icon_measure(self):
        from ui.screens.status_bar_view import WifiIcon
        icon = WifiIcon(strength=3, connected=True)
        size = icon.measure(100, 100)
        assert size.width == 16
        assert size.height == 16

    def test_dynamic_island_measure(self):
        from ui.screens.status_bar_view import DynamicIslandView
        island = DynamicIslandView()
        size = island.measure(1080, 54)
        assert size.width == 162
        assert size.height == 37

    def test_dynamic_island_expanded(self):
        from ui.screens.status_bar_view import DynamicIslandView
        island = DynamicIslandView()
        island.expanded = True
        size = island.measure(1080, 54)
        assert size.width > 162


# --- Keyboard View ---

class TestKeyboardView:
    def test_create(self):
        from ui.screens.keyboard_view import KeyboardView
        view = KeyboardView(1080)
        assert view._kb_w == 1080
        assert view._kb_h == 291

    def test_measure(self):
        from ui.screens.keyboard_view import KeyboardView
        view = KeyboardView(1080, height=291)
        size = view.measure(1080, 500)
        assert size.width == 1080
        assert size.height == 291

    def test_layer_switch(self):
        from ui.screens.keyboard_view import KeyboardView
        from ui.keyboard.keyboard import KeyboardLayer
        view = KeyboardView(1080)
        assert view.layer == KeyboardLayer.LOWERCASE
        view.set_layer(KeyboardLayer.UPPERCASE)
        assert view.layer == KeyboardLayer.UPPERCASE

    def test_layer_switch_numbers(self):
        from ui.screens.keyboard_view import KeyboardView
        from ui.keyboard.keyboard import KeyboardLayer
        view = KeyboardView(1080)
        view.set_layer(KeyboardLayer.NUMBERS)
        assert view.layer == KeyboardLayer.NUMBERS

    def test_suggestions(self):
        from ui.screens.keyboard_view import KeyboardView
        view = KeyboardView(1080)
        view.update_suggestions(["hello", "help", "hey"])
        assert view.suggestions == ["hello", "help", "hey"]

    def test_suggestion_bar_measure(self):
        from ui.screens.keyboard_view import SuggestionBar
        bar = SuggestionBar(suggestions=["a", "b", "c"])
        size = bar.measure(1080, 100)
        assert size.width == 1080
        assert size.height == 44

    def test_key_widget_measure(self):
        from ui.screens.keyboard_view import KeyWidget
        from ui.keyboard.keyboard import Key
        key = Key("q", "q")
        kw = KeyWidget(key, unit_width=100, row_height=60)
        size = kw.measure(200, 100)
        assert size.width > 0
        assert size.height > 0

    def test_key_handler(self):
        from ui.screens.keyboard_view import KeyboardView
        view = KeyboardView(1080)
        pressed = []
        view.set_key_handler(on_key=lambda k: pressed.append(k))
        from ui.keyboard.keyboard import Key
        view._handle_key_press(Key("a", "a"))
        assert pressed == ["a"]


# --- Notification View ---

class TestNotificationView:
    def test_create(self):
        from ui.screens.notification_view import NotificationView
        view = NotificationView(1080, 2340)
        assert view._screen_w == 1080

    def test_default_quick_settings(self):
        from ui.screens.notification_view import NotificationView
        view = NotificationView(1080, 2340)
        assert len(view.quick_settings) == 6

    def test_add_notification(self):
        from ui.screens.notification_view import NotificationView
        view = NotificationView(1080, 2340)
        view.add_notification("Claude", "Hello", "Test body")
        assert len(view.notifications) == 1
        assert view.notifications[0]["app_name"] == "Claude"

    def test_clear_notifications(self):
        from ui.screens.notification_view import NotificationView
        view = NotificationView(1080, 2340)
        view.add_notification("Claude", "Test", "Body")
        view.clear_notifications()
        assert len(view.notifications) == 0

    def test_measure(self):
        from ui.screens.notification_view import NotificationView
        view = NotificationView(1080, 2340, status_bar_h=54)
        size = view.measure(1080, 2340)
        assert size.width == 1080
        assert size.height == 2340 - 54

    def test_brightness_slider_measure(self):
        from ui.screens.notification_view import BrightnessSlider
        slider = BrightnessSlider(value=50)
        size = slider.measure(400, 100)
        assert size.width == 400
        assert size.height == 36

    def test_notification_card_measure(self):
        from ui.screens.notification_view import NotificationCard
        card = NotificationCard("Claude", "Title", "Body text")
        size = card.measure(400, 500)
        assert size.width == 400
        assert size.height > 0

    def test_quick_setting_toggle(self):
        from ui.screens.notification_view import QuickSettingToggle
        toggled = []
        toggle = QuickSettingToggle("WiFi", enabled=False,
                                     on_toggle=lambda v: toggled.append(v))
        toggle.layout(0, 0, 100, 64)
        event = TouchEvent(x=50, y=32, action=TouchAction.UP)
        toggle.handle_touch(event)
        assert toggle.enabled is True
        assert toggled == [True]


# --- App Drawer View ---

class TestAppDrawerView:
    def test_create(self):
        from ui.screens.app_drawer_view import AppDrawerView
        view = AppDrawerView(1080, 2340)
        assert view._screen_w == 1080

    def test_default_apps(self):
        from ui.screens.app_drawer_view import AppDrawerView
        view = AppDrawerView(1080, 2340)
        assert len(view.apps) == 20

    def test_apps_sorted(self):
        from ui.screens.app_drawer_view import AppDrawerView
        view = AppDrawerView(1080, 2340)
        names = [a["name"] for a in view.apps]
        assert names == sorted(names, key=str.lower)

    def test_search_filter(self):
        from ui.screens.app_drawer_view import AppDrawerView
        view = AppDrawerView(1080, 2340)
        view.search_query = "cal"
        filtered = view._get_filtered_apps()
        assert all("cal" in a["name"].lower() for a in filtered)
        assert len(filtered) >= 1

    def test_sections(self):
        from ui.screens.app_drawer_view import AppDrawerView
        view = AppDrawerView(1080, 2340)
        sections = view._get_sections()
        assert "C" in sections
        assert len(sections["C"]) >= 1

    def test_measure(self):
        from ui.screens.app_drawer_view import AppDrawerView
        view = AppDrawerView(1080, 2340, status_bar_h=54)
        size = view.measure(1080, 2340)
        assert size.width == 1080
        assert size.height == 2340 - 54

    def test_app_icon_widget(self):
        from ui.screens.app_drawer_view import AppIconWidget
        icon = AppIconWidget("Claude", color="#D4A574")
        size = icon.measure(100, 200)
        assert size.width > 0
        assert size.height > 0

    def test_set_search(self):
        from ui.screens.app_drawer_view import AppDrawerView
        view = AppDrawerView(1080, 2340)
        view.set_search("music")
        assert view.search_query == "music"


# --- Compositor State Transitions ---

class TestCompositorScreens:
    def test_build_lock_screen(self):
        from ui.compositor.compositor import Compositor, OutputConfig, CompositorState
        comp = Compositor(OutputConfig(width=1080, height=2340))
        comp.initialize()
        comp.state = CompositorState.LOCKED
        root = comp._build_widget_ui()
        assert root is not None
        assert comp._lock_view is not None

    def test_build_home_screen(self):
        from ui.compositor.compositor import Compositor, OutputConfig, CompositorState
        comp = Compositor(OutputConfig(width=1080, height=2340))
        comp.initialize()
        comp.state = CompositorState.HOME
        root = comp._build_widget_ui()
        assert root is not None
        assert comp._status_bar_view is not None
        assert comp._home_view is not None

    def test_build_app_drawer(self):
        from ui.compositor.compositor import Compositor, OutputConfig, CompositorState
        comp = Compositor(OutputConfig(width=1080, height=2340))
        comp.initialize()
        comp.state = CompositorState.APP_DRAWER
        root = comp._build_widget_ui()
        assert root is not None
        assert comp._app_drawer_view is not None

    def test_build_notification_shade(self):
        from ui.compositor.compositor import Compositor, OutputConfig, CompositorState
        comp = Compositor(OutputConfig(width=1080, height=2340))
        comp.initialize()
        comp.state = CompositorState.NOTIFICATION_SHADE
        root = comp._build_widget_ui()
        assert root is not None
        assert comp._notification_view is not None

    def test_state_transition_locked_to_home(self):
        from ui.compositor.compositor import Compositor, OutputConfig, CompositorState
        comp = Compositor(OutputConfig(width=1080, height=2340))
        comp.initialize()
        comp.state = CompositorState.LOCKED
        comp.unlock()
        assert comp.state == CompositorState.HOME

    def test_state_transition_home_to_drawer(self):
        from ui.compositor.compositor import Compositor, OutputConfig, CompositorState
        comp = Compositor(OutputConfig(width=1080, height=2340))
        comp.initialize()
        comp.state = CompositorState.HOME
        comp._handle_default_gesture("swipe_up", {})
        assert comp.state == CompositorState.APP_DRAWER

    def test_state_transition_drawer_to_home(self):
        from ui.compositor.compositor import Compositor, OutputConfig, CompositorState
        comp = Compositor(OutputConfig(width=1080, height=2340))
        comp.initialize()
        comp.state = CompositorState.APP_DRAWER
        comp._handle_default_gesture("swipe_down", {})
        assert comp.state == CompositorState.HOME

    def test_state_transition_notification_shade(self):
        from ui.compositor.compositor import Compositor, OutputConfig, CompositorState
        comp = Compositor(OutputConfig(width=1080, height=2340))
        comp.initialize()
        comp.state = CompositorState.HOME
        comp._handle_default_gesture("notification_shade", {})
        assert comp.state == CompositorState.NOTIFICATION_SHADE

    def test_state_transition_go_home(self):
        from ui.compositor.compositor import Compositor, OutputConfig, CompositorState
        comp = Compositor(OutputConfig(width=1080, height=2340))
        comp.initialize()
        comp.state = CompositorState.NOTIFICATION_SHADE
        comp._handle_default_gesture("go_home", {})
        assert comp.state == CompositorState.HOME

    def test_rebuild_on_state_change(self):
        from ui.compositor.compositor import Compositor, OutputConfig, CompositorState
        comp = Compositor(OutputConfig(width=1080, height=2340))
        comp.initialize()
        comp.state = CompositorState.HOME
        comp._build_widget_ui()
        assert comp._home_view is not None
        comp.state = CompositorState.LOCKED
        comp._rebuild_if_state_changed()
        assert comp._lock_view is not None

    def test_widget_count_per_state(self):
        from ui.compositor.compositor import Compositor, OutputConfig, CompositorState
        comp = Compositor(OutputConfig(width=1080, height=2340))
        comp.initialize()

        for state in [CompositorState.LOCKED, CompositorState.HOME,
                      CompositorState.APP_DRAWER, CompositorState.NOTIFICATION_SHADE]:
            comp.state = state
            comp._build_widget_ui()
            count = comp._count_widgets(comp._widget_root)
            assert count >= 5, f"State {state.name} has too few widgets: {count}"
