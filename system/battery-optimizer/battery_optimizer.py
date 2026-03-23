"""
Claude-OS Battery Optimizer

Monitors battery state and applies power-saving strategies to
maximize battery life. Claude can also suggest optimizations.

Power profiles:
- Performance: Full speed, all features enabled
- Balanced: Default — moderate savings
- Power Saver: Aggressive savings (dim screen, limit background, throttle CPU)
- Ultra Saver: Minimal functionality (screen very dim, WiFi periodic, no background)

Automatic transitions:
- 100-30%: Balanced
- 30-15%: Power Saver (auto-switch)
- 15-5%: Ultra Saver (auto-switch)
- <5%: Emergency mode (only essential services)
"""

import asyncio
import logging
import os
import subprocess
from enum import Enum, auto
from pathlib import Path

logger = logging.getLogger("battery-optimizer")


class PowerProfile(Enum):
    """Power management profiles."""
    PERFORMANCE = "performance"
    BALANCED = "balanced"
    POWER_SAVER = "power_saver"
    ULTRA_SAVER = "ultra_saver"
    EMERGENCY = "emergency"


# Profile configurations
PROFILES = {
    PowerProfile.PERFORMANCE: {
        "brightness": 100,
        "cpu_governor": "performance",
        "screen_timeout_sec": 300,
        "wifi_power_save": False,
        "background_limit": False,
        "sync_interval_sec": 60,
    },
    PowerProfile.BALANCED: {
        "brightness": 70,
        "cpu_governor": "schedutil",
        "screen_timeout_sec": 120,
        "wifi_power_save": True,
        "background_limit": False,
        "sync_interval_sec": 120,
    },
    PowerProfile.POWER_SAVER: {
        "brightness": 40,
        "cpu_governor": "powersave",
        "screen_timeout_sec": 60,
        "wifi_power_save": True,
        "background_limit": True,
        "sync_interval_sec": 300,
    },
    PowerProfile.ULTRA_SAVER: {
        "brightness": 15,
        "cpu_governor": "powersave",
        "screen_timeout_sec": 30,
        "wifi_power_save": True,
        "background_limit": True,
        "sync_interval_sec": 600,
    },
    PowerProfile.EMERGENCY: {
        "brightness": 5,
        "cpu_governor": "powersave",
        "screen_timeout_sec": 15,
        "wifi_power_save": True,
        "background_limit": True,
        "sync_interval_sec": 0,  # No background sync
    },
}

# Auto-switch thresholds
AUTO_THRESHOLDS = [
    (30, PowerProfile.POWER_SAVER),
    (15, PowerProfile.ULTRA_SAVER),
    (5, PowerProfile.EMERGENCY),
]


