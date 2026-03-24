"""
Claude-OS Wayland Compositor

A minimal Wayland compositor built on wlroots (via pywlroots bindings) designed
for a mobile phone form factor. The compositor manages:

- A single fullscreen app at a time (mobile paradigm)
- System overlays: status bar (top), on-screen keyboard (bottom)
- Touch gesture handling for navigation
- Display power management (DPMS)
- Scene-graph based rendering with theme-aware background

Architecture:
    ┌──────────────────────────────────────────┐
    │              Status Bar                  │  <- Always-on-top glassmorphic overlay
    ├──────────────────────────────────────────┤
    │                                          │
    │         Active App Surface               │  <- Fullscreen, one at a time
    │       (Claude App by default)            │
    │                                          │
    ├──────────────────────────────────────────┤
    │     Notification Panel (pull-down)       │  <- Swipe from top
    ├──────────────────────────────────────────┤
    │        On-Screen Keyboard                │  <- Shown when text input focused
    └──────────────────────────────────────────┘
"""

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
    NOTIFICATION_PANEL = auto()
    LOCK_SCREEN = auto()


class CompositorState(Enum):
    """High-level compositor state machine."""
    LOCKED = auto()
    HOME = auto()
    APP = auto()
    APP_DRAWER = auto()
    NOTIFICATION_SHADE = auto()


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
    """A managed Wayland surface with render metadata."""
    wl_surface: object  # wlroots surface handle
    role: SurfaceRole = SurfaceRole.APP
    x: int = 0
    y: int = 0
    width: int = 0
    height: int = 0
    visible: bool = True
    opacity: float = 1.0
    corner_radius: int = 0
    blur_behind: bool = False
    app_id: str = ""
    title: str = ""
    pid: int = 0
    z_index: int = 0  # Render ordering within same role


@dataclass
class SceneNode:
    """A node in the render scene graph."""
    surface: Surface | None = None
    background_color: str | None = None
    blur_radius: float = 0.0
    opacity: float = 1.0
    x: int = 0
    y: int = 0
    width: int = 0
    height: int = 0
    corner_radius: int = 0
    children: list = field(default_factory=list)


