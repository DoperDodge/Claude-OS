#!/usr/bin/env python3
"""
Claude-OS Visual UI Main Loop

The main entry point for the visual OS when running on real hardware
or in QEMU. Renders the full widget tree to DRM/framebuffer at 60fps.

This is started by the claude-os-compositor.service systemd unit.

Pipeline:
    1. Initialize DRM/framebuffer display via CompositorRenderer
    2. Build the widget tree (lock screen → home → etc.)
    3. Handle input from evdev (touch/keyboard)
    4. Render frames at 60fps
    5. Run Wayland server for third-party apps
"""

import asyncio
import logging
import os
import signal
import struct
import sys
import time

# Add source directories to path
PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
for subdir in [
    "ui/toolkit", "ui/screens", "ui/apps", "ui/vision",
    "ui/compositor", "ui/display",
]:
    sys.path.insert(0, os.path.join(PROJECT_ROOT, subdir))

from theme import Colors
from widget import Widget, Event, EventType
from widgets import Container, Label
from font import FontRenderer
from lock_screen import LockScreen
from home_screen import HomeScreen, MessageRole
from status_bar_widget import StatusBarWidget
from keyboard_widget import KeyboardWidget
from notification_panel import NotificationPanel
from app_drawer import AppDrawer
from animation import AnimationController

from renderer import CompositorRenderer, SurfaceBuffer

logger = logging.getLogger("claude-os-ui")

# Display defaults (overridden by env vars)
DISPLAY_WIDTH = int(os.environ.get("DISPLAY_WIDTH", "480"))
DISPLAY_HEIGHT = int(os.environ.get("DISPLAY_HEIGHT", "960"))
TARGET_FPS = 60