class BatteryOptimizer:
    """
    Manages battery optimization and power profiles.

    Monitors battery state and automatically adjusts system settings
    to maximize battery life based on the current level.
    """

    def __init__(self, event_bus=None):
        self.event_bus = event_bus
        self.active_profile = PowerProfile.BALANCED
        self.auto_switch = True
        self._last_level = 100
        self._running = False

        # Per-app battery usage tracking
        self._app_usage: dict[str, float] = {}

    async def start(self):
        """Start the battery optimizer daemon."""
        self._running = True
        logger.info("Battery optimizer started (profile: %s)",
                     self.active_profile.value)

        self._apply_profile(self.active_profile)

        await asyncio.gather(
            self._monitor_loop(),
            self._track_app_usage(),
        )

    # --- Profile Management ---

    def set_profile(self, profile_name: str) -> dict:
        """Manually set a power profile."""
        try:
            profile = PowerProfile(profile_name)
        except ValueError:
            raise ValueError(
                f"Unknown profile: {profile_name}. "
                f"Options: {[p.value for p in PowerProfile]}"
            )

        self.active_profile = profile
        self._apply_profile(profile)

        logger.info("Power profile set to: %s", profile.value)
        return {
            "profile": profile.value,
            "settings": PROFILES[profile],
        }

    def get_profile(self) -> dict:
        """Get current power profile and settings."""
        return {
            "profile": self.active_profile.value,
            "settings": PROFILES[self.active_profile],
            "auto_switch": self.auto_switch,
        }

    def _apply_profile(self, profile: PowerProfile):
        """Apply a power profile's settings to the system."""
        config = PROFILES[profile]

        # CPU governor
        self._set_cpu_governor(config["cpu_governor"])

        # Screen brightness
        self._set_brightness(config["brightness"])

        # WiFi power save
        self._set_wifi_power_save(config["wifi_power_save"])

        logger.info("Applied profile: %s", profile.value)

    # --- Battery Monitoring ---

    async def _monitor_loop(self):
        """Monitor battery and auto-switch profiles."""
        while self._running:
            level = self._read_battery_level()
            charging = self._is_charging()

            # Auto-switch profile based on battery level
            if self.auto_switch and not charging:
                for threshold, profile in AUTO_THRESHOLDS:
                    if level <= threshold and self._last_level > threshold:
                        logger.info(
                            "Battery at %d%%, switching to %s",
                            level, profile.value,
                        )
                        self.active_profile = profile
                        self._apply_profile(profile)

                        if self.event_bus:
                            await self.event_bus.emit("battery.profile_changed", {
                                "profile": profile.value,
                                "level": level,
                                "reason": "auto",
                            })
                        break

            # Reset to balanced when charging and level recovered
            if charging and level > 30 and self.auto_switch:
                if self.active_profile != PowerProfile.BALANCED:
                    self.active_profile = PowerProfile.BALANCED
                    self._apply_profile(PowerProfile.BALANCED)

            self._last_level = level
            await asyncio.sleep(30)

    def get_battery_stats(self) -> dict:
        """Get detailed battery statistics."""
        level = self._read_battery_level()
        charging = self._is_charging()

        stats = {
            "level": level,
            "charging": charging,
            "profile": self.active_profile.value,
            "auto_switch": self.auto_switch,
            "estimated_remaining": self._estimate_remaining(level, charging),
            "top_consumers": self._get_top_consumers(),
        }

        return stats

    def _estimate_remaining(self, level: int, charging: bool) -> str:
        """Estimate remaining battery time."""
        if charging:
            return "Charging"
        if level <= 0:
            return "Empty"

        # Rough estimate based on profile
        hours_per_percent = {
            PowerProfile.PERFORMANCE: 0.05,
            PowerProfile.BALANCED: 0.1,
            PowerProfile.POWER_SAVER: 0.15,
            PowerProfile.ULTRA_SAVER: 0.25,
            PowerProfile.EMERGENCY: 0.4,
        }

        hpp = hours_per_percent.get(self.active_profile, 0.1)
        hours = level * hpp
        h = int(hours)
        m = int((hours - h) * 60)
        return f"~{h}h {m}m"

    def _get_top_consumers(self) -> list[dict]:
        """Get apps consuming the most battery."""
        sorted_apps = sorted(
            self._app_usage.items(),
            key=lambda x: x[1],
            reverse=True,
        )
        return [
            {"app_id": app, "usage_percent": round(usage, 1)}
            for app, usage in sorted_apps[:5]
        ]

    async def _track_app_usage(self):
        """Track per-app CPU time for battery usage estimation."""
        while self._running:
            try:
                proc_dir = Path("/proc")
                for pid_dir in proc_dir.iterdir():
                    if not pid_dir.name.isdigit():
                        continue
                    try:
                        cmdline = (pid_dir / "cmdline").read_text().split("\0")[0]
                        stat = (pid_dir / "stat").read_text().split()
                        # Fields 13+14 = user + system time
                        cpu_time = int(stat[13]) + int(stat[14])
                        app_name = os.path.basename(cmdline) or pid_dir.name
                        self._app_usage[app_name] = self._app_usage.get(
                            app_name, 0
                        ) + cpu_time * 0.001
                    except (OSError, IndexError, ValueError):
                        continue
            except OSError:
                pass
            await asyncio.sleep(60)

    # --- System Controls ---

    def _set_cpu_governor(self, governor: str):
        """Set the CPU frequency governor."""
        cpu_base = "/sys/devices/system/cpu"
        try:
            for cpu in os.listdir(cpu_base):
                if cpu.startswith("cpu") and cpu[3:].isdigit():
                    gov_path = os.path.join(
                        cpu_base, cpu, "cpufreq/scaling_governor"
                    )
                    if os.path.exists(gov_path):
                        Path(gov_path).write_text(governor)
        except (PermissionError, OSError):
            logger.debug("Cannot set CPU governor (no permission)")

    def _set_brightness(self, level: int):
        """Set screen brightness."""
        backlight = "/sys/class/backlight"
        if os.path.exists(backlight):
            for device in os.listdir(backlight):
                try:
                    max_b = int(Path(
                        f"{backlight}/{device}/max_brightness"
                    ).read_text().strip())
                    raw = int(max_b * level / 100)
                    Path(f"{backlight}/{device}/brightness").write_text(str(raw))
                except (PermissionError, OSError, ValueError):
                    pass

    def _set_wifi_power_save(self, enabled: bool):
        """Toggle WiFi power save mode."""
        try:
            mode = "on" if enabled else "off"
            subprocess.run(
                ["iw", "dev", "wlan0", "set", "power_save", mode],
                capture_output=True, timeout=5,
            )
        except (FileNotFoundError, subprocess.TimeoutExpired):
            pass

    def _read_battery_level(self) -> int:
        """Read current battery level."""
        for name in ("BAT0", "BAT1", "battery"):
            path = f"/sys/class/power_supply/{name}/capacity"
            if os.path.exists(path):
                try:
                    return int(Path(path).read_text().strip())
                except (OSError, ValueError):
                    pass
        return 100  # Default for QEMU (no battery)

    def _is_charging(self) -> bool:
        """Check if battery is charging."""
        for name in ("BAT0", "BAT1", "battery"):
            path = f"/sys/class/power_supply/{name}/status"
            if os.path.exists(path):
                try:
                    return Path(path).read_text().strip() == "Charging"
                except OSError:
                    pass
        return False

    async def stop(self):
        """Stop the battery optimizer."""
        self._running = False
        logger.info("Battery optimizer stopped")
