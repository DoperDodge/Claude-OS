"""
Tests for Phase 6 — Animations & Polish.

Covers: easing functions, tweens, animations, animation controller,
screen transitions, scroll physics, ripple effect, loading spinner,
skeleton screen, dark/light theme, adaptive layout.
"""

import math
import pytest

from animation import (
    Easing, ease,
    Tween, Animation, AnimationState, AnimationController,
    TransitionType, TransitionState, ScreenTransitionManager,
    ScrollPhysics, RippleEffect, LoadingSpinner, SkeletonBlock,
    ThemeMode, ThemeManager, DarkColors, LightColors,
    ScreenSize, AdaptiveLayout,
)


# --- Easing ---

class TestEasing:
    def test_linear(self):
        assert ease(0.0, Easing.LINEAR) == 0.0
        assert ease(0.5, Easing.LINEAR) == 0.5
        assert ease(1.0, Easing.LINEAR) == 1.0

    def test_ease_in(self):
        assert ease(0.0, Easing.EASE_IN) == 0.0
        assert ease(1.0, Easing.EASE_IN) == 1.0
        # Ease in is slower at start: value at 0.5 should be < 0.5
        assert ease(0.5, Easing.EASE_IN) < 0.5

    def test_ease_out(self):
        assert ease(0.0, Easing.EASE_OUT) == 0.0
        assert ease(1.0, Easing.EASE_OUT) == 1.0
        # Ease out is faster at start: value at 0.5 should be > 0.5
        assert ease(0.5, Easing.EASE_OUT) > 0.5

    def test_ease_in_out(self):
        assert ease(0.0, Easing.EASE_IN_OUT) == 0.0
        assert ease(1.0, Easing.EASE_IN_OUT) == 1.0
        # Symmetric around 0.5
        val = ease(0.5, Easing.EASE_IN_OUT)
        assert 0.49 < val < 0.51

    def test_ease_out_back(self):
        assert ease(0.0, Easing.EASE_OUT_BACK) == pytest.approx(0.0, abs=0.01)
        assert ease(1.0, Easing.EASE_OUT_BACK) == pytest.approx(1.0, abs=0.01)
        # Overshoot: some value > 1.0 during the animation
        assert ease(0.7, Easing.EASE_OUT_BACK) > 1.0

    def test_ease_out_cubic(self):
        assert ease(0.0, Easing.EASE_OUT_CUBIC) == 0.0
        assert ease(1.0, Easing.EASE_OUT_CUBIC) == 1.0
        assert ease(0.5, Easing.EASE_OUT_CUBIC) > 0.5

    def test_clamps_input(self):
        assert ease(-1.0, Easing.LINEAR) == 0.0
        assert ease(2.0, Easing.LINEAR) == 1.0


# --- Tween ---

class TestTween:
    def test_initial_value(self):
        tw = Tween(start=0.0, end=100.0, duration_ms=500)
        assert tw.current_value == 0.0
        assert not tw.is_complete

    def test_tick_to_completion(self):
        tw = Tween(start=0.0, end=100.0, duration_ms=100, easing=Easing.LINEAR)
        tw.tick(50)
        assert 49.0 < tw.current_value < 51.0
        tw.tick(50)
        assert tw.current_value == 100.0
        assert tw.is_complete

    def test_on_update_called(self):
        values = []
        tw = Tween(start=0.0, end=10.0, duration_ms=100,
                   easing=Easing.LINEAR, on_update=values.append)
        tw.tick(50)
        tw.tick(50)
        assert len(values) >= 2
        assert values[-1] == 10.0

    def test_on_complete_called(self):
        completed = []
        tw = Tween(start=0.0, end=1.0, duration_ms=100,
                   on_complete=lambda: completed.append(True))
        tw.tick(200)
        assert len(completed) == 1

    def test_delay(self):
        tw = Tween(start=0.0, end=100.0, duration_ms=100,
                   easing=Easing.LINEAR, delay_ms=50)
        tw.tick(25)
        assert tw.current_value == 0.0  # Still in delay
        tw.tick(25)
        # Now 50ms elapsed, delay over, 0ms into animation
        assert tw.current_value == pytest.approx(0.0, abs=1.0)
        tw.tick(50)
        # 100ms elapsed, 50ms into animation
        assert 49.0 < tw.current_value < 51.0

    def test_reset(self):
        tw = Tween(start=0.0, end=100.0, duration_ms=100)
        tw.tick(200)
        assert tw.is_complete
        tw.reset()
        assert not tw.is_complete
        assert tw.current_value == 0.0

    def test_zero_duration(self):
        tw = Tween(start=0.0, end=50.0, duration_ms=0)
        assert tw.current_value == 50.0


