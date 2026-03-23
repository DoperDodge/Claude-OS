"""
Claude-OS Input Handler

Reads input events from Linux evdev devices (/dev/input/event*) and
routes them to the compositor. Handles:

    - Keyboard events from virtio-keyboard-pci (QEMU)
    - Mouse/pointer events from virtio-mouse-pci (QEMU)
    - Touch events (for future real hardware)

Uses the raw evdev protocol (struct input_event) — no external libraries
required. Events are translated to compositor actions (touch gestures,
key presses, pointer motion).
"""

import asyncio
import glob
import logging
import os
import struct
from dataclasses import dataclass
from enum import IntEnum

logger = logging.getLogger("input")

# Linux input event types (from linux/input-event-codes.h)
EV_SYN = 0x00
EV_KEY = 0x01
EV_REL = 0x02   # Relative (mouse movement)
EV_ABS = 0x03   # Absolute (touchscreen)

# Key state values
KEY_RELEASE = 0
KEY_PRESS = 1
KEY_REPEAT = 2

# Relative axis codes
REL_X = 0x00
REL_Y = 0x01
REL_WHEEL = 0x08

# Absolute axis codes
ABS_X = 0x00
ABS_Y = 0x01
ABS_MT_SLOT = 0x2F
ABS_MT_POSITION_X = 0x35
ABS_MT_POSITION_Y = 0x36
ABS_MT_TRACKING_ID = 0x39

# Mouse button codes
BTN_LEFT = 0x110
BTN_RIGHT = 0x111
BTN_MIDDLE = 0x112
BTN_TOUCH = 0x14A

# struct input_event: time_sec(8) + time_usec(8) + type(2) + code(2) + value(4) = 24 bytes
INPUT_EVENT_SIZE = 24
INPUT_EVENT_FORMAT = "llHHi"


class DeviceType(IntEnum):
    KEYBOARD = 1
    MOUSE = 2
    TOUCHSCREEN = 3
    UNKNOWN = 0


@dataclass
class InputEvent:
    """Parsed Linux input event."""
    device_type: DeviceType
    event_type: int
    code: int
    value: int
    timestamp: float


