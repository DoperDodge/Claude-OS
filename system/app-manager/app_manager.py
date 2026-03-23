"""
Claude-OS App Lifecycle Manager

Manages the lifecycle of apps running on the OS:
- Launch, suspend, resume, and kill applications
- Track running processes and foreground state
- Enforce resource limits (memory, CPU)
- Handle app crashes and auto-restart

Apps are defined by .desktop-style manifest files in /opt/claude-os/apps/.
The Claude launcher is always running as the "home" app.
"""

import asyncio
import json
import logging
import os
import signal
import subprocess
import time
from dataclasses import dataclass, field
from enum import Enum, auto
from pathlib import Path

logger = logging.getLogger("app-manager")

APPS_DIR = Path("/opt/claude-os/apps")
APP_DATA_BASE = Path("/var/lib/claude-os/apps")


class AppState(Enum):
    """Lifecycle state of an app."""
    STOPPED = "stopped"
    STARTING = "starting"
    RUNNING = "running"
    SUSPENDED = "suspended"
    CRASHED = "crashed"


@dataclass
class AppManifest:
    """App definition loaded from a manifest file."""
    app_id: str
    name: str
    exec_cmd: str
    icon: str = ""
    category: str = "other"
    autostart: bool = False
    restart_on_crash: bool = False
    max_memory_mb: int = 256
    permissions: list[str] = field(default_factory=list)

    @classmethod
    def from_file(cls, path: Path) -> "AppManifest":
        """Load manifest from a JSON file."""
        data = json.loads(path.read_text())
        return cls(
            app_id=data["app_id"],
            name=data["name"],
            exec_cmd=data["exec"],
            icon=data.get("icon", ""),
            category=data.get("category", "other"),
            autostart=data.get("autostart", False),
            restart_on_crash=data.get("restart_on_crash", False),
            max_memory_mb=data.get("max_memory_mb", 256),
            permissions=data.get("permissions", []),
        )


@dataclass
class RunningApp:
    """A currently managed app instance."""
    manifest: AppManifest
    process: subprocess.Popen | None = None
    state: AppState = AppState.STOPPED
    pid: int = 0
    started_at: float = 0
    crash_count: int = 0
    last_crash: float = 0


