"""
Tests for the minimal Wayland server.
"""

import os
import socket
import struct
import tempfile
import pytest
from wayland_server import (
    WaylandServer, WaylandClient, WaylandObject, ClientSurface,
    WL_DISPLAY_ID, WL_DISPLAY_SYNC, WL_DISPLAY_GET_REGISTRY,
)


@pytest.fixture
def server(tmp_path):
    """Create a Wayland server with a temp socket."""
    os.environ["XDG_RUNTIME_DIR"] = str(tmp_path)
    srv = WaylandServer(display_name="test-wayland-0")
    srv.start()
    yield srv
    srv.stop()


@pytest.fixture
def client_conn(server):
    """Connect a client socket to the server."""
    conn = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
    conn.connect(server.socket_path)
    conn.setblocking(False)
    yield conn
    conn.close()


class TestServerLifecycle:
    """Test server start/stop."""

    def test_start_creates_socket(self, server):
        assert os.path.exists(server.socket_path)

    def test_stop_removes_socket(self, tmp_path):
        os.environ["XDG_RUNTIME_DIR"] = str(tmp_path)
        srv = WaylandServer(display_name="test-stop-0")
        path = srv.start()
        assert os.path.exists(path)
        srv.stop()
        assert not os.path.exists(path)

    def test_sets_wayland_display_env(self, server):
        assert os.environ.get("WAYLAND_DISPLAY") == "test-wayland-0"

    def test_get_status(self, server):
        status = server.get_status()
        assert status["running"] is True
        assert "socket" in status


class TestClientConnection:
    """Test client connect/disconnect."""

    def test_accept_client(self, server, client_conn):
        server.poll()
        assert server.get_client_count() == 1

    def test_multiple_clients(self, server):
        conns = []
        for _ in range(3):
            c = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
            c.connect(server.socket_path)
            conns.append(c)

        server.poll()
        assert server.get_client_count() == 3

        for c in conns:
            c.close()

    def test_client_disconnect(self, server, client_conn):
        server.poll()
        assert server.get_client_count() == 1

        client_conn.close()
        server.poll()
        assert server.get_client_count() == 0


class TestWaylandProtocol:
    """Test Wayland wire protocol message handling."""

    def _send_msg(self, conn, obj_id, opcode, payload=b""):
        msg_size = 8 + len(payload)
        header = struct.pack("<II", obj_id, (msg_size << 16) | opcode)
        conn.sendall(header + payload)

    def _recv_events(self, conn, max_bytes=4096):
        """Read available events (non-blocking)."""
        import time
        time.sleep(0.05)  # Give server time to process
        try:
            return conn.recv(max_bytes)
        except BlockingIOError:
            return b""

    def test_sync_callback(self, server, client_conn):
        """wl_display.sync should return a callback done event."""
        callback_id = 2
        self._send_msg(client_conn, WL_DISPLAY_ID, WL_DISPLAY_SYNC,
                       struct.pack("<I", callback_id))

        server.poll()
        data = self._recv_events(client_conn)
        assert len(data) > 0  # Got some response

    def test_get_registry(self, server, client_conn):
        """wl_display.get_registry should return global advertisements."""
        registry_id = 2
        self._send_msg(client_conn, WL_DISPLAY_ID, WL_DISPLAY_GET_REGISTRY,
                       struct.pack("<I", registry_id))

        server.poll()
        data = self._recv_events(client_conn)

        # Should have received registry.global events for our globals
        assert len(data) > 0
        # Check that wl_compositor, wl_shm, xdg_wm_base are advertised
        assert b"wl_compositor" in data
        assert b"wl_shm" in data
        assert b"xdg_wm_base" in data


class TestWaylandObjects:
    """Test Wayland protocol object data structures."""

    def test_wayland_object(self):
        obj = WaylandObject(obj_id=5, interface="wl_surface")
        assert obj.obj_id == 5
        assert obj.interface == "wl_surface"
        assert obj.version == 1

    def test_client_surface(self):
        surface = ClientSurface(surface_id=10)
        assert surface.surface_id == 10
        assert surface.committed is False
        assert surface.app_id == ""

    def test_wayland_client(self):
        mock_conn = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
        try:
            client = WaylandClient(mock_conn, client_id=1)
            assert WL_DISPLAY_ID in client.objects
            assert client.objects[WL_DISPLAY_ID].interface == "wl_display"

            new_id = client.allocate_id()
            assert new_id > 0xFF000000
        finally:
            mock_conn.close()


class TestSurfaceCallbacks:
    """Test surface creation/commit/destroy callbacks."""

    def test_surface_created_callback(self, server, client_conn):
        created = []
        server.set_callbacks(on_created=lambda cid, s: created.append(s))

        # Get registry and bind wl_compositor
        registry_id = 2
        self._send_msg(client_conn, WL_DISPLAY_ID, WL_DISPLAY_GET_REGISTRY,
                       struct.pack("<I", registry_id))
        server.poll()
        self._recv_events(client_conn)

        # Bind wl_compositor (global name=1)
        compositor_id = 3
        iface = b"wl_compositor\x00"
        padded_len = (len(iface) + 3) & ~3
        padding = padded_len - len(iface)
        bind_payload = struct.pack("<I", 1)  # global name
        bind_payload += struct.pack("<I", len(iface))
        bind_payload += iface + (b'\x00' * padding)
        bind_payload += struct.pack("<II", 5, compositor_id)  # version, new_id

        self._send_msg(client_conn, registry_id, 0, bind_payload)
        server.poll()

        # Create surface
        surface_id = 4
        self._send_msg(client_conn, compositor_id, 0,
                       struct.pack("<I", surface_id))
        server.poll()

        assert len(created) == 1
        assert created[0].surface_id == surface_id

    def _send_msg(self, conn, obj_id, opcode, payload=b""):
        msg_size = 8 + len(payload)
        header = struct.pack("<II", obj_id, (msg_size << 16) | opcode)
        conn.sendall(header + payload)

    def _recv_events(self, conn):
        import time
        time.sleep(0.05)
        try:
            return conn.recv(4096)
        except BlockingIOError:
            return b""
