"""
Claude-OS DRM/fbdev Framebuffer Renderer

Renders the compositor's scene graph to the display using either:
  1. Linux fbdev (/dev/fb0) — simple mmap framebuffer (preferred for QEMU)
  2. DRM/KMS (/dev/dri/card0) — full modesetting with dumb buffers
  3. Headless — in-memory rendering for testing and PNG export

Rendering pipeline:
    Compositor.build_scene_graph() -> SceneNode tree
        -> DRMRenderer.render(scene_graph)
            -> Cairo draws to memory buffer
                -> present() copies buffer to display framebuffer
                    -> Pixels on screen

The renderer also handles VT (virtual terminal) switching to take
exclusive control of the display away from the kernel's fbcon.
"""

import ctypes
import ctypes.util
import logging
import mmap
import os
import struct
import fcntl
import sys
from pathlib import Path

logger = logging.getLogger("drm_renderer")

# --- Linux ioctl constants ---

# DRM ioctl numbers (from linux/drm.h)
DRM_IOCTL_BASE = 0x64
_IOC_WRITE = 1
_IOC_READ = 2
_IOC_NRBITS = 8
_IOC_TYPEBITS = 8
_IOC_SIZEBITS = 14
_IOC_NRSHIFT = 0
_IOC_TYPESHIFT = _IOC_NRSHIFT + _IOC_NRBITS
_IOC_SIZESHIFT = _IOC_TYPESHIFT + _IOC_TYPEBITS
_IOC_DIRSHIFT = _IOC_SIZESHIFT + _IOC_SIZEBITS


def _IOC(direction, type_val, nr, size):
    return (direction << _IOC_DIRSHIFT) | (type_val << _IOC_TYPESHIFT) | \
           (nr << _IOC_NRSHIFT) | (size << _IOC_SIZESHIFT)


def _IOWR(type_val, nr, size):
    return _IOC(_IOC_READ | _IOC_WRITE, type_val, nr, size)


# fbdev ioctl numbers (from linux/fb.h)
FBIOGET_VSCREENINFO = 0x4600
FBIOPUT_VSCREENINFO = 0x4601
FBIOGET_FSCREENINFO = 0x4602

# VT/KD ioctl numbers (from linux/kd.h, linux/vt.h)
KDSETMODE = 0x4B3A
KD_TEXT = 0x00
KD_GRAPHICS = 0x01
VT_ACTIVATE = 0x5606
VT_WAITACTIVE = 0x5607


# DRM mode structures
class DrmModeCreateDumb(ctypes.Structure):
    _fields_ = [
        ("height", ctypes.c_uint32),
        ("width", ctypes.c_uint32),
        ("bpp", ctypes.c_uint32),
        ("flags", ctypes.c_uint32),
        ("handle", ctypes.c_uint32),
        ("pitch", ctypes.c_uint32),
        ("size", ctypes.c_uint64),
    ]


class DrmModeMapDumb(ctypes.Structure):
    _fields_ = [
        ("handle", ctypes.c_uint32),
        ("pad", ctypes.c_uint32),
        ("offset", ctypes.c_uint64),
    ]


class DrmModeDestroyDumb(ctypes.Structure):
    _fields_ = [
        ("handle", ctypes.c_uint32),
    ]


DRM_IOCTL_MODE_CREATE_DUMB = _IOWR(DRM_IOCTL_BASE, 0xB2, ctypes.sizeof(DrmModeCreateDumb))
DRM_IOCTL_MODE_MAP_DUMB = _IOWR(DRM_IOCTL_BASE, 0xB3, ctypes.sizeof(DrmModeMapDumb))
DRM_IOCTL_MODE_DESTROY_DUMB = _IOWR(DRM_IOCTL_BASE, 0xB4, ctypes.sizeof(DrmModeDestroyDumb))


# --- fbdev screen info structures ---

class FbBitfield(ctypes.Structure):
    _fields_ = [
        ("offset", ctypes.c_uint32),
        ("length", ctypes.c_uint32),
        ("msb_right", ctypes.c_uint32),
    ]


