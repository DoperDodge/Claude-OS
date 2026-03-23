"""
Tests for the input handler.
"""

import struct
import pytest
from input_handler import (
    InputHandler, InputEvent, DeviceType,
    EV_KEY, EV_REL, EV_ABS,
    KEY_PRESS, KEY_RELEASE,
    REL_X, REL_Y,
    BTN_LEFT, BTN_RIGHT,
)


class TestInputEvent:
    """Test input event data structures."""

    def test_create_event(self):
        event = InputEvent(
            device_type=DeviceType.KEYBOARD,
            event_type=EV_KEY,
            code=30,  # KEY_A
            value=KEY_PRESS,
            timestamp=1234.5,
        )
        assert event.device_type == DeviceType.KEYBOARD
        assert event.code == 30

    def test_device_types(self):
        assert DeviceType.KEYBOARD == 1
        assert DeviceType.MOUSE == 2
        assert DeviceType.TOUCHSCREEN == 3


class TestInputDispatch:
    """Test event dispatch to callbacks."""

    def setup_method(self):
        self.handler = InputHandler()
        self.key_events = []
        self.pointer_events = []
        self.touch_events = []

        self.handler.set_callbacks(
            on_key=lambda code, val: self.key_events.append((code, val)),
            on_pointer_motion=lambda x, y: self.pointer_events.append(("move", x, y)),
            on_pointer_button=lambda x, y, btn, val: self.pointer_events.append(("btn", btn, val)),
            on_touch_down=lambda x, y, tid: self.touch_events.append(("down", x, y)),
            on_touch_up=lambda x, y, tid: self.touch_events.append(("up", x, y)),
            on_touch_motion=lambda x, y, tid: self.touch_events.append(("motion", x, y)),
        )

    def test_key_press_dispatch(self):
        event = InputEvent(DeviceType.KEYBOARD, EV_KEY, 30, KEY_PRESS, 0)
        self.handler._dispatch_event(event, 480, 960)
        assert (30, KEY_PRESS) in self.key_events

    def test_key_release_dispatch(self):
        event = InputEvent(DeviceType.KEYBOARD, EV_KEY, 30, KEY_RELEASE, 0)
        self.handler._dispatch_event(event, 480, 960)
        assert (30, KEY_RELEASE) in self.key_events

    def test_mouse_move_dispatch(self):
        event_x = InputEvent(DeviceType.MOUSE, EV_REL, REL_X, 10, 0)
        event_y = InputEvent(DeviceType.MOUSE, EV_REL, REL_Y, 20, 0)
        self.handler._dispatch_event(event_x, 480, 960)
        self.handler._dispatch_event(event_y, 480, 960)

        assert self.handler.pointer_x == 10
        assert self.handler.pointer_y == 20
        assert len(self.pointer_events) == 2

    def test_mouse_button_dispatch(self):
        event = InputEvent(DeviceType.MOUSE, EV_KEY, BTN_LEFT, KEY_PRESS, 0)
        self.handler._dispatch_event(event, 480, 960)
        assert ("btn", BTN_LEFT, KEY_PRESS) in self.pointer_events

    def test_mouse_click_generates_touch(self):
        """Left click should generate touch_down/touch_up events."""
        down = InputEvent(DeviceType.MOUSE, EV_KEY, BTN_LEFT, KEY_PRESS, 0)
        up = InputEvent(DeviceType.MOUSE, EV_KEY, BTN_LEFT, KEY_RELEASE, 0)
        self.handler._dispatch_event(down, 480, 960)
        self.handler._dispatch_event(up, 480, 960)

        touch_types = [t[0] for t in self.touch_events]
        assert "down" in touch_types
        assert "up" in touch_types

    def test_pointer_clamped_to_screen(self):
        """Pointer position should not go negative or past screen bounds."""
        event = InputEvent(DeviceType.MOUSE, EV_REL, REL_X, -100, 0)
        self.handler._dispatch_event(event, 480, 960)
        assert self.handler.pointer_x == 0

        event = InputEvent(DeviceType.MOUSE, EV_REL, REL_X, 1000, 0)
        self.handler._dispatch_event(event, 480, 960)
        assert self.handler.pointer_x == 479

    def test_right_button_no_touch(self):
        """Right click should not generate touch events."""
        event = InputEvent(DeviceType.MOUSE, EV_KEY, BTN_RIGHT, KEY_PRESS, 0)
        self.handler._dispatch_event(event, 480, 960)
        assert len(self.touch_events) == 0


class TestInputStatus:
    """Test status reporting."""

    def test_get_status(self):
        handler = InputHandler()
        status = handler.get_status()
        assert "pointer" in status
        assert status["pointer"]["x"] == 0
        assert status["pointer"]["y"] == 0
