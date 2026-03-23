"""Tests for the Wayland compositor."""

import pytest
from compositor import Compositor, OutputConfig, Surface, SurfaceRole


@pytest.fixture
def comp():
    """Create a compositor instance."""
    config = OutputConfig(width=1080, height=2340, scale=2.0)
    return Compositor(config)


class TestSurfaceManagement:
    """Test surface add/remove/focus."""

    def test_add_app_surface(self, comp):
        surface = comp.add_surface("wl_surf_1", app_id="claude-app",
                                    role=SurfaceRole.APP)
        assert surface.role == SurfaceRole.APP
        assert surface.app_id == "claude-app"
        assert surface.width == 1080
        assert surface.y == comp.STATUS_BAR_HEIGHT

    def test_add_status_bar(self, comp):
        surface = comp.add_surface("wl_surf_bar", role=SurfaceRole.STATUS_BAR)
        assert surface.role == SurfaceRole.STATUS_BAR
        assert surface.y == 0
        assert surface.height == comp.STATUS_BAR_HEIGHT
        assert surface.width == 1080

    def test_add_keyboard(self, comp):
        surface = comp.add_surface("wl_surf_kb", role=SurfaceRole.KEYBOARD)
        assert surface.role == SurfaceRole.KEYBOARD
        assert surface.visible is False  # Hidden by default
        assert surface.height == comp.KEYBOARD_HEIGHT

    def test_first_app_becomes_active(self, comp):
        surface = comp.add_surface("wl_surf_1", app_id="app1",
                                    role=SurfaceRole.APP)
        assert comp.active_surface == surface

    def test_remove_active_surface_falls_back(self, comp):
        s1 = comp.add_surface("s1", app_id="app1", role=SurfaceRole.APP)
        s2 = comp.add_surface("s2", app_id="app2", role=SurfaceRole.APP)
        comp.focus_surface(s2)

        comp.remove_surface(s2)
        assert comp.active_surface == s1

    def test_remove_last_surface(self, comp):
        s = comp.add_surface("s1", app_id="app1", role=SurfaceRole.APP)
        comp.remove_surface(s)
        assert comp.active_surface is None

    def test_focus_surface(self, comp):
        s1 = comp.add_surface("s1", app_id="app1", role=SurfaceRole.APP)
        s2 = comp.add_surface("s2", app_id="app2", role=SurfaceRole.APP)

        comp.focus_surface(s2)
        assert comp.active_surface == s2

        comp.focus_surface(s1)
        assert comp.active_surface == s1

    def test_focus_non_app_ignored(self, comp):
        app = comp.add_surface("app", app_id="app1", role=SurfaceRole.APP)
        bar = comp.add_surface("bar", role=SurfaceRole.STATUS_BAR)
        comp.focus_surface(bar)
        assert comp.active_surface == app  # Unchanged


class TestKeyboard:
    """Test keyboard show/hide and app resizing."""

    def test_show_keyboard(self, comp):
        comp.add_surface("kb", role=SurfaceRole.KEYBOARD)
        app = comp.add_surface("app", app_id="app1", role=SurfaceRole.APP)
        original_height = app.height

        comp.show_keyboard()
        assert comp.keyboard_visible is True
        assert app.height < original_height
        assert app.height == 2340 - comp.STATUS_BAR_HEIGHT - comp.KEYBOARD_HEIGHT

    def test_hide_keyboard(self, comp):
        comp.add_surface("kb", role=SurfaceRole.KEYBOARD)
        app = comp.add_surface("app", app_id="app1", role=SurfaceRole.APP)

        comp.show_keyboard()
        comp.hide_keyboard()
        assert comp.keyboard_visible is False
        assert app.height == 2340 - comp.STATUS_BAR_HEIGHT

    def test_show_keyboard_twice_noop(self, comp):
        comp.add_surface("kb", role=SurfaceRole.KEYBOARD)
        comp.add_surface("app", app_id="app1", role=SurfaceRole.APP)

        comp.show_keyboard()
        comp.show_keyboard()  # Should not error
        assert comp.keyboard_visible is True


class TestGestures:
    """Test touch gesture classification."""

    def test_tap(self, comp):
        gesture = comp._classify_gesture(dx=5, dy=5, dt=0.1)
        assert gesture == "tap"

    def test_swipe_up(self, comp):
        comp._touch_start_y = 500
        gesture = comp._classify_gesture(dx=0, dy=-200, dt=0.3)
        assert gesture == "swipe_up"

    def test_go_home(self, comp):
        comp._touch_start_y = comp.config.height - 50  # Near bottom
        gesture = comp._classify_gesture(dx=0, dy=-200, dt=0.3)
        assert gesture == "go_home"

    def test_notification_shade(self, comp):
        comp._touch_start_y = 30  # Near top
        gesture = comp._classify_gesture(dx=0, dy=200, dt=0.3)
        assert gesture == "notification_shade"

    def test_swipe_right_back(self, comp):
        comp._touch_start_y = 500
        gesture = comp._classify_gesture(dx=200, dy=0, dt=0.3)
        assert gesture == "swipe_right"

    def test_small_movement_no_gesture(self, comp):
        gesture = comp._classify_gesture(dx=10, dy=10, dt=1.0)
        # Below threshold and too slow for tap
        assert gesture is None

    def test_gesture_handler_callback(self, comp):
        received = []
        comp.set_gesture_handler(lambda g, d: received.append(g))

        comp.handle_touch_down(500, comp.config.height - 50)
        comp.handle_touch_up(500, comp.config.height - 250)

        assert "go_home" in received


class TestDisplayPower:
    """Test display on/off."""

    def test_display_off(self, comp):
        comp.set_display_power(False)
        assert comp.display_on is False

    def test_display_on(self, comp):
        comp.set_display_power(False)
        comp.set_display_power(True)
        assert comp.display_on is True

    def test_render_skipped_when_off(self, comp):
        comp.set_display_power(False)
        result = comp.render_frame()
        assert result is None


class TestRenderFrame:
    """Test frame rendering."""

    def test_render_returns_visible_surfaces(self, comp):
        comp.add_surface("bar", role=SurfaceRole.STATUS_BAR)
        comp.add_surface("app", app_id="app1", role=SurfaceRole.APP)

        surfaces = comp.render_frame()
        assert len(surfaces) == 2

    def test_hidden_keyboard_not_rendered(self, comp):
        comp.add_surface("bar", role=SurfaceRole.STATUS_BAR)
        comp.add_surface("app", app_id="app1", role=SurfaceRole.APP)
        comp.add_surface("kb", role=SurfaceRole.KEYBOARD)

        surfaces = comp.render_frame()
        roles = [s.role for s in surfaces]
        assert SurfaceRole.KEYBOARD not in roles

    def test_visible_keyboard_rendered(self, comp):
        comp.add_surface("bar", role=SurfaceRole.STATUS_BAR)
        comp.add_surface("app", app_id="app1", role=SurfaceRole.APP)
        comp.add_surface("kb", role=SurfaceRole.KEYBOARD)
        comp.show_keyboard()

        surfaces = comp.render_frame()
        roles = [s.role for s in surfaces]
        assert SurfaceRole.KEYBOARD in roles