class FbVarScreeninfo(ctypes.Structure):
    _fields_ = [
        ("xres", ctypes.c_uint32),
        ("yres", ctypes.c_uint32),
        ("xres_virtual", ctypes.c_uint32),
        ("yres_virtual", ctypes.c_uint32),
        ("xoffset", ctypes.c_uint32),
        ("yoffset", ctypes.c_uint32),
        ("bits_per_pixel", ctypes.c_uint32),
        ("grayscale", ctypes.c_uint32),
        ("red", FbBitfield),
        ("green", FbBitfield),
        ("blue", FbBitfield),
        ("transp", FbBitfield),
        ("nonstd", ctypes.c_uint32),
        ("activate", ctypes.c_uint32),
        ("height", ctypes.c_uint32),
        ("width", ctypes.c_uint32),
        ("accel_flags", ctypes.c_uint32),
        ("pixclock", ctypes.c_uint32),
        ("left_margin", ctypes.c_uint32),
        ("right_margin", ctypes.c_uint32),
        ("upper_margin", ctypes.c_uint32),
        ("lower_margin", ctypes.c_uint32),
        ("hsync_len", ctypes.c_uint32),
        ("vsync_len", ctypes.c_uint32),
        ("sync", ctypes.c_uint32),
        ("vmode", ctypes.c_uint32),
        ("rotate", ctypes.c_uint32),
        ("colorspace", ctypes.c_uint32),
        ("reserved", ctypes.c_uint32 * 4),
    ]


class FbFixScreeninfo(ctypes.Structure):
    _fields_ = [
        ("id", ctypes.c_char * 16),
        ("smem_start", ctypes.c_ulong),
        ("smem_len", ctypes.c_uint32),
        ("type", ctypes.c_uint32),
        ("type_aux", ctypes.c_uint32),
        ("visual", ctypes.c_uint32),
        ("xpanstep", ctypes.c_uint16),
        ("ypanstep", ctypes.c_uint16),
        ("xwrapstep", ctypes.c_uint16),
        ("_pad", ctypes.c_uint16),
        ("line_length", ctypes.c_uint32),
        ("mmio_start", ctypes.c_ulong),
        ("mmio_len", ctypes.c_uint32),
        ("accel", ctypes.c_uint32),
        ("capabilities", ctypes.c_uint16),
        ("reserved", ctypes.c_uint16 * 2),
    ]


def _parse_hex_color(color_str: str) -> tuple:
    """Parse a hex color string to (r, g, b, a) floats 0.0-1.0."""
    c = color_str.lstrip("#")
    if len(c) == 6:
        r, g, b = int(c[0:2], 16), int(c[2:4], 16), int(c[4:6], 16)
        return r / 255.0, g / 255.0, b / 255.0, 1.0
    elif len(c) == 8:
        r, g, b, a = int(c[0:2], 16), int(c[2:4], 16), int(c[4:6], 16), int(c[6:8], 16)
        return r / 255.0, g / 255.0, b / 255.0, a / 255.0
    return 0.0, 0.0, 0.0, 1.0


class DRMFramebuffer:
    """Manages a DRM dumb buffer framebuffer."""

    def __init__(self, fd, width, height):
        self.fd = fd
        self.width = width
        self.height = height
        self.handle = 0
        self.stride = 0
        self.size = 0
        self.fb_id = 0
        self.map = None
        self._map_obj = None

    def create(self):
        """Create and map a dumb DRM buffer."""
        # Load libdrm
        libdrm_path = ctypes.util.find_library("drm")
        if not libdrm_path:
            raise RuntimeError("libdrm not found")
        self._libdrm = ctypes.CDLL(libdrm_path)

        # Create dumb buffer
        create = DrmModeCreateDumb()
        create.width = self.width
        create.height = self.height
        create.bpp = 32
        create.flags = 0
        ret = fcntl.ioctl(self.fd, DRM_IOCTL_MODE_CREATE_DUMB, create)
        if ret < 0:
            raise RuntimeError(f"Failed to create dumb buffer: {ret}")

        self.handle = create.handle
        self.stride = create.pitch
        self.size = create.size

        # Add framebuffer
        fb_id = ctypes.c_uint32()
        ret = self._libdrm.drmModeAddFB(
            self.fd, self.width, self.height, 24, 32,
            self.stride, self.handle, ctypes.byref(fb_id)
        )
        if ret != 0:
            raise RuntimeError(f"drmModeAddFB failed: {ret}")
        self.fb_id = fb_id.value

        # Map to userspace
        map_req = DrmModeMapDumb()
        map_req.handle = self.handle
        fcntl.ioctl(self.fd, DRM_IOCTL_MODE_MAP_DUMB, map_req)

        self._map_obj = mmap.mmap(
            self.fd, self.size,
            mmap.MAP_SHARED, mmap.PROT_READ | mmap.PROT_WRITE,
            offset=map_req.offset
        )
        self.map = self._map_obj

    def destroy(self):
        """Clean up framebuffer resources."""
        if self._map_obj:
            self._map_obj.close()
        if self.fb_id:
            self._libdrm.drmModeRmFB(self.fd, self.fb_id)
        if self.handle:
            destroy = DrmModeDestroyDumb()
            destroy.handle = self.handle
            fcntl.ioctl(self.fd, DRM_IOCTL_MODE_DESTROY_DUMB, destroy)


