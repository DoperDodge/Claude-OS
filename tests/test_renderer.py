"""Tests for the DRM framebuffer renderer."""

import os
import sys
import tempfile
import pytest

# Add project root to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from ui.compositor.compositor import (
    Compositor,
    CompositorState,
    SceneNode,
    Surface,
    SurfaceRole,
)
from ui.renderer.drm_renderer import DRMRenderer, _parse_hex_color


class TestColorParsing:
    """Test hex color string parsing."""

    def test_six_digit_hex(self):
        r, g, b, a = _parse_hex_color("#FF0000")
        assert r == pytest.approx(1.0)
        assert g == pytest.approx(0.0)
        assert b == pytest.approx(0.0)
        assert a == pytest.approx(1.0)

    def test_eight_digit_hex(self):
        r, g, b, a = _parse_hex_color("#FF000080")
        assert r == pytest.approx(1.0)
        assert a == pytest.approx(128 / 255.0)

    def test_no_hash(self):
        r, g, b, a = _parse_hex_color("1A1A2E")
        assert r == pytest.approx(26 / 255.0)
        assert g == pytest.approx(26 / 255.0)

    def test_invalid_returns_black(self):
        r, g, b, a = _parse_hex_color("xyz")
        assert r == 0.0 and g == 0.0 and b == 0.0

    def test_theme_colors(self):
        """Test Claude-OS theme colors parse correctly."""
        r, g, b, _ = _parse_hex_color("#D4A574")  # Terracotta
        assert r == pytest.approx(212 / 255.0)

        r, g, b, _ = _parse_hex_color("#E8D5C4")  # Sand
        assert r == pytest.approx(232 / 255.0)


class TestRendererInit:
    """Test renderer initialization."""

    def test_headless_init(self):
        renderer = DRMRenderer()
        renderer.initialize(headless=True, width=540, height=1170)
        assert renderer.initialized
        assert renderer.width == 540
        assert renderer.height == 1170
        renderer.shutdown()

    def test_default_dimensions(self):
        renderer = DRMRenderer()
        renderer.initialize(headless=True)
        assert renderer.width == 1080
        assert renderer.height == 2340
        renderer.shutdown()

    def test_drm_fallback_to_headless(self):
        """DRM init should fall back to headless when no device exists."""
        renderer = DRMRenderer(device_path="/dev/dri/nonexistent")
        renderer.initialize(headless=False)
        assert renderer.initialized
        assert renderer._headless
        renderer.shutdown()


class TestRendering:
    """Test scene graph rendering."""

    @pytest.fixture
    def renderer(self):
        r = DRMRenderer()
        r.initialize(headless=True, width=1080, height=2340)
        yield r
        r.shutdown()

    def test_render_empty_scene(self, renderer):
        scene = SceneNode(
            background_color="#1A1A2E",
            width=1080,
            height=2340,
        )
        renderer.render(scene)
        data = renderer.get_pixel_data()
        assert len(data) > 0

    def test_render_scene_with_children(self, renderer):
        scene = SceneNode(
            background_color="#FAF6F1",
            width=1080,
            height=2340,
        )
        scene.children.append(SceneNode(
            background_color="#D4A574",
            x=100, y=100, width=200, height=100,
            corner_radius=16,
        ))
        renderer.render(scene)
        data = renderer.get_pixel_data()
        assert len(data) == 1080 * 2340 * 4

    def test_render_with_surface(self, renderer):
        surface = Surface(
            wl_surface="test",
            role=SurfaceRole.STATUS_BAR,
            x=0, y=0, width=1080, height=54,
            app_id="statusbar",
        )
        scene = SceneNode(
            background_color="#FAF6F1",
            width=1080, height=2340,
        )
        scene.children.append(SceneNode(
            surface=surface,
            x=0, y=0, width=1080, height=54,
            opacity=0.7,
        ))
        renderer.render(scene)

    def test_render_compositor_scene_graph(self, renderer):
        """Render a full compositor scene graph."""
        compositor = Compositor()
        compositor.initialize()
        compositor.add_surface("statusbar", role=SurfaceRole.STATUS_BAR, app_id="statusbar")
        compositor.add_surface("app", role=SurfaceRole.APP, app_id="claude-app")

        scene = compositor.render_frame()
        assert scene is not None
        renderer.render(scene)

    def test_render_locked_state(self, renderer):
        compositor = Compositor()
        compositor.initialize()
        compositor.add_surface("lock", role=SurfaceRole.LOCK_SCREEN, app_id="lockscreen")
        compositor.state = CompositorState.LOCKED

        scene = compositor.render_frame()
        assert scene is not None
        renderer.render(scene)


class TestPNGExport:
    """Test PNG file export."""

    def test_save_png(self):
        try:
            import cairo  # noqa: F401
        except ImportError:
            pytest.skip("pycairo not installed")

        renderer = DRMRenderer()
        renderer.initialize(headless=True, width=100, height=100)

        scene = SceneNode(
            background_color="#D4A574",
            width=100, height=100,
        )
        renderer.render(scene)

        with tempfile.NamedTemporaryFile(suffix=".png", delete=False) as f:
            path = f.name

        try:
            renderer.save_png(path)
            assert os.path.exists(path)
            assert os.path.getsize(path) > 0
        finally:
            os.unlink(path)
            renderer.shutdown()


class TestDisplayManagerDetection:
    """Test display backend detection."""

    def test_detect_stub_when_no_drm(self):
        # Import from the display manager module directly
        sys.path.insert(0, os.path.join(
            os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
            "system"
        ))
        from display_manager_compat import detect_display_backend_safe
        result = detect_display_backend_safe()
        assert result in ("drm", "stub")
