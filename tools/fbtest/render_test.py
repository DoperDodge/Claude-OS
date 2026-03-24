#!/usr/bin/env python3
"""
Claude-OS Render Test

Exercises the full rendering pipeline:
    Compositor -> Scene Graph -> DRM Renderer -> PNG output

This can run on the host (headless mode) or inside the QEMU VM
(DRM mode, draws to /dev/dri/card0).

Usage:
    python3 render_test.py                # Headless, saves frame.png
    python3 render_test.py --drm          # Draw to DRM framebuffer
    python3 render_test.py --state locked  # Test lock screen state
"""

import argparse
import os
import sys

# Add project root to path
project_root = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, project_root)

from ui.compositor.compositor import Compositor, CompositorState, SurfaceRole
from ui.renderer.drm_renderer import DRMRenderer


def build_test_compositor(state_name="home"):
    """Create a compositor with test surfaces for rendering."""
    compositor = Compositor()
    compositor.initialize()

    # Add test surfaces
    compositor.add_surface("statusbar", role=SurfaceRole.STATUS_BAR, app_id="statusbar")
    compositor.add_surface("claude-app", role=SurfaceRole.APP, app_id="claude-app")
    compositor.add_surface("keyboard", role=SurfaceRole.KEYBOARD, app_id="keyboard")
    compositor.add_surface("lockscreen", role=SurfaceRole.LOCK_SCREEN, app_id="lockscreen")

    # Set state
    state_map = {
        "locked": CompositorState.LOCKED,
        "home": CompositorState.HOME,
        "app": CompositorState.APP,
        "drawer": CompositorState.APP_DRAWER,
        "notifications": CompositorState.NOTIFICATION_SHADE,
    }
    compositor.state = state_map.get(state_name, CompositorState.HOME)

    return compositor


def main():
    parser = argparse.ArgumentParser(description="Claude-OS Render Test")
    parser.add_argument("--drm", action="store_true", help="Render to DRM framebuffer")
    parser.add_argument("--state", default="home",
                        choices=["locked", "home", "app", "drawer", "notifications"],
                        help="Compositor state to render")
    parser.add_argument("--output", default="frame.png", help="Output PNG path (headless only)")
    parser.add_argument("--width", type=int, default=1080, help="Display width")
    parser.add_argument("--height", type=int, default=2340, help="Display height")
    args = parser.parse_args()

    print(f"[render_test] State: {args.state}")
    print(f"[render_test] Mode: {'DRM' if args.drm else 'headless'}")

    # Build compositor with test surfaces
    compositor = build_test_compositor(args.state)
    scene = compositor.render_frame()

    if scene is None:
        print("[render_test] No scene to render (display off?)")
        return

    print(f"[render_test] Scene graph: {len(scene.children)} children")

    # Initialize renderer
    renderer = DRMRenderer()
    renderer.initialize(headless=not args.drm, width=args.width, height=args.height)

    # Render
    renderer.render(scene)

    if not args.drm:
        renderer.save_png(args.output)
        print(f"[render_test] Saved to {args.output}")
    else:
        print("[render_test] Frame rendered to DRM framebuffer")

    renderer.shutdown()
    print("[render_test] Done.")


if __name__ == "__main__":
    main()