class FBDevDisplay:
    """
    Linux framebuffer device (/dev/fb0) display backend.

    Opens the fbdev device, queries its resolution, mmaps the framebuffer
    memory, and provides a present() method to copy rendered pixels to
    the display. Also handles VT switching to take over the display.
    """

    def __init__(self, device_path="/dev/fb0"):
        self.device_path = device_path
        self.fd = -1
        self.width = 0
        self.height = 0
        self.stride = 0
        self.bpp = 0
        self.fb_size = 0
        self._fb_mmap = None
        self._tty_fd = -1

    def open(self):
        """Open the fbdev device and query display parameters."""
        self.fd = os.open(self.device_path, os.O_RDWR)

        # Query variable screen info (resolution, bpp)
        var_info = FbVarScreeninfo()
        fcntl.ioctl(self.fd, FBIOGET_VSCREENINFO, var_info)
        self.width = var_info.xres
        self.height = var_info.yres
        self.bpp = var_info.bits_per_pixel

        # Query fixed screen info (stride, memory size)
        fix_info = FbFixScreeninfo()
        fcntl.ioctl(self.fd, FBIOGET_FSCREENINFO, fix_info)
        self.stride = fix_info.line_length
        self.fb_size = fix_info.smem_len

        # Memory-map the framebuffer
        self._fb_mmap = mmap.mmap(
            self.fd, self.fb_size,
            mmap.MAP_SHARED, mmap.PROT_READ | mmap.PROT_WRITE,
        )

        logger.info("fbdev opened: %s (%dx%d, %dbpp, stride=%d, size=%d)",
                     self.device_path, self.width, self.height,
                     self.bpp, self.stride, self.fb_size)

    def acquire_vt(self):
        """Switch VT to graphics mode to take over the display from fbcon."""
        try:
            self._tty_fd = os.open("/dev/tty0", os.O_RDWR)
            fcntl.ioctl(self._tty_fd, KDSETMODE, KD_GRAPHICS)
            logger.info("VT switched to graphics mode")
        except OSError as e:
            logger.warning("Could not switch VT to graphics mode: %s", e)
            self._tty_fd = -1

    def release_vt(self):
        """Restore VT to text mode."""
        if self._tty_fd >= 0:
            try:
                fcntl.ioctl(self._tty_fd, KDSETMODE, KD_TEXT)
                os.close(self._tty_fd)
                logger.info("VT restored to text mode")
            except OSError as e:
                logger.warning("Could not restore VT: %s", e)
            self._tty_fd = -1

    def present(self, pixel_data: bytes, render_width: int, render_height: int):
        """
        Copy rendered pixel data to the framebuffer.

        Handles stride mismatch between the render buffer and the fbdev
        stride, and clips if render dimensions differ from display.
        """
        if not self._fb_mmap:
            return

        render_stride = render_width * 4  # ARGB32 = 4 bytes per pixel
        copy_width = min(render_width, self.width) * 4
        copy_height = min(render_height, self.height)

        if render_stride == self.stride and render_width == self.width:
            # Fast path: strides match, bulk copy
            nbytes = min(len(pixel_data), self.fb_size)
            self._fb_mmap.seek(0)
            self._fb_mmap.write(pixel_data[:nbytes])
        else:
            # Slow path: copy row by row to handle stride difference
            for y in range(copy_height):
                src_offset = y * render_stride
                dst_offset = y * self.stride
                self._fb_mmap.seek(dst_offset)
                self._fb_mmap.write(pixel_data[src_offset:src_offset + copy_width])

    def close(self):
        """Close the fbdev device and restore VT."""
        self.release_vt()
        if self._fb_mmap:
            self._fb_mmap.close()
            self._fb_mmap = None
        if self.fd >= 0:
            os.close(self.fd)
            self.fd = -1
        logger.info("fbdev display closed")


