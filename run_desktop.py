#!/usr/bin/env python3
"""
Claude-OS Desktop Demo

Runs the full visual OS in a desktop window using pygame.
Simulates a phone-sized display (360x720) with touch input via mouse,
keyboard input, and 60fps rendering.

Controls:
    Mouse click  = Touch tap
    Mouse drag   = Touch drag (scroll, swipe)
    Keyboard     = On-screen keyboard input
    ESC          = Exit

Usage:
    pip install pygame
    python run_desktop.py
"""

import os
import sys
import time

# Add source directories to path
PROJECT_ROOT = os.path.dirname(os.path.abspath(__file__))
for subdir in [
    "ui/toolkit", "ui/screens", "ui/apps", "ui/vision",
    "ui/compositor", "ui/display",
]:
    sys.path.insert(0, os.path.join(PROJECT_ROOT, subdir))

from theme import Colors, Color, Typography, Spacing
from widget import Widget, Size, EdgeInsets, Align, Direction, Event, EventType, _fill_rect
from widgets import Container, Label, Button, ScrollView, Spacer, Divider
from font import FontRenderer
from lock_screen import LockScreen
from home_screen import HomeScreen, MessageRole
from status_bar_widget import StatusBarWidget
from keyboard_widget import KeyboardWidget
from notification_panel import NotificationPanel
from app_drawer import AppDrawer
from window_manager import WindowManager
from animation import AnimationController, ThemeManager, ThemeMode

# Screen dimensions (phone-sized)
SCREEN_W = 360
SCREEN_H = 720
FPS = 60
WINDOW_TITLE = "Claude-OS"