class Compositor:
    """
    Claude-OS Wayland compositor with theme-aware rendering.

    Uses the design system tokens for all visual properties including
    status bar height, keyboard dimensions, background colors, blur
    effects, and animation curves.
    """

    # Swipe threshold in pixels
    SWIPE_THRESHOLD = 50

    def __init__(self, output_config: OutputConfig = None):
        # Import theme for layout metrics
        try:
            from ui.theme import get_theme
            self._theme = get_theme()
        except ImportError:
            self._theme = None

        self.config = output_config or OutputConfig()
        self.surfaces: list[Surface] = []
        self.active_surface: Surface | None = None
        self.keyboard_visible = False
        self.display_on = True
        self.state = CompositorState.LOCKED

        # Layout metrics from theme
        layout = self._theme.layout if self._theme else None
        self.STATUS_BAR_HEIGHT = layout.statusbar_height if layout else 54
        self.KEYBOARD_HEIGHT = layout.keyboard_height if layout else 291
        self.SAFE_AREA_TOP = layout.safe_area_top if layout else 54
        self.SAFE_AREA_BOTTOM = layout.safe_area_bottom if layout else 34
        self.HOME_INDICATOR_WIDTH = layout.home_indicator_width if layout else 134
        self.HOME_INDICATOR_HEIGHT = layout.home_indicator_height if layout else 5

        # Touch tracking
        self._touch_start_x = 0
        self._touch_start_y = 0
        self._touch_start_time = 0
        self._touching = False

        # Animation state
        self._notification_panel_y = -self.config.height  # Off-screen
        self._keyboard_y = self.config.height  # Off-screen below
        self._lock_screen_opacity = 1.0
        self._app_transition_progress = 1.0

        # Callbacks
        self._on_gesture = None
        self._on_app_launch = None
        self._on_display_power = None
        self._on_state_change = None

        # Wayland display/backend (set during init)
        self._wl_display = None
        self._backend = None
        self._renderer = None
        self._allocator = None

        logger.info("Compositor created: %dx%d @ %.1fx scale",
                     self.config.width, self.config.height, self.config.scale)

    def initialize(self):
        """
        Initialize the Wayland display and wlroots backend.

        Sets up display socket, renderer, output configuration,
        and input device handling.
        """
        logger.info("Initializing Wayland compositor...")

        try:
            self._init_wlroots()
        except (ImportError, OSError):
            logger.warning("wlroots not available, using stub backend")
            self._init_stub()

        # Set the Wayland display socket name for clients
        socket_name = self._get_socket_name()
        os.environ["WAYLAND_DISPLAY"] = socket_name
        logger.info("Wayland socket: %s", socket_name)

    def _init_wlroots(self):
        """Initialize real wlroots backend."""
        # wlr_backend_autocreate() - picks DRM for real HW, headless for CI
        # wlr_renderer_autocreate() - GLES2 or Pixman
        # wlr_allocator_autocreate() - GBM or shm
        # wl_display_create() - create Wayland display
        # wlr_xdg_shell_create() - handle app windows
        # wlr_layer_shell_v1_create() - handle overlays (status bar, keyboard)
        # wlr_seat_create() - input handling (touch, keyboard)
        # wlr_output_layout_create() - manage physical displays
        # wlr_scene_create() - scene graph for compositing
        raise ImportError("wlroots bindings not yet built")

    def _init_stub(self):
        """Initialize stub backend for development/testing."""
        self._wl_display = "stub"
        self._backend = "stub"
        logger.info("Running with stub compositor backend")

    def _get_socket_name(self) -> str:
        """Get or generate the Wayland socket name."""
        return os.environ.get("WAYLAND_DISPLAY", "wayland-0")

    # --- State Management ---

    def set_state(self, new_state: CompositorState):
        """Transition to a new compositor state."""
        old_state = self.state
        self.state = new_state
        logger.info("State: %s -> %s", old_state.name, new_state.name)
        if self._on_state_change:
            self._on_state_change(old_state, new_state)

    def unlock(self):
        """Transition from lock screen to home."""
        if self.state == CompositorState.LOCKED:
            self.set_state(CompositorState.HOME)

    def lock(self):
        """Lock the device."""
        self.set_state(CompositorState.LOCKED)

    # --- Surface Management ---

    def add_surface(self, wl_surface, app_id: str = "", title: str = "",
                    role: SurfaceRole = SurfaceRole.APP) -> Surface:
        """Register a new surface with the compositor."""
        theme = self._theme
        spacing = theme.spacing if theme else None

        surface = Surface(
            wl_surface=wl_surface,
            role=role,
            app_id=app_id,
            title=title,
        )

        # Position and style based on role
        if role == SurfaceRole.STATUS_BAR:
            surface.x = 0
            surface.y = 0
            surface.width = self.config.width
            surface.height = self.STATUS_BAR_HEIGHT
            surface.blur_behind = True
            surface.z_index = 100
        elif role == SurfaceRole.KEYBOARD:
            surface.x = 0
            surface.width = self.config.width
            surface.height = self.KEYBOARD_HEIGHT
            surface.y = self.config.height - self.KEYBOARD_HEIGHT
            surface.visible = False
            surface.z_index = 90
        elif role == SurfaceRole.NOTIFICATION_PANEL:
            surface.x = 0
            surface.y = 0
            surface.width = self.config.width
            surface.height = self.config.height
            surface.visible = False
            surface.blur_behind = True
            surface.z_index = 110
        elif role == SurfaceRole.LOCK_SCREEN:
            surface.x = 0
            surface.y = 0
            surface.width = self.config.width
            surface.height = self.config.height
            surface.z_index = 200
        elif role == SurfaceRole.APP:
            surface.x = 0
            surface.y = self.STATUS_BAR_HEIGHT
            surface.width = self.config.width
            surface.height = self._app_area_height()
            surface.z_index = 10
        else:  # OVERLAY
            surface.width = self.config.width
            surface.height = self.config.height
            surface.z_index = 150

        self.surfaces.append(surface)

        # First app surface becomes active
        if role == SurfaceRole.APP and self.active_surface is None:
            self.active_surface = surface

        logger.info("Surface added: role=%s app_id=%s (%dx%d) z=%d",
                     role.name, app_id, surface.width, surface.height,
                     surface.z_index)
        return surface

    def remove_surface(self, surface: Surface):
        """Remove a surface from the compositor."""
        if surface in self.surfaces:
            self.surfaces.remove(surface)
        if self.active_surface == surface:
            apps = [s for s in self.surfaces if s.role == SurfaceRole.APP]
            self.active_surface = apps[-1] if apps else None
        logger.info("Surface removed: %s", surface.app_id)

    def focus_surface(self, surface: Surface):
        """Bring a surface to focus (for APP surfaces)."""
        if surface.role != SurfaceRole.APP:
            return
        self.active_surface = surface
        self.set_state(CompositorState.APP)
        logger.info("Focused: %s", surface.app_id)

    def _app_area_height(self) -> int:
        """Calculate available height for the app area."""
        height = self.config.height - self.STATUS_BAR_HEIGHT
        if self.keyboard_visible:
            height -= self.KEYBOARD_HEIGHT
        return height

    # --- Keyboard Control ---

    def show_keyboard(self):
        """Show the on-screen keyboard with animation."""
        if self.keyboard_visible:
            return
        self.keyboard_visible = True

        if self.active_surface:
            self.active_surface.height = self._app_area_height()

        for s in self.surfaces:
            if s.role == SurfaceRole.KEYBOARD:
                s.visible = True
        logger.info("Keyboard shown")

    def hide_keyboard(self):
        """Hide the on-screen keyboard with animation."""
        if not self.keyboard_visible:
            return
        self.keyboard_visible = False

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
        """Handle touch end event - detect gestures."""
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

        if abs_dx < 20 and abs_dy < 20 and dt < 0.3:
            return "tap"

        if abs_dx < self.SWIPE_THRESHOLD and abs_dy < self.SWIPE_THRESHOLD:
            return None

        if abs_dy > abs_dx:
            if dy < 0:
                if self._touch_start_y > self.config.height - 100:
                    return "go_home"
                return "swipe_up"
            else:
                if self._touch_start_y < 100:
                    return "notification_shade"
                return "swipe_down"

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
        if not on:
            self.lock()
        if self._on_display_power:
            self._on_display_power(on)
        logger.info("Display %s", "ON" if on else "OFF")

    # --- Scene Graph Rendering ---

    def build_scene_graph(self) -> SceneNode:
        """
        Build the render scene graph for the current frame.

        Returns a tree of SceneNodes that a renderer can walk to
        produce the final composited image.
        """
        theme = self._theme
        colors = theme.colors if theme else None
        bg_color = colors.background if colors else "#FAF6F1"

        root = SceneNode(
            background_color=bg_color,
            width=self.config.width,
            height=self.config.height,
        )

        if self.state == CompositorState.LOCKED:
            # Lock screen is fullscreen, above everything
            for s in self.surfaces:
                if s.role == SurfaceRole.LOCK_SCREEN and s.visible:
                    root.children.append(SceneNode(
                        surface=s, x=s.x, y=s.y,
                        width=s.width, height=s.height,
                        opacity=self._lock_screen_opacity,
                    ))
            return root

        # Active app
        if self.active_surface and self.active_surface.visible:
            root.children.append(SceneNode(
                surface=self.active_surface,
                x=self.active_surface.x,
                y=self.active_surface.y,
                width=self.active_surface.width,
                height=self.active_surface.height,
            ))

        # Sort overlays by z_index
        overlays = sorted(
            [s for s in self.surfaces
             if s.role in (SurfaceRole.STATUS_BAR, SurfaceRole.KEYBOARD,
                           SurfaceRole.OVERLAY, SurfaceRole.NOTIFICATION_PANEL)
             and s.visible],
            key=lambda s: s.z_index,
        )

        for s in overlays:
            node = SceneNode(
                surface=s, x=s.x, y=s.y,
                width=s.width, height=s.height,
                opacity=s.opacity,
            )
            if s.blur_behind and theme:
                node.blur_radius = theme.effects.glass_blur_regular
            root.children.append(node)

        # Home indicator bar at bottom
        if self.state != CompositorState.LOCKED:
            indicator_x = (self.config.width - self.HOME_INDICATOR_WIDTH) // 2
            indicator_y = (self.config.height - self.SAFE_AREA_BOTTOM +
                          (self.SAFE_AREA_BOTTOM - self.HOME_INDICATOR_HEIGHT) // 2)
            root.children.append(SceneNode(
                background_color=colors.text_primary if colors else "#1A1A2E",
                x=indicator_x, y=indicator_y,
                width=self.HOME_INDICATOR_WIDTH,
                height=self.HOME_INDICATOR_HEIGHT,
                corner_radius=self.HOME_INDICATOR_HEIGHT // 2,
                opacity=0.3,
            ))

        return root

    def render_frame(self):
        """
        Render one frame.

        Compositing order (back to front):
        1. Background (theme-colored)
        2. Active app surface
        3. Status bar overlay (glassmorphic)
        4. Keyboard overlay (if visible)
        5. Notification panel (if open)
        6. Lock screen (if locked)
        7. Home indicator pill
        """
        if not self.display_on:
            return

        return self.build_scene_graph()

    def get_render_state(self) -> dict:
        """Return serializable render state for external renderers."""
        theme = self._theme
        colors = theme.colors if theme else None

        return {
            "state": self.state.name,
            "display_on": self.display_on,
            "keyboard_visible": self.keyboard_visible,
            "screen": {
                "width": self.config.width,
                "height": self.config.height,
                "scale": self.config.scale,
            },
            "background_color": colors.background if colors else "#FAF6F1",
            "surfaces": [
                {
                    "role": s.role.name,
                    "app_id": s.app_id,
                    "x": s.x, "y": s.y,
                    "width": s.width, "height": s.height,
                    "visible": s.visible,
                    "opacity": s.opacity,
                    "z_index": s.z_index,
                    "blur_behind": s.blur_behind,
                    "corner_radius": s.corner_radius,
                }
                for s in sorted(self.surfaces, key=lambda s: s.z_index)
            ],
            "active_app": self.active_surface.app_id if self.active_surface else None,
            "safe_area": {
                "top": self.SAFE_AREA_TOP,
                "bottom": self.SAFE_AREA_BOTTOM,
            },
        }

    # --- Lifecycle ---

    def run(self):
        """
        Run the compositor event loop.

        In production, calls wl_display_run() which blocks
        and processes Wayland events + renders frames.
        """
        logger.info("Compositor running")

        if self._wl_display == "stub":
            try:
                signal.pause()
            except KeyboardInterrupt:
                pass
        else:
            pass

        logger.info("Compositor stopped")

    def destroy(self):
        """Clean up compositor resources."""
        self.surfaces.clear()
        self.active_surface = None
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