class DRMRenderer:
    """
    Renders compositor scene graphs to a display framebuffer using Cairo.

    Supports three backends:
      - fbdev: Uses /dev/fb0 with fbdev emulation (simplest, works in QEMU)
      - drm: Uses /dev/dri/card0 with DRM dumb buffers
      - headless: In-memory rendering for testing/PNG export

    Usage:
        renderer = DRMRenderer()
        renderer.initialize()           # Auto-detects backend
        renderer.render(scene_graph)     # Draws a frame to internal buffer
        renderer.present()              # Copies buffer to display
        renderer.shutdown()              # Cleans up
    """

    def __init__(self, device_path="/dev/dri/card0"):
        self.device_path = device_path
        self.fd = -1
        self.fb = None
        self.width = 0
        self.height = 0
        self._cairo = None
        self._connector_id = 0
        self._crtc_id = 0
        self._saved_crtc = None
        self._libdrm = None
        self._headless = False
        self._cairo_surface = None
        self._cairo_ctx = None
        self._display = None  # FBDevDisplay instance
        self._backend = "headless"  # "fbdev", "drm", or "headless"

    @property
    def initialized(self):
        return self.fd >= 0 or self._headless or self._display is not None

    def initialize(self, headless=False, width=1080, height=2340):
        """
        Initialize the renderer.

        Tries backends in order: fbdev -> DRM -> headless.
        """
        if headless:
            return self._init_headless(width, height)

        # Try fbdev first (simplest, works with QEMU virtio-gpu + fbdev emulation)
        for fb_path in ["/dev/fb0", "/dev/fb1"]:
            if os.path.exists(fb_path):
                try:
                    return self._init_fbdev(fb_path)
                except Exception as e:
                    logger.warning("fbdev init failed for %s: %s", fb_path, e)

        # Try DRM
        for drm_path in ["/dev/dri/card0", "/dev/dri/card1"]:
            if os.path.exists(drm_path):
                try:
                    return self._init_drm(drm_path)
                except Exception as e:
                    logger.warning("DRM init failed for %s: %s", drm_path, e)

        # Fall back to headless
        logger.warning("No display device found, falling back to headless")
        return self._init_headless(width, height)

    def _init_fbdev(self, device_path):
        """Initialize using Linux framebuffer device."""
        self._display = FBDevDisplay(device_path)
        self._display.open()
        self._display.acquire_vt()

        self.width = self._display.width
        self.height = self._display.height
        self._backend = "fbdev"

        logger.info("fbdev renderer initialized: %dx%d", self.width, self.height)
        self._init_cairo_surface()

    def _init_drm(self, device_path=None):
        """Initialize real DRM output."""
        device_path = device_path or self.device_path

        libdrm_path = ctypes.util.find_library("drm")
        if not libdrm_path:
            raise RuntimeError("libdrm not found — install libdrm-dev")
        self._libdrm = ctypes.CDLL(libdrm_path)

        # Set return types for libdrm functions
        self._libdrm.drmModeGetResources.restype = ctypes.c_void_p
        self._libdrm.drmModeGetConnector.restype = ctypes.c_void_p
        self._libdrm.drmModeGetEncoder.restype = ctypes.c_void_p
        self._libdrm.drmModeGetCrtc.restype = ctypes.c_void_p

        self.fd = os.open(device_path, os.O_RDWR)
        logger.info("Opened DRM device: %s", device_path)

        res = self._libdrm.drmModeGetResources(self.fd)
        if not res:
            raise RuntimeError("drmModeGetResources failed — no display?")

        self.width = 1080
        self.height = 2340
        self._backend = "drm"

        logger.info("DRM renderer initialized: %dx%d", self.width, self.height)
        self._init_cairo_surface()

    def _init_headless(self, width, height):
        """Initialize headless (in-memory) rendering."""
        self._headless = True
        self.width = width
        self.height = height
        self._backend = "headless"
        logger.info("Headless renderer initialized: %dx%d", width, height)
        self._init_cairo_surface()

    def _init_cairo_surface(self):
        """Create a Cairo image surface for rendering."""
        try:
            import cairo
            self._cairo = cairo
            self._cairo_surface = cairo.ImageSurface(
                cairo.FORMAT_ARGB32, self.width, self.height
            )
            self._cairo_ctx = cairo.Context(self._cairo_surface)
            logger.info("Cairo rendering backend ready")
        except ImportError:
            logger.warning("pycairo not available — using raw pixel rendering")
            self._cairo = None
            self._pixel_buffer = bytearray(self.width * self.height * 4)

    def render(self, scene_graph):
        """
        Render a scene graph to the internal buffer.

        Args:
            scene_graph: A SceneNode tree from Compositor.build_scene_graph()
        """
        if self._cairo and self._cairo_ctx:
            self._render_cairo(scene_graph)
        else:
            self._render_raw(scene_graph)

    def present(self):
        """Copy the rendered frame to the display framebuffer."""
        if self._backend == "fbdev" and self._display:
            pixel_data = self.get_pixel_data()
            if pixel_data:
                self._display.present(pixel_data, self.width, self.height)
        elif self._backend == "drm" and self.fb:
            # Copy Cairo surface to DRM dumb buffer
            pixel_data = self.get_pixel_data()
            if pixel_data and self.fb.map:
                self.fb.map.seek(0)
                self.fb.map.write(pixel_data[:self.fb.size])

    def _render_cairo(self, node):
        """Render scene graph using Cairo."""
        ctx = self._cairo_ctx
        cairo = self._cairo

        # Clear with background color
        if node.background_color:
            r, g, b, a = _parse_hex_color(node.background_color)
            ctx.set_source_rgba(r, g, b, a)
            ctx.rectangle(0, 0, self.width, self.height)
            ctx.fill()

        # Render children
        for child in node.children:
            self._render_node_cairo(ctx, child)

    def _render_node_cairo(self, ctx, node):
        """Render a single SceneNode with Cairo."""
        cairo = self._cairo
        ctx.save()

        # Apply opacity
        if node.opacity < 1.0:
            ctx.push_group()

        # Draw background color if present
        if node.background_color:
            r, g, b, a = _parse_hex_color(node.background_color)

            if node.corner_radius > 0:
                self._rounded_rect(ctx, node.x, node.y,
                                   node.width, node.height, node.corner_radius)
                ctx.set_source_rgba(r, g, b, a)
                ctx.fill()
            else:
                ctx.set_source_rgba(r, g, b, a)
                ctx.rectangle(node.x, node.y, node.width, node.height)
                ctx.fill()

        # Draw surface placeholder (colored rect based on role)
        if node.surface:
            self._render_surface_placeholder(ctx, node)

        # Render children
        for child in node.children:
            self._render_node_cairo(ctx, child)

        # Apply opacity
        if node.opacity < 1.0:
            ctx.pop_group_to_source()
            ctx.paint_with_alpha(node.opacity)

        ctx.restore()

    def _render_surface_placeholder(self, ctx, node):
        """Render a placeholder rectangle for a surface."""
        role_colors = {
            "STATUS_BAR": (0.05, 0.05, 0.1, 0.7),
            "KEYBOARD": (0.12, 0.12, 0.15, 0.95),
            "NOTIFICATION_PANEL": (0.08, 0.08, 0.12, 0.9),
            "LOCK_SCREEN": (0.1, 0.1, 0.18, 1.0),
            "APP": (0.96, 0.96, 0.95, 1.0),
            "OVERLAY": (0.0, 0.0, 0.0, 0.5),
        }

        role_name = node.surface.role.name if node.surface.role else "APP"
        r, g, b, a = role_colors.get(role_name, (0.5, 0.5, 0.5, 1.0))

        if node.corner_radius > 0:
            self._rounded_rect(ctx, node.x, node.y,
                               node.width, node.height, node.corner_radius)
            ctx.set_source_rgba(r, g, b, a)
            ctx.fill()
        else:
            ctx.set_source_rgba(r, g, b, a)
            ctx.rectangle(node.x, node.y, node.width, node.height)
            ctx.fill()

        # Draw role label text in the center
        if self._cairo:
            ctx.set_source_rgba(1.0, 1.0, 1.0, 0.6)
            ctx.select_font_face("sans-serif", self._cairo.FONT_SLANT_NORMAL,
                                 self._cairo.FONT_WEIGHT_NORMAL)
            ctx.set_font_size(24)
            label = node.surface.app_id or role_name
            extents = ctx.text_extents(label)
            text_x = node.x + (node.width - extents.width) / 2
            text_y = node.y + (node.height + extents.height) / 2
            ctx.move_to(text_x, text_y)
            ctx.show_text(label)

    def _rounded_rect(self, ctx, x, y, w, h, r):
        """Draw a rounded rectangle path."""
        import math
        ctx.new_sub_path()
        ctx.arc(x + w - r, y + r, r, -math.pi / 2, 0)
        ctx.arc(x + w - r, y + h - r, r, 0, math.pi / 2)
        ctx.arc(x + r, y + h - r, r, math.pi / 2, math.pi)
        ctx.arc(x + r, y + r, r, math.pi, 3 * math.pi / 2)
        ctx.close_path()

    def _render_raw(self, node):
        """Fallback renderer without Cairo — optimized filled rectangles."""
        buf = self._pixel_buffer
        stride = self.width * 4

        # Fill background
        if node.background_color:
            r, g, b, _ = _parse_hex_color(node.background_color)
            pixel = struct.pack("BBBB", int(b * 255), int(g * 255), int(r * 255), 255)
            row = pixel * self.width
            for y in range(self.height):
                buf[y * stride:(y + 1) * stride] = row

        # Render child rectangles
        for child in node.children:
            self._fill_rect_raw(buf, stride, child)

    def _fill_rect_raw(self, buf, stride, node):
        """Fill a rectangle in the raw pixel buffer (optimized row fills)."""
        if node.background_color:
            r, g, b, a = _parse_hex_color(node.background_color)
        elif node.surface:
            r, g, b, a = 0.5, 0.5, 0.5, 1.0
        else:
            return

        x0 = max(0, node.x)
        y0 = max(0, node.y)
        x1 = min(self.width, node.x + node.width)
        y1 = min(self.height, node.y + node.height)
        rect_w = x1 - x0

        if rect_w <= 0 or y1 <= y0:
            return

        pixel = struct.pack("BBBB", int(b * 255), int(g * 255), int(r * 255), int(a * 255))
        row = pixel * rect_w

        for y in range(y0, y1):
            offset = y * stride + x0 * 4
            buf[offset:offset + rect_w * 4] = row

    def save_png(self, path):
        """Save the current frame to a PNG file (requires Cairo)."""
        if self._cairo_surface:
            self._cairo_surface.write_to_png(str(path))
            logger.info("Frame saved to %s", path)
        else:
            logger.warning("PNG export requires Cairo")

    def get_pixel_data(self):
        """Return raw ARGB32 pixel data for the current frame."""
        if self._cairo_surface:
            self._cairo_surface.flush()
            return bytes(self._cairo_surface.get_data())
        elif hasattr(self, "_pixel_buffer"):
            return bytes(self._pixel_buffer)
        return b""

    def shutdown(self):
        """Clean up renderer resources."""
        if self._cairo_surface:
            self._cairo_surface.finish()
            self._cairo_surface = None
            self._cairo_ctx = None

        if self._display:
            self._display.close()
            self._display = None

        if self.fb:
            self.fb.destroy()
            self.fb = None

        if self.fd >= 0:
            os.close(self.fd)
            self.fd = -1

        logger.info("Renderer shut down (backend=%s)", self._backend)
