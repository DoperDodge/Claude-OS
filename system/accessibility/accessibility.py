"""
Claude-OS Accessibility Features

Makes Claude-OS usable for people with disabilities.
Claude itself serves as the primary accessibility tool —
voice interaction is a natural accessible interface.

Features:
- Screen reader (Claude reads screen content aloud)
- High contrast / large text modes
- Color correction for color blindness
- Haptic feedback control
- Voice-only mode (no touch required)
- Switch access support
"""

import asyncio
import json
import logging
import os
import subprocess
from dataclasses import dataclass, field
from pathlib import Path

logger = logging.getLogger("accessibility")

CONFIG_DIR = Path(os.environ.get("CLAUDE_OS_CONFIG", "/etc/claude-os"))
A11Y_CONFIG = CONFIG_DIR / "accessibility.json"


@dataclass
class AccessibilitySettings:
    """All accessibility configuration."""

    # Display
    large_text: bool = False
    text_scale: float = 1.0  # 1.0 = normal, up to 3.0
    high_contrast: bool = False
    color_inversion: bool = False
    color_correction: str = "none"  # "none", "deuteranomaly", "protanomaly", "tritanomaly"
    reduce_motion: bool = False
    reduce_transparency: bool = False

    # Audio & Speech
    screen_reader: bool = False
    speech_rate: float = 1.0  # 0.5 to 2.0
    voice_only_mode: bool = False
    mono_audio: bool = False
    caption_display: bool = False

    # Touch & Input
    touch_hold_delay_ms: int = 400
    ignore_repeated_touches: bool = False
    repeat_filter_ms: int = 100
    switch_access: bool = False
    haptic_feedback: bool = True
    haptic_strength: str = "medium"  # "light", "medium", "strong"

    # Claude-specific
    simple_language: bool = False  # Claude uses simpler language
    verbose_descriptions: bool = False  # Claude gives more detailed descriptions
    auto_read_responses: bool = False  # Automatically speak Claude's responses

    def to_dict(self) -> dict:
        return {
            "display": {
                "large_text": self.large_text,
                "text_scale": self.text_scale,
                "high_contrast": self.high_contrast,
                "color_inversion": self.color_inversion,
                "color_correction": self.color_correction,
                "reduce_motion": self.reduce_motion,
                "reduce_transparency": self.reduce_transparency,
            },
            "audio": {
                "screen_reader": self.screen_reader,
                "speech_rate": self.speech_rate,
                "voice_only_mode": self.voice_only_mode,
                "mono_audio": self.mono_audio,
                "caption_display": self.caption_display,
            },
            "input": {
                "touch_hold_delay_ms": self.touch_hold_delay_ms,
                "ignore_repeated_touches": self.ignore_repeated_touches,
                "repeat_filter_ms": self.repeat_filter_ms,
                "switch_access": self.switch_access,
                "haptic_feedback": self.haptic_feedback,
                "haptic_strength": self.haptic_strength,
            },
            "claude": {
                "simple_language": self.simple_language,
                "verbose_descriptions": self.verbose_descriptions,
                "auto_read_responses": self.auto_read_responses,
            },
        }


