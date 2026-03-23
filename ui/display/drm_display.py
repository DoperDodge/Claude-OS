"""
Claude-OS DRM/KMS Display

Modern display backend using the Linux DRM (Direct Rendering Manager)
subsystem. Talks directly to /dev/dri/card0 via the dumb buffer API.

Advantages over framebuffer:
  - Proper vsync via page-flipping
  - Multi-buffer support (double/triple buffering)
  - Resolution and mode enumeration
  - Foundation for Wayland compositor integration

This uses the "dumb buffer" DRM API which works without GPU-specific
userspace drivers — perfect for virtio-gpu in QEMU.
"""

import ctypes
import ctypes.util
import fcntl
import logging
import mmap
import os
import struct
from dataclasses import dataclass, field

logger = logging.getLogger("display.drm")

# DRM ioctl numbers (from drm.h / drm_mode.h)
DRM_IOCTL_BASE = 0x64

# Mode-setting ioctls
DRM_IOCTL_MODE_GETRESOURCES = 0xC04064A0
DRM_IOCTL_MODE_GETCRTC = 0xC06864A1
DRM_IOCTL_MODE_SETCRTC = 0xC06864A2
DRM_IOCTL_MODE_GETENCODER = 0xC01464A6
DRM_IOCTL_MODE_GETCONNECTOR = 0xC05064A7
DRM_IOCTL_MODE_GETPROPERTY = 0xC04064AA

# Dumb buffer ioctls
DRM_IOCTL_MODE_CREATE_DUMB = 0xC02064B2
DRM_IOCTL_MODE_MAP_DUMB = 0xC01064B3
DRM_IOCTL_MODE_DESTROY_DUMB = 0xC00464B4
DRM_IOCTL_MODE_ADDFB = 0xC04464AE
DRM_IOCTL_MODE_RMFB = 0xC00464AF

# Connector status
DRM_MODE_CONNECTED = 1
DRM_MODE_DISCONNECTED = 2

# Page flip
DRM_IOCTL_MODE_PAGE_FLIP = 0xC01864B0
DRM_MODE_PAGE_FLIP_EVENT = 0x01


@dataclass
class DRMMode:
    """A display mode (resolution + refresh rate)."""
    width: int
    height: int
    refresh: int
    name: str
    raw: bytes = field(default=b'', repr=False)


@dataclass
class DRMConnector:
    """A display connector (e.g., HDMI, DSI, Virtual)."""
    id: int
    status: int  # 1=connected, 2=disconnected
    encoder_id: int
    modes: list[DRMMode] = field(default_factory=list)

    @property
    def connected(self) -> bool:
        return self.status == DRM_MODE_CONNECTED


@dataclass
class DRMBuffer:
    """A dumb DRM buffer for rendering."""
    handle: int
    width: int
    height: int
    stride: int
    size: int
    fb_id: int = 0
    map_offset: int = 0
    data: mmap.mmap | None = None


