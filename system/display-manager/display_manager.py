"""
Claude-OS Display Manager

Daemon that coordinates the compositor, status bar, and keyboard.
Acts as the session manager — launches the compositor, then starts
UI components as Wayland clients.

Boot sequence:
    1. systemd starts display-manager
    2. Display manager starts compositor (Wayland server)
    3. Compositor exports WAYLAND_DISPLAY
    4. Display manager launches: status bar, keyboard, Claude app
"""

import asyncio
import logging
import os
import signal
import subprocess
import sys
import time

logger = logging.getLogger("display-manager")

# Paths to UI components
COMPOSITOR_PATH = "/opt/claude-os/ui/compositor/compositor.py"
STATUSBAR_PATH = "/opt/claude-os/ui/statusbar/statusbar.py"
KEYBOARD_PATH = "/opt/claude-os/ui/keyboard/keyboard.py"
CLAUDE_APP_PATH = "/opt/claude-os/claude-app/launcher.py"


class DisplayManager:
    """
    Manages the display session lifecycle.

    Starts the compositor, then launches UI components as Wayland clients
    once the compositor is ready.
    """

    def __init__(self):
        self._compositor_proc = None
        self._child_procs: list[subprocess.Popen] = []
        self._running = False
        self._wayland_display = "wayland-0"

    async def start(self):
        """Start the display session."""
        self._running = True
        logger.info("Display manager starting")

        # Step 1: Start the compositor
        await self._start_compositor()

        # Step 2: Wait for Wayland socket to appear
        await self._wait_for_compositor()

        # Step 3: Launch UI components
        await self._launch_ui()

        logger.info("Display session is ready")

        # Monitor child processes
        await self._monitor()

    async def _start_compositor(self):
        """Start the Wayland compositor."""
        env = os.environ.copy()
        env["XDG_RUNTIME_DIR"] = "/run/user/0"
        env["DISPLAY_WIDTH"] = os.environ.get("DISPLAY_WIDTH", "1080")
        env["DISPLAY_HEIGHT"] = os.environ.get("DISPLAY_HEIGHT", "2340")

        logger.info("Starting compositor: %s", COMPOSITOR_PATH)
        self._compositor_proc = subprocess.Popen(
            [sys.executable, COMPOSITOR_PATH],
            env=env,
        )

    async def _wait_for_compositor(self, timeout: float = 10.0):
        """Wait for the Wayland socket to become available."""
        runtime_dir = os.environ.get("XDG_RUNTIME_DIR", "/run/user/0")
        socket_path = os.path.join(runtime_dir, self._wayland_display)

        start = time.monotonic()
        while time.monotonic() - start < timeout:
            if os.path.exists(socket_path):
                logger.info("Compositor ready (socket: %s)", socket_path)
                os.environ["WAYLAND_DISPLAY"] = self._wayland_display
                return
            if self._compositor_proc.poll() is not None:
                raise RuntimeError("Compositor exited unexpectedly")
            await asyncio.sleep(0.1)

        # If socket doesn't appear, proceed anyway (stub mode)
        logger.warning("Compositor socket not found after %.1fs, "
                       "proceeding in stub mode", timeout)

    async def _launch_ui(self):
        """Launch UI components as Wayland clients."""
        env = os.environ.copy()
        env["WAYLAND_DISPLAY"] = self._wayland_display
        env["XDG_RUNTIME_DIR"] = os.environ.get("XDG_RUNTIME_DIR", "/run/user/0")

        components = [
            ("status bar", STATUSBAR_PATH),
            ("on-screen keyboard", KEYBOARD_PATH),
            ("Claude app", CLAUDE_APP_PATH),
        ]

        for name, path in components:
            if os.path.exists(path):
                logger.info("Launching %s: %s", name, path)
                proc = subprocess.Popen(
                    [sys.executable, path],
                    env=env,
                )
                self._child_procs.append(proc)
            else:
                logger.warning("Component not found, skipping: %s (%s)", name, path)

    async def _monitor(self):
        """Monitor child processes and restart if they crash."""
        while self._running:
            # Check compositor
            if self._compositor_proc and self._compositor_proc.poll() is not None:
                logger.error("Compositor crashed (exit code: %d)",
                             self._compositor_proc.returncode)
                # Compositor crash = restart entire session
                await self.restart()
                return

            # Check child processes
            for proc in self._child_procs:
                if proc.poll() is not None:
                    logger.warning("Child process %d exited (code: %d)",
                                   proc.pid, proc.returncode)
                    # Could restart individual components here

            await asyncio.sleep(2)

    async def restart(self):
        """Restart the entire display session."""
        logger.info("Restarting display session")
        await self.stop()
        await asyncio.sleep(1)
        await self.start()

    async def stop(self):
        """Stop all display components."""
        self._running = False
        logger.info("Stopping display session")

        # Stop children first
        for proc in self._child_procs:
            if proc.poll() is None:
                proc.terminate()
        for proc in self._child_procs:
            try:
                proc.wait(timeout=5)
            except subprocess.TimeoutExpired:
                proc.kill()
        self._child_procs.clear()

        # Stop compositor
        if self._compositor_proc and self._compositor_proc.poll() is None:
            self._compositor_proc.terminate()
            try:
                self._compositor_proc.wait(timeout=5)
            except subprocess.TimeoutExpired:
                self._compositor_proc.kill()

        logger.info("Display session stopped")


def main():
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    )

    dm = DisplayManager()
    loop = asyncio.new_event_loop()

    def handle_signal(sig):
        logger.info("Received signal %s", sig)
        loop.create_task(dm.stop())
        loop.call_later(1, loop.stop)

    for sig in (signal.SIGTERM, signal.SIGINT):
        loop.add_signal_handler(sig, handle_signal, sig)

    try:
        loop.run_until_complete(dm.start())
    except KeyboardInterrupt:
        loop.run_until_complete(dm.stop())
    finally:
        loop.close()


if __name__ == "__main__":
    main()
