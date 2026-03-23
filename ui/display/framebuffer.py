"""
Claude-OS Framebuffer Renderer

Draws directly to /dev/fb0 via mmap. This is the simplest possible way to
get pixels on screen — no compositor, no toolkit, just raw pixel writes.

Used for:
  - Phase 1 proof-of-life ("can we see pixels?")
  - Boot splash screen
  - Emergency/recovery display fallback

The framebuffer uses BGRA8888 pixel format (4 bytes per pixel) which is
what virtio-gpu exposes through the fbdev compatibility layer.
"""

import ctypes
import fcntl
import logging
import mmap
import os
import struct
from dataclasses import dataclass

logger = logging.getLogger("display.fb")

# Linux ioctl constants for framebuffer (from linux/fb.h)
FBIOGET_VSCREENINFO = 0x4600
FBIOGET_FSCREENINFO = 0x4602


@dataclass
class ScreenInfo:
    """Framebuffer screen dimensions and format."""
    width: int
    height: int
    bits_per_pixel: int
    stride: int  # bytes per row (may include padding)
    size: int    # total buffer size in bytes

    @property
    def bytes_per_pixel(self) -> int:
        return self.bits_per_pixel // 8


class Framebuffer:
    """
    Direct framebuffer renderer via /dev/fb0.

    Usage:
        fb = Framebuffer()
        fb.open()
        fb.fill(0, 0, 255)           # Fill screen blue
        fb.rect(100, 100, 200, 200,  # Draw red rectangle
                255, 0, 0)
        fb.close()
    """

    def __init__(self, device: str = "/dev/fb0"):
        self.device = device
        self.info: ScreenInfo | None = None
        self._fd: int | None = None
        self._mmap: mmap.mmap | None = None

    def open(self):
        """Open the framebuffer device and mmap it."""
        self._fd = os.open(self.device, os.O_RDWR)

        # Get variable screen info (resolution, bpp)
        vinfo = self._ioctl_vscreeninfo()
        # Get fixed screen info (stride, buffer size)
        finfo = self._ioctl_fscreeninfo()

        self.info = ScreenInfo(
            width=vinfo["xres"],
            height=vinfo["yres"],
            bits_per_pixel=vinfo["bits_per_pixel"],
            stride=finfo["line_length"],
            size=finfo["smem_len"],
        )

        # Memory-map the framebuffer
        self._mmap = mmap.mmap(
            self._fd, self.info.size,
            mmap.MAP_SHARED, mmap.PROT_READ | mmap.PROT_WRITE,
        )

        logger.info(
            "Framebuffer opened: %dx%d, %dbpp, stride=%d, size=%d",
            self.info.width, self.info.height, self.info.bits_per_pixel,
            self.info.stride, self.info.size,
        )

    def close(self):
        """Close the framebuffer device."""
        if self._mmap:
            self._mmap.close()
            self._mmap = None
        if self._fd is not None:
            os.close(self._fd)
            self._fd = None
        logger.info("Framebuffer closed")

    def fill(self, r: int, g: int, b: int, a: int = 255):
        """Fill the entire screen with a solid color."""
        if not self._mmap or not self.info:
            raise RuntimeError("Framebuffer not open")

        pixel = self._pack_pixel(r, g, b, a)
        row = pixel * self.info.width

        # Pad row to stride if needed
        row_bytes = len(row)
        if row_bytes < self.info.stride:
            row += b'\x00' * (self.info.stride - row_bytes)

        self._mmap.seek(0)
        for _ in range(self.info.height):
            self._mmap.write(row)

    def rect(self, x: int, y: int, w: int, h: int,
             r: int, g: int, b: int, a: int = 255):
        """Draw a filled rectangle."""
        if not self._mmap or not self.info:
            raise RuntimeError("Framebuffer not open")

        # Clip to screen bounds
        x0 = max(0, x)
        y0 = max(0, y)
        x1 = min(self.info.width, x + w)
        y1 = min(self.info.height, y + h)

        if x0 >= x1 or y0 >= y1:
            return

        pixel = self._pack_pixel(r, g, b, a)
        row_pixels = pixel * (x1 - x0)
        bpp = self.info.bytes_per_pixel

        for row in range(y0, y1):
            offset = row * self.info.stride + x0 * bpp
            self._mmap.seek(offset)
            self._mmap.write(row_pixels)

    def pixel(self, x: int, y: int, r: int, g: int, b: int, a: int = 255):
        """Set a single pixel."""
        if not self._mmap or not self.info:
            raise RuntimeError("Framebuffer not open")
        if 0 <= x < self.info.width and 0 <= y < self.info.height:
            offset = y * self.info.stride + x * self.info.bytes_per_pixel
            self._mmap.seek(offset)
            self._mmap.write(self._pack_pixel(r, g, b, a))

    def gradient(self, r1: int, g1: int, b1: int,
                 r2: int, g2: int, b2: int, vertical: bool = True):
        """Draw a gradient fill across the entire screen."""
        if not self._mmap or not self.info:
            raise RuntimeError("Framebuffer not open")

        steps = self.info.height if vertical else self.info.width

        for i in range(steps):
            t = i / max(1, steps - 1)
            r = int(r1 + (r2 - r1) * t)
            g = int(g1 + (g2 - g1) * t)
            b = int(b1 + (b2 - b1) * t)

            if vertical:
                # Draw one full row
                pixel = self._pack_pixel(r, g, b)
                row = pixel * self.info.width
                offset = i * self.info.stride
                self._mmap.seek(offset)
                self._mmap.write(row)
            else:
                # Draw one full column
                pixel = self._pack_pixel(r, g, b)
                bpp = self.info.bytes_per_pixel
                for row in range(self.info.height):
                    offset = row * self.info.stride + i * bpp
                    self._mmap.seek(offset)
                    self._mmap.write(pixel)

    def _pack_pixel(self, r: int, g: int, b: int, a: int = 255) -> bytes:
        """Pack RGBA values into framebuffer pixel format (BGRA8888)."""
        if self.info and self.info.bits_per_pixel == 32:
            return struct.pack("BBBB", b, g, r, a)
        elif self.info and self.info.bits_per_pixel == 16:
            # RGB565
            pixel = ((r >> 3) << 11) | ((g >> 2) << 5) | (b >> 3)
            return struct.pack("<H", pixel)
        else:
            return struct.pack("BBBB", b, g, r, a)

    def _ioctl_vscreeninfo(self) -> dict:
        """Read variable screen info via ioctl."""
        buf = bytearray(160)  # struct fb_var_screeninfo
        fcntl.ioctl(self._fd, FBIOGET_VSCREENINFO, buf)
        xres, yres = struct.unpack_from("<II", buf, 0)
        bpp = struct.unpack_from("<I", buf, 24)[0]
        return {"xres": xres, "yres": yres, "bits_per_pixel": bpp}

    def _ioctl_fscreeninfo(self) -> dict:
        """Read fixed screen info via ioctl."""
        buf = bytearray(168)  # struct fb_fix_screeninfo
        fcntl.ioctl(self._fd, FBIOGET_FSCREENINFO, buf)
        # line_length is at offset 32 in fb_fix_screeninfo
        smem_len = struct.unpack_from("<I", buf, 16 + 4 + 4 + 4)[0]
        line_length = struct.unpack_from("<I", buf, 16 + 4 + 4 + 4 + 4 + 4 + 4 + 4 + 4 + 4)[0]
        return {"smem_len": smem_len, "line_length": line_length}

    def get_info(self) -> dict:
        """Return display information for debugging."""
        if not self.info:
            return {"status": "not_open"}
        return {
            "device": self.device,
            "width": self.info.width,
            "height": self.info.height,
            "bpp": self.info.bits_per_pixel,
            "stride": self.info.stride,
            "size": self.info.size,
        }

    def __enter__(self):
        self.open()
        return self

    def __exit__(self, *args):
        self.close()
