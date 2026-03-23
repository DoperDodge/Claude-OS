"""
Claude-OS Wayland Compositor

A minimal Wayland compositor built on wlroots (via pywlroots bindings) designed
for a mobile phone form factor. The compositor manages:

- A single fullscreen app at a time (mobile paradigm)
- System overlays: status bar (top), on-screen keyboard (bottom)
- Touch gesture handling for navigation
- Display power management (DPMS)

Architecture:
    ┌──────────────────────────────┐
    │         Status Bar           │  ← Always-on-top overlay
    ├──────────────────────────────┤
    │                              │
    │      Active App Surface      │  ← Fullscreen, one at a time
    │    (Claude App by default)   │
    │                              │
    ├──────────────────────────────┤
    │      On-Screen Keyboard      │  ← Shown when text input focused
    └──────────────────────────────┘
"""

import asyncio
import ctypes
import logging
import os
import signal
import sys
import time
from dataclasses import dataclass, field
from enum import Enum, auto

logger = logging.getLogger("compositor")


class SurfaceRole(Enum):
    """Role assigned to a Wayland surface."""
    APP = auto()
    STATUS_BAR = auto()
    KEYBOARD = auto()
    OVERLAY = auto()


@dataclass
class OutputConfig:
    """Display output configuration."""
    width: int = 1080
    height: int = 2340
    refresh_mhz: int = 60000  # 60Hz in millihertz
    scale: float = 2.0
    rotation: int = 0  # 0, 90, 180, 270


@dataclass
class Surface:
    """A managed Wayland surface."""
    wl_surface: object  # wlroots surface handle
    role: SurfaceRole = SurfaceRole.APP
    x: int = 0
    y: int = 0
    width: int = 0
    height: int = 0
    visible: bool = True
    app_id: str = ""
    title: str = ""
    pid: int = 0