class ClaudeOSUI:
    """
    Main UI controller for on-device / QEMU rendering.

    Manages the widget tree, input dispatch, and render loop.
    Outputs to DRM/framebuffer via CompositorRenderer.
    """

    def __init__(self, width: int, height: int):
        self.width = width
        self.height = height
        self.buf = bytearray(width * height * 4)

        self.renderer = CompositorRenderer()
        self.anim_controller = AnimationController()

        # State
        self.screen = "lock"
        self.keyboard_visible = False
        self.notification_visible = False
        self._running = False

        # Build UI
        self._build_screens()

        logger.info("UI initialized: %dx%d", width, height)

    def _build_screens(self):
        self.lock_screen = LockScreen(
            on_unlock=self._on_unlock,
            pin_required=True,
        )

        self.status_bar = StatusBarWidget()
        self.status_bar.update_time(time.strftime("%H:%M"))
        self.status_bar.update_battery(100, False)
        self.status_bar.update_wifi(4)

        self.home_screen = HomeScreen(
            on_send_message=self._on_send_message,
        )
        self.home_screen.add_message(
            MessageRole.CLAUDE,
            "Hello! I'm Claude, running on Claude-OS. "
            "How can I help you?"
        )

        self.keyboard = KeyboardWidget(
            on_key=self._on_key_press,
        )

        self.notification_panel = NotificationPanel()
        self.app_drawer = AppDrawer(
            on_launch=self._on_app_launch,
        )

    def _on_unlock(self):
        self.screen = "home"

    def _on_send_message(self, text: str):
        # Placeholder — in production this goes to the chat engine
        self.home_screen.add_message(
            MessageRole.CLAUDE,
            f"I received: \"{text}\". Connect the Claude API for real responses."
        )

    def _on_key_press(self, key: str):
        if key == "ENTER":
            self.home_screen.input_bar.send()
            self.keyboard_visible = False
        elif key == "BACKSPACE":
            self.home_screen.input_bar.append_char("BACKSPACE")
        else:
            self.home_screen.input_bar.append_char(key)

    def _on_app_launch(self, app_name: str):
        self.screen = "home"

    def render_frame(self):
        """Render one frame into self.buf."""
        # Clear
        bg = Colors.BACKGROUND
        pixel = bytes([bg.b, bg.g, bg.r, bg.a]) * self.width
        for y in range(self.height):
            off = y * self.width * 4
            self.buf[off:off + len(pixel)] = pixel

        if self.screen == "lock":
            self.lock_screen.layout(0, 0, self.width, self.height)
            self.lock_screen.draw(self.buf, self.width, self.height)
        elif self.screen == "home":
            bar_h = 32
            self.status_bar.layout(0, 0, self.width, bar_h)
            self.status_bar.draw(self.buf, self.width, self.height)

            chat_h = self.height - bar_h
            if self.keyboard_visible:
                chat_h -= 260
            self.home_screen.layout(0, bar_h, self.width, chat_h)
            self.home_screen.draw(self.buf, self.width, self.height, 0, 0)

            if self.keyboard_visible:
                kb_y = self.height - 260
                self.keyboard.layout(0, kb_y, self.width, 260)
                self.keyboard.draw(self.buf, self.width, self.height)

            if self.notification_visible:
                self.notification_panel.layout(0, bar_h, self.width, 300)
                self.notification_panel.draw(self.buf, self.width, self.height, 0, 0)

        elif self.screen == "app_drawer":
            bar_h = 32
            self.status_bar.layout(0, 0, self.width, bar_h)
            self.status_bar.draw(self.buf, self.width, self.height)

            self.app_drawer.layout(0, bar_h, self.width, self.height - bar_h)
            self.app_drawer.draw(self.buf, self.width, self.height, 0, 0)

    def handle_touch(self, event_type: EventType, x: int, y: int):
        """Handle touch/mouse events from the input handler."""
        event = Event(type=event_type, x=x, y=y)

        if self.screen == "lock":
            self.lock_screen.on_event(event)
        elif self.screen == "home":
            if event_type == EventType.TOUCH_DOWN:
                if y > self.height - 80 and not self.keyboard_visible:
                    self.keyboard_visible = True
                    return
            if self.keyboard_visible and y >= self.height - 260:
                self.keyboard.on_event(event)
            else:
                self.home_screen.on_event(event)
        elif self.screen == "app_drawer":
            self.app_drawer.on_event(event)

    async def run(self):
        """Main render loop at 60fps."""
        # Initialize renderer (tries DRM → framebuffer → headless)
        display_info = self.renderer.initialize(self.width, self.height)
        logger.info("Display: %s", display_info)

        # Create a surface buffer for our UI
        ui_surface_id = 1
        frame_time = 1.0 / TARGET_FPS
        self._running = True

        # Optional: try to start input handler
        input_task = None
        try:
            from input_handler import InputHandler
            self._input_handler = InputHandler(
                screen_width=self.width,
                screen_height=self.height,
            )
            self._input_handler.set_callbacks(
                on_touch=lambda x, y, pressed:
                    self.handle_touch(
                        EventType.TOUCH_DOWN if pressed else EventType.TOUCH_UP,
                        x, y
                    ),
            )
            input_task = asyncio.create_task(
                asyncio.to_thread(self._input_handler.poll_loop)
            )
            logger.info("Input handler started")
        except Exception as e:
            logger.warning("No input handler: %s (mouse/keyboard won't work)", e)

        try:
            while self._running:
                start = time.monotonic()

                # Update clock
                self.status_bar.update_time(time.strftime("%H:%M"))

                # Animate
                self.anim_controller.tick()

                # Render widgets to pixel buffer
                self.render_frame()

                # Push pixel buffer to display
                ui_buf = SurfaceBuffer(
                    width=self.width,
                    height=self.height,
                    stride=self.width * 4,
                    data=self.buf,
                )
                self.renderer.attach_buffer(ui_surface_id, ui_buf)

                # Create a fake surface for the render list
                class FakeSurface:
                    x = 0
                    y = 0
                    width = self.width
                    height = self.height

                fake = FakeSurface()
                fake.width = self.width
                fake.height = self.height
                self.renderer._surface_buffers[id(fake)] = ui_buf
                self.renderer.render_frame([fake])

                # Frame pacing
                elapsed = time.monotonic() - start
                sleep_time = frame_time - elapsed
                if sleep_time > 0:
                    await asyncio.sleep(sleep_time)
                else:
                    await asyncio.sleep(0)

        except (KeyboardInterrupt, asyncio.CancelledError):
            logger.info("Shutting down...")
        finally:
            self._running = False
            if input_task:
                input_task.cancel()
            self.renderer.shutdown()

    def stop(self):
        self._running = False


def main():
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s [%(name)s] %(message)s",
    )

    ui = ClaudeOSUI(DISPLAY_WIDTH, DISPLAY_HEIGHT)

    def handle_signal(signum, frame):
        logger.info("Signal %d, stopping", signum)
        ui.stop()

    signal.signal(signal.SIGTERM, handle_signal)
    signal.signal(signal.SIGINT, handle_signal)

    logger.info("Claude-OS UI starting (%dx%d @ %dfps)",
                DISPLAY_WIDTH, DISPLAY_HEIGHT, TARGET_FPS)
    asyncio.run(ui.run())
    logger.info("Claude-OS UI stopped")


if __name__ == "__main__":
    main()
