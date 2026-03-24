"""
Claude-OS Wayland Compositor

A minimal Wayland compositor built on wlroots (via pywlroots bindings) designed
for a mobile phone form factor. The compositor manages:

- A single fullscreen app at a time (mobile paradigm)
- System overlays: status bar (top), on-screen keyboard (bottom)
- Touch gesture handling for navigation
- Display power management (DPMS)
- Spring-based animation system for fluid transitions
- Frosted glass compositing pipeline

Architecture:
    ┌──────────────────────────────────┐
    │   Status Bar (frosted glass)     │  ← 54px, blurred background
    ├──────────────────────────────────┤
    │                                  │
    │     Active App Surface           │  ← Fullscreen, one at a time
    │   (Claude Chat by default)       │
    │                                  │
    ├──────────────────────────────────┤
    │    On-Screen Keyboard            │  ← Spring-animated slide up
    └──────────────────────────────────┘
    │         Home Indicator           │  ← Thin bar, always visible

Design:
    Claude's warm aesthetic × Apple's motion design.
    All transitions use spring physics or ease-out curves.
    Overlays use frosted glass with warm tint.
"""

import ctypes
import logging
import math
import os
import signal
import sys
import time
from dataclasses import dataclass, field
from enum import Enum, auto

logger = logging.getLogger("compositor")


# ---------------------------------------------------------------------------
# Animation Engine
# ---------------------------------------------------------------------------

@dataclass
class AnimationState:
    """Tracks an in-flight animation on a property."""
    target: float
    current: float
    velocity: float = 0.0
    damping: float = 0.85
    stiffness: float = 300.0
    mass: float = 1.0
    started_at: float = 0.0
    settled: bool = False
    # Threshold below which we snap to target
    settle_threshold: float = 0.5

    def tick(self, dt: float) -> float:
        """Advance the spring simulation by dt seconds.  Returns new value."""
        if self.settled:
            return self.target

        # Spring force:  F = -k * displacement - c * velocity
        displacement = self.current - self.target
        spring_force = -self.stiffness * displacement
        damping_force = -2.0 * self.damping * math.sqrt(self.stiffness * self.mass) * self.velocity

        acceleration = (spring_force + damping_force) / self.mass
        self.velocity += acceleration * dt
        self.current += self.velocity * dt

        # Check settled
        if abs(displacement) < self.settle_threshold and abs(self.velocity) < self.settle_threshold:
            self.current = self.target
            self.velocity = 0.0
            self.settled = True

        return self.current


class AnimationManager:
    """
    Manages spring-based animations for compositor properties.

    Each animated property is identified by a string key and driven
    by a critically-damped (or under-damped) spring.
    """

    def __init__(self):
        self.animations: dict[str, AnimationState] = {}

    def animate_to(self, key: str, target: float, current: float = None,
                   damping: float = 0.85, stiffness: float = 300.0,
                   mass: float = 1.0):
        """Start or redirect an animation."""
        existing = self.animations.get(key)
        if existing and not existing.settled:
            # Redirect in-flight animation (preserves velocity)
            existing.target = target
            return

        self.animations[key] = AnimationState(
            target=target,
            current=current if current is not None else target,
            damping=damping,
            stiffness=stiffness,
            mass=mass,
            started_at=time.monotonic(),
        )

    def tick(self, dt: float):
        """Advance all animations by dt seconds."""
        settled_keys = []
        for key, anim in self.animations.items():
            anim.tick(dt)
            if anim.settled:
                settled_keys.append(key)
        # Clean up settled animations
        for key in settled_keys:
            del self.animations[key]

    def value(self, key: str, default: float = 0.0) -> float:
        """Get the current animated value (or default if not animating)."""
        anim = self.animations.get(key)
        return anim.current if anim else default

    def is_animating(self, key: str = None) -> bool:
        """Check if any (or a specific) animation is in flight."""
        if key:
            return key in self.animations and not self.animations[key].settled
        return any(not a.settled for a in self.animations.values())

    @property
    def active_count(self) -> int:
        return sum(1 for a in self.animations.values() if not a.settled)


# ---------------------------------------------------------------------------
# Surface & Output
# ---------------------------------------------------------------------------

class SurfaceRole(Enum):
    """Role assigned to a Wayland surface."""
    APP = auto()
    STATUS_BAR = auto()
    KEYBOARD = auto()
    OVERLAY = auto()
    LOCK_SCREEN = auto()
    NOTIFICATION_PANEL = auto()
    APP_DRAWER = auto()


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
    """A managed Wayland surface with animation support."""
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
    # Visual properties for compositing
    opacity: float = 1.0
    corner_radius: float = 0.0
    blur_radius: float = 0.0
    scale: float = 1.0


