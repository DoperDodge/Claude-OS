"""
Claude-OS App Launcher

The primary system launcher — replaces a traditional home screen.
Launches as a fullscreen Wayland client and presents the Claude chat
interface as the default view.

Boot flow:
    display-manager → compositor → launcher.py (this file)
                                      ├── Lock Screen (initial view)
                                      ├── Chat UI (default home view)
                                      ├── Voice engine
                                      ├── System tools
                                      ├── Notification panel (swipe down)
                                      └── App drawer (swipe up)

The launcher is always running. Swiping home returns here.

Design:
    Claude's warm, intelligent aesthetic × Apple's motion design.
    All views use the unified theme system. Transitions are spring-based.
"""

import asyncio
import logging
import os
import signal
import sys

# Add project paths
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "../system/bridge"))

from chat.chat_engine import ChatEngine
from voice.voice_engine import VoiceEngine
from tools.system_tools import SystemToolManager

logger = logging.getLogger("launcher")


class ClaudeAppState:
    """Tracks the current state of the launcher."""
    LOCK_SCREEN = "lock"         # Lock screen (initial)
    CHAT = "chat"                # Main chat view (default after unlock)
    APP_DRAWER = "drawer"        # App drawer overlay
    SETTINGS = "settings"        # Settings panel
    NOTIFICATION_PANEL = "notifications"  # Notification panel