# --- Animation ---

class TestAnimation:
    def test_create(self):
        anim = Animation(name="test")
        assert anim.name == "test"
        assert anim.state == AnimationState.IDLE

    def test_start(self):
        anim = Animation()
        anim.add_tween(Tween(0, 1, 100))
        anim.start()
        assert anim.state == AnimationState.RUNNING
        assert anim.is_running

    def test_tick_completes(self):
        anim = Animation()
        anim.add_tween(Tween(0, 1, 100))
        anim.start()
        anim.tick(200)
        assert anim.state == AnimationState.COMPLETED

    def test_on_complete(self):
        done = []
        anim = Animation(on_complete=lambda: done.append(True))
        anim.add_tween(Tween(0, 1, 100))
        anim.start()
        anim.tick(200)
        assert len(done) == 1

    def test_loop(self):
        anim = Animation(loop=True)
        anim.add_tween(Tween(0, 1, 100))
        anim.start()
        anim.tick(200)
        # Should still be running because it loops
        assert anim.state == AnimationState.RUNNING

    def test_pause_resume(self):
        anim = Animation()
        anim.add_tween(Tween(0, 1, 100))
        anim.start()
        anim.pause()
        assert anim.state == AnimationState.PAUSED
        anim.tick(200)  # Should not advance
        anim.resume()
        assert anim.state == AnimationState.RUNNING

    def test_stop(self):
        anim = Animation()
        anim.add_tween(Tween(0, 1, 100))
        anim.start()
        anim.stop()
        assert anim.state == AnimationState.COMPLETED

    def test_progress(self):
        anim = Animation()
        anim.add_tween(Tween(0, 1, 200))
        anim.start()
        anim.tick(100)
        assert 0.49 < anim.progress < 0.51

    def test_multiple_tweens(self):
        vals_a = []
        vals_b = []
        anim = Animation()
        anim.add_tween(Tween(0, 100, 100, easing=Easing.LINEAR,
                             on_update=vals_a.append))
        anim.add_tween(Tween(0, 200, 100, easing=Easing.LINEAR,
                             on_update=vals_b.append))
        anim.start()
        anim.tick(100)
        assert vals_a[-1] == 100.0
        assert vals_b[-1] == 200.0

    def test_total_duration(self):
        anim = Animation()
        anim.add_tween(Tween(0, 1, 200, delay_ms=100))
        anim.add_tween(Tween(0, 1, 150))
        assert anim.total_duration_ms == 300  # 200 + 100 delay


# --- AnimationController ---

class TestAnimationController:
    def test_create(self):
        ctrl = AnimationController()
        assert not ctrl.has_active
        assert ctrl.active_count == 0

    def test_add_starts_animation(self):
        ctrl = AnimationController()
        anim = Animation()
        anim.add_tween(Tween(0, 1, 100))
        ctrl.add(anim)
        assert ctrl.has_active
        assert ctrl.active_count == 1

    def test_tick_advances(self):
        ctrl = AnimationController()
        vals = []
        anim = Animation()
        anim.add_tween(Tween(0, 100, 100, easing=Easing.LINEAR,
                             on_update=vals.append))
        ctrl.add(anim)
        ctrl.tick(0)     # First tick: records time
        ctrl.tick(100)   # Second tick: dt=100
        assert len(vals) >= 1
        assert vals[-1] == 100.0

    def test_removes_completed(self):
        ctrl = AnimationController()
        anim = Animation()
        anim.add_tween(Tween(0, 1, 50))
        ctrl.add(anim)
        ctrl.tick(0)
        ctrl.tick(100)
        assert ctrl.active_count == 0

    def test_cancel_by_name(self):
        ctrl = AnimationController()
        anim = Animation(name="test_anim")
        anim.add_tween(Tween(0, 1, 1000))
        ctrl.add(anim)
        assert ctrl.active_count == 1
        ctrl.cancel("test_anim")
        assert ctrl.active_count == 0

    def test_cancel_all(self):
        ctrl = AnimationController()
        for i in range(3):
            a = Animation(name=f"a{i}")
            a.add_tween(Tween(0, 1, 1000))
            ctrl.add(a)
        assert ctrl.active_count == 3
        ctrl.cancel_all()
        assert ctrl.active_count == 0

    def test_get_by_name(self):
        ctrl = AnimationController()
        anim = Animation(name="findme")
        anim.add_tween(Tween(0, 1, 100))
        ctrl.add(anim)
        assert ctrl.get("findme") is anim
        assert ctrl.get("nonexistent") is None