class Compositor:
    """
    Claude-OS Wayland compositor.

    In production this uses wlroots via C bindings. This implementation
    provides the compositor logic and surface management, with the wlroots
    backend abstracted for testability.

    Design changes:
    - Taller status bar (54px) with frosted glass effect
    - Spring-animated keyboard show/hide
    - Home indicator bar at bottom
    - Page transitions with scale + fade
    - Lock screen with parallax depth
    """

    # Layout constants (from theme)
    STATUS_BAR_HEIGHT = 54
    KEYBOARD_HEIGHT = 300
    HOME_INDICATOR_HEIGHT = 34
    SWIPE_THRESHOLD = 50

    # Animation springs
    SPRING_KEYBOARD = {"damping": 0.85, "stiffness": 300}
    SPRING_OVERLAY = {"damping": 0.9, "stiffness": 180}
    SPRING_PAGE = {"damping": 0.86, "stiffness": 400}

    def __init__(self, output_config: OutputConfig = None):
        self.config = output_config or OutputConfig()
        self.surfaces: list[Surface] = []
        self.active_surface: Surface | None = None
        self.keyboard_visible = False
        self.display_on = True

        # Animation
        self.animator = AnimationManager()
        self._last_frame_time = time.monotonic()

        # Touch tracking
        self._touch_start_x = 0
        self._touch_start_y = 0
        self._touch_start_time = 0
        self._touching = False

        # Callbacks
        self._on_gesture = None
        self._on_app_launch = None
        self._on_display_power = None

        # Wayland display/backend (set during init)
        self._wl_display = None
        self._backend = None
        self._renderer = None
        self._allocator = None

        # Compositor state
        self._lock_screen_active = False
        self._notification_panel_offset = 0.0  # 0=hidden, 1=fully open
        self._app_drawer_offset = 0.0          # 0=hidden, 1=fully open

        logger.info("Compositor created: %dx%d @ %.1fx scale",
                     self.config.width, self.config.height, self.config.scale)

    def initialize(self):
        """
        Initialize the Wayland display and wlroots backend.

        This sets up:
        - Wayland display socket
        - wlroots backend (DRM/KMS for real hardware, headless for testing)
        - Renderer (GLES2 or Pixman)
        - Output configuration
        - Input device handling
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
        raise ImportError("wlroots bindings not yet built")

    def _init_stub(self):
        """Initialize stub backend for development/testing."""
        self._wl_display = "stub"
        self._backend = "stub"
        logger.info("Running with stub compositor backend")

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
            surface.blur_radius = 24.0
            surface.corner_radius = 0
        elif role == SurfaceRole.KEYBOARD:
            surface.x = 0
            surface.width = self.config.width
            surface.height = self.KEYBOARD_HEIGHT
            surface.y = self.config.height - self.KEYBOARD_HEIGHT
            surface.visible = False
            surface.blur_radius = 30.0
        elif role == SurfaceRole.APP:
            surface.x = 0
            surface.y = self.STATUS_BAR_HEIGHT
            surface.width = self.config.width
            surface.height = self._app_area_height()
        elif role == SurfaceRole.LOCK_SCREEN:
            surface.x = 0
            surface.y = 0
            surface.width = self.config.width
            surface.height = self.config.height
        elif role == SurfaceRole.NOTIFICATION_PANEL:
            surface.x = 0
            surface.y = 0
            surface.width = self.config.width
            surface.height = self.config.height
            surface.visible = False
            surface.blur_radius = 20.0
        elif role == SurfaceRole.APP_DRAWER:
            surface.x = 0
            surface.y = 0
            surface.width = self.config.width
            surface.height = self.config.height
            surface.visible = False
            surface.blur_radius = 20.0
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

    # --- Keyboard Control (with spring animation) ---

    def show_keyboard(self):
        """Show the on-screen keyboard with spring animation."""
        if self.keyboard_visible:
            return
        self.keyboard_visible = True

        # Resize active app to make room
        if self.active_surface:
            self.active_surface.height = self._app_area_height()

        # Animate keyboard sliding up from bottom
        self.animator.animate_to(
            "keyboard_y",
            target=self.config.height - self.KEYBOARD_HEIGHT,
            current=float(self.config.height),
            **self.SPRING_KEYBOARD,
        )
        # Fade in
        self.animator.animate_to(
            "keyboard_opacity", target=1.0, current=0.0,
            damping=0.95, stiffness=200,
        )

        # Show keyboard surface
        for s in self.surfaces:
            if s.role == SurfaceRole.KEYBOARD:
                s.visible = True

        logger.info("Keyboard shown (animated)")

    def hide_keyboard(self):
        """Hide the on-screen keyboard with animation."""
        if not self.keyboard_visible:
            return
        self.keyboard_visible = False

        # Expand active app
        if self.active_surface:
            self.active_surface.height = self._app_area_height()

        # Animate keyboard sliding down
        self.animator.animate_to(
            "keyboard_y",
            target=float(self.config.height),
            current=float(self.config.height - self.KEYBOARD_HEIGHT),
            damping=0.95, stiffness=250,
        )
        self.animator.animate_to(
            "keyboard_opacity", target=0.0, current=1.0,
            damping=0.95, stiffness=200,
        )

        for s in self.surfaces:
            if s.role == SurfaceRole.KEYBOARD:
                s.visible = False

        logger.info("Keyboard hidden (animated)")

    # --- Overlay Control ---

    def show_notification_panel(self):
        """Slide the notification panel down from top."""
        self.animator.animate_to(
            "notif_panel_offset", target=1.0, current=0.0,
            **self.SPRING_OVERLAY,
        )
        for s in self.surfaces:
            if s.role == SurfaceRole.NOTIFICATION_PANEL:
                s.visible = True
        self._notification_panel_offset = 1.0
        logger.info("Notification panel shown")

    def hide_notification_panel(self):
        """Slide the notification panel back up."""
        self.animator.animate_to(
            "notif_panel_offset", target=0.0, current=1.0,
            damping=0.9, stiffness=250,
        )
        for s in self.surfaces:
            if s.role == SurfaceRole.NOTIFICATION_PANEL:
                s.visible = False
        self._notification_panel_offset = 0.0
        logger.info("Notification panel hidden")

    def show_app_drawer(self):
        """Slide the app drawer up from bottom."""
        self.animator.animate_to(
            "app_drawer_offset", target=1.0, current=0.0,
            **self.SPRING_OVERLAY,
        )
        for s in self.surfaces:
            if s.role == SurfaceRole.APP_DRAWER:
                s.visible = True
        self._app_drawer_offset = 1.0
        logger.info("App drawer shown")

    def hide_app_drawer(self):
        """Slide the app drawer back down."""
        self.animator.animate_to(
            "app_drawer_offset", target=0.0, current=1.0,
            damping=0.9, stiffness=250,
        )
        for s in self.surfaces:
            if s.role == SurfaceRole.APP_DRAWER:
                s.visible = False
        self._app_drawer_offset = 0.0
        logger.info("App drawer hidden")

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
        """Handle touch move event (for interactive dismiss gestures)."""
        if not self._touching:
            return
        # Interactive drag for notification panel / app drawer
        dy = y - self._touch_start_y
        if self._touch_start_y < 100 and dy > 0:
            # Dragging notification panel
            progress = min(1.0, dy / (self.config.height * 0.6))
            self._notification_panel_offset = progress
        elif self._touch_start_y > self.config.height - 100 and dy < 0:
            # Dragging app drawer
            progress = min(1.0, abs(dy) / (self.config.height * 0.6))
            self._app_drawer_offset = progress

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
        1. Background (warm gradient or wallpaper)
        2. Active app surface
        3. Lock screen (if active, on top of everything)
        4. Status bar (frosted glass overlay)
        5. Notification panel (frosted glass, animated)
        6. App drawer (frosted glass, animated)
        7. Keyboard overlay (frosted glass, animated)
        8. Home indicator (thin bar at bottom)

        Each layer applies its blur, opacity, and transform from animations.
        """
        if not self.display_on:
            return

        # Advance animations
        now = time.monotonic()
        dt = now - self._last_frame_time
        self._last_frame_time = now
        self.animator.tick(dt)

        # Apply animated values to surfaces
        for surface in self.surfaces:
            if surface.role == SurfaceRole.KEYBOARD:
                anim_y = self.animator.value("keyboard_y",
                                              default=float(surface.y))
                surface.y = int(anim_y)
                surface.opacity = self.animator.value("keyboard_opacity",
                                                       default=1.0 if surface.visible else 0.0)

        # Determine visible surfaces in render order
        render_list = []

        # Active app
        if self.active_surface and self.active_surface.visible:
            render_list.append(self.active_surface)

        # Overlays (status bar, keyboard, panels) on top
        for surface in self.surfaces:
            if surface.role in (SurfaceRole.STATUS_BAR, SurfaceRole.KEYBOARD,
                                SurfaceRole.OVERLAY, SurfaceRole.LOCK_SCREEN,
                                SurfaceRole.NOTIFICATION_PANEL,
                                SurfaceRole.APP_DRAWER):
                if surface.visible:
                    render_list.append(surface)

        return render_list

    def get_render_metadata(self) -> dict:
        """
        Return per-frame metadata for the rendering pipeline.

        Includes animated values, blur configs, and transition progress
        so the actual renderer (Cairo/Skia/GLES) knows how to composite.
        """
        return {
            "keyboard": {
                "y": self.animator.value("keyboard_y",
                                          default=float(self.config.height)),
                "opacity": self.animator.value("keyboard_opacity", default=0.0),
            },
            "notification_panel": {
                "offset": self.animator.value("notif_panel_offset", default=0.0),
            },
            "app_drawer": {
                "offset": self.animator.value("app_drawer_offset", default=0.0),
            },
            "animating": self.animator.is_animating(),
            "active_animations": self.animator.active_count,
        }

    def run(self):
        """
        Run the compositor event loop.

        In production, this calls wl_display_run() which blocks
        and processes Wayland events + renders frames at 60fps.
        """
        logger.info("Compositor running")

        if self._wl_display == "stub":
            # Stub: just block until signal
            try:
                signal.pause()
            except KeyboardInterrupt:
                pass
        else:
            # Would call: wl_display_run(self._wl_display)
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
