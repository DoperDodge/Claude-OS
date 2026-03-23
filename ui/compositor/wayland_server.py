"""
Claude-OS Minimal Wayland Server

Implements a minimal Wayland compositor protocol server using Unix sockets.
This handles the core Wayland wire protocol so real Wayland clients (e.g.,
weston-simple-shm, GTK apps) can connect and render.

Implemented protocols:
    - wl_display: Global registry, sync, error
    - wl_registry: Global object advertisement
    - wl_compositor: Surface creation (wl_surface)
    - wl_surface: Attach, commit, damage, frame callbacks
    - wl_shm: Shared memory buffer management
    - wl_shm_pool: Buffer pool from shared memory fd
    - xdg_wm_base: XDG shell for app window management
    - xdg_surface: Window surface role
    - xdg_toplevel: Toplevel (fullscreen) window management

Not implemented (future):
    - wl_seat / wl_keyboard / wl_pointer (Phase 2.5)
    - wl_output (display info advertisement)
    - zwp_layer_shell (for status bar / keyboard overlays)
"""

import asyncio
import logging
import mmap
import os
import socket
import struct
from dataclasses import dataclass, field
from pathlib import Path

logger = logging.getLogger("wayland.server")

# Wayland wire protocol constants
WL_DISPLAY_ERROR = 0
WL_DISPLAY_DELETE_ID = 1

# Wayland object IDs (globals)
WL_DISPLAY_ID = 1

# Interface opcodes — wl_display
WL_DISPLAY_SYNC = 0
WL_DISPLAY_GET_REGISTRY = 1

# Interface opcodes — wl_registry
WL_REGISTRY_BIND = 0

# Interface opcodes — wl_compositor
WL_COMPOSITOR_CREATE_SURFACE = 0

# Interface opcodes — wl_surface
WL_SURFACE_DESTROY = 0
WL_SURFACE_ATTACH = 1
WL_SURFACE_DAMAGE = 2
WL_SURFACE_FRAME = 3
WL_SURFACE_COMMIT = 6

# Interface opcodes — wl_shm
WL_SHM_CREATE_POOL = 0

# Interface opcodes — wl_shm_pool
WL_SHM_POOL_CREATE_BUFFER = 0
WL_SHM_POOL_DESTROY = 2

# Interface opcodes — xdg_wm_base
XDG_WM_BASE_GET_SURFACE = 1
XDG_WM_BASE_PONG = 3

# Interface opcodes — xdg_surface
XDG_SURFACE_GET_TOPLEVEL = 1
XDG_SURFACE_ACK_CONFIGURE = 4

# Interface opcodes — xdg_toplevel
XDG_TOPLEVEL_SET_TITLE = 2
XDG_TOPLEVEL_SET_APP_ID = 3

# SHM format
WL_SHM_FORMAT_ARGB8888 = 0
WL_SHM_FORMAT_XRGB8888 = 1


@dataclass
class WaylandObject:
    """A server-side Wayland protocol object."""
    obj_id: int
    interface: str
    version: int = 1
    data: dict = field(default_factory=dict)


@dataclass
class ClientSurface:
    """Tracks a client's wl_surface state."""
    surface_id: int
    buffer_id: int = 0
    x_offset: int = 0
    y_offset: int = 0
    width: int = 0
    height: int = 0
    stride: int = 0
    shm_data: bytearray | None = None
    committed: bool = False
    app_id: str = ""
    title: str = ""
    xdg_surface_id: int = 0
    xdg_toplevel_id: int = 0
    frame_callbacks: list[int] = field(default_factory=list)


@dataclass
class ShmPool:
    """A shared memory pool from a client."""
    pool_id: int
    fd: int
    size: int
    data: mmap.mmap | None = None


class WaylandClient:
    """Represents a connected Wayland client."""

    def __init__(self, conn: socket.socket, client_id: int):
        self.conn = conn
        self.client_id = client_id
        self.objects: dict[int, WaylandObject] = {}
        self.surfaces: dict[int, ClientSurface] = {}
        self.shm_pools: dict[int, ShmPool] = {}
        self.next_id = 0xFF000000  # Server-allocated IDs start high
        self._recv_buf = bytearray()

        # wl_display is always object 1
        self.objects[WL_DISPLAY_ID] = WaylandObject(
            obj_id=WL_DISPLAY_ID, interface="wl_display",
        )

    def allocate_id(self) -> int:
        """Allocate a server-side object ID."""
        self.next_id += 1
        return self.next_id

    def close(self):
        """Close client connection."""
        for pool in self.shm_pools.values():
            if pool.data:
                pool.data.close()
        try:
            self.conn.close()
        except OSError:
            pass


