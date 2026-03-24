"""
Claude Vision Tools

Tools that give Claude the ability to see and interact with the display.
Registered with the ChatEngine so Claude can invoke them during conversations.

Tools:
    - take_screenshot: Capture the current screen as a base64 PNG
    - read_screen: Extract all visible text and interactive elements
    - describe_screen: Get a human-readable description of the screen
    - find_text: Search for text on the current screen
    - generate_ui: Create a dynamic UI view from a specification
"""

import asyncio
import json
import logging
import os
import sys
import time

logger = logging.getLogger("vision_tools")

# Add vision module to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "../../ui/vision"))
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "../../ui/toolkit"))


class VisionToolManager:
    """
    Manages vision-related tools for Claude.

    Holds references to the compositor's display buffer and widget tree
    so it can capture screenshots and read screen content.
    """

    def __init__(self):
        self._display_buffer: bytearray | None = None
        self._display_width: int = 360
        self._display_height: int = 720
        self._root_widget = None
        self._screen_name: str = "home"
        self._screenshot_capture = None
        self._screen_reader = None
        self._dynamic_builder = None
        self._ui_callback = None  # Called when Claude generates UI

    def initialize(self, display_buffer: bytearray = None,
                   width: int = 360, height: int = 720,
                   root_widget=None):
        """
        Initialize with references to the display system.

        Args:
            display_buffer: The compositor's BGRA pixel buffer
            width: Display width
            height: Display height
            root_widget: Root of the current widget tree
        """
        from screenshot import ScreenshotCapture, ScreenReader
        from dynamic_ui import DynamicViewBuilder

        self._display_buffer = display_buffer
        self._display_width = width
        self._display_height = height
        self._root_widget = root_widget
        self._screenshot_capture = ScreenshotCapture()
        self._screen_reader = ScreenReader()
        self._dynamic_builder = DynamicViewBuilder()

    def set_display(self, buffer: bytearray, width: int, height: int):
        """Update the display buffer reference."""
        self._display_buffer = buffer
        self._display_width = width
        self._display_height = height

    def set_root_widget(self, widget):
        """Update the root widget reference."""
        self._root_widget = widget

    def set_screen_name(self, name: str):
        """Update current screen name."""
        self._screen_name = name

    def set_ui_callback(self, callback):
        """Set callback for when Claude generates dynamic UI."""
        self._ui_callback = callback

    def register_tools(self, chat_engine):
        """Register all vision tools with the chat engine."""
        chat_engine.register_tool(
            "take_screenshot",
            self.take_screenshot,
            "Capture the current screen as a PNG image. Returns base64-encoded PNG data.",
            {
                "type": "object",
                "properties": {
                    "region": {
                        "type": "object",
                        "description": "Optional region to capture (x, y, width, height)",
                        "properties": {
                            "x": {"type": "integer"},
                            "y": {"type": "integer"},
                            "width": {"type": "integer"},
                            "height": {"type": "integer"},
                        },
                    },
                },
            },
        )

        chat_engine.register_tool(
            "read_screen",
            self.read_screen,
            "Read all visible text and interactive elements on the current screen. "
            "Returns text content, positions, and widget types.",
            {
                "type": "object",
                "properties": {},
            },
        )

        chat_engine.register_tool(
            "describe_screen",
            self.describe_screen,
            "Get a human-readable description of what's currently displayed.",
            {
                "type": "object",
                "properties": {},
            },
        )

        chat_engine.register_tool(
            "find_text",
            self.find_text,
            "Search for specific text on the current screen.",
            {
                "type": "object",
                "properties": {
                    "query": {
                        "type": "string",
                        "description": "Text to search for",
                    },
                },
                "required": ["query"],
            },
        )

        chat_engine.register_tool(
            "generate_ui",
            self.generate_ui,
            "Generate a dynamic UI view. Supported types: checklist, calendar, info, form.",
            {
                "type": "object",
                "properties": {
                    "view_spec": {
                        "type": "object",
                        "description": "View specification with 'type' key",
                    },
                },
                "required": ["view_spec"],
            },
        )

        logger.info("Registered 5 vision tools with chat engine")

    # --- Tool Handlers ---

    async def take_screenshot(self, region: dict = None) -> dict:
        """Capture the current screen."""
        if not self._display_buffer or not self._screenshot_capture:
            return {"error": "Display not initialized"}

        from screenshot import ScreenRegion

        screen_region = None
        if region:
            screen_region = ScreenRegion(
                x=region.get("x", 0),
                y=region.get("y", 0),
                width=region.get("width", self._display_width),
                height=region.get("height", self._display_height),
            )

        b64 = await asyncio.to_thread(
            self._screenshot_capture.capture_base64,
            self._display_buffer,
            self._display_width,
            self._display_height,
            screen_region,
        )

        return {
            "image_base64": b64,
            "width": self._display_width,
            "height": self._display_height,
            "format": "png",
            "screen": self._screen_name,
            "timestamp": time.time(),
        }

    async def read_screen(self) -> dict:
        """Read all visible text and elements on screen."""
        if not self._screen_reader:
            return {"error": "Screen reader not initialized"}

        desc = self._screen_reader.read_screen(
            self._root_widget,
            screen_name=self._screen_name,
            screen_width=self._display_width,
            screen_height=self._display_height,
        )

        return desc.to_dict()

    async def describe_screen(self) -> dict:
        """Get a human-readable screen description."""
        if not self._screen_reader:
            return {"error": "Screen reader not initialized"}

        desc = self._screen_reader.read_screen(
            self._root_widget,
            screen_name=self._screen_name,
            screen_width=self._display_width,
            screen_height=self._display_height,
        )

        return {
            "description": desc.to_text(),
            "screen": self._screen_name,
            "timestamp": time.time(),
        }

    async def find_text(self, query: str) -> dict:
        """Find text on the current screen."""
        if not self._screen_reader:
            return {"error": "Screen reader not initialized"}

        results = self._screen_reader.find_text(self._root_widget, query)

        return {
            "query": query,
            "found": len(results),
            "matches": [
                {
                    "text": r.text,
                    "x": r.x,
                    "y": r.y,
                    "width": r.width,
                    "height": r.height,
                    "widget_type": r.widget_type,
                }
                for r in results
            ],
        }

    async def generate_ui(self, view_spec: dict) -> dict:
        """Generate a dynamic UI view."""
        if not self._dynamic_builder:
            return {"error": "Dynamic builder not initialized"}

        widget = self._dynamic_builder.build(view_spec)

        if widget is None:
            return {
                "error": f"Unsupported view type: {view_spec.get('type', 'unknown')}",
            }

        if self._ui_callback:
            self._ui_callback(widget, view_spec)

        return {
            "success": True,
            "view_type": view_spec.get("type", ""),
            "widget_class": type(widget).__name__,
        }
