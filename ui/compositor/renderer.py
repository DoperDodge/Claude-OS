"""
Claude-OS Compositor Renderer

Bridges the compositor's surface management logic to actual pixel output.
Takes the compositor's render list (which surfaces are visible and where)
and draws them to the screen via the DRM or framebuffer display backend.

Rendering pipeline each frame:
    1. Clear to background color
    2. Draw active app surface
    3. Draw status bar overlay
    4. Draw keyboard overlay (if visible)
    5. Present (flip buffer)

Surface content is stored as raw BGRA pixel buffers — the Wayland server
fills these when clients commit new frames.
"""

import logging
import struct
import time
from dataclasses import dataclass, field

logger = logging.getLogger("compositor.renderer")


@dataclass
class SurfaceBuffer:
    """Pixel data for a surface, committed by Wayland clients."""
    width: int
    height: int
    stride: int
    data: bytearray  # BGRA8888 pixel data
    dirty: bool = True

    @classmethod
    def solid_color(cls, width: int, height: int,
                    r: int, g: int, b: int, a: int = 255) -> "SurfaceBuffer":
        """Create a surface buffer filled with a solid color."""
        stride = width * 4
        pixel = struct.pack("BBBB", b, g, r, a)
        row = pixel * width
        data = bytearray(row * height)
        return cls(width=width, height=height, stride=stride, data=data)


class CompositorRenderer:
    """
    Renders compositor frames to the display.

    Manages display backend lifecycle and composites surfaces each frame.
    Supports both DRM and framebuffer backends with automatic fallback.
    """

    # Background color (dark navy)
    BG_COLOR = (10, 10, 35)

    def __init__(self):
        self._display = None
        self._backend_type: str = "none"
        self._surface_buffers: dict[int, SurfaceBuffer] = {}  # surface id -> buffer
        self._frame_count: int = 0
        self._fps_time: float = 0
        self._fps: float = 0

    def initialize(self, width: int = 480, height: int = 960) -> dict:
        """
        Initialize the display backend.

        Tries DRM first, then framebuffer, then headless (for testing).
        Returns info about the initialized display.
        """
        import os

        # Try DRM
        if os.path.exists("/dev/dri/card0"):
            try:
                return self._init_drm(width, height)
            except Exception as e:
                logger.warning("DRM init failed: %s", e)

        # Try framebuffer
        if os.path.exists("/dev/fb0"):
            try:
                return self._init_framebuffer()
            except Exception as e:
                logger.warning("Framebuffer init failed: %s", e)

        # Headless fallback (for testing / CI)
        return self._init_headless(width, height)

    def _init_drm(self, width: int, height: int) -> dict:
        """Initialize DRM display backend."""
        from drm_display import DRMDisplay

        self._display = DRMDisplay()
        self._display.open()
        self._display.setup(preferred_width=width, preferred_height=height)
        self._backend_type = "drm"

        logger.info("Renderer initialized: DRM (%dx%d)",
                     self._display.mode.width, self._display.mode.height)
        return self._display.get_info()

    def _init_framebuffer(self) -> dict:
        """Initialize framebuffer display backend."""
        from framebuffer import Framebuffer

        self._display = Framebuffer()
        self._display.open()
        self._backend_type = "framebuffer"

        logger.info("Renderer initialized: framebuffer (%dx%d)",
                     self._display.info.width, self._display.info.height)
        return self._display.get_info()

    def _init_headless(self, width: int, height: int) -> dict:
        """Initialize headless backend (in-memory buffer for testing)."""
        self._display = HeadlessDisplay(width, height)
        self._backend_type = "headless"

        logger.info("Renderer initialized: headless (%dx%d)", width, height)
        return {"backend": "headless", "width": width, "height": height}

    def shutdown(self):
        """Clean up the display backend."""
        if self._display and hasattr(self._display, 'close'):
            self._display.close()
        self._display = None
        self._backend_type = "none"
        logger.info("Renderer shut down")

    @property
    def width(self) -> int:
        if self._backend_type == "drm":
            return self._display.mode.width
        elif self._backend_type == "framebuffer":
            return self._display.info.width
        elif self._backend_type == "headless":
            return self._display.width
        return 0

    @property
    def height(self) -> int:
        if self._backend_type == "drm":
            return self._display.mode.height
        elif self._backend_type == "framebuffer":
            return self._display.info.height
        elif self._backend_type == "headless":
            return self._display.height
        return 0

    # --- Surface Buffer Management ---

    def attach_buffer(self, surface_id: int, buffer: SurfaceBuffer):
        """Attach a pixel buffer to a surface (called on Wayland commit)."""
        self._surface_buffers[surface_id] = buffer

    def detach_buffer(self, surface_id: int):
        """Remove the buffer for a destroyed surface."""
        self._surface_buffers.pop(surface_id, None)

    def create_solid_buffer(self, surface_id: int, width: int, height: int,
                            r: int, g: int, b: int) -> SurfaceBuffer:
        """Create and attach a solid-color buffer for a surface."""
        buf = SurfaceBuffer.solid_color(width, height, r, g, b)
        self.attach_buffer(surface_id, buf)
        return buf

    # --- Frame Rendering ---

    def render_frame(self, render_list: list) -> int:
        """
        Render one compositor frame.

        Args:
            render_list: Ordered list of Surface objects to draw
                         (from compositor.render_frame())

        Returns:
            Number of surfaces drawn.
        """
        if not self._display:
            return 0

        # Clear background
        r, g, b = self.BG_COLOR
        self._display.fill(r, g, b)

        # Draw each surface
        drawn = 0
        for surface in render_list:
            buf = self._surface_buffers.get(id(surface))
            if buf:
                self._blit_surface(surface.x, surface.y, buf)
                drawn += 1
            else:
                # Surface has no buffer yet — draw placeholder
                self._draw_placeholder(surface)
                drawn += 1

        # Present
        if hasattr(self._display, 'present'):
            self._display.present()

        # FPS tracking
        self._frame_count += 1
        now = time.monotonic()
        if now - self._fps_time >= 1.0:
            self._fps = self._frame_count / (now - self._fps_time)
            self._frame_count = 0
            self._fps_time = now

        return drawn

    def _blit_surface(self, dest_x: int, dest_y: int, buf: SurfaceBuffer):
        """Blit a surface buffer onto the display at the given position."""
        if self._backend_type == "headless":
            self._display.blit(dest_x, dest_y, buf)
            return

        # For DRM and framebuffer, write pixel rows directly
        display_buf = self._get_display_buffer()
        if not display_buf:
            return

        display_stride = self._get_display_stride()
        display_w = self.width
        display_h = self.height

        for row in range(buf.height):
            screen_y = dest_y + row
            if screen_y < 0 or screen_y >= display_h:
                continue

            # Source row
            src_offset = row * buf.stride
            # How much of the row to copy
            copy_w = min(buf.width, display_w - max(0, dest_x))
            if copy_w <= 0:
                continue

            src_x = 0
            dst_x = dest_x
            if dest_x < 0:
                src_x = -dest_x
                dst_x = 0
                copy_w += dest_x  # dest_x is negative

            src_start = src_offset + src_x * 4
            src_end = src_start + copy_w * 4
            dst_offset = screen_y * display_stride + dst_x * 4

            display_buf.seek(dst_offset)
            display_buf.write(buf.data[src_start:src_end])

    def _draw_placeholder(self, surface):
        """Draw a placeholder rectangle for a surface without a buffer."""
        # Dark gray rectangle
        self._display.rect(surface.x, surface.y,
                           surface.width, surface.height,
                           30, 30, 40)

    def _get_display_buffer(self):
        """Get the raw mmap buffer for the display."""
        if self._backend_type == "drm" and self._display.buffer:
            return self._display.buffer.data
        elif self._backend_type == "framebuffer":
            return self._display._mmap
        return None

    def _get_display_stride(self) -> int:
        """Get the display stride (bytes per row)."""
        if self._backend_type == "drm" and self._display.buffer:
            return self._display.buffer.stride
        elif self._backend_type == "framebuffer" and self._display.info:
            return self._display.info.stride
        return self.width * 4

    def get_stats(self) -> dict:
        """Get renderer statistics."""
        return {
            "backend": self._backend_type,
            "width": self.width,
            "height": self.height,
            "fps": round(self._fps, 1),
            "surfaces": len(self._surface_buffers),
        }