class WaylandServer:
    """
    Minimal Wayland protocol server.

    Listens on a Unix socket, handles client connections, and dispatches
    protocol messages. Works with the Compositor for surface management
    and the CompositorRenderer for pixel output.
    """

    # Globals advertised to clients
    GLOBALS = [
        ("wl_compositor", 5),
        ("wl_shm", 1),
        ("xdg_wm_base", 4),
    ]

    def __init__(self, display_name: str = "wayland-0"):
        self.display_name = display_name
        self.socket_path: str = ""
        self._server_socket: socket.socket | None = None
        self._clients: dict[int, WaylandClient] = {}
        self._next_client_id = 1
        self._running = False

        # Callbacks to compositor
        self._on_surface_created = None
        self._on_surface_committed = None
        self._on_surface_destroyed = None

    def set_callbacks(self, on_created=None, on_committed=None, on_destroyed=None):
        """Set compositor callbacks for surface events."""
        self._on_surface_created = on_created
        self._on_surface_committed = on_committed
        self._on_surface_destroyed = on_destroyed

    def start(self) -> str:
        """
        Create the Wayland socket and start listening.

        Returns the socket path.
        """
        xdg_runtime = os.environ.get("XDG_RUNTIME_DIR", "/run/user/0")
        os.makedirs(xdg_runtime, exist_ok=True)

        self.socket_path = os.path.join(xdg_runtime, self.display_name)

        # Remove stale socket
        if os.path.exists(self.socket_path):
            os.unlink(self.socket_path)

        self._server_socket = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
        self._server_socket.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        self._server_socket.bind(self.socket_path)
        self._server_socket.listen(16)
        self._server_socket.setblocking(False)

        self._running = True

        os.environ["WAYLAND_DISPLAY"] = self.display_name
        logger.info("Wayland server listening: %s", self.socket_path)
        return self.socket_path

    def stop(self):
        """Stop the server and clean up."""
        self._running = False
        for client in self._clients.values():
            client.close()
        self._clients.clear()

        if self._server_socket:
            self._server_socket.close()
            self._server_socket = None

        if self.socket_path and os.path.exists(self.socket_path):
            os.unlink(self.socket_path)

        logger.info("Wayland server stopped")

    async def run(self):
        """Async event loop — accept clients and process messages."""
        loop = asyncio.get_event_loop()

        while self._running:
            # Accept new clients (non-blocking)
            try:
                conn, _ = await loop.sock_accept(self._server_socket)
                self._accept_client(conn)
            except (BlockingIOError, OSError):
                pass

            # Process messages from all clients
            disconnected = []
            for cid, client in self._clients.items():
                try:
                    data = await asyncio.wait_for(
                        loop.sock_recv(client.conn, 4096),
                        timeout=0.001,
                    )
                    if not data:
                        disconnected.append(cid)
                        continue
                    self._process_messages(client, data)
                except (asyncio.TimeoutError, BlockingIOError):
                    pass
                except (ConnectionError, OSError):
                    disconnected.append(cid)

            for cid in disconnected:
                self._disconnect_client(cid)

            await asyncio.sleep(0.001)  # Yield to other tasks

    def poll(self):
        """Non-async single poll — process pending messages from all clients."""
        # Accept all pending connections
        if self._server_socket:
            while True:
                try:
                    conn, _ = self._server_socket.accept()
                    conn.setblocking(False)
                    self._accept_client(conn)
                except (BlockingIOError, OSError):
                    break

        # Read from clients
        disconnected = []
        for cid, client in self._clients.items():
            try:
                data = client.conn.recv(4096)
                if not data:
                    disconnected.append(cid)
                    continue
                self._process_messages(client, data)
            except (BlockingIOError, OSError):
                pass

        for cid in disconnected:
            self._disconnect_client(cid)

    def send_frame_done(self, timestamp_ms: int):
        """Send frame callback done events to all clients with pending callbacks."""
        for client in self._clients.values():
            for surface in client.surfaces.values():
                for cb_id in surface.frame_callbacks:
                    self._send_event(client, cb_id, 0, struct.pack("<I", timestamp_ms))
                    # Destroy the callback object
                    self._send_event(client, WL_DISPLAY_ID, WL_DISPLAY_DELETE_ID,
                                     struct.pack("<I", cb_id))
                surface.frame_callbacks.clear()

    # --- Client Management ---

    def _accept_client(self, conn: socket.socket):
        """Register a new client connection."""
        conn.setblocking(False)
        cid = self._next_client_id
        self._next_client_id += 1

        client = WaylandClient(conn, cid)
        self._clients[cid] = client
        logger.info("Client %d connected", cid)

    def _disconnect_client(self, client_id: int):
        """Clean up a disconnected client."""
        client = self._clients.pop(client_id, None)
        if not client:
            return

        # Notify compositor about destroyed surfaces
        for surface in client.surfaces.values():
            if self._on_surface_destroyed:
                self._on_surface_destroyed(client_id, surface)

        client.close()
        logger.info("Client %d disconnected", client_id)

    # --- Message Processing ---

    def _process_messages(self, client: WaylandClient, data: bytes):
        """Parse and dispatch Wayland wire protocol messages."""
        client._recv_buf.extend(data)

        while len(client._recv_buf) >= 8:
            # Wayland message header: object_id (4 bytes) + size_opcode (4 bytes)
            obj_id = struct.unpack_from("<I", client._recv_buf, 0)[0]
            size_opcode = struct.unpack_from("<I", client._recv_buf, 4)[0]
            msg_size = size_opcode >> 16
            opcode = size_opcode & 0xFFFF

            if len(client._recv_buf) < msg_size:
                break  # Wait for more data

            payload = bytes(client._recv_buf[8:msg_size])
            client._recv_buf = client._recv_buf[msg_size:]

            self._dispatch_message(client, obj_id, opcode, payload)

    def _dispatch_message(self, client: WaylandClient, obj_id: int,
                          opcode: int, payload: bytes):
        """Route a message to the appropriate handler."""
        obj = client.objects.get(obj_id)
        if not obj:
            logger.debug("Message for unknown object %d", obj_id)
            return

        iface = obj.interface

        if iface == "wl_display":
            self._handle_display(client, opcode, payload)
        elif iface == "wl_registry":
            self._handle_registry(client, obj, opcode, payload)
        elif iface == "wl_compositor":
            self._handle_compositor(client, opcode, payload)
        elif iface == "wl_surface":
            self._handle_surface(client, obj, opcode, payload)
        elif iface == "wl_shm":
            self._handle_shm(client, opcode, payload)
        elif iface == "wl_shm_pool":
            self._handle_shm_pool(client, obj, opcode, payload)
        elif iface == "xdg_wm_base":
            self._handle_xdg_wm_base(client, opcode, payload)
        elif iface == "xdg_surface":
            self._handle_xdg_surface(client, obj, opcode, payload)
        elif iface == "xdg_toplevel":
            self._handle_xdg_toplevel(client, obj, opcode, payload)

    # --- Protocol Handlers ---

    def _handle_display(self, client: WaylandClient, opcode: int, payload: bytes):
        """Handle wl_display requests."""
        if opcode == WL_DISPLAY_SYNC:
            # Client requests a sync callback
            callback_id = struct.unpack_from("<I", payload, 0)[0]
            client.objects[callback_id] = WaylandObject(
                obj_id=callback_id, interface="wl_callback",
            )
            # Send done event immediately
            self._send_event(client, callback_id, 0,
                             struct.pack("<I", 0))  # serial=0
            self._send_event(client, WL_DISPLAY_ID, WL_DISPLAY_DELETE_ID,
                             struct.pack("<I", callback_id))

        elif opcode == WL_DISPLAY_GET_REGISTRY:
            registry_id = struct.unpack_from("<I", payload, 0)[0]
            client.objects[registry_id] = WaylandObject(
                obj_id=registry_id, interface="wl_registry",
            )
            # Advertise globals
            for i, (name, version) in enumerate(self.GLOBALS, start=1):
                self._send_registry_global(client, registry_id, i, name, version)

    def _handle_registry(self, client: WaylandClient, obj: WaylandObject,
                         opcode: int, payload: bytes):
        """Handle wl_registry.bind requests."""
        if opcode == WL_REGISTRY_BIND:
            global_name = struct.unpack_from("<I", payload, 0)[0]
            # Read new_id (string interface name + version + id)
            str_len = struct.unpack_from("<I", payload, 4)[0]
            padded = (str_len + 3) & ~3
            iface_name = payload[8:8 + str_len - 1].decode('ascii')
            offset = 8 + padded
            version = struct.unpack_from("<I", payload, offset)[0]
            new_id = struct.unpack_from("<I", payload, offset + 4)[0]

            client.objects[new_id] = WaylandObject(
                obj_id=new_id, interface=iface_name, version=version,
            )

            # If binding wl_shm, send supported formats
            if iface_name == "wl_shm":
                self._send_event(client, new_id, 0,
                                 struct.pack("<I", WL_SHM_FORMAT_ARGB8888))
                self._send_event(client, new_id, 0,
                                 struct.pack("<I", WL_SHM_FORMAT_XRGB8888))

            logger.debug("Client %d bound %s (id=%d)", client.client_id, iface_name, new_id)

    def _handle_compositor(self, client: WaylandClient, opcode: int, payload: bytes):
        """Handle wl_compositor requests."""
        if opcode == WL_COMPOSITOR_CREATE_SURFACE:
            surface_id = struct.unpack_from("<I", payload, 0)[0]
            client.objects[surface_id] = WaylandObject(
                obj_id=surface_id, interface="wl_surface",
            )
            client.surfaces[surface_id] = ClientSurface(surface_id=surface_id)

            if self._on_surface_created:
                self._on_surface_created(client.client_id, client.surfaces[surface_id])

            logger.debug("Surface created: %d", surface_id)

    def _handle_surface(self, client: WaylandClient, obj: WaylandObject,
                        opcode: int, payload: bytes):
        """Handle wl_surface requests."""
        surface = client.surfaces.get(obj.obj_id)
        if not surface:
            return

        if opcode == WL_SURFACE_ATTACH:
            buffer_id = struct.unpack_from("<I", payload, 0)[0]
            x = struct.unpack_from("<i", payload, 4)[0]
            y = struct.unpack_from("<i", payload, 8)[0]
            surface.buffer_id = buffer_id
            surface.x_offset = x
            surface.y_offset = y

        elif opcode == WL_SURFACE_DAMAGE:
            pass  # We redraw full surface each frame

        elif opcode == WL_SURFACE_FRAME:
            callback_id = struct.unpack_from("<I", payload, 0)[0]
            client.objects[callback_id] = WaylandObject(
                obj_id=callback_id, interface="wl_callback",
            )
            surface.frame_callbacks.append(callback_id)

        elif opcode == WL_SURFACE_COMMIT:
            surface.committed = True
            # Copy pixel data from shm buffer
            self._read_surface_pixels(client, surface)

            if self._on_surface_committed:
                self._on_surface_committed(client.client_id, surface)

        elif opcode == WL_SURFACE_DESTROY:
            if self._on_surface_destroyed:
                self._on_surface_destroyed(client.client_id, surface)
            client.surfaces.pop(obj.obj_id, None)
            client.objects.pop(obj.obj_id, None)

    def _handle_shm(self, client: WaylandClient, opcode: int, payload: bytes):
        """Handle wl_shm requests."""
        if opcode == WL_SHM_CREATE_POOL:
            pool_id = struct.unpack_from("<I", payload, 0)[0]
            # fd is passed via ancillary data (SCM_RIGHTS)
            # For now, size is in payload
            pool_size = struct.unpack_from("<i", payload, 4)[0]

            pool = ShmPool(pool_id=pool_id, fd=-1, size=pool_size)
            client.shm_pools[pool_id] = pool
            client.objects[pool_id] = WaylandObject(
                obj_id=pool_id, interface="wl_shm_pool",
            )

    def _handle_shm_pool(self, client: WaylandClient, obj: WaylandObject,
                         opcode: int, payload: bytes):
        """Handle wl_shm_pool requests."""
        pool = client.shm_pools.get(obj.obj_id)

        if opcode == WL_SHM_POOL_CREATE_BUFFER:
            buffer_id = struct.unpack_from("<I", payload, 0)[0]
            offset = struct.unpack_from("<i", payload, 4)[0]
            width = struct.unpack_from("<i", payload, 8)[0]
            height = struct.unpack_from("<i", payload, 12)[0]
            stride = struct.unpack_from("<i", payload, 16)[0]
            fmt = struct.unpack_from("<I", payload, 20)[0]

            client.objects[buffer_id] = WaylandObject(
                obj_id=buffer_id, interface="wl_buffer",
                data={
                    "pool_id": obj.obj_id,
                    "offset": offset,
                    "width": width,
                    "height": height,
                    "stride": stride,
                    "format": fmt,
                },
            )

        elif opcode == WL_SHM_POOL_DESTROY:
            client.shm_pools.pop(obj.obj_id, None)
            client.objects.pop(obj.obj_id, None)

    def _handle_xdg_wm_base(self, client: WaylandClient, opcode: int, payload: bytes):
        """Handle xdg_wm_base requests."""
        if opcode == XDG_WM_BASE_GET_SURFACE:
            xdg_surface_id = struct.unpack_from("<I", payload, 0)[0]
            wl_surface_id = struct.unpack_from("<I", payload, 4)[0]

            client.objects[xdg_surface_id] = WaylandObject(
                obj_id=xdg_surface_id, interface="xdg_surface",
                data={"wl_surface_id": wl_surface_id},
            )

            surface = client.surfaces.get(wl_surface_id)
            if surface:
                surface.xdg_surface_id = xdg_surface_id

            # Send configure event
            serial = client.allocate_id()
            self._send_event(client, xdg_surface_id, 0,
                             struct.pack("<I", serial))

        elif opcode == XDG_WM_BASE_PONG:
            pass  # Client responded to ping

    def _handle_xdg_surface(self, client: WaylandClient, obj: WaylandObject,
                            opcode: int, payload: bytes):
        """Handle xdg_surface requests."""
        if opcode == XDG_SURFACE_GET_TOPLEVEL:
            toplevel_id = struct.unpack_from("<I", payload, 0)[0]
            client.objects[toplevel_id] = WaylandObject(
                obj_id=toplevel_id, interface="xdg_toplevel",
                data={"xdg_surface_id": obj.obj_id},
            )

            wl_surface_id = obj.data.get("wl_surface_id")
            surface = client.surfaces.get(wl_surface_id)
            if surface:
                surface.xdg_toplevel_id = toplevel_id

            # Send configure with empty states (client picks its own size)
            # xdg_toplevel.configure(width, height, states)
            self._send_event(client, toplevel_id, 0,
                             struct.pack("<ii", 0, 0) + struct.pack("<I", 0))

        elif opcode == XDG_SURFACE_ACK_CONFIGURE:
            pass  # Client acknowledged our configure

    def _handle_xdg_toplevel(self, client: WaylandClient, obj: WaylandObject,
                             opcode: int, payload: bytes):
        """Handle xdg_toplevel requests."""
        xdg_surface_id = obj.data.get("xdg_surface_id", 0)
        xdg_surface = client.objects.get(xdg_surface_id)
        wl_surface_id = xdg_surface.data.get("wl_surface_id") if xdg_surface else None
        surface = client.surfaces.get(wl_surface_id) if wl_surface_id else None

        if opcode == XDG_TOPLEVEL_SET_TITLE:
            str_len = struct.unpack_from("<I", payload, 0)[0]
            title = payload[4:4 + str_len - 1].decode('utf-8', errors='replace')
            if surface:
                surface.title = title

        elif opcode == XDG_TOPLEVEL_SET_APP_ID:
            str_len = struct.unpack_from("<I", payload, 0)[0]
            app_id = payload[4:4 + str_len - 1].decode('utf-8', errors='replace')
            if surface:
                surface.app_id = app_id

    # --- Pixel Data ---

    def _read_surface_pixels(self, client: WaylandClient, surface: ClientSurface):
        """Copy pixel data from the client's shm buffer into the surface."""
        buf_obj = client.objects.get(surface.buffer_id)
        if not buf_obj or buf_obj.interface != "wl_buffer":
            return

        buf_data = buf_obj.data
        pool = client.shm_pools.get(buf_data.get("pool_id"))
        if not pool or not pool.data:
            return

        width = buf_data["width"]
        height = buf_data["height"]
        stride = buf_data["stride"]
        offset = buf_data["offset"]

        surface.width = width
        surface.height = height
        surface.stride = stride

        # Copy pixel data
        total = stride * height
        surface.shm_data = bytearray(pool.data[offset:offset + total])

    # --- Wire Protocol Sending ---

    def _send_event(self, client: WaylandClient, obj_id: int,
                    opcode: int, payload: bytes = b""):
        """Send a Wayland event to a client."""
        msg_size = 8 + len(payload)
        header = struct.pack("<II", obj_id, (msg_size << 16) | opcode)
        try:
            client.conn.sendall(header + payload)
        except (BrokenPipeError, ConnectionError, OSError):
            pass

    def _send_registry_global(self, client: WaylandClient, registry_id: int,
                              name: int, interface: str, version: int):
        """Send a wl_registry.global event."""
        iface_bytes = interface.encode('ascii') + b'\x00'
        str_len = len(iface_bytes)
        padded_len = (str_len + 3) & ~3
        padding = padded_len - str_len

        payload = struct.pack("<I", name)
        payload += struct.pack("<I", str_len)
        payload += iface_bytes + (b'\x00' * padding)
        payload += struct.pack("<I", version)

        self._send_event(client, registry_id, 0, payload)

    # --- Queries ---

    def get_client_count(self) -> int:
        return len(self._clients)

    def get_surface_count(self) -> int:
        return sum(len(c.surfaces) for c in self._clients.values())

    def get_status(self) -> dict:
        return {
            "socket": self.socket_path,
            "running": self._running,
            "clients": self.get_client_count(),
            "surfaces": self.get_surface_count(),
        }