# --- Screen Transitions ---

class TestScreenTransitions:
    def test_slide_left(self):
        ctrl = AnimationController()
        mgr = ScreenTransitionManager(360, 720, ctrl)
        mgr.start_transition(TransitionType.SLIDE_LEFT, duration_ms=200)
        assert mgr.is_transitioning
        assert mgr.state.active
        # Simulate time
        ctrl.tick(0)
        ctrl.tick(100)
        # Mid-transition: old screen should be sliding left, new from right
        assert mgr.state.old_offset_x < 0
        assert mgr.state.new_offset_x > 0
        ctrl.tick(200)
        assert not mgr.is_transitioning

    def test_slide_right(self):
        ctrl = AnimationController()
        mgr = ScreenTransitionManager(360, 720, ctrl)
        mgr.start_transition(TransitionType.SLIDE_RIGHT, duration_ms=200)
        ctrl.tick(0)
        ctrl.tick(100)
        assert mgr.state.old_offset_x > 0
        assert mgr.state.new_offset_x < 0

    def test_slide_up(self):
        ctrl = AnimationController()
        mgr = ScreenTransitionManager(360, 720, ctrl)
        mgr.start_transition(TransitionType.SLIDE_UP, duration_ms=200)
        ctrl.tick(0)
        ctrl.tick(100)
        assert mgr.state.old_offset_y < 0
        assert mgr.state.new_offset_y > 0

    def test_slide_down(self):
        ctrl = AnimationController()
        mgr = ScreenTransitionManager(360, 720, ctrl)
        mgr.start_transition(TransitionType.SLIDE_DOWN, duration_ms=200)
        ctrl.tick(0)
        ctrl.tick(100)
        assert mgr.state.old_offset_y > 0
        assert mgr.state.new_offset_y < 0

    def test_zoom_in(self):
        ctrl = AnimationController()
        mgr = ScreenTransitionManager(360, 720, ctrl)
        mgr.start_transition(TransitionType.ZOOM_IN, duration_ms=200)
        ctrl.tick(0)
        ctrl.tick(100)
        # New screen should be scaling up
        assert mgr.state.new_scale < 1.0
        assert mgr.state.new_alpha < 255

    def test_fade(self):
        ctrl = AnimationController()
        mgr = ScreenTransitionManager(360, 720, ctrl)
        mgr.start_transition(TransitionType.FADE, duration_ms=200)
        ctrl.tick(0)
        ctrl.tick(100)
        assert mgr.state.old_alpha < 255
        assert mgr.state.new_alpha < 255

    def test_cancel(self):
        ctrl = AnimationController()
        mgr = ScreenTransitionManager(360, 720, ctrl)
        mgr.start_transition(TransitionType.SLIDE_LEFT, duration_ms=500)
        assert mgr.is_transitioning
        mgr.cancel()
        assert not mgr.is_transitioning

    def test_replaces_previous(self):
        ctrl = AnimationController()
        mgr = ScreenTransitionManager(360, 720, ctrl)
        mgr.start_transition(TransitionType.SLIDE_LEFT, duration_ms=500)
        mgr.start_transition(TransitionType.SLIDE_RIGHT, duration_ms=500)
        assert mgr.state.transition_type == TransitionType.SLIDE_RIGHT


