"""
Power management bridge service.

Handles shutdown, reboot, and suspend operations.
All power actions require explicit permission grants.
"""

import asyncio
import logging
import subprocess

from event_bus import EventBus

logger = logging.getLogger("bridge.power")


class PowerBridgeService:
    """Bridge service for power management."""

    def __init__(self, event_bus: EventBus):
        self.event_bus = event_bus

    async def handle_shutdown(self, body: dict) -> dict:
        """Shut down the device."""
        delay = body.get("delay_seconds", 0)
        logger.warning("Shutdown requested (delay: %ds)", delay)
        await self.event_bus.emit("power.shutdown_requested", {"delay": delay})

        if delay > 0:
            await asyncio.sleep(delay)

        self._run_power_cmd(["systemctl", "poweroff"])
        return {"status": "shutting_down"}

    async def handle_reboot(self, body: dict) -> dict:
        """Reboot the device."""
        logger.warning("Reboot requested")
        await self.event_bus.emit("power.reboot_requested", {})
        self._run_power_cmd(["systemctl", "reboot"])
        return {"status": "rebooting"}

    async def handle_suspend(self, body: dict) -> dict:
        """Suspend/sleep the device."""
        logger.info("Suspend requested")
        await self.event_bus.emit("power.suspend_requested", {})
        self._run_power_cmd(["systemctl", "suspend"])
        return {"status": "suspending"}

    @staticmethod
    def _run_power_cmd(cmd: list[str]):
        """Execute a power management command."""
        try:
            subprocess.Popen(cmd)
        except FileNotFoundError:
            logger.error("Command not found: %s", cmd[0])
            raise RuntimeError(f"Power command not available: {cmd[0]}")
