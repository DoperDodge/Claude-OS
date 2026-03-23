"""
System information bridge service.

Provides device info, battery status, and display control.
"""

import asyncio
import logging
import os
import subprocess
from pathlib import Path

from event_bus import EventBus

logger = logging.getLogger("bridge.system")


class SystemBridgeService:
    """Bridge service for system information and display control."""

    def __init__(self, event_bus: EventBus):
        self.event_bus = event_bus

        # Start battery monitor
        asyncio.ensure_future(self._monitor_battery())

    async def handle_info(self, body: dict) -> dict:
        """Get general system information."""
        return {
            "hostname": self._read_file("/etc/hostname", "claude-os"),
            "os": "Claude-OS",
            "version": "0.1.0",
            "kernel": self._run_cmd("uname -r"),
            "arch": self._run_cmd("uname -m"),
            "uptime_seconds": self._get_uptime(),
            "memory": self._get_memory_info(),
            "storage": self._get_storage_info(),
        }

    async def handle_battery(self, body: dict) -> dict:
        """Get battery status."""
        return self._get_battery_info()

    async def handle_set_brightness(self, body: dict) -> dict:
        """Set screen brightness (0-100)."""
        level = body.get("level")
        if level is None:
            raise ValueError("Missing required field: level")

        level = max(0, min(100, int(level)))

        # Try sysfs brightness control
        backlight_path = self._find_backlight()
        if backlight_path:
            max_brightness = int(self._read_file(
                f"{backlight_path}/max_brightness", "255"
            ))
            raw_value = int(max_brightness * level / 100)
            try:
                with open(f"{backlight_path}/brightness", "w") as f:
                    f.write(str(raw_value))
                await self.event_bus.emit("system.brightness_changed",
                                          {"level": level})
                return {"brightness": level}
            except PermissionError:
                raise RuntimeError("No permission to set brightness")

        raise RuntimeError("No backlight device found")

    def _get_uptime(self) -> float:
        """Get system uptime in seconds."""
        try:
            uptime_str = self._read_file("/proc/uptime", "0 0")
            return float(uptime_str.split()[0])
        except (ValueError, IndexError):
            return 0.0

    def _get_memory_info(self) -> dict:
        """Get memory usage from /proc/meminfo."""
        try:
            meminfo = self._read_file("/proc/meminfo", "")
            info = {}
            for line in meminfo.split("\n"):
                if ":" in line:
                    key, _, value = line.partition(":")
                    # Convert "1234 kB" to integer KB
                    parts = value.strip().split()
                    if parts:
                        info[key.strip()] = int(parts[0])

            total = info.get("MemTotal", 0)
            available = info.get("MemAvailable", 0)
            used = total - available

            return {
                "total_mb": total // 1024,
                "used_mb": used // 1024,
                "available_mb": available // 1024,
                "percent_used": round(used / total * 100, 1) if total else 0,
            }
        except Exception:
            return {"error": "Could not read memory info"}

    def _get_storage_info(self) -> dict:
        """Get root filesystem usage."""
        try:
            stat = os.statvfs("/")
            total = stat.f_blocks * stat.f_frsize
            free = stat.f_bfree * stat.f_frsize
            used = total - free
            return {
                "total_mb": total // (1024 * 1024),
                "used_mb": used // (1024 * 1024),
                "free_mb": free // (1024 * 1024),
                "percent_used": round(used / total * 100, 1) if total else 0,
            }
        except Exception:
            return {"error": "Could not read storage info"}

    def _get_battery_info(self) -> dict:
        """Read battery status from sysfs."""
        battery_path = "/sys/class/power_supply/BAT0"
        if not os.path.exists(battery_path):
            # Try alternative paths
            for name in ("battery", "BAT1", "axp20x-battery"):
                alt = f"/sys/class/power_supply/{name}"
                if os.path.exists(alt):
                    battery_path = alt
                    break
            else:
                return {"available": False, "message": "No battery detected (QEMU)"}

        return {
            "available": True,
            "level": int(self._read_file(f"{battery_path}/capacity", "0")),
            "status": self._read_file(f"{battery_path}/status", "Unknown"),
            "voltage_uv": int(self._read_file(f"{battery_path}/voltage_now", "0")),
            "current_ua": int(self._read_file(f"{battery_path}/current_now", "0")),
        }

    def _find_backlight(self) -> str | None:
        """Find the sysfs backlight device path."""
        base = "/sys/class/backlight"
        if os.path.exists(base):
            entries = os.listdir(base)
            if entries:
                return os.path.join(base, entries[0])
        return None

    async def _monitor_battery(self):
        """Emit events when battery state changes significantly."""
        await asyncio.sleep(10)
        last_level = -1

        while True:
            info = self._get_battery_info()
            if info.get("available"):
                level = info.get("level", -1)
                if level != last_level:
                    if level <= 10 and last_level > 10:
                        await self.event_bus.emit("battery.low", info)
                    if level <= 5 and last_level > 5:
                        await self.event_bus.emit("battery.critical", info)
                    last_level = level

            await asyncio.sleep(60)

    @staticmethod
    def _read_file(path: str, default: str = "") -> str:
        try:
            return Path(path).read_text().strip()
        except OSError:
            return default

    @staticmethod
    def _run_cmd(cmd: str) -> str:
        try:
            result = subprocess.run(
                cmd.split(), capture_output=True, text=True, timeout=5
            )
            return result.stdout.strip()
        except (subprocess.TimeoutExpired, FileNotFoundError):
            return "unknown"
