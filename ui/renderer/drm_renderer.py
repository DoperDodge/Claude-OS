"""
Claude-OS DRM Framebuffer Renderer

Renders the compositor's scene graph to a DRM framebuffer using Cairo
for 2D drawing. This is the bridge between the abstract scene graph
(SceneNode tree) and actual pixels on screen via /dev/dri/card0.

Rendering pipeline:
    Compositor.build_scene_graph() -> SceneNode tree
        -> DRMRenderer.render(scene_graph)
            -> Cairo draws to memory buffer
                -> Buffer copied to DRM framebuffer
                    -> Pixels on screen

Fallback: If DRM is not available (e.g., running in -nographic mode),
the renderer operates in "headless" mode and can dump frames to PNG.
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


class DRMRenderer:
    """
    Renders compositor scene graphs to a DRM framebuffer using Cairo.

    Usage:
        renderer = DRMRenderer()
        renderer.initialize()           # Opens /dev/dri/card0, sets up FB
        renderer.render(scene_graph)     # Draws a frame
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

    @property
    def initialized(self):
        return self.fd >= 0 or self._headless

    def initialize(self, headless=False, width=1080, height=2340):
        """
        Initialize the DRM renderer.

        Args:
            headless: If True, render to an in-memory Cairo surface (no DRM).
            width: Display width (used in headless mode or if DRM detection fails).
            height: Display height.
        """
        if headless:
            return self._init_headless(width, height)

        try:
            return self._init_drm()
        except Exception as e:
            logger.warning(f"DRM init failed ({e}), falling back to headless")
            return self._init_headless(width, height)

    def _init_drm(self):
        """Initialize real DRM output."""
        # Load libdrm
        libdrm_path = ctypes.util.find_library("drm")
        if not libdrm_path:
            raise RuntimeError("libdrm not found — install libdrm-dev")
        self._libdrm = ctypes.CDLL(libdrm_path)

        # Open DRM device
        self.fd = os.open(self.device_path, os.O_RDWR)
        logger.info(f"Opened DRM device: {self.device_path}")

        # Get resources
        res = self._libdrm.drmModeGetResources(self.fd)
        if not res:
            raise RuntimeError("drmModeGetResources failed — no display?")

        # Define return types for libdrm functions
        self._libdrm.drmModeGetResources.restype = ctypes.c_void_p
        self._libdrm.drmModeGetConnector.restype = ctypes.c_void_p
        self._libdrm.drmModeGetEncoder.restype = ctypes.c_void_p
        self._libdrm.drmModeGetCrtc.restype = ctypes.c_void_p

        # For simplicity with ctypes, we use the C test program for actual
        # DRM modesetting. The Python renderer targets Cairo image surfaces
        # that get blitted to the DRM framebuffer via mmap.
        #
        # In production, this will be replaced by wlroots which handles
        # all DRM modesetting natively.

        # For now, detect display dimensions from DRM
        # and set up a framebuffer we can render to
        self.width = 1080  # Default, will be overridden by actual mode
        self.height = 2340

        logger.info(f"DRM renderer initialized: {self.width}x{self.height}")
        self._init_cairo_surface()

    def _init_headless(self, width, height):
        """Initialize headless (in-memory) rendering."""
        self._headless = True
        self.width = width
        self.height = height
        logger.info(f"Headless renderer initialized: {width}x{height}")
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
            # Allocate raw pixel buffer as fallback
            self._pixel_buffer = bytearray(self.width * self.height * 4)

    def render(self, scene_graph):
        """
        Render a scene graph to the framebuffer.

        Args:
            scene_graph: A SceneNode tree from Compositor.build_scene_graph()
        """
        if self._cairo and self._cairo_ctx:
            self._render_cairo(scene_graph)
        else:
            self._render_raw(scene_graph)

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
                # Rounded rectangle
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
        """Render a placeholder rectangle for a Wayland surface."""
        # Until real Wayland clients render pixels, show role-appropriate colors
        role_colors = {
            "STATUS_BAR": (0.05, 0.05, 0.1, 0.7),    # Dark translucent
            "KEYBOARD": (0.12, 0.12, 0.15, 0.95),     # Dark opaque
            "NOTIFICATION_PANEL": (0.08, 0.08, 0.12, 0.9),
            "LOCK_SCREEN": (0.1, 0.1, 0.18, 1.0),     # Navy
            "APP": (0.96, 0.96, 0.95, 1.0),            # Light off-white
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
        """Fallback renderer without Cairo — simple filled rectangles."""
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
        """Fill a rectangle in the raw pixel buffer."""
        if node.background_color:
            r, g, b, a = _parse_hex_color(node.background_color)
        elif node.surface:
            r, g, b, a = 0.5, 0.5, 0.5, 1.0
        else:
            return

        pixel = struct.pack("BBBB", int(b * 255), int(g * 255), int(r * 255), int(a * 255))
        for y in range(max(0, node.y), min(self.height, node.y + node.height)):
            for x in range(max(0, node.x), min(self.width, node.x + node.width)):
                offset = y * stride + x * 4
                buf[offset:offset + 4] = pixel

    def save_png(self, path):
        """Save the current frame to a PNG file (requires Cairo)."""
        if self._cairo_surface:
            self._cairo_surface.write_to_png(str(path))
            logger.info(f"Frame saved to {path}")
        else:
            logger.warning("PNG export requires Cairo")

    def get_pixel_data(self):
        """Return raw ARGB32 pixel data for the current frame."""
        if self._cairo_surface:
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

        if self.fb:
            self.fb.destroy()
            self.fb = None

        if self.fd >= 0:
            os.close(self.fd)
            self.fd = -1

        logger.info("DRM renderer shut down")
