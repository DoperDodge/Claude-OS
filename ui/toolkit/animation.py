"""
Claude-OS Animation Engine

Provides tweening, easing functions, and a timeline for driving smooth
UI animations at 60fps. All animations are time-based (not frame-based)
for consistent speed regardless of actual frame rate.

Core concepts:
    - Easing: Mathematical functions that shape how values change over time
    - Tween: Interpolates a single value from start to end over a duration
    - Animation: Groups of tweens that run together
    - AnimationController: Manages all active animations, ticked each frame
"""

import math
import time
from dataclasses import dataclass, field
from enum import Enum, auto
from typing import Callable


# --- Easing Functions ---

class Easing(Enum):
    """Standard easing curves for animations."""
    LINEAR = auto()
    EASE_IN = auto()       # Slow start
    EASE_OUT = auto()      # Slow end
    EASE_IN_OUT = auto()   # Slow start and end
    EASE_OUT_BACK = auto() # Slight overshoot at end (bounce-like)
    EASE_OUT_CUBIC = auto()  # Smooth deceleration


def ease(t: float, easing: Easing = Easing.LINEAR) -> float:
    """
    Apply an easing function to a normalized time value (0.0 - 1.0).

    Returns the eased value, also in 0.0 - 1.0 range (may exceed
    slightly for overshoot easings like EASE_OUT_BACK).
    """
    t = max(0.0, min(1.0, t))

    if easing == Easing.LINEAR:
        return t
    elif easing == Easing.EASE_IN:
        return t * t * t
    elif easing == Easing.EASE_OUT:
        inv = 1.0 - t
        return 1.0 - inv * inv * inv
    elif easing == Easing.EASE_IN_OUT:
        if t < 0.5:
            return 4.0 * t * t * t
        else:
            inv = (-2.0 * t + 2.0)
            return 1.0 - inv * inv * inv / 2.0
    elif easing == Easing.EASE_OUT_BACK:
        c1 = 1.70158
        c3 = c1 + 1.0
        return 1.0 + c3 * ((t - 1.0) ** 3) + c1 * ((t - 1.0) ** 2)
    elif easing == Easing.EASE_OUT_CUBIC:
        inv = 1.0 - t
        return 1.0 - inv * inv * inv
    return t


# --- Tween ---

@dataclass
class Tween:
    """
    Interpolates a single numeric value from start to end over a duration.

    Attributes:
        start: Starting value
        end: Ending value
        duration_ms: How long the tween takes in milliseconds
        easing: Easing function to apply
        delay_ms: Delay before starting (ms)
        on_update: Called with the current value each tick
        on_complete: Called when the tween finishes
    """
    start: float
    end: float
    duration_ms: int
    easing: Easing = Easing.EASE_OUT
    delay_ms: int = 0
    on_update: Callable[[float], None] | None = None
    on_complete: Callable[[], None] | None = None

    # Internal state
    _elapsed_ms: float = field(default=0.0, repr=False)
    _started: bool = field(default=False, repr=False)
    _completed: bool = field(default=False, repr=False)

    @property
    def current_value(self) -> float:
        """Get the current interpolated value."""
        if self.duration_ms <= 0 and self._elapsed_ms >= self.delay_ms:
            return self.end
        if self._elapsed_ms <= self.delay_ms:
            return self.start
        active_time = self._elapsed_ms - self.delay_ms
        if self.duration_ms <= 0:
            return self.end
        t = min(1.0, active_time / self.duration_ms)
        eased = ease(t, self.easing)
        return self.start + (self.end - self.start) * eased

    @property
    def is_complete(self) -> bool:
        return self._completed

    def tick(self, dt_ms: float):
        """Advance the tween by dt_ms milliseconds."""
        if self._completed:
            return

        self._elapsed_ms += dt_ms

        if self._elapsed_ms > self.delay_ms:
            self._started = True

        value = self.current_value

        if self.on_update:
            self.on_update(value)

        # Check completion
        active_time = self._elapsed_ms - self.delay_ms
        if active_time >= self.duration_ms:
            self._completed = True
            if self.on_update:
                self.on_update(self.end)
            if self.on_complete:
                self.on_complete()

    def reset(self):
        """Reset the tween to its initial state."""
        self._elapsed_ms = 0.0
        self._started = False
        self._completed = False


