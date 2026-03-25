"""
Claude-OS Widget Toolkit

A Cairo-based widget system for rendering UI elements to the compositor's
framebuffer. All widgets use the theme system for consistent styling.
"""

from ui.widgets.base import (
    Widget,
    Container,
    Rect,
    Size,
    TouchEvent,
    TouchAction,
)
from ui.widgets.text import Label, TextInput
from ui.widgets.buttons import Button, IconButton
from ui.widgets.layout import VStack, HStack, Spacer, Padding
from ui.widgets.scrolling import ScrollView

__all__ = [
    "Widget",
    "Container",
    "Rect",
    "Size",
    "TouchEvent",
    "TouchAction",
    "Label",
    "TextInput",
    "Button",
    "IconButton",
    "VStack",
    "HStack",
    "Spacer",
    "Padding",
    "ScrollView",
]
