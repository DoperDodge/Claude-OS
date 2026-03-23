"""
Tests for the compositor renderer and headless display backend.
"""

import struct
import pytest
from renderer import CompositorRenderer, HeadlessDisplay, SurfaceBuffer


class TestHeadlessDisplay:
    """Test the in-memory headless display."""

    def test_create(self):
        d = HeadlessDisplay(320, 240)
        assert d.width == 320
        assert d.height == 240
        assert d.stride == 320 * 4
        assert len(d.buffer) == 320 * 240 * 4

    def test_fill(self):
        d = HeadlessDisplay(4, 4)
        d.fill(255, 0, 0)
        assert d.get_pixel(0, 0) == (255, 0, 0, 255)
        assert d.get_pixel(3, 3) == (255, 0, 0, 255)

    def test_rect(self):
        d = HeadlessDisplay(10, 10)
        d.fill(0, 0, 0)
        d.rect(2, 2, 3, 3, 0, 255, 0)
        assert d.get_pixel(2, 2) == (0, 255, 0, 255)
        assert d.get_pixel(4, 4) == (0, 255, 0, 255)
        assert d.get_pixel(0, 0) == (0, 0, 0, 255)  # Outside rect
        assert d.get_pixel(5, 5) == (0, 0, 0, 255)  # Outside rect

    def test_rect_clips(self):
        d = HeadlessDisplay(10, 10)
        d.fill(0, 0, 0)
        d.rect(-2, -2, 5, 5, 128, 128, 128)
        assert d.get_pixel(0, 0) == (128, 128, 128, 255)
        assert d.get_pixel(2, 2) == (128, 128, 128, 255)
        assert d.get_pixel(3, 0) == (0, 0, 0, 255)

    def test_blit_surface(self):
        d = HeadlessDisplay(10, 10)
        d.fill(0, 0, 0)

        # Create a 3x3 red surface
        buf = SurfaceBuffer.solid_color(3, 3, 255, 0, 0)
        d.blit(2, 2, buf)

        assert d.get_pixel(2, 2) == (255, 0, 0, 255)
        assert d.get_pixel(4, 4) == (255, 0, 0, 255)
        assert d.get_pixel(1, 1) == (0, 0, 0, 255)


class TestSurfaceBuffer:
    """Test surface buffer creation."""

    def test_solid_color(self):
        buf = SurfaceBuffer.solid_color(4, 4, 255, 128, 0)
        assert buf.width == 4
        assert buf.height == 4
        assert buf.stride == 16
        # Check first pixel: BGRA
        assert buf.data[0:4] == bytes([0, 128, 255, 255])

    def test_solid_color_size(self):
        buf = SurfaceBuffer.solid_color(100, 200, 0, 0, 0)
        assert len(buf.data) == 100 * 200 * 4


class TestCompositorRenderer:
    """Test the compositor renderer with headless backend."""

    def setup_method(self):
        self.renderer = CompositorRenderer()
        self.renderer._init_headless(100, 100)

    def test_init_headless(self):
        assert self.renderer._backend_type == "headless"
        assert self.renderer.width == 100
        assert self.renderer.height == 100

    def test_render_empty_frame(self):
        drawn = self.renderer.render_frame([])
        assert drawn == 0
        # Should be filled with background color
        bg = self.renderer._display.get_pixel(50, 50)
        assert bg == (10, 10, 35, 255)  # BG_COLOR

    def test_render_with_placeholder(self):
        """Surface without a buffer gets a placeholder rect."""
        from compositor import Surface, SurfaceRole
        s = Surface(wl_surface=None, role=SurfaceRole.APP,
                    x=10, y=10, width=30, height=30)
        drawn = self.renderer.render_frame([s])
        assert drawn == 1
        # Placeholder is dark gray
        pixel = self.renderer._display.get_pixel(15, 15)
        assert pixel == (30, 30, 40, 255)

    def test_render_with_buffer(self):
        """Surface with an attached buffer gets blitted."""
        from compositor import Surface, SurfaceRole
        s = Surface(wl_surface=None, role=SurfaceRole.APP,
                    x=5, y=5, width=10, height=10)

        buf = SurfaceBuffer.solid_color(10, 10, 255, 0, 0)
        self.renderer.attach_buffer(id(s), buf)

        self.renderer.render_frame([s])

        pixel = self.renderer._display.get_pixel(7, 7)
        assert pixel == (255, 0, 0, 255)

    def test_detach_buffer(self):
        from compositor import Surface, SurfaceRole
        s = Surface(wl_surface=None, role=SurfaceRole.APP,
                    x=0, y=0, width=10, height=10)
        buf = SurfaceBuffer.solid_color(10, 10, 0, 255, 0)
        self.renderer.attach_buffer(id(s), buf)
        self.renderer.detach_buffer(id(s))
        assert id(s) not in self.renderer._surface_buffers

    def test_get_stats(self):
        stats = self.renderer.get_stats()
        assert stats["backend"] == "headless"
        assert stats["width"] == 100
        assert stats["height"] == 100

    def test_shutdown(self):
        self.renderer.shutdown()
        assert self.renderer._backend_type == "none"
        assert self.renderer._display is None


class TestRendererSurfaceCompositing:
    """Test multi-surface compositing."""

    def setup_method(self):
        self.renderer = CompositorRenderer()
        self.renderer._init_headless(100, 100)

    def test_surfaces_drawn_in_order(self):
        """Later surfaces draw on top of earlier ones."""
        from compositor import Surface, SurfaceRole

        # Blue background surface
        s1 = Surface(wl_surface=None, role=SurfaceRole.APP,
                     x=0, y=0, width=100, height=100)
        buf1 = SurfaceBuffer.solid_color(100, 100, 0, 0, 255)
        self.renderer.attach_buffer(id(s1), buf1)

        # Red overlay surface at (40,40) 20x20
        s2 = Surface(wl_surface=None, role=SurfaceRole.STATUS_BAR,
                     x=40, y=40, width=20, height=20)
        buf2 = SurfaceBuffer.solid_color(20, 20, 255, 0, 0)
        self.renderer.attach_buffer(id(s2), buf2)

        self.renderer.render_frame([s1, s2])

        # Point under overlay should be red
        assert self.renderer._display.get_pixel(45, 45) == (255, 0, 0, 255)
        # Point outside overlay should be blue
        assert self.renderer._display.get_pixel(10, 10) == (0, 0, 255, 255)