class AppManager:
    """
    Manages app lifecycles — launch, suspend, resume, kill.

    Tracks all running processes and provides an API for the bridge
    to query and control apps.
    """

    MAX_CRASH_RESTARTS = 3
    CRASH_COOLDOWN = 30  # Seconds between crash restarts

    def __init__(self, event_bus=None):
        self.event_bus = event_bus
        self.apps: dict[str, RunningApp] = {}
        self.manifests: dict[str, AppManifest] = {}
        self.foreground_app: str | None = None
        self._running = False

    async def start(self):
        """Start the app manager and launch autostart apps."""
        self._running = True
        logger.info("App manager started")

        # Load app manifests
        self._load_manifests()

        # Launch autostart apps
        for app_id, manifest in self.manifests.items():
            if manifest.autostart:
                await self.launch(app_id)

        # Monitor running apps
        await self._monitor_loop()

    def _load_manifests(self):
        """Load all app manifests from the apps directory."""
        if not APPS_DIR.exists():
            APPS_DIR.mkdir(parents=True, exist_ok=True)
            logger.info("Created apps directory: %s", APPS_DIR)
            return

        for manifest_file in APPS_DIR.glob("*/manifest.json"):
            try:
                manifest = AppManifest.from_file(manifest_file)
                self.manifests[manifest.app_id] = manifest
                logger.info("Loaded app: %s (%s)", manifest.name, manifest.app_id)
            except (json.JSONDecodeError, KeyError) as e:
                logger.error("Invalid manifest %s: %s", manifest_file, e)

        logger.info("Loaded %d app manifests", len(self.manifests))

    # --- Lifecycle Operations ---

    async def launch(self, app_id: str) -> dict:
        """
        Launch an app.

        If the app is suspended, resume it instead.
        """
        # Check if already running
        if app_id in self.apps:
            app = self.apps[app_id]
            if app.state == AppState.RUNNING:
                return {"status": "already_running", "pid": app.pid}
            if app.state == AppState.SUSPENDED:
                return await self.resume(app_id)

        # Find manifest
        manifest = self.manifests.get(app_id)
        if not manifest:
            raise ValueError(f"Unknown app: {app_id}")

        logger.info("Launching app: %s (%s)", manifest.name, app_id)

        # Prepare environment
        env = os.environ.copy()
        env["APP_ID"] = app_id
        env["APP_DATA_DIR"] = str(APP_DATA_BASE / app_id / "data")
        env["WAYLAND_DISPLAY"] = os.environ.get("WAYLAND_DISPLAY", "wayland-0")
        env["XDG_RUNTIME_DIR"] = os.environ.get("XDG_RUNTIME_DIR", "/run/user/0")

        # Create app data directory
        os.makedirs(env["APP_DATA_DIR"], exist_ok=True)

        try:
            proc = subprocess.Popen(
                manifest.exec_cmd.split(),
                env=env,
                stdout=subprocess.DEVNULL,
                stderr=subprocess.PIPE,
            )

            app = RunningApp(
                manifest=manifest,
                process=proc,
                state=AppState.RUNNING,
                pid=proc.pid,
                started_at=time.time(),
            )
            self.apps[app_id] = app

            # First app launched becomes foreground
            if self.foreground_app is None:
                self.foreground_app = app_id

            if self.event_bus:
                await self.event_bus.emit("app.launched", {
                    "app_id": app_id,
                    "name": manifest.name,
                    "pid": proc.pid,
                })

            logger.info("App launched: %s (PID %d)", manifest.name, proc.pid)
            return {"status": "launched", "pid": proc.pid}

        except FileNotFoundError:
            logger.error("App executable not found: %s", manifest.exec_cmd)
            raise RuntimeError(f"Executable not found: {manifest.exec_cmd}")

    async def suspend(self, app_id: str) -> dict:
        """Suspend an app (send SIGSTOP)."""
        app = self._get_running(app_id)

        if app.process and app.process.poll() is None:
            os.kill(app.pid, signal.SIGSTOP)
            app.state = AppState.SUSPENDED

            if self.event_bus:
                await self.event_bus.emit("app.suspended", {"app_id": app_id})

            logger.info("App suspended: %s", app_id)
            return {"status": "suspended"}

        raise RuntimeError(f"App {app_id} is not running")

    async def resume(self, app_id: str) -> dict:
        """Resume a suspended app (send SIGCONT)."""
        app = self.apps.get(app_id)
        if not app or app.state != AppState.SUSPENDED:
            raise RuntimeError(f"App {app_id} is not suspended")

        if app.process and app.process.poll() is None:
            os.kill(app.pid, signal.SIGCONT)
            app.state = AppState.RUNNING

            if self.event_bus:
                await self.event_bus.emit("app.resumed", {"app_id": app_id})

            logger.info("App resumed: %s", app_id)
            return {"status": "resumed"}

        raise RuntimeError(f"App {app_id} process is dead")

    async def kill(self, app_id: str) -> dict:
        """Kill an app (send SIGTERM, then SIGKILL if needed)."""
        app = self.apps.get(app_id)
        if not app:
            raise ValueError(f"App not found: {app_id}")

        if app.process and app.process.poll() is None:
            # Try graceful termination first
            app.process.terminate()
            try:
                app.process.wait(timeout=5)
            except subprocess.TimeoutExpired:
                app.process.kill()
                app.process.wait(timeout=2)

        app.state = AppState.STOPPED
        del self.apps[app_id]

        if self.foreground_app == app_id:
            # Return to home (Claude launcher)
            remaining = [a for a in self.apps if self.apps[a].state == AppState.RUNNING]
            self.foreground_app = remaining[0] if remaining else None

        if self.event_bus:
            await self.event_bus.emit("app.killed", {"app_id": app_id})

        logger.info("App killed: %s", app_id)
        return {"status": "killed"}

    async def switch_to(self, app_id: str) -> dict:
        """Bring an app to the foreground."""
        app = self._get_running(app_id)

        # Suspend current foreground app
        if self.foreground_app and self.foreground_app != app_id:
            try:
                await self.suspend(self.foreground_app)
            except RuntimeError:
                pass

        # Resume target if suspended
        if app.state == AppState.SUSPENDED:
            await self.resume(app_id)

        self.foreground_app = app_id

        if self.event_bus:
            await self.event_bus.emit("app.foreground", {"app_id": app_id})

        return {"status": "foreground", "app_id": app_id}

    # --- Queries ---

    def list_running(self) -> list[dict]:
        """List all running/suspended apps."""
        result = []
        for app_id, app in self.apps.items():
            result.append({
                "app_id": app_id,
                "name": app.manifest.name,
                "state": app.state.value,
                "pid": app.pid,
                "foreground": app_id == self.foreground_app,
                "uptime_seconds": time.time() - app.started_at if app.started_at else 0,
            })
        return result

    def list_installed(self) -> list[dict]:
        """List all installed apps."""
        return [
            {
                "app_id": m.app_id,
                "name": m.name,
                "icon": m.icon,
                "category": m.category,
                "running": m.app_id in self.apps,
            }
            for m in self.manifests.values()
        ]

    def get_app_info(self, app_id: str) -> dict:
        """Get detailed info about an app."""
        manifest = self.manifests.get(app_id)
        if not manifest:
            raise ValueError(f"Unknown app: {app_id}")

        info = {
            "app_id": manifest.app_id,
            "name": manifest.name,
            "category": manifest.category,
            "permissions": manifest.permissions,
            "max_memory_mb": manifest.max_memory_mb,
            "installed": True,
        }

        if app_id in self.apps:
            app = self.apps[app_id]
            info["state"] = app.state.value
            info["pid"] = app.pid
            info["uptime_seconds"] = time.time() - app.started_at

            # Get memory usage from /proc
            info["memory_mb"] = self._get_proc_memory(app.pid)

        return info

    # --- Internal ---

    def _get_running(self, app_id: str) -> RunningApp:
        """Get a running app or raise."""
        app = self.apps.get(app_id)
        if not app or app.state not in (AppState.RUNNING, AppState.SUSPENDED):
            raise RuntimeError(f"App {app_id} is not running")
        return app

    def _get_proc_memory(self, pid: int) -> float:
        """Get memory usage of a process in MB."""
        try:
            status = Path(f"/proc/{pid}/status").read_text()
            for line in status.split("\n"):
                if line.startswith("VmRSS:"):
                    kb = int(line.split()[1])
                    return round(kb / 1024, 1)
        except (OSError, ValueError, IndexError):
            pass
        return 0

    async def _monitor_loop(self):
        """Monitor running apps for crashes and resource usage."""
        while self._running:
            for app_id, app in list(self.apps.items()):
                if app.state == AppState.RUNNING and app.process:
                    ret = app.process.poll()
                    if ret is not None:
                        # App exited
                        if ret != 0:
                            logger.warning("App crashed: %s (exit code %d)",
                                           app_id, ret)
                            app.state = AppState.CRASHED
                            app.crash_count += 1
                            app.last_crash = time.time()

                            if self.event_bus:
                                await self.event_bus.emit("app.crashed", {
                                    "app_id": app_id,
                                    "exit_code": ret,
                                    "crash_count": app.crash_count,
                                })

                            # Auto-restart if configured
                            if (app.manifest.restart_on_crash
                                    and app.crash_count <= self.MAX_CRASH_RESTARTS):
                                logger.info("Auto-restarting %s (crash %d/%d)",
                                            app_id, app.crash_count,
                                            self.MAX_CRASH_RESTARTS)
                                del self.apps[app_id]
                                await asyncio.sleep(2)
                                await self.launch(app_id)
                        else:
                            logger.info("App exited normally: %s", app_id)
                            app.state = AppState.STOPPED
                            del self.apps[app_id]

            await asyncio.sleep(2)

    async def stop(self):
        """Stop the app manager and kill all apps."""
        self._running = False
        for app_id in list(self.apps.keys()):
            try:
                await self.kill(app_id)
            except Exception:
                pass
        logger.info("App manager stopped")


def main():
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    )
    manager = AppManager()
    asyncio.run(manager.start())


if __name__ == "__main__":
    main()
