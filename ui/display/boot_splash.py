#!/usr/bin/env python3
"""
Claude-OS Boot Splash

Draws the Claude-OS boot splash screen — proof that the display pipeline
works end-to-end: QEMU virtio-gpu → kernel DRM → framebuffer → pixels.

Can be run directly on the device:
    python3 /opt/claude-os/ui/display/boot_splash.py

Tries DRM first (modern), falls back to framebuffer (legacy).
"""

import logging
import sys
import time

logging.basicConfig(level=logging.INFO, format="[%(name)s] %(message)s")
logger = logging.getLogger("boot_splash")


def draw_splash_fb():
    """Draw splash screen via framebuffer."""
    from framebuffer import Framebuffer

    with Framebuffer() as fb:
        w = fb.info.width
        h = fb.info.height

        # Dark background gradient (dark blue → darker blue)
        fb.gradient(10, 10, 40, 5, 5, 20)

        # Claude-OS "logo" — a centered rounded-ish rectangle
        logo_w = min(280, w - 40)
        logo_h = min(280, h // 3)
        logo_x = (w - logo_w) // 2
        logo_y = (h - logo_h) // 2 - 60

        # Orange accent (Claude's color)
        fb.rect(logo_x, logo_y, logo_w, logo_h, 217, 119, 52)

        # Inner dark rectangle
        border = 6
        fb.rect(logo_x + border, logo_y + border,
                logo_w - border * 2, logo_h - border * 2,
                15, 15, 45)

        # Simple "C" shape drawn with rectangles (pixel art style)
        cx = logo_x + logo_w // 2 - 40
        cy = logo_y + logo_h // 2 - 50
        bar = 16

        # Top horizontal bar of C
        fb.rect(cx + bar, cy, 80 - bar, bar, 217, 119, 52)
        # Left vertical bar of C
        fb.rect(cx, cy, bar, 100, 217, 119, 52)
        # Bottom horizontal bar of C
        fb.rect(cx + bar, cy + 100 - bar, 80 - bar, bar, 217, 119, 52)

        # Loading bar at the bottom
        bar_y = logo_y + logo_h + 40
        bar_w = logo_w
        bar_h = 8
        bar_x = logo_x

        # Bar background
        fb.rect(bar_x, bar_y, bar_w, bar_h, 30, 30, 60)

        # Animated loading bar
        for progress in range(0, bar_w, 4):
            fb.rect(bar_x, bar_y, progress, bar_h, 217, 119, 52)
            time.sleep(0.01)

        logger.info("Boot splash drawn via framebuffer (%dx%d)", w, h)

        # Keep splash visible
        time.sleep(2)


def draw_splash_drm():
    """Draw splash screen via DRM."""
    from drm_display import DRMDisplay

    with DRMDisplay() as drm:
        w = drm.mode.width
        h = drm.mode.height

        # Dark background
        drm.fill(10, 10, 40)

        # Logo rectangle (Claude orange)
        logo_w = min(280, w - 40)
        logo_h = min(280, h // 3)
        logo_x = (w - logo_w) // 2
        logo_y = (h - logo_h) // 2 - 60

        drm.rect(logo_x, logo_y, logo_w, logo_h, 217, 119, 52)

        # Inner dark
        border = 6
        drm.rect(logo_x + border, logo_y + border,
                 logo_w - border * 2, logo_h - border * 2,
                 15, 15, 45)

        # "C" shape
        cx = logo_x + logo_w // 2 - 40
        cy = logo_y + logo_h // 2 - 50
        bar = 16
        drm.rect(cx + bar, cy, 80 - bar, bar, 217, 119, 52)
        drm.rect(cx, cy, bar, 100, 217, 119, 52)
        drm.rect(cx + bar, cy + 100 - bar, 80 - bar, bar, 217, 119, 52)

        # Loading bar
        bar_y = logo_y + logo_h + 40
        bar_w = logo_w
        bar_h = 8
        bar_x = logo_x
        drm.rect(bar_x, bar_y, bar_w, bar_h, 30, 30, 60)

        drm.present()
        logger.info("Boot splash drawn via DRM (%dx%d)", w, h)

        # Animate loading bar
        for progress in range(0, bar_w, 4):
            drm.rect(bar_x, bar_y, progress, bar_h, 217, 119, 52)
            drm.present()
            time.sleep(0.01)

        time.sleep(2)


def main():
    """Draw boot splash using the best available backend."""
    # Try DRM first (modern path)
    try:
        if __import__('os').path.exists("/dev/dri/card0"):
            logger.info("Trying DRM display...")
            draw_splash_drm()
            return 0
    except Exception as e:
        logger.warning("DRM failed: %s", e)

    # Fall back to framebuffer
    try:
        if __import__('os').path.exists("/dev/fb0"):
            logger.info("Trying framebuffer display...")
            draw_splash_fb()
            return 0
    except Exception as e:
        logger.warning("Framebuffer failed: %s", e)

    logger.error("No display backend available. Is QEMU running with --gui?")
    return 1


if __name__ == "__main__":
    sys.exit(main())