class DesktopOS:
    """
    Main desktop emulator that wires up all OS screens
    and renders them to a pygame window.
    """

    def __init__(self):
        self.width = SCREEN_W
        self.height = SCREEN_H
        self.buf = bytearray(self.width * self.height * 4)

        # Animation
        self.anim_controller = AnimationController()
        self.theme_manager = ThemeManager()

        # State
        self.screen = "lock"  # lock, home, app_drawer
        self.keyboard_visible = False
        self.notification_visible = False

        # Build screens
        self._build_screens()

        # Mouse state
        self._mouse_down = False
        self._mouse_x = 0
        self._mouse_y = 0
        self._drag_start_x = 0
        self._drag_start_y = 0

    def _build_screens(self):
        # Lock screen
        self.lock_screen = LockScreen(
            on_unlock=self._on_unlock,
            pin_required=True,
        )
        self.lock_screen.set_pin("1234")

        # Status bar
        self.status_bar = StatusBarWidget()
        self.status_bar.update_time(time.strftime("%H:%M"))
        self.status_bar.update_battery(85, False)
        self.status_bar.update_wifi(3)

        # Home screen (Claude chat)
        self.home_screen = HomeScreen(
            on_send_message=self._on_send_message,
        )
        # Add welcome message
        self.home_screen.add_message(
            MessageRole.CLAUDE,
            "Hello! I'm Claude, your AI-powered operating system. "
            "How can I help you today?"
        )

        # Keyboard
        self.keyboard = KeyboardWidget(
            on_key=self._on_key_press,
        )

        # Notification panel
        self.notification_panel = NotificationPanel()
        self.notification_panel.add_notification(
            "Claude", "Welcome", "Tap to chat with Claude"
        )

        # App drawer
        self.app_drawer = AppDrawer(
            on_launch=self._on_app_launch,
        )

    def _on_unlock(self):
        self.screen = "home"

    def _on_send_message(self, text: str):
        # Simulate Claude response
        self.home_screen.set_typing(True)
        # In a real implementation, this would call the Claude API
        # For demo, we echo back after a short delay
        self._pending_response = text
        self._response_time = time.monotonic() + 1.5

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
        self.home_screen.add_message(
            MessageRole.SYSTEM,
            f"Launched {app_name}"
        )

    def tick(self):
        """Update state each frame."""
        # Update clock
        self.status_bar.update_time(time.strftime("%H:%M"))

        # Animation tick
        self.anim_controller.tick()

        # Handle pending Claude response
        if hasattr(self, '_pending_response') and self._pending_response:
            if time.monotonic() >= self._response_time:
                self.home_screen.set_typing(False)
                self.home_screen.add_message(
                    MessageRole.CLAUDE,
                    f'You said: "{self._pending_response}". '
                    f"I'm running as a demo right now, but in the full OS "
                    f"I'd process this through the Claude API!"
                )
                self._pending_response = None

    def render(self):
        """Render the current frame to self.buf."""
        # Clear buffer
        bg = Colors.BACKGROUND
        pixel = bytes([bg.b, bg.g, bg.r, bg.a]) * self.width
        for y in range(self.height):
            off = y * self.width * 4
            self.buf[off:off + len(pixel)] = pixel

        if self.screen == "lock":
            self.lock_screen.layout(0, 0, self.width, self.height)
            self.lock_screen.draw(self.buf, self.width, self.height)
        elif self.screen == "home":
            # Status bar
            self.status_bar.layout(0, 0, self.width, 32)
            self.status_bar.draw(self.buf, self.width, self.height)

            # Home screen (chat)
            chat_h = self.height - 32
            if self.keyboard_visible:
                chat_h -= 260
            self.home_screen.layout(0, 32, self.width, chat_h)
            self.home_screen.draw(self.buf, self.width, self.height, 0, 0)

            # Keyboard
            if self.keyboard_visible:
                kb_y = self.height - 260
                self.keyboard.layout(0, kb_y, self.width, 260)
                self.keyboard.draw(self.buf, self.width, self.height)

            # Notification panel overlay
            if self.notification_visible:
                self.notification_panel.layout(0, 32, self.width, 300)
                self.notification_panel.draw(self.buf, self.width, self.height, 0, 0)

        elif self.screen == "app_drawer":
            # Status bar
            self.status_bar.layout(0, 0, self.width, 32)
            self.status_bar.draw(self.buf, self.width, self.height)

            # App drawer
            self.app_drawer.layout(0, 32, self.width, self.height - 32)
            self.app_drawer.draw(self.buf, self.width, self.height, 0, 0)

    def handle_mouse_down(self, x: int, y: int):
        self._mouse_down = True
        self._mouse_x = x
        self._mouse_y = y
        self._drag_start_x = x
        self._drag_start_y = y

        # Dispatch touch event to active screen
        event = Event(type=EventType.TOUCH_DOWN, x=x, y=y)

        if self.screen == "lock":
            self.lock_screen.on_event(event)
        elif self.screen == "home":
            if self.notification_visible and y < 332:
                self.notification_panel.on_event(event)
            elif self.keyboard_visible and y >= self.height - 260:
                self.keyboard.on_event(event)
            else:
                # Check if tapped on input bar area (show keyboard)
                if y > self.height - 80 and not self.keyboard_visible:
                    self.keyboard_visible = True
                else:
                    self.home_screen.on_event(event)
        elif self.screen == "app_drawer":
            self.app_drawer.on_event(event)

    def handle_mouse_up(self, x: int, y: int):
        if not self._mouse_down:
            return
        self._mouse_down = False

        dx = x - self._drag_start_x
        dy = y - self._drag_start_y

        event = Event(type=EventType.TOUCH_UP, x=x, y=y)

        if self.screen == "lock":
            self.lock_screen.on_event(event)
        elif self.screen == "home":
            # Swipe down from top → notification panel
            if self._drag_start_y < 40 and dy > 80:
                self.notification_visible = not self.notification_visible
            # Swipe up from bottom → app drawer
            elif self._drag_start_y > self.height - 40 and dy < -80:
                self.screen = "app_drawer"
            elif self.keyboard_visible and y >= self.height - 260:
                self.keyboard.on_event(event)
            elif self.notification_visible and y < 332:
                self.notification_panel.on_event(event)
            else:
                self.home_screen.on_event(event)
        elif self.screen == "app_drawer":
            # Swipe down to close app drawer
            if dy > 80:
                self.screen = "home"
            else:
                self.app_drawer.on_event(event)

    def handle_mouse_motion(self, x: int, y: int):
        if self._mouse_down:
            event = Event(type=EventType.TOUCH_MOVE, x=x, y=y)
            if self.screen == "lock":
                self.lock_screen.on_event(event)

    def handle_key(self, key_name: str):
        """Handle physical keyboard input (for convenience)."""
        if key_name == "escape":
            return "quit"

        # Lock screen: route number keys to PIN entry
        if self.screen == "lock":
            if key_name in "0123456789" and len(key_name) == 1:
                # Auto-swipe to PIN view if not showing yet
                if not self.lock_screen._show_pin:
                    self.lock_screen._show_pin = True
                    self.lock_screen._build_pin_ui()
                self.lock_screen._on_pin_key(key_name)
            elif key_name == "backspace":
                if self.lock_screen._show_pin:
                    self.lock_screen._on_pin_key("DEL")
            return None

        # Home screen
        if key_name == "backspace":
            if self.screen == "home":
                self.home_screen.input_bar.append_char("BACKSPACE")
        elif key_name == "return":
            if self.screen == "home":
                self.home_screen.input_bar.send()
                self.keyboard_visible = False
        elif key_name == "space":
            if self.screen == "home":
                self.home_screen.input_bar.append_char(" ")
        elif key_name == "tab":
            # Toggle keyboard
            self.keyboard_visible = not self.keyboard_visible
        elif len(key_name) == 1 and key_name.isprintable():
            if self.screen == "home":
                self.home_screen.input_bar.append_char(key_name)

        return None