class Compositor:
    """
    Claude-OS Wayland compositor.

    In production this uses wlroots via C bindings. This implementation
    provides the compositor logic and surface management, with the wlroots
    backend abstracted for testability.
    """

    # Status bar height in logical pixels
    STATUS_BAR_HEIGHT = 48
    # Keyboard height when visible
    KEYBOARD_HEIGHT = 300
    # Swipe threshold in pixels
    SWIPE_THRESHOLD = 50

    def __init__(self, output_config: OutputConfig = None):
        self.config = output_config or OutputConfig()
        self.surfaces: list[Surface] = []
        self.active_surface: Surface | None = None
        self.keyboard_visible = False
        self.display_on = True

        # Touch tracking
        self._touch_start_x = 0
        self._touch_start_y = 0
        self._touch_start_time = 0
        self._touching = False

        # Callbacks
        self._on_gesture = None
        self._on_app_launch = None
        self._on_display_power = None

        # Backend state (set during init)
        self._wl_display = None
        self._backend = None
        self._renderer_obj = None
        self._wayland_server = None
        self._running = False

        logger.info("Compositor created: %dx%d @ %.1fx scale",
                     self.config.width, self.config.height, self.config.scale)

    def initialize(self):
        """
        Initialize the Wayland display, renderer, and protocol server.

        Sets up:
        - Display renderer (DRM/framebuffer/headless)
        - Wayland protocol server (Unix socket for clients)
        - Input event handling
        """
        logger.info("Initializing Wayland compositor...")

        # Initialize display renderer
        from renderer import CompositorRenderer
        self._renderer_obj = CompositorRenderer()
        display_info = self._renderer_obj.initialize(
            width=self.config.width, height=self.config.height,
        )
        self._backend = display_info.get("backend", "unknown")

        # Initialize Wayland server
        from wayland_server import WaylandServer
        self._wayland_server = WaylandServer()
        socket_path = self._wayland_server.start()

        self._wayland_server.set_callbacks(
            on_created=self._on_client_surface_created,
            on_committed=self._on_client_surface_committed,
            on_destroyed=self._on_client_surface_destroyed,
        )

        # Set Wayland display name for clients
        socket_name = self._get_socket_name()
        os.environ["WAYLAND_DISPLAY"] = socket_name

        self._wl_display = socket_path
        logger.info("Compositor initialized: renderer=%s, socket=%s",
                     self._backend, socket_path)

    def _init_stub(self):
        """Initialize stub backend for development/testing."""
        self._wl_display = "stub"
        self._backend = "stub"
        self._renderer_obj = None
        self._wayland_server = None
        logger.info("Running with stub compositor backend")

    # --- Wayland Client Callbacks ---

    def _on_client_surface_created(self, client_id: int, client_surface):
        """Called when a Wayland client creates a new surface."""
        logger.info("Client %d created surface %d",
                     client_id, client_surface.surface_id)

    def _on_client_surface_committed(self, client_id: int, client_surface):
        """Called when a Wayland client commits a surface frame."""
        from renderer import SurfaceBuffer

        # Find or create compositor surface for this client surface
        comp_surface = self._find_surface_by_client(
            client_id, client_surface.surface_id
        )

        if not comp_surface:
            # New surface — register it with the compositor
            comp_surface = self.add_surface(
                wl_surface=client_surface,
                app_id=client_surface.app_id or f"client-{client_id}",
                title=client_surface.title,
                role=SurfaceRole.APP,
            )
            comp_surface.pid = client_id  # Track client ID via pid field

        # Update surface buffer if client has pixel data
        if client_surface.shm_data:
            buf = SurfaceBuffer(
                width=client_surface.width,
                height=client_surface.height,
                stride=client_surface.stride,
                data=client_surface.shm_data,
            )
            if self._renderer_obj:
                self._renderer_obj.attach_buffer(id(comp_surface), buf)

    def _on_client_surface_destroyed(self, client_id: int, client_surface):
        """Called when a client surface is destroyed."""
        comp_surface = self._find_surface_by_client(
            client_id, client_surface.surface_id
        )
        if comp_surface:
            if self._renderer_obj:
                self._renderer_obj.detach_buffer(id(comp_surface))
            self.remove_surface(comp_surface)

    def _find_surface_by_client(self, client_id: int, surface_id: int):
        """Find a compositor surface matching a client surface."""
        for s in self.surfaces:
            if (s.pid == client_id and
                    hasattr(s.wl_surface, 'surface_id') and
                    s.wl_surface.surface_id == surface_id):
                return s
        return None

    def _get_socket_name(self) -> str:
        """Get or generate the Wayland socket name."""
        return os.environ.get("WAYLAND_DISPLAY", "wayland-0")

    # --- Surface Management ---

    def add_surface(self, wl_surface, app_id: str = "", title: str = "",
                    role: SurfaceRole = SurfaceRole.APP) -> Surface:
        """Register a new surface with the compositor."""
        surface = Surface(
            wl_surface=wl_surface,
            role=role,
            app_id=app_id,
            title=title,
        )

        # Position based on role
        if role == SurfaceRole.STATUS_BAR:
            surface.x = 0
            surface.y = 0
            surface.width = self.config.width
            surface.height = self.STATUS_BAR_HEIGHT
        elif role == SurfaceRole.KEYBOARD:
            surface.x = 0
            surface.width = self.config.width
            surface.height = self.KEYBOARD_HEIGHT
            surface.y = self.config.height - self.KEYBOARD_HEIGHT
            surface.visible = False
        elif role == SurfaceRole.APP:
            surface.x = 0
            surface.y = self.STATUS_BAR_HEIGHT
            surface.width = self.config.width
            surface.height = self._app_area_height()
        else:
            surface.width = self.config.width
            surface.height = self.config.height

        self.surfaces.append(surface)

        # First app surface becomes active
        if role == SurfaceRole.APP and self.active_surface is None:
            self.active_surface = surface

        logger.info("Surface added: role=%s app_id=%s (%dx%d)",
                     role.name, app_id, surface.width, surface.height)
        return surface

    def remove_surface(self, surface: Surface):
        """Remove a surface from the compositor."""
        if surface in self.surfaces:
            self.surfaces.remove(surface)
        if self.active_surface == surface:
            # Activate next app surface, if any
            apps = [s for s in self.surfaces if s.role == SurfaceRole.APP]
            self.active_surface = apps[-1] if apps else None
        logger.info("Surface removed: %s", surface.app_id)

    def focus_surface(self, surface: Surface):
        """Bring a surface to focus (for APP surfaces)."""
        if surface.role != SurfaceRole.APP:
            return
        self.active_surface = surface
        logger.info("Focused: %s", surface.app_id)

    def _app_area_height(self) -> int:
        """Calculate available height for the app area."""
        height = self.config.height - self.STATUS_BAR_HEIGHT
        if self.keyboard_visible:
            height -= self.KEYBOARD_HEIGHT
        return height

    # --- Keyboard Control ---

    def show_keyboard(self):
        """Show the on-screen keyboard."""
        if self.keyboard_visible:
            return
        self.keyboard_visible = True

        # Resize active app to make room
        if self.active_surface:
            self.active_surface.height = self._app_area_height()

        # Show keyboard surface
        for s in self.surfaces:
            if s.role == SurfaceRole.KEYBOARD:
                s.visible = True

        logger.info("Keyboard shown")

    def hide_keyboard(self):
        """Hide the on-screen keyboard."""
        if not self.keyboard_visible:
            return
        self.keyboard_visible = False

        # Expand active app
        if self.active_surface:
            self.active_surface.height = self._app_area_height()

        for s in self.surfaces:
            if s.role == SurfaceRole.KEYBOARD:
                s.visible = False

        logger.info("Keyboard hidden")

    # --- Touch Input ---

    def handle_touch_down(self, x: int, y: int, touch_id: int = 0):
        """Handle touch start event."""
        self._touch_start_x = x
        self._touch_start_y = y
        self._touch_start_time = time.monotonic()
        self._touching = True

    def handle_touch_up(self, x: int, y: int, touch_id: int = 0):
        """Handle touch end event — detect gestures."""
        if not self._touching:
            return
        self._touching = False

        dx = x - self._touch_start_x
        dy = y - self._touch_start_y
        dt = time.monotonic() - self._touch_start_time

        gesture = self._classify_gesture(dx, dy, dt)
        if gesture and self._on_gesture:
            self._on_gesture(gesture, {"dx": dx, "dy": dy, "dt": dt})

    def handle_touch_motion(self, x: int, y: int, touch_id: int = 0):
        """Handle touch move event."""
        pass  # Used for drag gestures in future

    def _classify_gesture(self, dx: int, dy: int, dt: float) -> str | None:
        """Classify a touch gesture based on displacement and duration."""
        abs_dx = abs(dx)
        abs_dy = abs(dy)

        # Tap (small displacement, short duration)
        if abs_dx < 20 and abs_dy < 20 and dt < 0.3:
            return "tap"

        # Must exceed threshold for swipe
        if abs_dx < self.SWIPE_THRESHOLD and abs_dy < self.SWIPE_THRESHOLD:
            return None

        # Vertical swipes
        if abs_dy > abs_dx:
            if dy < 0:
                # Swipe up from bottom edge = go home
                if self._touch_start_y > self.config.height - 100:
                    return "go_home"
                return "swipe_up"
            else:
                # Swipe down from top = notification shade
                if self._touch_start_y < 100:
                    return "notification_shade"
                return "swipe_down"

        # Horizontal swipes
        if dx > 0:
            return "swipe_right"  # Back gesture
        else:
            return "swipe_left"

        return None

    def set_gesture_handler(self, handler):
        """Set callback for gesture events."""
        self._on_gesture = handler

    # --- Display Power ---

    def set_display_power(self, on: bool):
        """Turn display on or off (DPMS)."""
        self.display_on = on
        if self._on_display_power:
            self._on_display_power(on)
        logger.info("Display %s", "ON" if on else "OFF")

    # --- Render Loop ---

    def render_frame(self):
        """
        Render one frame.

        Compositing order (back to front):
        1. Background color
        2. Active app surface
        3. Status bar overlay
        4. Keyboard overlay (if visible)
        5. Any modal overlays
        """
        if not self.display_on:
            return

        # In production, this calls wlr_renderer_begin() and
        # wlr_render_texture() for each visible surface

        # Determine visible surfaces in render order
        render_list = []

        # Active app
        if self.active_surface and self.active_surface.visible:
            render_list.append(self.active_surface)

        # Overlays (status bar, keyboard) on top
        for surface in self.surfaces:
            if surface.role in (SurfaceRole.STATUS_BAR, SurfaceRole.KEYBOARD,
                                SurfaceRole.OVERLAY):
                if surface.visible:
                    render_list.append(surface)

        return render_list

    def composite_frame(self):
        """
        Render one full compositor frame using the renderer.

        Calls render_frame() for the surface list, then hands it
        to the renderer for actual pixel output.
        """
        render_list = self.render_frame()
        if render_list is None:
            return  # Display off

        if self._renderer_obj:
            self._renderer_obj.render_frame(render_list)

            # Send frame done to Wayland clients
            if self._wayland_server:
                ts = int(time.monotonic() * 1000)
                self._wayland_server.send_frame_done(ts)

    def run(self):
        """
        Run the compositor event loop.

        Runs the Wayland server, processes input, and renders frames
        at ~60fps. Uses asyncio for concurrent I/O.
        """
        logger.info("Compositor running")

        if self._wl_display == "stub":
            try:
                signal.pause()
            except KeyboardInterrupt:
                pass
        elif self._wayland_server:
            asyncio.run(self._main_loop())
        else:
            try:
                signal.pause()
            except KeyboardInterrupt:
                pass

        logger.info("Compositor stopped")

    async def _main_loop(self):
        """Async main loop — Wayland server + render loop."""
        frame_time = 1.0 / 60  # 60 FPS target
        self._running = True

        # Start Wayland server in background
        server_task = asyncio.create_task(self._wayland_server.run())

        try:
            while self._running:
                start = time.monotonic()

                # Render a frame
                self.composite_frame()

                # Sleep for remainder of frame budget
                elapsed = time.monotonic() - start
                sleep_time = frame_time - elapsed
                if sleep_time > 0:
                    await asyncio.sleep(sleep_time)
                else:
                    await asyncio.sleep(0)  # Yield
        except (KeyboardInterrupt, asyncio.CancelledError):
            pass
        finally:
            self._running = False
            server_task.cancel()
            try:
                await server_task
            except asyncio.CancelledError:
                pass

    def destroy(self):
        """Clean up compositor resources."""
        if hasattr(self, '_wayland_server') and self._wayland_server:
            self._wayland_server.stop()
        if hasattr(self, '_renderer_obj') and self._renderer_obj:
            self._renderer_obj.shutdown()
        self.surfaces.clear()
        self.active_surface = None
        self._running = False
        logger.info("Compositor destroyed")


def main():
    """Entry point for the compositor process."""
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    )

    config = OutputConfig(
        width=int(os.environ.get("DISPLAY_WIDTH", "1080")),
        height=int(os.environ.get("DISPLAY_HEIGHT", "2340")),
        scale=float(os.environ.get("DISPLAY_SCALE", "2.0")),
    )

    compositor = Compositor(config)

    def handle_signal(signum, frame):
        logger.info("Signal %d received, shutting down", signum)
        compositor.destroy()
        sys.exit(0)

    signal.signal(signal.SIGTERM, handle_signal)
    signal.signal(signal.SIGINT, handle_signal)

    compositor.initialize()
    compositor.run()


if __name__ == "__main__":
    main()