class Launcher:
    """
    Claude-OS system launcher.

    Acts as the home screen and primary user interface. All interaction
    flows through the Claude chat — including system controls, app
    launching, and information queries.

    UI flow:
        Lock Screen → (swipe up / PIN) → Chat Home
        Chat Home → (swipe down from top) → Notification Panel
        Chat Home → (swipe up from bottom) → App Drawer
        Any screen → (swipe up from very bottom) → Chat Home

    Design integrations:
        - Status bar: always visible (frosted glass, Dynamic Island)
        - Chat: message bubbles with Claude terracotta (user) / white (Claude)
        - Transitions: spring-based page transitions
        - Keyboard: spring slide-up from bottom
    """

    def __init__(self):
        self.state = ClaudeAppState.LOCK_SCREEN

        # Core components
        self.chat = ChatEngine()
        self.voice = VoiceEngine()
        self.tools = SystemToolManager()

        # UI state
        self._locked = True
        self._notification_panel_open = False
        self._app_drawer_open = False

        self._running = False

    async def start(self):
        """Start the launcher and all subsystems."""
        self._running = True
        logger.info("Claude-OS Launcher starting")

        # Initialize subsystems
        await self.tools.initialize()
        self.chat.set_tool_manager(self.tools)

        # Register system tools with the chat engine
        self._register_tools()

        # Start background services
        tasks = [
            self._run_chat(),
            self.voice.start(on_transcript=self._handle_voice_input),
            self.tools.start_monitoring(),
        ]

        logger.info("Claude-OS Launcher ready — lock screen active")
        await asyncio.gather(*tasks)

    def _register_tools(self):
        """Register system tools that Claude can invoke during chat."""
        self.chat.register_tool("wifi_scan", self.tools.wifi_scan,
                                "Scan for available WiFi networks")
        self.chat.register_tool("wifi_connect", self.tools.wifi_connect,
                                "Connect to a WiFi network")
        self.chat.register_tool("wifi_status", self.tools.wifi_status,
                                "Check current WiFi connection status")
        self.chat.register_tool("get_battery", self.tools.get_battery,
                                "Check battery level and charging state")
        self.chat.register_tool("set_brightness", self.tools.set_brightness,
                                "Set screen brightness (0-100)")
        self.chat.register_tool("set_volume", self.tools.set_volume,
                                "Set audio volume (0-100)")
        self.chat.register_tool("system_info", self.tools.system_info,
                                "Get device system information")

    async def _run_chat(self):
        """Run the chat interface event loop."""
        while self._running:
            await asyncio.sleep(0.1)

    async def _handle_voice_input(self, transcript: str):
        """Handle transcribed voice input — send to chat engine."""
        if transcript.strip():
            logger.info("Voice input: %s", transcript)
            response = await self.chat.send_message(transcript, source="voice")
            # Speak the response back
            await self.voice.speak(response.text)

    async def handle_touch_input(self, text: str):
        """Handle text typed via the on-screen keyboard."""
        response = await self.chat.send_message(text, source="keyboard")
        return response

    def handle_gesture(self, gesture: str, data: dict):
        """
        Handle compositor gestures forwarded to the launcher.

        Gesture → State transitions:
        - swipe_up (from chat) → app drawer
        - swipe_down / notification_shade → notification panel
        - go_home → dismiss overlays, return to chat
        - swipe_right → back (dismiss current overlay)
        - tap (on lock screen) → wake / focus
        """
        if gesture == "swipe_up" and self.state == ClaudeAppState.CHAT:
            self.state = ClaudeAppState.APP_DRAWER
            self._app_drawer_open = True
            logger.info("Opened app drawer")

        elif gesture == "notification_shade":
            self.state = ClaudeAppState.NOTIFICATION_PANEL
            self._notification_panel_open = True
            logger.info("Opened notification panel")

        elif gesture == "go_home":
            self._dismiss_overlays()
            if self._locked:
                self.state = ClaudeAppState.LOCK_SCREEN
            else:
                self.state = ClaudeAppState.CHAT
            logger.info("Returned to %s", self.state)

        elif gesture == "swipe_right":
            # Back gesture — dismiss current overlay
            if self.state != ClaudeAppState.CHAT:
                self._dismiss_overlays()
                self.state = ClaudeAppState.CHAT

        elif gesture == "swipe_down" and self.state == ClaudeAppState.CHAT:
            self.state = ClaudeAppState.NOTIFICATION_PANEL
            self._notification_panel_open = True

    def _dismiss_overlays(self):
        """Dismiss all overlays and return to base state."""
        self._notification_panel_open = False
        self._app_drawer_open = False

    def handle_unlock(self):
        """Handle successful unlock from lock screen."""
        self._locked = False
        self.state = ClaudeAppState.CHAT
        logger.info("Device unlocked — chat view active")

    def handle_lock(self):
        """Lock the device."""
        self._locked = True
        self.state = ClaudeAppState.LOCK_SCREEN
        self._dismiss_overlays()
        logger.info("Device locked")

    async def shutdown(self):
        """Shut down the launcher."""
        self._running = False
        await self.voice.stop()
        logger.info("Launcher shut down")

    def get_render_state(self) -> dict:
        """
        Return current UI state for the renderer.

        Provides all the data the rendering pipeline needs to draw
        the current screen, including animations, theme, and transitions.
        """
        return {
            "view": self.state,
            "locked": self._locked,
            "chat": self.chat.get_render_state(),
            "voice_listening": self.voice.is_listening,
            "overlays": {
                "notification_panel": self._notification_panel_open,
                "app_drawer": self._app_drawer_open,
            },
            # Chat UI design specs
            "chat_style": {
                "bubble_user": {
                    "color": "accent",         # Claude terracotta
                    "text_color": "white",
                    "radius": 20,
                    "tail_radius": 4,
                    "max_width": 0.78,
                    "shadow": "chat_bubble",
                    "alignment": "right",
                },
                "bubble_assistant": {
                    "color": "bg_elevated",    # White / dark card
                    "text_color": "text_primary",
                    "radius": 20,
                    "tail_radius": 4,
                    "max_width": 0.78,
                    "shadow": "chat_bubble",
                    "alignment": "left",
                },
                "input_bar": {
                    "height": 52,
                    "radius": 26,
                    "bg": "bg_secondary",
                    "placeholder": "Message Claude...",
                    "mic_button": True,
                },
                "typing_indicator": {
                    "dot_count": 3,
                    "dot_size": 8,
                    "animation": "ease_in_out",
                    "duration": 0.6,
                },
                "animation": {
                    "bubble_appear": {
                        "spring": {"damping": 0.7, "stiffness": 200},
                    },
                    "scroll": "smooth",
                },
            },
        }


def main():
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    )

    launcher = Launcher()
    loop = asyncio.new_event_loop()

    def handle_signal(sig):
        logger.info("Signal %s received", sig)
        loop.create_task(launcher.shutdown())
        loop.call_later(2, loop.stop)

    for sig in (signal.SIGTERM, signal.SIGINT):
        loop.add_signal_handler(sig, handle_signal, sig)

    try:
        loop.run_until_complete(launcher.start())
    except KeyboardInterrupt:
        loop.run_until_complete(launcher.shutdown())
    finally:
        loop.close()


if __name__ == "__main__":
    main()