class InputHandler:
    """
    Reads and dispatches Linux input events.

    Discovers input devices, classifies them, and feeds events
    to the compositor's gesture/key handlers.
    """

    def __init__(self):
        self._devices: dict[str, DeviceType] = {}  # path -> type
        self._fds: dict[str, int] = {}  # path -> fd
        self._running = False

        # Pointer state
        self.pointer_x: int = 0
        self.pointer_y: int = 0
        self.pointer_button_left = False

        # Callbacks
        self._on_key = None
        self._on_pointer_motion = None
        self._on_pointer_button = None
        self._on_touch_down = None
        self._on_touch_up = None
        self._on_touch_motion = None

    def set_callbacks(self, on_key=None, on_pointer_motion=None,
                      on_pointer_button=None, on_touch_down=None,
                      on_touch_up=None, on_touch_motion=None):
        """Set event callbacks."""
        self._on_key = on_key
        self._on_pointer_motion = on_pointer_motion
        self._on_pointer_button = on_pointer_button
        self._on_touch_down = on_touch_down
        self._on_touch_up = on_touch_up
        self._on_touch_motion = on_touch_motion

    def discover_devices(self) -> list[dict]:
        """Find and classify input devices."""
        devices = []
        for path in sorted(glob.glob("/dev/input/event*")):
            dtype = self._classify_device(path)
            self._devices[path] = dtype
            devices.append({"path": path, "type": dtype.name})
            logger.info("Input device: %s (%s)", path, dtype.name)
        return devices

    def open_devices(self):
        """Open all discovered input devices for reading."""
        for path, dtype in self._devices.items():
            if dtype == DeviceType.UNKNOWN:
                continue
            try:
                fd = os.open(path, os.O_RDONLY | os.O_NONBLOCK)
                self._fds[path] = fd
                logger.info("Opened input device: %s (fd=%d)", path, fd)
            except OSError as e:
                logger.warning("Cannot open %s: %s", path, e)

    def close_devices(self):
        """Close all input devices."""
        for path, fd in self._fds.items():
            try:
                os.close(fd)
            except OSError:
                pass
        self._fds.clear()

    async def run(self, screen_width: int = 480, screen_height: int = 960):
        """Async event loop — read and dispatch input events."""
        self._running = True
        loop = asyncio.get_event_loop()

        while self._running:
            for path, fd in list(self._fds.items()):
                try:
                    data = os.read(fd, INPUT_EVENT_SIZE * 16)
                    self._process_events(path, data, screen_width, screen_height)
                except BlockingIOError:
                    pass
                except OSError:
                    logger.warning("Lost input device: %s", path)
                    self._fds.pop(path, None)

            await asyncio.sleep(0.004)  # ~250Hz polling

    def stop(self):
        self._running = False

    def _process_events(self, path: str, data: bytes,
                        screen_w: int, screen_h: int):
        """Parse raw evdev data into events and dispatch."""
        dtype = self._devices.get(path, DeviceType.UNKNOWN)
        offset = 0

        while offset + INPUT_EVENT_SIZE <= len(data):
            sec, usec, etype, code, value = struct.unpack_from(
                INPUT_EVENT_FORMAT, data, offset,
            )
            offset += INPUT_EVENT_SIZE

            if etype == EV_SYN:
                continue

            event = InputEvent(
                device_type=dtype,
                event_type=etype,
                code=code,
                value=value,
                timestamp=sec + usec / 1_000_000,
            )

            self._dispatch_event(event, screen_w, screen_h)

    def _dispatch_event(self, event: InputEvent, screen_w: int, screen_h: int):
        """Route an input event to the appropriate callback."""
        if event.event_type == EV_KEY:
            if event.code in (BTN_LEFT, BTN_RIGHT, BTN_MIDDLE):
                self.pointer_button_left = (event.code == BTN_LEFT and
                                             event.value == KEY_PRESS)
                if self._on_pointer_button:
                    self._on_pointer_button(
                        self.pointer_x, self.pointer_y,
                        event.code, event.value,
                    )
                # Simulate touch from mouse click
                if event.code == BTN_LEFT:
                    if event.value == KEY_PRESS and self._on_touch_down:
                        self._on_touch_down(self.pointer_x, self.pointer_y, 0)
                    elif event.value == KEY_RELEASE and self._on_touch_up:
                        self._on_touch_up(self.pointer_x, self.pointer_y, 0)

            elif event.code == BTN_TOUCH:
                if event.value == KEY_PRESS and self._on_touch_down:
                    self._on_touch_down(self.pointer_x, self.pointer_y, 0)
                elif event.value == KEY_RELEASE and self._on_touch_up:
                    self._on_touch_up(self.pointer_x, self.pointer_y, 0)

            elif self._on_key:
                self._on_key(event.code, event.value)

        elif event.event_type == EV_REL:
            if event.code == REL_X:
                self.pointer_x = max(0, min(screen_w - 1,
                                             self.pointer_x + event.value))
            elif event.code == REL_Y:
                self.pointer_y = max(0, min(screen_h - 1,
                                             self.pointer_y + event.value))
            if self._on_pointer_motion:
                self._on_pointer_motion(self.pointer_x, self.pointer_y)
            # If dragging (left button held), send touch motion
            if self.pointer_button_left and self._on_touch_motion:
                self._on_touch_motion(self.pointer_x, self.pointer_y, 0)

        elif event.event_type == EV_ABS:
            if event.code in (ABS_X, ABS_MT_POSITION_X):
                self.pointer_x = event.value
            elif event.code in (ABS_Y, ABS_MT_POSITION_Y):
                self.pointer_y = event.value

            if self._on_touch_motion:
                self._on_touch_motion(self.pointer_x, self.pointer_y, 0)

    def _classify_device(self, path: str) -> DeviceType:
        """Classify an input device by reading its capabilities."""
        try:
            # Read device name from sysfs
            event_name = os.path.basename(path)
            sysfs_name = f"/sys/class/input/{event_name}/device/name"
            if os.path.exists(sysfs_name):
                with open(sysfs_name) as f:
                    name = f.read().strip().lower()

                if "keyboard" in name or "key" in name:
                    return DeviceType.KEYBOARD
                elif "mouse" in name or "pointer" in name:
                    return DeviceType.MOUSE
                elif "touch" in name:
                    return DeviceType.TOUCHSCREEN
                elif "virtio" in name:
                    # QEMU virtio devices — check by capabilities
                    return self._classify_by_caps(path)

            return self._classify_by_caps(path)
        except OSError:
            return DeviceType.UNKNOWN

    def _classify_by_caps(self, path: str) -> DeviceType:
        """Classify device by reading evdev capability bits."""
        event_name = os.path.basename(path)
        cap_path = f"/sys/class/input/{event_name}/device/capabilities/ev"
        try:
            if os.path.exists(cap_path):
                with open(cap_path) as f:
                    caps = int(f.read().strip(), 16)

                has_key = bool(caps & (1 << EV_KEY))
                has_rel = bool(caps & (1 << EV_REL))
                has_abs = bool(caps & (1 << EV_ABS))

                if has_abs:
                    return DeviceType.TOUCHSCREEN
                elif has_rel:
                    return DeviceType.MOUSE
                elif has_key:
                    return DeviceType.KEYBOARD
        except (OSError, ValueError):
            pass
        return DeviceType.UNKNOWN

    def get_status(self) -> dict:
        return {
            "devices": {p: t.name for p, t in self._devices.items()},
            "open_fds": len(self._fds),
            "pointer": {"x": self.pointer_x, "y": self.pointer_y},
        }