class HeadlessDisplay:
    """
    In-memory display for testing and CI.

    Implements the same fill/rect interface as framebuffer/DRM but
    writes to a bytearray instead of a real device.
    """

    def __init__(self, width: int, height: int):
        self.width = width
        self.height = height
        self.stride = width * 4
        self.size = self.stride * height
        self.buffer = bytearray(self.size)
        self._pos = 0

    def fill(self, r: int, g: int, b: int, a: int = 255):
        pixel = struct.pack("BBBB", b, g, r, a)
        row = pixel * self.width
        for y in range(self.height):
            offset = y * self.stride
            self.buffer[offset:offset + len(row)] = row

    def rect(self, x: int, y: int, w: int, h: int,
             r: int, g: int, b: int, a: int = 255):
        x0 = max(0, x)
        y0 = max(0, y)
        x1 = min(self.width, x + w)
        y1 = min(self.height, y + h)
        if x0 >= x1 or y0 >= y1:
            return

        pixel = struct.pack("BBBB", b, g, r, a)
        row_pixels = pixel * (x1 - x0)

        for row in range(y0, y1):
            offset = row * self.stride + x0 * 4
            self.buffer[offset:offset + len(row_pixels)] = row_pixels

    def blit(self, dest_x: int, dest_y: int, surface_buf: "SurfaceBuffer"):
        """Blit a surface buffer onto the headless display."""
        for row in range(surface_buf.height):
            screen_y = dest_y + row
            if screen_y < 0 or screen_y >= self.height:
                continue
            copy_w = min(surface_buf.width, self.width - max(0, dest_x))
            if copy_w <= 0:
                continue

            src_x = 0
            dst_x = dest_x
            if dest_x < 0:
                src_x = -dest_x
                dst_x = 0
                copy_w += dest_x

            src_start = row * surface_buf.stride + src_x * 4
            src_end = src_start + copy_w * 4
            dst_offset = screen_y * self.stride + dst_x * 4

            self.buffer[dst_offset:dst_offset + (src_end - src_start)] = \
                surface_buf.data[src_start:src_end]

    def present(self):
        pass

    def close(self):
        pass

    def get_pixel(self, x: int, y: int) -> tuple[int, int, int, int]:
        """Read a pixel (for test assertions). Returns (R, G, B, A)."""
        offset = y * self.stride + x * 4
        b, g, r, a = struct.unpack_from("BBBB", self.buffer, offset)
        return (r, g, b, a)