# --- Animation ---

class AnimationState(Enum):
    IDLE = auto()
    RUNNING = auto()
    PAUSED = auto()
    COMPLETED = auto()


class Animation:
    """
    A group of tweens that run together as a single animation.

    Tweens within an animation run concurrently. Use delay_ms on
    individual tweens for staggered effects.
    """

    def __init__(self, name: str = "", loop: bool = False,
                 on_complete: Callable = None):
        self.name = name
        self.loop = loop
        self.on_complete = on_complete
        self.tweens: list[Tween] = []
        self.state = AnimationState.IDLE
        self._elapsed_ms: float = 0.0

    def add_tween(self, tween: Tween) -> "Animation":
        """Add a tween to this animation. Returns self for chaining."""
        self.tweens.append(tween)
        return self

    def start(self):
        """Start or restart the animation."""
        self.state = AnimationState.RUNNING
        self._elapsed_ms = 0.0
        for tw in self.tweens:
            tw.reset()

    def pause(self):
        if self.state == AnimationState.RUNNING:
            self.state = AnimationState.PAUSED

    def resume(self):
        if self.state == AnimationState.PAUSED:
            self.state = AnimationState.RUNNING

    def stop(self):
        """Stop the animation immediately."""
        self.state = AnimationState.COMPLETED

    def tick(self, dt_ms: float):
        """Advance all tweens by dt_ms."""
        if self.state != AnimationState.RUNNING:
            return

        self._elapsed_ms += dt_ms

        for tw in self.tweens:
            tw.tick(dt_ms)

        # Check if all tweens are done
        if all(tw.is_complete for tw in self.tweens):
            if self.loop:
                for tw in self.tweens:
                    tw.reset()
                self._elapsed_ms = 0.0
            else:
                self.state = AnimationState.COMPLETED
                if self.on_complete:
                    self.on_complete()

    @property
    def progress(self) -> float:
        """Overall progress (0.0 - 1.0) based on longest tween."""
        if not self.tweens:
            return 1.0
        max_dur = max(tw.duration_ms + tw.delay_ms for tw in self.tweens)
        if max_dur <= 0:
            return 1.0
        return min(1.0, self._elapsed_ms / max_dur)

    @property
    def is_running(self) -> bool:
        return self.state == AnimationState.RUNNING

    @property
    def total_duration_ms(self) -> int:
        """Total duration including delays."""
        if not self.tweens:
            return 0
        return max(tw.duration_ms + tw.delay_ms for tw in self.tweens)


# --- Animation Controller ---

class AnimationController:
    """
    Manages all active animations. Call tick() once per frame.

    Automatically removes completed animations (unless looping).
    """

    def __init__(self):
        self._animations: list[Animation] = []
        self._last_tick_ms: float | None = None

    def add(self, animation: Animation) -> Animation:
        """Add and start an animation. Returns the animation."""
        animation.start()
        self._animations.append(animation)
        return animation

    def remove(self, animation: Animation):
        """Remove an animation."""
        if animation in self._animations:
            self._animations.remove(animation)

    def cancel(self, name: str):
        """Cancel all animations with the given name."""
        self._animations = [a for a in self._animations if a.name != name]

    def cancel_all(self):
        """Cancel all animations."""
        self._animations.clear()
        self._last_tick_ms = None

    def tick(self, now_ms: float = None):
        """
        Advance all animations.

        Args:
            now_ms: Current time in milliseconds. If None, uses time.monotonic().
        """
        if now_ms is None:
            now_ms = time.monotonic() * 1000.0

        if self._last_tick_ms is None:
            self._last_tick_ms = now_ms
            return  # First tick — just record the time

        dt = now_ms - self._last_tick_ms
        self._last_tick_ms = now_ms

        if dt <= 0:
            return

        # Tick all running animations
        for anim in self._animations:
            anim.tick(dt)

        # Remove completed (non-looping) animations
        self._animations = [
            a for a in self._animations
            if a.state != AnimationState.COMPLETED
        ]

    @property
    def has_active(self) -> bool:
        """True if any animations are currently running."""
        return any(a.is_running for a in self._animations)

    @property
    def active_count(self) -> int:
        return sum(1 for a in self._animations if a.is_running)

    def get(self, name: str) -> Animation | None:
        """Find an animation by name."""
        for a in self._animations:
            if a.name == name:
                return a
        return None