class DRMDisplay:
    """
    DRM/KMS display backend.

    Usage:
        drm = DRMDisplay()
        drm.open()
        drm.setup()          # Find connector, create buffer
        drm.fill(0, 0, 128)  # Fill dark blue
        drm.present()         # Show on screen
        drm.close()
    """

    def __init__(self, device: str = "/dev/dri/card0"):
        self.device = device
        self._fd: int | None = None
        self.connector: DRMConnector | None = None
        self.mode: DRMMode | None = None
        self.buffer: DRMBuffer | None = None
        self._crtc_id: int = 0
        self._original_crtc: bytes | None = None

    def open(self):
        """Open the DRM device."""
        self._fd = os.open(self.device, os.O_RDWR | os.O_CLOEXEC)
        logger.info("DRM device opened: %s (fd=%d)", self.device, self._fd)

    def close(self):
        """Clean up and close the DRM device."""
        if self.buffer:
            self._destroy_buffer(self.buffer)
            self.buffer = None
        if self._fd is not None:
            os.close(self._fd)
            self._fd = None
        logger.info("DRM device closed")

    def setup(self, preferred_width: int = 0, preferred_height: int = 0):
        """
        Auto-detect display and set up rendering.

        Finds the first connected connector, picks the best mode,
        creates a dumb buffer, and sets the CRTC.
        """
        if self._fd is None:
            raise RuntimeError("DRM device not open")

        # Find connected connectors
        connectors = self._get_connectors()
        connected = [c for c in connectors if c.connected]

        if not connected:
            raise RuntimeError("No connected display found")

        self.connector = connected[0]
        logger.info("Using connector %d (%d modes available)",
                     self.connector.id, len(self.connector.modes))

        # Pick mode
        if preferred_width and preferred_height:
            for m in self.connector.modes:
                if m.width == preferred_width and m.height == preferred_height:
                    self.mode = m
                    break

        if not self.mode and self.connector.modes:
            self.mode = self.connector.modes[0]  # First mode = preferred

        if not self.mode:
            raise RuntimeError("No display modes available")

        logger.info("Display mode: %s (%dx%d @ %dHz)",
                     self.mode.name, self.mode.width, self.mode.height,
                     self.mode.refresh)

        # Find CRTC via encoder
        self._crtc_id = self._find_crtc(self.connector)

        # Create framebuffer
        self.buffer = self._create_buffer(self.mode.width, self.mode.height)

        # Set the mode
        self._set_crtc(self._crtc_id, self.buffer.fb_id, self.mode)

        logger.info("DRM display ready: %dx%d, buffer=%d",
                     self.mode.width, self.mode.height, self.buffer.fb_id)

    def fill(self, r: int, g: int, b: int, a: int = 255):
        """Fill the entire buffer with a solid color."""
        if not self.buffer or not self.buffer.data:
            raise RuntimeError("No buffer available")

        pixel = struct.pack("BBBB", b, g, r, a)  # BGRA
        row = pixel * self.buffer.width
        padding = self.buffer.stride - (self.buffer.width * 4)
        if padding > 0:
            row += b'\x00' * padding

        self.buffer.data.seek(0)
        for _ in range(self.buffer.height):
            self.buffer.data.write(row)

    def rect(self, x: int, y: int, w: int, h: int,
             r: int, g: int, b: int, a: int = 255):
        """Draw a filled rectangle to the buffer."""
        if not self.buffer or not self.buffer.data:
            raise RuntimeError("No buffer available")

        x0 = max(0, x)
        y0 = max(0, y)
        x1 = min(self.buffer.width, x + w)
        y1 = min(self.buffer.height, y + h)

        if x0 >= x1 or y0 >= y1:
            return

        pixel = struct.pack("BBBB", b, g, r, a)
        row_pixels = pixel * (x1 - x0)

        for row in range(y0, y1):
            offset = row * self.buffer.stride + x0 * 4
            self.buffer.data.seek(offset)
            self.buffer.data.write(row_pixels)

    def present(self):
        """Present the current buffer to the screen (no-op for single buffer + setCrtc)."""
        # With dumb buffers and setCrtc, drawing is immediately visible.
        # For double-buffering, we'd use page-flip here.
        pass

    # --- DRM Resource Enumeration ---

    def _get_connectors(self) -> list[DRMConnector]:
        """Enumerate display connectors."""
        # First call: get counts
        res_buf = bytearray(64)
        try:
            fcntl.ioctl(self._fd, DRM_IOCTL_MODE_GETRESOURCES, res_buf)
        except OSError as e:
            logger.error("Failed to get DRM resources: %s", e)
            return []

        count_connectors = struct.unpack_from("<I", res_buf, 28)[0]
        if count_connectors == 0:
            return []

        # Second call: get connector IDs
        connector_ids_buf = (ctypes.c_uint32 * count_connectors)()
        struct.pack_into("<Q", res_buf, 32, ctypes.addressof(connector_ids_buf))
        struct.pack_into("<I", res_buf, 28, count_connectors)

        try:
            fcntl.ioctl(self._fd, DRM_IOCTL_MODE_GETRESOURCES, res_buf)
        except OSError:
            return []

        connectors = []
        for i in range(count_connectors):
            conn_id = connector_ids_buf[i]
            conn = self._get_connector(conn_id)
            if conn:
                connectors.append(conn)

        return connectors

    def _get_connector(self, connector_id: int) -> DRMConnector | None:
        """Get details for a specific connector."""
        # First call to get counts
        buf = bytearray(80)
        struct.pack_into("<I", buf, 76, connector_id)

        try:
            fcntl.ioctl(self._fd, DRM_IOCTL_MODE_GETCONNECTOR, buf)
        except OSError:
            return None

        count_modes = struct.unpack_from("<I", buf, 32)[0]
        encoder_id = struct.unpack_from("<I", buf, 40)[0]
        status = struct.unpack_from("<I", buf, 56)[0]

        modes = []
        if count_modes > 0:
            # Allocate mode array and re-query
            mode_size = 68  # sizeof(struct drm_mode_modeinfo)
            modes_buf = bytearray(mode_size * count_modes)
            struct.pack_into("<Q", buf, 0, id(modes_buf))
            struct.pack_into("<I", buf, 32, count_modes)
            struct.pack_into("<I", buf, 76, connector_id)

            try:
                fcntl.ioctl(self._fd, DRM_IOCTL_MODE_GETCONNECTOR, buf)
                for j in range(count_modes):
                    offset = j * mode_size
                    mode_data = modes_buf[offset:offset + mode_size]
                    hdisplay = struct.unpack_from("<H", mode_data, 16)[0]
                    vdisplay = struct.unpack_from("<H", mode_data, 26)[0]
                    vrefresh = struct.unpack_from("<I", mode_data, 60)[0]
                    name = mode_data[36:68].split(b'\x00')[0].decode('ascii', errors='replace')
                    modes.append(DRMMode(
                        width=hdisplay,
                        height=vdisplay,
                        refresh=vrefresh,
                        name=name,
                        raw=mode_data,
                    ))
            except OSError:
                pass

        return DRMConnector(
            id=connector_id,
            status=status,
            encoder_id=encoder_id,
            modes=modes,
        )

    def _find_crtc(self, connector: DRMConnector) -> int:
        """Find a CRTC for the given connector."""
        # Get resources to find CRTC IDs
        res_buf = bytearray(64)
        try:
            fcntl.ioctl(self._fd, DRM_IOCTL_MODE_GETRESOURCES, res_buf)
        except OSError:
            raise RuntimeError("Failed to get DRM resources")

        count_crtcs = struct.unpack_from("<I", res_buf, 24)[0]
        if count_crtcs == 0:
            raise RuntimeError("No CRTCs available")

        crtc_ids_buf = (ctypes.c_uint32 * count_crtcs)()
        struct.pack_into("<Q", res_buf, 16, ctypes.addressof(crtc_ids_buf))
        struct.pack_into("<I", res_buf, 24, count_crtcs)

        try:
            fcntl.ioctl(self._fd, DRM_IOCTL_MODE_GETRESOURCES, res_buf)
        except OSError:
            raise RuntimeError("Failed to enumerate CRTCs")

        # Use the first CRTC
        return crtc_ids_buf[0]

    # --- Buffer Management ---

    def _create_buffer(self, width: int, height: int) -> DRMBuffer:
        """Create a dumb buffer and add it as a framebuffer."""
        # Create dumb buffer
        # struct drm_mode_create_dumb { height, width, bpp, flags, handle, pitch, size }
        create_buf = bytearray(32)
        struct.pack_into("<II", create_buf, 0, height, width)
        struct.pack_into("<I", create_buf, 8, 32)  # bpp = 32

        fcntl.ioctl(self._fd, DRM_IOCTL_MODE_CREATE_DUMB, create_buf)

        handle = struct.unpack_from("<I", create_buf, 16)[0]
        stride = struct.unpack_from("<I", create_buf, 20)[0]
        size = struct.unpack_from("<Q", create_buf, 24)[0]

        buf = DRMBuffer(
            handle=handle,
            width=width,
            height=height,
            stride=stride,
            size=size,
        )

        # Add as framebuffer
        # struct drm_mode_fb_cmd { fb_id, width, height, pitch, bpp, depth, handle }
        fb_buf = bytearray(28)
        struct.pack_into("<III", fb_buf, 4, width, height, stride)
        struct.pack_into("<II", fb_buf, 16, 32, 24)  # bpp=32, depth=24
        struct.pack_into("<I", fb_buf, 24, handle)

        fcntl.ioctl(self._fd, DRM_IOCTL_MODE_ADDFB, fb_buf)
        buf.fb_id = struct.unpack_from("<I", fb_buf, 0)[0]

        # Map dumb buffer for CPU access
        map_buf = bytearray(16)
        struct.pack_into("<I", map_buf, 0, handle)

        fcntl.ioctl(self._fd, DRM_IOCTL_MODE_MAP_DUMB, map_buf)
        buf.map_offset = struct.unpack_from("<Q", map_buf, 8)[0]

        # mmap the buffer
        buf.data = mmap.mmap(
            self._fd, size,
            mmap.MAP_SHARED, mmap.PROT_READ | mmap.PROT_WRITE,
            offset=buf.map_offset,
        )

        logger.info("DRM buffer created: %dx%d, stride=%d, fb=%d",
                     width, height, stride, buf.fb_id)
        return buf

    def _destroy_buffer(self, buf: DRMBuffer):
        """Destroy a dumb buffer."""
        if buf.data:
            buf.data.close()
        if buf.fb_id:
            try:
                rm_buf = struct.pack("<I", buf.fb_id)
                fcntl.ioctl(self._fd, DRM_IOCTL_MODE_RMFB, rm_buf)
            except OSError:
                pass
        if buf.handle:
            try:
                destroy_buf = struct.pack("<I", buf.handle)
                fcntl.ioctl(self._fd, DRM_IOCTL_MODE_DESTROY_DUMB, destroy_buf)
            except OSError:
                pass

    def _set_crtc(self, crtc_id: int, fb_id: int, mode: DRMMode):
        """Set the CRTC mode and framebuffer."""
        # struct drm_mode_crtc { set_connectors_ptr, count_connectors,
        #                        crtc_id, fb_id, x, y, ..., mode }
        buf = bytearray(104)

        connector_ids = (ctypes.c_uint32 * 1)(self.connector.id)
        struct.pack_into("<Q", buf, 0, ctypes.addressof(connector_ids))
        struct.pack_into("<I", buf, 8, 1)  # count_connectors
        struct.pack_into("<I", buf, 12, crtc_id)
        struct.pack_into("<I", buf, 16, fb_id)

        # Copy mode info (68 bytes starting at offset 36)
        if mode.raw:
            buf[36:36 + len(mode.raw)] = mode.raw

        # Set mode flag
        struct.pack_into("<I", buf, 32, 1)  # mode_valid = 1

        fcntl.ioctl(self._fd, DRM_IOCTL_MODE_SETCRTC, buf)
        logger.info("CRTC %d set: fb=%d, mode=%s", crtc_id, fb_id, mode.name)

    def get_info(self) -> dict:
        """Return display information."""
        info = {"device": self.device, "status": "open" if self._fd else "closed"}
        if self.mode:
            info["mode"] = {
                "width": self.mode.width,
                "height": self.mode.height,
                "refresh": self.mode.refresh,
                "name": self.mode.name,
            }
        if self.buffer:
            info["buffer"] = {
                "fb_id": self.buffer.fb_id,
                "stride": self.buffer.stride,
                "size": self.buffer.size,
            }
        return info

    def __enter__(self):
        self.open()
        self.setup()
        return self

    def __exit__(self, *args):
        self.close()
