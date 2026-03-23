"""
Audio control bridge service.

Manages volume levels and mute state via ALSA (amixer).
"""

import asyncio
import logging
import subprocess

from event_bus import EventBus

logger = logging.getLogger("bridge.audio")


class AudioBridgeService:
    """Bridge service for audio control."""

    def __init__(self, event_bus: EventBus):
        self.event_bus = event_bus

    async def handle_get_volume(self, body: dict) -> dict:
        """Get current volume level and mute state."""
        return self._get_volume()

    async def handle_set_volume(self, body: dict) -> dict:
        """Set volume level (0-100)."""
        level = body.get("level")
        if level is None:
            raise ValueError("Missing required field: level")

        level = max(0, min(100, int(level)))

        try:
            subprocess.run(
                ["amixer", "sset", "Master", f"{level}%"],
                capture_output=True, timeout=5,
            )
            await self.event_bus.emit("audio.volume_changed", {"level": level})
            return {"volume": level}
        except FileNotFoundError:
            raise RuntimeError("amixer not available")

    async def handle_mute(self, body: dict) -> dict:
        """Toggle or set mute state."""
        mute = body.get("mute")  # True, False, or None (toggle)

        try:
            if mute is None:
                # Toggle
                subprocess.run(
                    ["amixer", "sset", "Master", "toggle"],
                    capture_output=True, timeout=5,
                )
            elif mute:
                subprocess.run(
                    ["amixer", "sset", "Master", "mute"],
                    capture_output=True, timeout=5,
                )
            else:
                subprocess.run(
                    ["amixer", "sset", "Master", "unmute"],
                    capture_output=True, timeout=5,
                )

            status = self._get_volume()
            await self.event_bus.emit("audio.mute_changed",
                                      {"muted": status.get("muted", False)})
            return status
        except FileNotFoundError:
            raise RuntimeError("amixer not available")

    def _get_volume(self) -> dict:
        """Read current volume from amixer."""
        try:
            result = subprocess.run(
                ["amixer", "sget", "Master"],
                capture_output=True, text=True, timeout=5,
            )

            volume = 0
            muted = False

            for line in result.stdout.split("\n"):
                if "%" in line:
                    # Parse "[75%] [on]" or "[75%] [off]"
                    start = line.index("[") + 1
                    end = line.index("%")
                    volume = int(line[start:end])
                    muted = "[off]" in line
                    break

            return {"volume": volume, "muted": muted}
        except (FileNotFoundError, subprocess.TimeoutExpired):
            return {"volume": 0, "muted": False, "error": "amixer not available"}
        except (ValueError, IndexError):
            return {"volume": 0, "muted": False, "error": "Could not parse volume"}