# --- Screen Transition ---

class TransitionType(Enum):
    """Types of screen transitions."""
    SLIDE_LEFT = auto()    # New screen slides in from right
    SLIDE_RIGHT = auto()   # New screen slides in from left
    SLIDE_UP = auto()      # New screen slides in from bottom
    SLIDE_DOWN = auto()    # New screen slides in from top
    ZOOM_IN = auto()       # New screen zooms in from center
    FADE = auto()          # Crossfade


@dataclass
class TransitionState:
    """Current state of a screen transition."""
    active: bool = False
    progress: float = 0.0    # 0.0 = showing old, 1.0 = showing new
    transition_type: TransitionType = TransitionType.SLIDE_LEFT
    # Pixel offsets for rendering
    old_offset_x: int = 0
    old_offset_y: int = 0
    new_offset_x: int = 0
    new_offset_y: int = 0
    # Zoom scale (1.0 = normal)
    old_scale: float = 1.0
    new_scale: float = 1.0
    # Alpha (0-255)
    old_alpha: int = 255
    new_alpha: int = 255


class ScreenTransitionManager:
    """
    Manages animated transitions between screens.

    The compositor calls get_state() each frame to determine how to
    composite the old and new screens during a transition.
    """

    def __init__(self, screen_width: int = 360, screen_height: int = 720,
                 controller: AnimationController = None):
        self.screen_width = screen_width
        self.screen_height = screen_height
        self.controller = controller or AnimationController()
        self.state = TransitionState()
        self._animation: Animation | None = None

    def start_transition(self, transition_type: TransitionType,
                         duration_ms: int = 300,
                         easing: Easing = Easing.EASE_OUT):
        """Start a screen transition animation."""
        # Cancel any running transition
        if self._animation:
            self.controller.remove(self._animation)

        self.state = TransitionState(active=True,
                                     transition_type=transition_type)

        anim = Animation(name="screen_transition")

        tween = Tween(
            start=0.0, end=1.0,
            duration_ms=duration_ms,
            easing=easing,
            on_update=lambda v: self._update_state(v, transition_type),
            on_complete=self._on_complete,
        )
        anim.add_tween(tween)

        self._animation = self.controller.add(anim)

    def _update_state(self, progress: float, tt: TransitionType):
        """Update offsets/alpha based on progress and transition type."""
        self.state.progress = progress
        w = self.screen_width
        h = self.screen_height

        if tt == TransitionType.SLIDE_LEFT:
            self.state.old_offset_x = int(-w * progress)
            self.state.new_offset_x = int(w * (1.0 - progress))
            self.state.old_offset_y = 0
            self.state.new_offset_y = 0

        elif tt == TransitionType.SLIDE_RIGHT:
            self.state.old_offset_x = int(w * progress)
            self.state.new_offset_x = int(-w * (1.0 - progress))
            self.state.old_offset_y = 0
            self.state.new_offset_y = 0

        elif tt == TransitionType.SLIDE_UP:
            self.state.old_offset_x = 0
            self.state.new_offset_x = 0
            self.state.old_offset_y = int(-h * progress)
            self.state.new_offset_y = int(h * (1.0 - progress))

        elif tt == TransitionType.SLIDE_DOWN:
            self.state.old_offset_x = 0
            self.state.new_offset_x = 0
            self.state.old_offset_y = int(h * progress)
            self.state.new_offset_y = int(-h * (1.0 - progress))

        elif tt == TransitionType.ZOOM_IN:
            self.state.old_scale = 1.0
            self.state.new_scale = 0.5 + 0.5 * progress  # 0.5 → 1.0
            self.state.new_alpha = int(255 * progress)
            self.state.old_alpha = int(255 * (1.0 - progress))
            self.state.old_offset_x = 0
            self.state.new_offset_x = 0
            self.state.old_offset_y = 0
            self.state.new_offset_y = 0

        elif tt == TransitionType.FADE:
            self.state.old_alpha = int(255 * (1.0 - progress))
            self.state.new_alpha = int(255 * progress)
            self.state.old_offset_x = 0
            self.state.new_offset_x = 0
            self.state.old_offset_y = 0
            self.state.new_offset_y = 0

    def _on_complete(self):
        """Transition finished."""
        self.state.active = False
        self.state.progress = 1.0
        self._animation = None

    def cancel(self):
        """Cancel the current transition."""
        if self._animation:
            self.controller.remove(self._animation)
            self._animation = None
        self.state = TransitionState()

    @property
    def is_transitioning(self) -> bool:
        return self.state.active