# --- Scroll Physics ---

class TestScrollPhysics:
    def test_initial_state(self):
        sp = ScrollPhysics()
        assert not sp.is_active
        assert sp.velocity == 0.0

    def test_fling(self):
        sp = ScrollPhysics()
        sp.fling(10.0)
        assert sp.is_active
        delta = sp.tick(16.67)
        assert delta != 0.0
        assert sp.velocity < 10.0  # Friction applied

    def test_deceleration(self):
        sp = ScrollPhysics()
        sp.fling(100.0)
        deltas = []
        for _ in range(20):
            deltas.append(abs(sp.tick(16.67)))
        # Each delta should be smaller than the previous (decelerating)
        for i in range(1, len(deltas)):
            if deltas[i] == 0:
                break
            assert deltas[i] <= deltas[i - 1] + 0.01

    def test_stops_eventually(self):
        sp = ScrollPhysics()
        sp.fling(5.0)
        for _ in range(200):
            sp.tick(16.67)
        assert not sp.is_active

    def test_stop(self):
        sp = ScrollPhysics()
        sp.fling(100.0)
        sp.stop()
        assert not sp.is_active
        assert sp.velocity == 0.0

    def test_zero_velocity_not_active(self):
        sp = ScrollPhysics()
        sp.fling(0.0)
        assert not sp.is_active


# --- Ripple Effect ---

class TestRippleEffect:
    def test_initial_state(self):
        rip = RippleEffect()
        assert not rip.is_active

    def test_start(self):
        rip = RippleEffect()
        rip.start(50, 50, 100, 100)
        assert rip.is_active
        assert rip.center_x == 50
        assert rip.center_y == 50
        assert rip.max_radius > 0

    def test_progress(self):
        rip = RippleEffect(duration_ms=200)
        rip.start(50, 50, 100, 100)
        rip.tick(100)
        assert 0.49 < rip.progress < 0.51

    def test_completes(self):
        rip = RippleEffect(duration_ms=100)
        rip.start(50, 50, 100, 100)
        rip.tick(200)
        assert not rip.is_active

    def test_radius_grows(self):
        rip = RippleEffect(duration_ms=200)
        rip.start(50, 50, 100, 100)
        rip.tick(50)
        r1 = rip.current_radius
        rip.tick(50)
        r2 = rip.current_radius
        assert r2 > r1

    def test_alpha_fades(self):
        rip = RippleEffect(duration_ms=200)
        rip.start(50, 50, 100, 100)
        rip.tick(50)
        a1 = rip.current_alpha  # First half — full alpha
        rip.tick(100)
        a2 = rip.current_alpha  # Second half — fading
        assert a2 < a1

    def test_draw(self):
        rip = RippleEffect(duration_ms=200)
        rip.start(10, 10, 20, 20)
        rip.tick(50)
        buf = bytearray(40 * 40 * 4)
        rip.draw(buf, 40, 40, 0, 0, 20, 20)
        # Verify some pixels were drawn (non-zero)
        any_drawn = any(buf[i] != 0 for i in range(0, len(buf), 4))
        assert any_drawn

    def test_max_radius_corner(self):
        rip = RippleEffect()
        rip.start(0, 0, 100, 100)
        # Max radius from (0,0) to farthest corner (100, 100)
        expected = int(math.sqrt(100**2 + 100**2))
        assert rip.max_radius == expected


# --- Loading Spinner ---

class TestLoadingSpinner:
    def test_initial(self):
        spinner = LoadingSpinner()
        assert not spinner.is_active

    def test_start_stop(self):
        spinner = LoadingSpinner()
        spinner.start()
        assert spinner.is_active
        spinner.stop()
        assert not spinner.is_active

    def test_tick_rotates(self):
        spinner = LoadingSpinner()
        spinner.start()
        angle0 = spinner._angle
        spinner.tick(100)
        assert spinner._angle > angle0

    def test_draw(self):
        spinner = LoadingSpinner(size=20, thickness=3)
        spinner.start()
        spinner.tick(100)
        buf = bytearray(40 * 40 * 4)
        spinner.draw(buf, 40, 40, 20, 20)
        any_drawn = any(buf[i] != 0 for i in range(0, len(buf), 4))
        assert any_drawn

    def test_no_draw_when_stopped(self):
        spinner = LoadingSpinner(size=20)
        buf = bytearray(40 * 40 * 4)
        spinner.draw(buf, 40, 40, 20, 20)
        assert all(b == 0 for b in buf)


