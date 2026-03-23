"""
Tests for Claude-OS display module (framebuffer + DRM).

Tests rendering logic, pixel packing, clipping, and gradient math
without requiring actual display hardware.
"""

import struct
import pytest


# --- Framebuffer Tests ---

class TestFramebufferPixelPacking:
    """Test pixel format encoding."""

    def setup_method(self):
        from framebuffer import Framebuffer, ScreenInfo
        self.fb = Framebuffer.__new__(Framebuffer)
        self.fb.info = ScreenInfo(
            width=480, height=960,
            bits_per_pixel=32, stride=480 * 4, size=480 * 960 * 4,
        )

    def test_pack_pixel_bgra_32bit(self):
        """BGRA8888: red=255 should have R in byte 2."""
        pixel = self.fb._pack_pixel(255, 0, 0)
        assert pixel == struct.pack("BBBB", 0, 0, 255, 255)

    def test_pack_pixel_green(self):
        pixel = self.fb._pack_pixel(0, 255, 0)
        assert pixel == struct.pack("BBBB", 0, 255, 0, 255)

    def test_pack_pixel_blue(self):
        pixel = self.fb._pack_pixel(0, 0, 255)
        assert pixel == struct.pack("BBBB", 255, 0, 0, 255)

    def test_pack_pixel_white(self):
        pixel = self.fb._pack_pixel(255, 255, 255)
        assert pixel == struct.pack("BBBB", 255, 255, 255, 255)

    def test_pack_pixel_with_alpha(self):
        pixel = self.fb._pack_pixel(100, 150, 200, 128)
        assert pixel == struct.pack("BBBB", 200, 150, 100, 128)

    def test_pack_pixel_16bit_rgb565(self):
        """RGB565 packing for 16-bit displays."""
        self.fb.info.bits_per_pixel = 16
        pixel = self.fb._pack_pixel(255, 0, 0)
        # Red in RGB565: 11111 000000 00000 = 0xF800
        expected = struct.pack("<H", 0xF800)
        assert pixel == expected

    def test_pack_pixel_16bit_green(self):
        self.fb.info.bits_per_pixel = 16
        pixel = self.fb._pack_pixel(0, 255, 0)
        # Green in RGB565: 00000 111111 00000 = 0x07E0
        expected = struct.pack("<H", 0x07E0)
        assert pixel == expected


class TestFramebufferScreenInfo:
    """Test ScreenInfo calculations."""

    def test_bytes_per_pixel_32bpp(self):
        from framebuffer import ScreenInfo
        info = ScreenInfo(480, 960, 32, 1920, 480 * 960 * 4)
        assert info.bytes_per_pixel == 4

    def test_bytes_per_pixel_16bpp(self):
        from framebuffer import ScreenInfo
        info = ScreenInfo(480, 960, 16, 960, 480 * 960 * 2)
        assert info.bytes_per_pixel == 2


class TestFramebufferRendering:
    """Test rendering to an in-memory buffer (mocked mmap)."""

    def setup_method(self):
        from framebuffer import Framebuffer, ScreenInfo
        self.fb = Framebuffer.__new__(Framebuffer)
        self.fb.device = "/dev/fb0"
        self.width = 16
        self.height = 16
        self.stride = self.width * 4
        self.fb.info = ScreenInfo(
            width=self.width, height=self.height,
            bits_per_pixel=32, stride=self.stride,
            size=self.stride * self.height,
        )
        # Use a bytearray as a fake mmap
        self.buffer = bytearray(self.fb.info.size)
        self.fb._mmap = FakeMmap(self.buffer)

    def test_fill_writes_all_pixels(self):
        self.fb.fill(255, 0, 0)
        # Every pixel should be BGRA = (0, 0, 255, 255)
        for i in range(0, len(self.buffer), 4):
            assert self.buffer[i:i+4] == bytes([0, 0, 255, 255])

    def test_rect_draws_at_correct_position(self):
        self.fb.fill(0, 0, 0)
        self.fb.rect(2, 3, 4, 5, 0, 255, 0)

        # Check pixel at (2, 3) — should be green
        offset = 3 * self.stride + 2 * 4
        assert self.buffer[offset:offset+4] == bytes([0, 255, 0, 255])

        # Check pixel at (0, 0) — should still be black
        assert self.buffer[0:4] == bytes([0, 0, 0, 255])

    def test_rect_clips_to_screen(self):
        """Rectangle extending past screen edge should be clipped."""
        self.fb.fill(0, 0, 0)
        self.fb.rect(-5, -5, 10, 10, 255, 0, 0)

        # Pixel at (0,0) should be red (clipped from -5,-5)
        assert self.buffer[0:4] == bytes([0, 0, 255, 255])

        # Pixel at (4,0) should be red (within 10-wide rect starting at -5)
        offset = 0 * self.stride + 4 * 4
        assert self.buffer[offset:offset+4] == bytes([0, 0, 255, 255])

        # Pixel at (5,0) should be black (outside rect)
        offset = 0 * self.stride + 5 * 4
        assert self.buffer[offset:offset+4] == bytes([0, 0, 0, 255])

    def test_rect_fully_offscreen(self):
        """Rectangle fully offscreen should be a no-op."""
        self.fb.fill(0, 0, 0)
        original = bytes(self.buffer)
        self.fb.rect(-100, -100, 10, 10, 255, 0, 0)
        assert self.buffer == bytearray(original)

    def test_pixel_set(self):
        self.fb.fill(0, 0, 0)
        self.fb.pixel(7, 8, 128, 64, 32)
        offset = 8 * self.stride + 7 * 4
        assert self.buffer[offset:offset+4] == bytes([32, 64, 128, 255])

    def test_pixel_out_of_bounds_ignored(self):
        self.fb.fill(0, 0, 0)
        original = bytes(self.buffer)
        self.fb.pixel(-1, 0, 255, 255, 255)
        self.fb.pixel(0, -1, 255, 255, 255)
        self.fb.pixel(self.width, 0, 255, 255, 255)
        self.fb.pixel(0, self.height, 255, 255, 255)
        assert self.buffer == bytearray(original)