# --- Smooth Scroll Physics ---

class ScrollPhysics:
    """
    Momentum-based scrolling with deceleration.

    After the user lifts their finger, the scroll continues with
    velocity that decays exponentially (friction).
    """

    def __init__(self, friction: float = 0.95, min_velocity: float = 0.5):
        self.friction = friction
        self.min_velocity = min_velocity
        self.velocity: float = 0.0
        self._active = False

    def fling(self, velocity: float):
        """Start a fling with the given velocity (pixels per frame at 60fps)."""
        self.velocity = velocity
        self._active = abs(velocity) > self.min_velocity

    def tick(self, dt_ms: float) -> float:
        """
        Advance physics by dt_ms. Returns the scroll delta (pixels).
        """
        if not self._active:
            return 0.0

        # Scale friction for actual dt (friction is calibrated for 16.67ms)
        frames = dt_ms / 16.667
        effective_friction = self.friction ** frames

        delta = self.velocity * frames
        self.velocity *= effective_friction

        if abs(self.velocity) < self.min_velocity:
            self.velocity = 0.0
            self._active = False

        return delta

    def stop(self):
        """Stop any active fling."""
        self.velocity = 0.0
        self._active = False

    @property
    def is_active(self) -> bool:
        return self._active


# --- Ripple Effect ---

@dataclass
class RippleEffect:
    """
    Material-style ripple that expands from a touch point.

    The ripple is a circle that grows outward and fades.
    Rendered as a series of alpha-blended rings in the pixel buffer.
    """
    center_x: int = 0
    center_y: int = 0
    max_radius: int = 0
    duration_ms: int = 400
    color_r: int = 255
    color_g: int = 255
    color_b: int = 255
    max_alpha: int = 60

    # Internal
    _elapsed_ms: float = 0.0
    _active: bool = False

    def start(self, cx: int, cy: int, widget_width: int, widget_height: int):
        """Start a ripple at the given center point."""
        self.center_x = cx
        self.center_y = cy
        # Max radius = distance to farthest corner
        dx = max(cx, widget_width - cx)
        dy = max(cy, widget_height - cy)
        self.max_radius = int(math.sqrt(dx * dx + dy * dy))
        self._elapsed_ms = 0.0
        self._active = True

    def tick(self, dt_ms: float):
        """Advance the ripple animation."""
        if not self._active:
            return
        self._elapsed_ms += dt_ms
        if self._elapsed_ms >= self.duration_ms:
            self._active = False

    @property
    def is_active(self) -> bool:
        return self._active

    @property
    def progress(self) -> float:
        if self.duration_ms <= 0:
            return 1.0
        return min(1.0, self._elapsed_ms / self.duration_ms)

    @property
    def current_radius(self) -> int:
        return int(self.max_radius * ease(self.progress, Easing.EASE_OUT))

    @property
    def current_alpha(self) -> int:
        # Fade out in the second half
        p = self.progress
        if p < 0.5:
            return self.max_alpha
        fade = (p - 0.5) / 0.5  # 0→1 in second half
        return int(self.max_alpha * (1.0 - fade))

    def draw(self, buf: bytearray, buf_w: int, buf_h: int,
             ox: int, oy: int, clip_w: int, clip_h: int):
        """
        Draw the ripple into a pixel buffer.

        Args:
            ox, oy: Offset to the widget's top-left in the buffer
            clip_w, clip_h: Widget dimensions (for clipping)
        """
        if not self._active:
            return

        radius = self.current_radius
        alpha = self.current_alpha
        if alpha <= 0 or radius <= 0:
            return

        cx = ox + self.center_x
        cy = oy + self.center_y

        # Draw filled circle with alpha blending
        r2 = radius * radius
        a_frac = alpha / 255.0
        inv_a = 1.0 - a_frac

        # Clip to widget bounds
        x0 = max(ox, cx - radius)
        y0 = max(oy, cy - radius)
        x1 = min(ox + clip_w, cx + radius + 1)
        y1 = min(oy + clip_h, cy + radius + 1)
        x0 = max(0, x0)
        y0 = max(0, y0)
        x1 = min(buf_w, x1)
        y1 = min(buf_h, y1)

        for row in range(y0, y1):
            dy = row - cy
            dy2 = dy * dy
            for col in range(x0, x1):
                dx = col - cx
                if dx * dx + dy2 <= r2:
                    off = (row * buf_w + col) * 4
                    if off + 3 < len(buf):
                        buf[off] = int(buf[off] * inv_a + self.color_b * a_frac)
                        buf[off + 1] = int(buf[off + 1] * inv_a + self.color_g * a_frac)
                        buf[off + 2] = int(buf[off + 2] * inv_a + self.color_r * a_frac)
                        buf[off + 3] = 255


