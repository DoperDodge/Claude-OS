"""
D-Bus service interface for the WiFi Manager.

Exposes WiFi operations over D-Bus so that other Claude-OS components
(the Claude bridge, status bar, settings UI) can interact with WiFi.

Bus name: org.claude_os.wifi
Object path: /org/claude_os/wifi
Interface: org.claude_os.wifi.Manager
"""

import asyncio
import json
import logging

logger = logging.getLogger("wifi-manager.dbus")

# D-Bus interface XML for introspection
INTERFACE_XML = """
<node>
  <interface name="org.claude_os.wifi.Manager">
    <method name="Scan">
      <arg direction="out" type="s" name="networks_json"/>
    </method>
    <method name="Connect">
      <arg direction="in" type="s" name="ssid"/>
      <arg direction="in" type="s" name="password"/>
      <arg direction="in" type="s" name="security"/>
      <arg direction="out" type="b" name="success"/>
    </method>
    <method name="Disconnect">
      <arg direction="out" type="b" name="success"/>
    </method>
    <method name="GetStatus">
      <arg direction="out" type="s" name="status_json"/>
    </method>
    <method name="GetSavedNetworks">
      <arg direction="out" type="s" name="networks_json"/>
    </method>
    <method name="ForgetNetwork">
      <arg direction="in" type="s" name="ssid"/>
      <arg direction="out" type="b" name="success"/>
    </method>
    <signal name="ConnectionChanged">
      <arg type="s" name="status_json"/>
    </signal>
  </interface>
</node>
"""

BUS_NAME = "org.claude_os.wifi"
OBJECT_PATH = "/org/claude_os/wifi"


class WiFiDBusService:
    """
    D-Bus service that wraps the WiFi manager.

    Uses dbus-next for async D-Bus support. Falls back to a simple
    Unix socket server if dbus-next is not available.
    """

    def __init__(self, manager):
        self.manager = manager
        self._bus = None

    async def start(self):
        """Start the D-Bus service or fall back to socket server."""
        try:
            from dbus_next.aio import MessageBus
            from dbus_next.service import ServiceInterface, method, signal
            from dbus_next import Variant

            class WiFiInterface(ServiceInterface):
                def __init__(self, mgr):
                    super().__init__("org.claude_os.wifi.Manager")
                    self._mgr = mgr

                @method()
                async def Scan(self) -> "s":
                    networks = await self._mgr.scan()
                    return json.dumps(networks)

                @method()
                async def Connect(self, ssid: "s", password: "s",
                                  security: "s") -> "b":
                    return await self._mgr.connect(ssid, password, security)

                @method()
                async def Disconnect(self) -> "b":
                    return await self._mgr.disconnect()

                @method()
                async def GetStatus(self) -> "s":
                    return json.dumps(self._mgr.get_status())

                @method()
                async def GetSavedNetworks(self) -> "s":
                    return json.dumps(self._mgr.get_saved_networks())

                @method()
                async def ForgetNetwork(self, ssid: "s") -> "b":
                    return self._mgr.forget_network(ssid)

                @signal()
                def ConnectionChanged(self, status_json: "s"):
                    return status_json

            self._bus = await MessageBus(bus_type=1).connect()  # System bus
            interface = WiFiInterface(self.manager)
            self._bus.export(OBJECT_PATH, interface)
            await self._bus.request_name(BUS_NAME)
            logger.info("D-Bus service started: %s", BUS_NAME)

        except ImportError:
            logger.warning("dbus-next not available, starting socket server")
            await self._start_socket_server()

    async def _start_socket_server(self):
        """
        Fallback: simple Unix socket JSON-RPC server.

        Listens on /run/claude-os/wifi.sock for JSON commands.
        """
        sock_path = "/run/claude-os/wifi.sock"

        import os
        os.makedirs(os.path.dirname(sock_path), exist_ok=True)
        if os.path.exists(sock_path):
            os.unlink(sock_path)

        async def handle_client(reader, writer):
            try:
                data = await reader.read(4096)
                request = json.loads(data.decode())
                response = await self._handle_request(request)
                writer.write(json.dumps(response).encode())
                await writer.drain()
            except Exception as e:
                error = {"error": str(e)}
                writer.write(json.dumps(error).encode())
                await writer.drain()
            finally:
                writer.close()

        server = await asyncio.start_unix_server(handle_client, path=sock_path)
        os.chmod(sock_path, 0o660)
        logger.info("Socket server started: %s", sock_path)

        asyncio.create_task(server.serve_forever())

    async def _handle_request(self, request: dict) -> dict:
        """Handle a JSON-RPC style request from the socket server."""
        method = request.get("method", "")
        params = request.get("params", {})

        if method == "scan":
            networks = await self.manager.scan()
            return {"result": networks}

        elif method == "connect":
            success = await self.manager.connect(
                params["ssid"],
                params.get("password"),
                params.get("security", "wpa2"),
            )
            return {"result": success}

        elif method == "disconnect":
            success = await self.manager.disconnect()
            return {"result": success}

        elif method == "status":
            return {"result": self.manager.get_status()}

        elif method == "saved_networks":
            return {"result": self.manager.get_saved_networks()}

        elif method == "forget":
            success = self.manager.forget_network(params["ssid"])
            return {"result": success}

        else:
            return {"error": f"Unknown method: {method}"}
