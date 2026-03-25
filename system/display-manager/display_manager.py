"""
Claude-OS Display Manager

Daemon that coordinates the compositor, status bar, and keyboard.
Acts as the session manager — launches the compositor, then starts
UI components once the compositor is ready.

Boot sequence:
    1. systemd starts display-manager
    2. Display manager detects display backend (DRM/fbdev or stub)
    3. Display manager ensures XDG_RUNTIME_DIR exists
    4. Display manager starts compositor process
    5. Compositor initializes display (fbdev/DRM) and creates IPC socket
    6. Compositor creates wayland-0 marker file
    7. Display manager detects marker and launches UI components

Display backends:
    - fbdev: Framebuffer rendering via /dev/fb0 (QEMU --gui with virtio-gpu)
    - drm: Direct rendering via /dev/dri/card0 (alternative path)
    - stub: No display, services run but nothing is drawn (text mode)
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

    Starts the compositor, then launches UI components once
    the compositor is ready.
    """

    def __init__(self):
        self._compositor_proc = None
        self._child_procs: list[subprocess.Popen] = []
        self._running = False
        self._wayland_display = "wayland-0"
        self._display_backend = "stub"  # "drm", "fbdev", or "stub"

    @staticmethod
    def detect_display_backend() -> str:
        """Detect available display backend."""
        # Check for fbdev device (available with DRM_FBDEV_EMULATION)
        if os.path.exists("/dev/fb0"):
            logger.info("Framebuffer device found: /dev/fb0")
            return "fbdev"

        # Check for DRM device (present when QEMU has virtio-gpu)
        drm_devices = ["/dev/dri/card0", "/dev/dri/card1"]
        for dev in drm_devices:
            if os.path.exists(dev):
                logger.info("DRM device found: %s", dev)
                return "drm"

        logger.info("No display device found, using stub backend")
        return "stub"

    async def start(self):
        """Start the display session."""
        self._running = True
        logger.info("Display manager starting")

        # Step 0: Detect display backend
        self._display_backend = self.detect_display_backend()
        logger.info("Display backend: %s", self._display_backend)

        # Step 1: Ensure runtime directory exists
        runtime_dir = os.environ.get("XDG_RUNTIME_DIR", "/run/user/0")
        os.makedirs(runtime_dir, exist_ok=True)

        # Step 2: Start the compositor
        await self._start_compositor()

        # Step 3: Wait for compositor to be ready
        await self._wait_for_compositor()

        # Step 4: Launch UI components
        await self._launch_ui()

        logger.info("Display session is ready (backend=%s)", self._display_backend)

        # Monitor child processes
        await self._monitor()

    async def _start_compositor(self):
        """Start the compositor process."""
        env = os.environ.copy()
        env["XDG_RUNTIME_DIR"] = os.environ.get("XDG_RUNTIME_DIR", "/run/user/0")
        env["DISPLAY_WIDTH"] = os.environ.get("DISPLAY_WIDTH", "1080")
        env["DISPLAY_HEIGHT"] = os.environ.get("DISPLAY_HEIGHT", "2340")
        env["CLAUDE_OS_DISPLAY_BACKEND"] = self._display_backend

        logger.info("Starting compositor: %s (backend=%s)",
                     COMPOSITOR_PATH, self._display_backend)
        self._compositor_proc = subprocess.Popen(
            [sys.executable, COMPOSITOR_PATH],
            env=env,
        )

    async def _wait_for_compositor(self, timeout: float = 15.0):
        """Wait for the compositor to become ready."""
        runtime_dir = os.environ.get("XDG_RUNTIME_DIR", "/run/user/0")
        socket_path = os.path.join(runtime_dir, self._wayland_display)
        ipc_path = os.path.join(runtime_dir, "claude-compositor")

        start = time.monotonic()
        while time.monotonic() - start < timeout:
            # Check for either the wayland-0 marker or the IPC socket
            if os.path.exists(socket_path) or os.path.exists(ipc_path):
                logger.info("Compositor ready (marker found)")
                os.environ["WAYLAND_DISPLAY"] = self._wayland_display
                return
            if self._compositor_proc.poll() is not None:
                raise RuntimeError("Compositor exited unexpectedly (code=%d)" %
                                   self._compositor_proc.returncode)
            await asyncio.sleep(0.1)

        # If marker doesn't appear, proceed anyway (stub mode)
        logger.warning("Compositor marker not found after %.1fs, "
                       "proceeding in stub mode", timeout)

    async def _launch_ui(self):
        """Launch UI components."""
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