# --- Loading Spinner ---

class LoadingSpinner:
    """
    Animated loading spinner.

    Renders an arc that rotates. Drawn as pixels in a bounding box.
    """

    def __init__(self, size: int = 32, thickness: int = 3,
                 color_r: int = 217, color_g: int = 119, color_b: int = 52):
        self.size = size
        self.thickness = thickness
        self.color_r = color_r
        self.color_g = color_g
        self.color_b = color_b
        self._angle: float = 0.0  # radians
        self._active = False
        self.speed: float = 4.0  # radians per second

    def start(self):
        self._active = True
        self._angle = 0.0

    def stop(self):
        self._active = False

    @property
    def is_active(self) -> bool:
        return self._active

    def tick(self, dt_ms: float):
        if not self._active:
            return
        self._angle += self.speed * (dt_ms / 1000.0)
        if self._angle >= 2 * math.pi:
            self._angle -= 2 * math.pi

    def draw(self, buf: bytearray, buf_w: int, buf_h: int,
             cx: int, cy: int):
        """
        Draw the spinner centered at (cx, cy).
        """
        if not self._active:
            return

        r_outer = self.size // 2
        r_inner = r_outer - self.thickness
        if r_inner < 0:
            r_inner = 0

        r_outer2 = r_outer * r_outer
        r_inner2 = r_inner * r_inner

        # The arc spans 270 degrees (3/4 of circle), rotated by _angle
        arc_span = math.pi * 1.5  # 270 degrees
        start_angle = self._angle
        end_angle = start_angle + arc_span

        for row in range(max(0, cy - r_outer), min(buf_h, cy + r_outer + 1)):
            dy = row - cy
            dy2 = dy * dy
            for col in range(max(0, cx - r_outer), min(buf_w, cx + r_outer + 1)):
                dx = col - cx
                dist2 = dx * dx + dy2

                # Check if within ring
                if dist2 < r_inner2 or dist2 > r_outer2:
                    continue

                # Check if within arc angle
                angle = math.atan2(dy, dx) + math.pi  # 0 to 2pi
                # Normalize relative to start_angle
                rel = (angle - start_angle) % (2 * math.pi)
                if rel > arc_span:
                    continue

                off = (row * buf_w + col) * 4
                if off + 3 < len(buf):
                    # Anti-alias at edges
                    alpha = 200
                    a_frac = alpha / 255.0
                    inv_a = 1.0 - a_frac
                    buf[off] = int(buf[off] * inv_a + self.color_b * a_frac)
                    buf[off + 1] = int(buf[off + 1] * inv_a + self.color_g * a_frac)
                    buf[off + 2] = int(buf[off + 2] * inv_a + self.color_r * a_frac)
                    buf[off + 3] = 255


# --- Skeleton Screen ---

