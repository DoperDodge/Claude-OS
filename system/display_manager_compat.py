"""Importable display manager utilities for testing."""

import os


def detect_display_backend_safe() -> str:
    """Detect display backend without starting the full display manager."""
    # Check fbdev first (simplest path)
    if os.path.exists("/dev/fb0"):
        return "fbdev"
    for dev in ["/dev/dri/card0", "/dev/dri/card1"]:
        if os.path.exists(dev):
            return "drm"
    return "stub"