# --- Skeleton Screen ---

class TestSkeletonBlock:
    def test_initial(self):
        sk = SkeletonBlock()
        assert sk.is_active

    def test_tick_advances_phase(self):
        sk = SkeletonBlock()
        phase0 = sk._phase
        sk.tick(100)
        assert sk._phase > phase0

    def test_phase_wraps(self):
        sk = SkeletonBlock()
        sk.shimmer_speed = 10.0
        sk.tick(1000)
        assert sk._phase < 1.0

    def test_draw(self):
        sk = SkeletonBlock(width=30, height=10)
        sk.tick(100)
        buf = bytearray(50 * 20 * 4)
        sk.draw(buf, 50, 20, 5, 5)
        # Should have drawn something (non-zero pixels)
        any_drawn = any(buf[i] != 0 for i in range(0, len(buf), 4))
        assert any_drawn

    def test_stop(self):
        sk = SkeletonBlock()
        sk.stop()
        assert not sk.is_active

    def test_start(self):
        sk = SkeletonBlock()
        sk.stop()
        sk.start()
        assert sk.is_active


# --- Theme Manager ---

class TestThemeManager:
    def test_default_dark(self):
        tm = ThemeManager()
        assert tm.mode == ThemeMode.DARK
        assert tm.is_dark

    def test_toggle(self):
        tm = ThemeManager()
        tm.toggle()
        assert tm.mode == ThemeMode.LIGHT
        assert not tm.is_dark
        tm.toggle()
        assert tm.mode == ThemeMode.DARK

    def test_set_mode(self):
        tm = ThemeManager()
        tm.set_mode(ThemeMode.LIGHT)
        assert tm.mode == ThemeMode.LIGHT

    def test_set_same_mode_noop(self):
        changes = []
        tm = ThemeManager()
        tm.on_change(changes.append)
        tm.set_mode(ThemeMode.DARK)  # Already dark
        assert len(changes) == 0

    def test_listener(self):
        changes = []
        tm = ThemeManager()
        tm.on_change(changes.append)
        tm.toggle()
        assert len(changes) == 1
        assert changes[0] == ThemeMode.LIGHT

    def test_applies_colors(self):
        from theme import Colors
        tm = ThemeManager()
        tm.set_mode(ThemeMode.LIGHT)
        assert Colors.BACKGROUND.r == LightColors.BACKGROUND[0]
        assert Colors.BACKGROUND.g == LightColors.BACKGROUND[1]
        # Reset
        tm.set_mode(ThemeMode.DARK)
        assert Colors.BACKGROUND.r == DarkColors.BACKGROUND[0]

    def test_get_colors(self):
        tm = ThemeManager()
        assert tm.get_colors() == DarkColors
        tm.toggle()
        assert tm.get_colors() == LightColors

    def test_light_mode_colors(self):
        tm = ThemeManager(mode=ThemeMode.LIGHT)
        assert not tm.is_dark


# --- Adaptive Layout ---