class TestFramebufferNotOpen:
    """Test error handling when framebuffer is not open."""

    def test_fill_raises_without_open(self):
        from framebuffer import Framebuffer
        fb = Framebuffer.__new__(Framebuffer)
        fb._mmap = None
        fb.info = None
        with pytest.raises(RuntimeError, match="not open"):
            fb.fill(0, 0, 0)

    def test_rect_raises_without_open(self):
        from framebuffer import Framebuffer
        fb = Framebuffer.__new__(Framebuffer)
        fb._mmap = None
        fb.info = None
        with pytest.raises(RuntimeError, match="not open"):
            fb.rect(0, 0, 10, 10, 0, 0, 0)


# --- DRM Display Tests ---

class TestDRMMode:
    """Test DRM mode and connector data structures."""

    def test_connector_connected(self):
        from drm_display import DRMConnector, DRM_MODE_CONNECTED
        conn = DRMConnector(id=1, status=DRM_MODE_CONNECTED, encoder_id=1)
        assert conn.connected is True

    def test_connector_disconnected(self):
        from drm_display import DRMConnector, DRM_MODE_DISCONNECTED
        conn = DRMConnector(id=1, status=DRM_MODE_DISCONNECTED, encoder_id=0)
        assert conn.connected is False

    def test_mode_attributes(self):
        from drm_display import DRMMode
        mode = DRMMode(width=480, height=960, refresh=60, name="480x960")
        assert mode.width == 480
        assert mode.height == 960
        assert mode.refresh == 60


class TestDRMBuffer:
    """Test DRM buffer data structures."""

    def test_buffer_defaults(self):
        from drm_display import DRMBuffer
        buf = DRMBuffer(handle=1, width=480, height=960, stride=1920, size=1843200)
        assert buf.fb_id == 0
        assert buf.data is None


class TestDRMRendering:
    """Test DRM rendering to an in-memory buffer."""

    def setup_method(self):
        from drm_display import DRMDisplay, DRMBuffer, DRMMode
        self.drm = DRMDisplay.__new__(DRMDisplay)
        self.drm.device = "/dev/dri/card0"
        self.drm._fd = None
        self.width = 16
        self.height = 16
        self.stride = self.width * 4

        self.buffer_data = bytearray(self.stride * self.height)
        self.drm.buffer = DRMBuffer(
            handle=1, width=self.width, height=self.height,
            stride=self.stride, size=len(self.buffer_data),
            fb_id=1, data=FakeMmap(self.buffer_data),
        )
        self.drm.mode = DRMMode(
            width=self.width, height=self.height, refresh=60, name="16x16",
        )

    def test_fill(self):
        self.drm.fill(0, 0, 255)
        for i in range(0, len(self.buffer_data), 4):
            assert self.buffer_data[i:i+4] == bytes([255, 0, 0, 255])

    def test_rect(self):
        self.drm.fill(0, 0, 0)
        self.drm.rect(1, 1, 3, 3, 255, 128, 0)
        offset = 1 * self.stride + 1 * 4
        assert self.buffer_data[offset:offset+4] == bytes([0, 128, 255, 255])

    def test_rect_clips(self):
        self.drm.fill(0, 0, 0)
        self.drm.rect(14, 14, 10, 10, 255, 255, 255)
        # Only 2x2 area should be drawn (14..15 x 14..15)
        offset = 14 * self.stride + 14 * 4
        assert self.buffer_data[offset:offset+4] == bytes([255, 255, 255, 255])
        # Pixel at (13,14) should still be black
        offset = 14 * self.stride + 13 * 4
        assert self.buffer_data[offset:offset+4] == bytes([0, 0, 0, 255])


# --- Helper ---

class FakeMmap:
    """In-memory stand-in for mmap with seek/write interface."""

    def __init__(self, buffer: bytearray):
        self._buf = buffer
        self._pos = 0

    def seek(self, offset: int):
        self._pos = offset

    def write(self, data: bytes):
        end = self._pos + len(data)
        self._buf[self._pos:end] = data
        self._pos = end

    def read(self, n: int) -> bytes:
        data = bytes(self._buf[self._pos:self._pos + n])
        self._pos += n
        return data

    def close(self):
        pass
