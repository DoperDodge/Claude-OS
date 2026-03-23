"""
Lightweight async HTTP/WebSocket server for the Bridge API.

Uses aiohttp. Routes are registered by each service module.
Also serves a WebSocket endpoint for real-time event streaming.
"""

import asyncio
import json
import logging
from typing import Callable

logger = logging.getLogger("bridge.http")


class Route:
    """A registered API route."""

    def __init__(self, method: str, path: str, handler: Callable,
                 permission: str = None):
        self.method = method
        self.path = path
        self.handler = handler
        self.permission = permission


class HTTPServer:
    """Async HTTP server with WebSocket support."""

    def __init__(self, bridge):
        self.bridge = bridge
        self.routes: list[Route] = []
        self._ws_clients: list = []
        self._server = None

    def add_route(self, method: str, path: str, handler: Callable,
                  permission: str = None):
        """Register an API route."""
        self.routes.append(Route(method, path, handler, permission))

    def register_routes(self):
        """Register all service routes."""
        # WiFi routes
        wifi = self.bridge.wifi
        self.add_route("GET", "/api/wifi/scan", wifi.handle_scan)
        self.add_route("POST", "/api/wifi/connect", wifi.handle_connect,
                       permission="wifi.connect")
        self.add_route("POST", "/api/wifi/disconnect", wifi.handle_disconnect,
                       permission="wifi.disconnect")
        self.add_route("GET", "/api/wifi/status", wifi.handle_status)
        self.add_route("GET", "/api/wifi/saved", wifi.handle_saved)
        self.add_route("POST", "/api/wifi/forget", wifi.handle_forget,
                       permission="wifi.modify")

        # System info routes
        sys_svc = self.bridge.system
        self.add_route("GET", "/api/system/info", sys_svc.handle_info)
        self.add_route("GET", "/api/system/battery", sys_svc.handle_battery)
        self.add_route("POST", "/api/system/brightness", sys_svc.handle_set_brightness,
                       permission="system.display")

        # Power routes
        power = self.bridge.power
        self.add_route("POST", "/api/power/shutdown", power.handle_shutdown,
                       permission="power.shutdown")
        self.add_route("POST", "/api/power/reboot", power.handle_reboot,
                       permission="power.reboot")
        self.add_route("POST", "/api/power/suspend", power.handle_suspend,
                       permission="power.suspend")

        # Audio routes
        audio = self.bridge.audio
        self.add_route("GET", "/api/audio/volume", audio.handle_get_volume)
        self.add_route("POST", "/api/audio/volume", audio.handle_set_volume,
                       permission="audio.volume")
        self.add_route("POST", "/api/audio/mute", audio.handle_mute,
                       permission="audio.volume")

        # Storage routes
        storage = self.bridge.storage
        self.add_route("GET", "/api/storage/usage", storage.handle_usage)
        self.add_route("GET", "/api/storage/dirs", storage.handle_user_dirs)
        self.add_route("POST", "/api/storage/list", storage.handle_list_files,
                       permission="files.read")
        self.add_route("POST", "/api/storage/read", storage.handle_read_file,
                       permission="files.read")
        self.add_route("POST", "/api/storage/write", storage.handle_write_file,
                       permission="files.write")
        self.add_route("POST", "/api/storage/delete", storage.handle_delete_file,
                       permission="files.write")

        # App lifecycle routes
        apps = self.bridge.apps
        self.add_route("GET", "/api/apps/running", apps.handle_list_running)
        self.add_route("GET", "/api/apps/installed", apps.handle_list_installed)
        self.add_route("POST", "/api/apps/info", apps.handle_app_info)
        self.add_route("POST", "/api/apps/launch", apps.handle_launch,
                       permission="apps.launch")
        self.add_route("POST", "/api/apps/kill", apps.handle_kill,
                       permission="apps.kill")
        self.add_route("POST", "/api/apps/suspend", apps.handle_suspend,
                       permission="apps.manage")
        self.add_route("POST", "/api/apps/resume", apps.handle_resume,
                       permission="apps.manage")
        self.add_route("POST", "/api/apps/switch", apps.handle_switch)

        # Notification routes
        notifs = self.bridge.notifications
        self.add_route("POST", "/api/notifications/post", notifs.handle_post)
        self.add_route("GET", "/api/notifications/all", notifs.handle_get_all)
        self.add_route("GET", "/api/notifications/unread", notifs.handle_get_unread)
        self.add_route("GET", "/api/notifications/summary", notifs.handle_summary)
        self.add_route("POST", "/api/notifications/read", notifs.handle_mark_read)
        self.add_route("POST", "/api/notifications/dismiss", notifs.handle_dismiss)
        self.add_route("POST", "/api/notifications/dismiss-all", notifs.handle_dismiss_all)
        self.add_route("POST", "/api/notifications/dnd", notifs.handle_dnd)

        # Meta routes
        self.add_route("GET", "/api/health", self._handle_health)
        self.add_route("GET", "/api/permissions", self._handle_permissions)

        logger.info("Registered %d API routes", len(self.routes))

    async def start(self, host: str, port: int):
        """Start the HTTP server."""
        try:
            from aiohttp import web

            app = web.Application()

            # Register routes with aiohttp
            for route in self.routes:
                aiohttp_handler = self._wrap_handler(route)
                app.router.add_route(route.method, route.path, aiohttp_handler)

            # WebSocket endpoint
            app.router.add_get("/api/events", self._handle_websocket)

            runner = web.AppRunner(app)
            await runner.setup()
            site = web.TCPSite(runner, host, port)
            await site.start()
            self._server = runner

        except ImportError:
            logger.warning("aiohttp not available, starting basic HTTP server")
            await self._start_basic_server(host, port)

    async def stop(self):
        """Stop the HTTP server."""
        if self._server:
            await self._server.cleanup()

    def _wrap_handler(self, route: Route):
        """Wrap a handler with permission checking and error handling."""
        async def wrapped(request):
            from aiohttp import web

            # Check permission if required
            if route.permission:
                allowed = self.bridge.permissions.check(route.permission)
                if not allowed:
                    return web.json_response(
                        {"error": "Permission denied",
                         "permission": route.permission,
                         "message": f"Action requires '{route.permission}' permission. "
                                    "Grant it in Claude-OS settings."},
                        status=403,
                    )

            try:
                # Parse body for POST requests
                body = {}
                if request.method == "POST" and request.content_length:
                    body = await request.json()

                result = await route.handler(body)
                return web.json_response({"ok": True, "data": result})

            except Exception as e:
                logger.error("Handler error on %s %s: %s",
                             route.method, route.path, e)
                return web.json_response(
                    {"ok": False, "error": str(e)}, status=500
                )

        return wrapped

    async def _handle_websocket(self, request):
        """WebSocket endpoint for real-time event streaming."""
        from aiohttp import web

        ws = web.WebSocketResponse()
        await ws.prepare(request)
        self._ws_clients.append(ws)

        logger.info("WebSocket client connected (%d total)", len(self._ws_clients))

        # Subscribe to all events and forward to this client
        async def forward_event(event_type, data):
            if not ws.closed:
                await ws.send_json({"event": event_type, "data": data})

        self.bridge.event_bus.subscribe("*", forward_event)

        try:
            async for msg in ws:
                pass  # Client messages not needed yet
        finally:
            self._ws_clients.remove(ws)
            logger.info("WebSocket client disconnected (%d remaining)",
                        len(self._ws_clients))

        return ws

    async def _handle_health(self, body: dict) -> dict:
        """Health check endpoint."""
        return {
            "status": "ok",
            "service": "claude-os-bridge",
            "version": "0.1.0",
        }

    async def _handle_permissions(self, body: dict) -> dict:
        """List all permissions and their status."""
        return self.bridge.permissions.list_all()

    async def _start_basic_server(self, host: str, port: int):
        """Fallback basic HTTP server using asyncio streams."""

        async def handle_client(reader, writer):
            try:
                request_line = await reader.readline()
                headers = {}
                while True:
                    line = await reader.readline()
                    if line == b"\r\n" or not line:
                        break
                    key, _, value = line.decode().partition(":")
                    headers[key.strip().lower()] = value.strip()

                parts = request_line.decode().split()
                if len(parts) < 2:
                    return

                method, path = parts[0], parts[1]

                # Read body if present
                body = {}
                content_length = int(headers.get("content-length", 0))
                if content_length > 0:
                    raw = await reader.read(content_length)
                    body = json.loads(raw.decode())

                # Find matching route
                result = None
                for route in self.routes:
                    if route.method == method and route.path == path:
                        if route.permission:
                            if not self.bridge.permissions.check(route.permission):
                                result = json.dumps({"error": "Permission denied"})
                                status = "403 Forbidden"
                                break
                        result = await route.handler(body)
                        result = json.dumps({"ok": True, "data": result})
                        status = "200 OK"
                        break

                if result is None:
                    result = json.dumps({"error": "Not found"})
                    status = "404 Not Found"

                response = (
                    f"HTTP/1.1 {status}\r\n"
                    f"Content-Type: application/json\r\n"
                    f"Content-Length: {len(result)}\r\n"
                    f"Connection: close\r\n"
                    f"\r\n"
                    f"{result}"
                )
                writer.write(response.encode())
                await writer.drain()
            finally:
                writer.close()

        server = await asyncio.start_server(handle_client, host, port)
        logger.info("Basic HTTP server started on %s:%d", host, port)
        asyncio.create_task(server.serve_forever())