class TestAdaptiveLayout:
    def test_default(self):
        al = AdaptiveLayout()
        assert al.screen_width == 360
        assert al.screen_height == 720
        assert al.size_class == ScreenSize.MEDIUM

    def test_small_screen(self):
        al = AdaptiveLayout(320, 568)
        assert al.size_class == ScreenSize.SMALL
        assert al.grid_columns == 3
        assert al.font_scale < 1.0

    def test_medium_screen(self):
        al = AdaptiveLayout(375, 667)
        assert al.size_class == ScreenSize.MEDIUM
        assert al.grid_columns == 4
        assert al.font_scale == 1.0

    def test_large_screen(self):
        al = AdaptiveLayout(414, 896)
        assert al.size_class == ScreenSize.LARGE
        assert al.grid_columns == 5
        assert al.font_scale > 1.0

    def test_xlarge_screen(self):
        al = AdaptiveLayout(768, 1024)
        assert al.size_class == ScreenSize.XLARGE
        assert al.grid_columns == 6
        assert al.font_scale > 1.0

    def test_scale_spacing(self):
        al = AdaptiveLayout(320, 568)  # Small
        assert al.scale_spacing(16) < 16
        al2 = AdaptiveLayout(768, 1024)  # XLarge
        assert al2.scale_spacing(16) > 16

    def test_scale_font(self):
        al = AdaptiveLayout(320, 568)
        assert al.scale_font(16) < 16
        al2 = AdaptiveLayout(768, 1024)
        assert al2.scale_font(16) > 16

    def test_min_font_size(self):
        al = AdaptiveLayout(320, 568)
        assert al.scale_font(8) >= 8

    def test_content_width(self):
        al = AdaptiveLayout(360, 720)
        cw = al.get_content_width(16)
        assert cw < 360
        assert cw > 300

    def test_landscape(self):
        al = AdaptiveLayout(720, 360)
        assert al.is_landscape

    def test_portrait(self):
        al = AdaptiveLayout(360, 720)
        assert not al.is_landscape

    def test_update(self):
        al = AdaptiveLayout(360, 720)
        al.update(720, 360)
        assert al.screen_width == 720
        assert al.is_landscape

    def test_keyboard_height(self):
        al = AdaptiveLayout(360, 720)
        kh = al.keyboard_height
        assert kh >= 200

    def test_icon_size(self):
        al_small = AdaptiveLayout(320, 568)
        al_large = AdaptiveLayout(768, 1024)
        assert al_large.icon_size > al_small.icon_size

    def test_status_bar_height(self):
        al = AdaptiveLayout(360, 720)
        assert al.status_bar_height > 0


# --- Integration ---

class TestIntegration:
    def test_controller_with_transition(self):
        """Screen transition works end-to-end via the shared controller."""
        ctrl = AnimationController()
        mgr = ScreenTransitionManager(360, 720, ctrl)
        mgr.start_transition(TransitionType.SLIDE_LEFT, duration_ms=100)

        ctrl.tick(0)
        assert mgr.is_transitioning

        ctrl.tick(50)
        assert mgr.state.progress > 0
        assert mgr.state.new_offset_x > 0

        ctrl.tick(100)
        assert not mgr.is_transitioning

    def test_multiple_animations(self):
        """Multiple animations run concurrently."""
        ctrl = AnimationController()
        vals = {"a": 0, "b": 0}
        a1 = Animation(name="a")
        a1.add_tween(Tween(0, 100, 100, easing=Easing.LINEAR,
                           on_update=lambda v: vals.__setitem__("a", v)))
        a2 = Animation(name="b")
        a2.add_tween(Tween(0, 200, 100, easing=Easing.LINEAR,
                           on_update=lambda v: vals.__setitem__("b", v)))
        ctrl.add(a1)
        ctrl.add(a2)
        ctrl.tick(0)
        ctrl.tick(100)
        assert vals["a"] == 100.0
        assert vals["b"] == 200.0

    def test_scroll_physics_with_controller(self):
        """Scroll physics integrates with animation controller timing."""
        sp = ScrollPhysics()
        sp.fling(50.0)
        total = 0
        for _ in range(30):
            total += sp.tick(16.67)
        assert total > 0
        # Should have stopped after enough frames
        for _ in range(200):
            sp.tick(16.67)
        assert not sp.is_active

    def test_theme_toggle_restores(self):
        """Toggling theme twice restores original colors."""
        from theme import Colors
        # Force dark mode to establish baseline
        tm = ThemeManager(mode=ThemeMode.LIGHT)  # Start light so set_mode(DARK) actually applies
        tm.set_mode(ThemeMode.DARK)
        orig_bg = (Colors.BACKGROUND.r, Colors.BACKGROUND.g, Colors.BACKGROUND.b)
        tm.toggle()  # → Light
        tm.toggle()  # → Dark
        restored = (Colors.BACKGROUND.r, Colors.BACKGROUND.g, Colors.BACKGROUND.b)
        assert orig_bg == restored