class AccessibilityManager:
    """
    Manages accessibility features for Claude-OS.

    Claude-OS has a unique advantage for accessibility: the primary
    interface IS a conversational AI. Users can interact entirely
    through voice, making the OS inherently more accessible than
    traditional touch-first mobile OSes.
    """

    def __init__(self, event_bus=None):
        self.event_bus = event_bus
        self.settings = AccessibilitySettings()

    def load(self):
        """Load accessibility settings from disk."""
        if A11Y_CONFIG.exists():
            try:
                data = json.loads(A11Y_CONFIG.read_text())
                self._apply_config(data)
                logger.info("Loaded accessibility settings")
            except (json.JSONDecodeError, OSError) as e:
                logger.error("Failed to load a11y settings: %s", e)

    def save(self):
        """Save accessibility settings to disk."""
        try:
            CONFIG_DIR.mkdir(parents=True, exist_ok=True)
            A11Y_CONFIG.write_text(
                json.dumps(self.settings.to_dict(), indent=2)
            )
        except OSError as e:
            logger.error("Failed to save a11y settings: %s", e)

    def _apply_config(self, data: dict):
        """Apply a config dict to settings."""
        display = data.get("display", {})
        audio = data.get("audio", {})
        inp = data.get("input", {})
        claude = data.get("claude", {})

        for key, val in display.items():
            if hasattr(self.settings, key):
                setattr(self.settings, key, val)
        for key, val in audio.items():
            if hasattr(self.settings, key):
                setattr(self.settings, key, val)
        for key, val in inp.items():
            if hasattr(self.settings, key):
                setattr(self.settings, key, val)
        for key, val in claude.items():
            if hasattr(self.settings, key):
                setattr(self.settings, key, val)

    # --- Feature Controls ---

    def get_settings(self) -> dict:
        """Get all accessibility settings."""
        return self.settings.to_dict()

    async def update_settings(self, changes: dict) -> dict:
        """
        Update accessibility settings.

        Args:
            changes: Flat dict of setting_name -> value
        """
        for key, value in changes.items():
            if hasattr(self.settings, key):
                setattr(self.settings, key, value)
                logger.info("A11y setting changed: %s = %s", key, value)
            else:
                logger.warning("Unknown a11y setting: %s", key)

        self.save()
        await self._apply_settings()

        if self.event_bus:
            await self.event_bus.emit("accessibility.changed", changes)

        return self.settings.to_dict()

    async def enable_screen_reader(self) -> dict:
        """Enable the screen reader."""
        self.settings.screen_reader = True
        self.settings.auto_read_responses = True
        self.save()
        await self._apply_settings()
        return {"screen_reader": True, "auto_read_responses": True}

    async def enable_voice_only_mode(self) -> dict:
        """
        Enable voice-only mode.

        In this mode, all interaction is through voice — no touch required.
        Claude reads everything aloud and listens for voice commands.
        """
        self.settings.voice_only_mode = True
        self.settings.screen_reader = True
        self.settings.auto_read_responses = True
        self.settings.verbose_descriptions = True
        self.save()
        await self._apply_settings()

        logger.info("Voice-only mode enabled")
        return {"voice_only_mode": True}

    async def enable_high_contrast(self) -> dict:
        """Enable high contrast display mode."""
        self.settings.high_contrast = True
        self.settings.reduce_transparency = True
        self.save()
        await self._apply_settings()
        return {"high_contrast": True}

    async def set_text_scale(self, scale: float) -> dict:
        """Set text scaling factor (0.5 to 3.0)."""
        scale = max(0.5, min(3.0, scale))
        self.settings.text_scale = scale
        self.settings.large_text = scale > 1.3
        self.save()
        await self._apply_settings()
        return {"text_scale": scale, "large_text": self.settings.large_text}

    async def set_color_correction(self, mode: str) -> dict:
        """
        Set color correction mode for color blindness.

        Modes: "none", "deuteranomaly" (red-green), "protanomaly" (red),
               "tritanomaly" (blue-yellow)
        """
        valid_modes = ("none", "deuteranomaly", "protanomaly", "tritanomaly")
        if mode not in valid_modes:
            raise ValueError(f"Invalid mode. Options: {valid_modes}")

        self.settings.color_correction = mode
        self.save()
        await self._apply_settings()
        return {"color_correction": mode}

    def get_claude_prompt_modifiers(self) -> str:
        """
        Get Claude system prompt modifications based on accessibility settings.

        This is injected into Claude's system prompt to adjust how it
        communicates with the user.
        """
        modifiers = []

        if self.settings.simple_language:
            modifiers.append(
                "Use simple, clear language. Short sentences. "
                "Avoid jargon and complex vocabulary."
            )

        if self.settings.verbose_descriptions:
            modifiers.append(
                "When describing UI elements, actions, or results, "
                "be extra descriptive. Include details about position, "
                "color, and state that a sighted user would see."
            )

        if self.settings.voice_only_mode:
            modifiers.append(
                "The user is in voice-only mode. Structure your responses "
                "for listening — use natural pauses, enumerate lists, "
                "and confirm actions verbally."
            )

        return " ".join(modifiers)

    # --- Apply Settings ---

    async def _apply_settings(self):
        """Apply current settings to the system."""
        # These would communicate with the compositor and other services
        # to actually change display and input behavior

        if self.settings.mono_audio:
            self._set_mono_audio(True)

        if self.settings.haptic_feedback:
            self._set_haptic_strength(self.settings.haptic_strength)

    def _set_mono_audio(self, enabled: bool):
        """Set mono audio output (merge L+R channels)."""
        try:
            # PulseAudio/PipeWire: remap channels
            if enabled:
                subprocess.run(
                    ["pactl", "load-module",
                     "module-remap-sink", "channels=1"],
                    capture_output=True, timeout=5,
                )
        except (FileNotFoundError, subprocess.TimeoutExpired):
            pass

    def _set_haptic_strength(self, strength: str):
        """Set haptic feedback strength."""
        strength_map = {"light": 1, "medium": 2, "strong": 3}
        level = strength_map.get(strength, 2)

        # Write to haptic driver (device-specific)
        haptic_path = "/sys/class/leds/vibrator/brightness"
        if os.path.exists(haptic_path):
            try:
                Path(haptic_path).write_text(str(level * 85))
            except (PermissionError, OSError):
                pass