def main():
    try:
        import pygame
    except ImportError:
        print("=" * 60)
        print("  pygame is required for the desktop demo")
        print()
        print("  Install it with:")
        print("    pip install pygame")
        print("=" * 60)
        sys.exit(1)

    pygame.init()

    # Create resizable window — default 1x scale, fits most screens
    SCALE = 1
    display_w = SCREEN_W * SCALE
    display_h = SCREEN_H * SCALE

    screen = pygame.display.set_mode(
        (display_w, display_h), pygame.RESIZABLE
    )
    pygame.display.set_caption(WINDOW_TITLE)
    clock = pygame.time.Clock()

    os_app = DesktopOS()

    # Create a pygame surface for the phone screen
    phone_surface = pygame.Surface((SCREEN_W, SCREEN_H))

    # Track current display size for coordinate mapping
    cur_w, cur_h = display_w, display_h

    def mouse_to_phone(pos):
        """Map window mouse coordinates to phone coordinates."""
        mx = int(pos[0] * SCREEN_W / cur_w)
        my = int(pos[1] * SCREEN_H / cur_h)
        return max(0, min(mx, SCREEN_W - 1)), max(0, min(my, SCREEN_H - 1))

    running = True
    while running:
        # Handle events
        for event in pygame.event.get():
            if event.type == pygame.QUIT:
                running = False

            elif event.type == pygame.VIDEORESIZE:
                cur_w, cur_h = event.w, event.h
                screen = pygame.display.set_mode(
                    (cur_w, cur_h), pygame.RESIZABLE
                )

            elif event.type == pygame.MOUSEBUTTONDOWN:
                mx, my = mouse_to_phone(event.pos)
                os_app.handle_mouse_down(mx, my)

            elif event.type == pygame.MOUSEBUTTONUP:
                mx, my = mouse_to_phone(event.pos)
                os_app.handle_mouse_up(mx, my)

            elif event.type == pygame.MOUSEMOTION:
                if pygame.mouse.get_pressed()[0]:
                    mx, my = mouse_to_phone(event.pos)
                    os_app.handle_mouse_motion(mx, my)

            elif event.type == pygame.KEYDOWN:
                key_name = pygame.key.name(event.key)
                result = os_app.handle_key(key_name)
                if result == "quit":
                    running = False

        # Update
        os_app.tick()

        # Render to pixel buffer
        os_app.render()

        # Convert BGRA buffer → RGBA for pygame (swap R and B channels)
        rgba_buf = bytearray(len(os_app.buf))
        for i in range(0, len(os_app.buf), 4):
            rgba_buf[i] = os_app.buf[i + 2]      # R
            rgba_buf[i + 1] = os_app.buf[i + 1]  # G
            rgba_buf[i + 2] = os_app.buf[i]      # B
            rgba_buf[i + 3] = 255                 # A
        phone_surface = pygame.image.frombuffer(
            bytes(rgba_buf), (SCREEN_W, SCREEN_H), "RGBA"
        )

        # Scale up and blit to display
        scaled = pygame.transform.scale(phone_surface, (cur_w, cur_h))
        screen.blit(scaled, (0, 0))
        pygame.display.flip()

        clock.tick(FPS)

    pygame.quit()


if __name__ == "__main__":
    print("=" * 60)
    print("  Claude-OS Desktop Demo")
    print("  " + "=" * 56)
    print(f"  Resolution: {SCREEN_W}x{SCREEN_H} @ {FPS}fps (resizable)")
    print()
    print("  Controls:")
    print("    Mouse click     = Touch tap")
    print("    Mouse drag      = Swipe gesture")
    print("    Type on keyboard = Input text")
    print("    Tab             = Toggle on-screen keyboard")
    print("    Enter           = Send message")
    print("    ESC             = Exit")
    print()
    print("  Gestures:")
    print("    Swipe down from top    = Notifications")
    print("    Swipe up from bottom   = App drawer")
    print("    Swipe down in drawer   = Close drawer")
    print()
    print("  PIN: 1234")
    print("=" * 60)
    print()
    main()