class SkeletonBlock:
    """
    A placeholder block that shimmers while content loads.

    Renders a rectangle with a shimmer highlight that moves across it.
    """

    def __init__(self, width: int = 200, height: int = 16,
                 corner_radius: int = 4):
        self.width = width
        self.height = height
        self.corner_radius = corner_radius
        self.base_color_r: int = 38
        self.base_color_g: int = 38
        self.base_color_b: int = 52
        self.highlight_color_r: int = 55
        self.highlight_color_g: int = 55
        self.highlight_color_b: int = 70
        self._phase: float = 0.0
        self._active = True
        self.shimmer_speed: float = 1.5  # cycles per second

    def tick(self, dt_ms: float):
        if not self._active:
            return
        self._phase += self.shimmer_speed * (dt_ms / 1000.0)
        if self._phase >= 1.0:
            self._phase = self._phase % 1.0

    def start(self):
        self._active = True
        self._phase = 0.0

    def stop(self):
        self._active = False

    @property
    def is_active(self) -> bool:
        return self._active

    def draw(self, buf: bytearray, buf_w: int, buf_h: int,
             x: int, y: int):
        """Draw the skeleton block with shimmer effect."""
        if not self._active:
            return

        # Shimmer position: moves from left to right
        shimmer_center = int((self._phase * 2.0 - 0.5) * self.width)
        shimmer_half_width = self.width // 4

        x0 = max(0, x)
        y0 = max(0, y)
        x1 = min(buf_w, x + self.width)
        y1 = min(buf_h, y + self.height)

        for row in range(y0, y1):
            for col in range(x0, x1):
                # Shimmer blend factor
                dist = abs(col - x - shimmer_center)
                if dist < shimmer_half_width:
                    blend = 1.0 - (dist / shimmer_half_width)
                else:
                    blend = 0.0

                r = int(self.base_color_r + (self.highlight_color_r - self.base_color_r) * blend)
                g = int(self.base_color_g + (self.highlight_color_g - self.base_color_g) * blend)
                b = int(self.base_color_b + (self.highlight_color_b - self.base_color_b) * blend)

                off = (row * buf_w + col) * 4
                if off + 3 < len(buf):
                    buf[off] = b
                    buf[off + 1] = g
                    buf[off + 2] = r
                    buf[off + 3] = 255


# --- Dark/Light Theme ---

class DarkColors:
    """Dark theme colors (default)."""
    PRIMARY = (217, 119, 52)
    BACKGROUND = (10, 10, 20)
    SURFACE = (24, 24, 36)
    SURFACE_DIM = (18, 18, 28)
    SURFACE_BRIGHT = (38, 38, 52)
    SURFACE_CONTAINER = (30, 30, 44)
    TEXT_PRIMARY = (240, 240, 245)
    TEXT_SECONDARY = (180, 180, 195)
    TEXT_DISABLED = (100, 100, 115)
    BORDER = (60, 60, 75)
    DIVIDER = (45, 45, 60)


class LightColors:
    """Light theme colors."""
    PRIMARY = (217, 119, 52)
    BACKGROUND = (248, 248, 252)
    SURFACE = (255, 255, 255)
    SURFACE_DIM = (238, 238, 242)
    SURFACE_BRIGHT = (245, 245, 249)
    SURFACE_CONTAINER = (242, 242, 246)
    TEXT_PRIMARY = (20, 20, 30)
    TEXT_SECONDARY = (90, 90, 105)
    TEXT_DISABLED = (160, 160, 175)
    BORDER = (210, 210, 220)
    DIVIDER = (225, 225, 235)


class ThemeMode(Enum):
    DARK = auto()
    LIGHT = auto()


class ThemeManager:
    """
    Manages dark/light mode switching.

    Applies color changes to the Colors class when the theme is toggled.
    Supports animated transitions between themes.
    """

    def __init__(self, mode: ThemeMode = ThemeMode.DARK):
        self._mode = mode
        self._listeners: list[Callable[[ThemeMode], None]] = []

    @property
    def mode(self) -> ThemeMode:
        return self._mode

    @property
    def is_dark(self) -> bool:
        return self._mode == ThemeMode.DARK

    def toggle(self):
        """Toggle between dark and light mode."""
        if self._mode == ThemeMode.DARK:
            self.set_mode(ThemeMode.LIGHT)
        else:
            self.set_mode(ThemeMode.DARK)

    def set_mode(self, mode: ThemeMode):
        """Set the theme mode and apply colors."""
        if mode == self._mode:
            return
        self._mode = mode
        self._apply()
        for listener in self._listeners:
            listener(mode)

    def _apply(self):
        """Apply the current theme colors to the Colors class."""
        from theme import Color, Colors

        palette = DarkColors if self._mode == ThemeMode.DARK else LightColors

        Colors.PRIMARY = Color(*palette.PRIMARY)
        Colors.BACKGROUND = Color(*palette.BACKGROUND)
        Colors.SURFACE = Color(*palette.SURFACE)
        Colors.SURFACE_DIM = Color(*palette.SURFACE_DIM)
        Colors.SURFACE_BRIGHT = Color(*palette.SURFACE_BRIGHT)
        Colors.SURFACE_CONTAINER = Color(*palette.SURFACE_CONTAINER)
        Colors.TEXT_PRIMARY = Color(*palette.TEXT_PRIMARY)
        Colors.TEXT_SECONDARY = Color(*palette.TEXT_SECONDARY)
        Colors.TEXT_DISABLED = Color(*palette.TEXT_DISABLED)
        Colors.BORDER = Color(*palette.BORDER)
        Colors.DIVIDER = Color(*palette.DIVIDER)

    def on_change(self, listener: Callable[[ThemeMode], None]):
        """Register a callback for theme changes."""
        self._listeners.append(listener)

    def get_colors(self) -> type:
        """Get the color class for the current theme."""
        if self._mode == ThemeMode.DARK:
            return DarkColors
        return LightColors


# --- Adaptive Layout ---

class ScreenSize(Enum):
    """Screen size categories."""
    SMALL = auto()    # < 360px wide (small phone)
    MEDIUM = auto()   # 360-414px (standard phone)
    LARGE = auto()    # 414-768px (large phone / small tablet)
    XLARGE = auto()   # >= 768px (tablet)


class AdaptiveLayout:
    """
    Determines layout parameters based on screen dimensions.

    Provides responsive values for columns, font scale, spacing,
    and component sizes.
    """

    def __init__(self, screen_width: int = 360, screen_height: int = 720):
        self.screen_width = screen_width
        self.screen_height = screen_height

    @property
    def size_class(self) -> ScreenSize:
        w = self.screen_width
        if w < 360:
            return ScreenSize.SMALL
        elif w < 414:
            return ScreenSize.MEDIUM
        elif w < 768:
            return ScreenSize.LARGE
        return ScreenSize.XLARGE

    @property
    def grid_columns(self) -> int:
        """Number of columns for app grid layouts."""
        sc = self.size_class
        if sc == ScreenSize.SMALL:
            return 3
        elif sc == ScreenSize.MEDIUM:
            return 4
        elif sc == ScreenSize.LARGE:
            return 5
        return 6

    @property
    def font_scale(self) -> float:
        """Scale factor for font sizes."""
        sc = self.size_class
        if sc == ScreenSize.SMALL:
            return 0.85
        elif sc == ScreenSize.MEDIUM:
            return 1.0
        elif sc == ScreenSize.LARGE:
            return 1.1
        return 1.2

    @property
    def spacing_scale(self) -> float:
        """Scale factor for spacing values."""
        sc = self.size_class
        if sc == ScreenSize.SMALL:
            return 0.8
        elif sc == ScreenSize.MEDIUM:
            return 1.0
        elif sc == ScreenSize.LARGE:
            return 1.15
        return 1.3

    @property
    def status_bar_height(self) -> int:
        return int(48 * self.spacing_scale)

    @property
    def keyboard_height(self) -> int:
        """Keyboard height adapts to screen height."""
        return max(200, int(self.screen_height * 0.38))

    @property
    def icon_size(self) -> int:
        """App icon size."""
        sc = self.size_class
        if sc == ScreenSize.SMALL:
            return 40
        elif sc == ScreenSize.MEDIUM:
            return 48
        elif sc == ScreenSize.LARGE:
            return 56
        return 64

    def scale_spacing(self, base: int) -> int:
        """Scale a spacing value for the current screen size."""
        return int(base * self.spacing_scale)

    def scale_font(self, base_size: int) -> int:
        """Scale a font size for the current screen size."""
        return max(8, int(base_size * self.font_scale))

    def get_content_width(self, margin: int = 16) -> int:
        """Available content width after margins."""
        return self.screen_width - 2 * self.scale_spacing(margin)

    @property
    def is_landscape(self) -> bool:
        return self.screen_width > self.screen_height

    def update(self, width: int, height: int):
        """Update dimensions (e.g., on rotation)."""
        self.screen_width = width
        self.screen_height = height
