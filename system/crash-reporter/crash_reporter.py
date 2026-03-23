"""
Claude-OS Crash Reporter and Diagnostics

Captures, stores, and reports crashes and system diagnostics.
Claude can read crash reports to help users troubleshoot issues.

Features:
- Captures crash dumps from all system services
- Structured crash reports with stack traces
- System health diagnostics (CPU, memory, disk, temp)
- Log aggregation from all services
- Optional anonymous crash reporting to development server
"""

import asyncio
import json
import logging
import os
import subprocess
import time
import traceback
from dataclasses import dataclass, field
from pathlib import Path

logger = logging.getLogger("crash-reporter")

DATA_DIR = Path(os.environ.get("CLAUDE_OS_DATA", "/var/lib/claude-os"))
CRASH_DIR = DATA_DIR / "crashes"
DIAG_DIR = DATA_DIR / "diagnostics"
MAX_CRASH_REPORTS = 50


@dataclass
class CrashReport:
    """A structured crash report."""
    report_id: str
    timestamp: float
    service: str
    pid: int
    signal: int
    exit_code: int
    stack_trace: str
    system_state: dict
    coredump_path: str = ""
    reported: bool = False

    def to_dict(self) -> dict:
        return {
            "report_id": self.report_id,
            "timestamp": self.timestamp,
            "service": self.service,
            "pid": self.pid,
            "signal": self.signal,
            "exit_code": self.exit_code,
            "stack_trace": self.stack_trace,
            "system_state": self.system_state,
            "coredump_path": self.coredump_path,
            "reported": self.reported,
        }


class CrashReporter:
    """
    Captures and manages crash reports for all system services.

    Also provides system diagnostics that Claude can use to help
    users troubleshoot device issues.
    """

    def __init__(self, event_bus=None):
        self.event_bus = event_bus
        self._running = False

    async def start(self):
        """Start the crash reporter daemon."""
        self._running = True
        CRASH_DIR.mkdir(parents=True, exist_ok=True)
        DIAG_DIR.mkdir(parents=True, exist_ok=True)

        logger.info("Crash reporter started")

        # Configure coredump handler
        self._setup_coredump_handler()

        # Monitor for crashes and run periodic diagnostics
        await asyncio.gather(
            self._watch_coredumps(),
            self._periodic_diagnostics(),
            self._watch_journal(),
        )

    # --- Crash Capture ---

    async def record_crash(self, service: str, pid: int,
                           signal_num: int = 0, exit_code: int = 1,
                           stack_trace: str = "") -> dict:
        """
        Record a crash event.

        Args:
            service: Name of the crashed service
            pid: PID of the crashed process
            signal_num: Signal that caused the crash (0 if exit)
            exit_code: Exit code
            stack_trace: Stack trace if available
        """
        report_id = f"{service}-{int(time.time())}-{pid}"
        system_state = self._capture_system_state()

        report = CrashReport(
            report_id=report_id,
            timestamp=time.time(),
            service=service,
            pid=pid,
            signal=signal_num,
            exit_code=exit_code,
            stack_trace=stack_trace,
            system_state=system_state,
        )

        # Save to disk
        report_path = CRASH_DIR / f"{report_id}.json"
        report_path.write_text(json.dumps(report.to_dict(), indent=2))

        logger.warning("Crash recorded: %s (PID %d, signal %d)",
                        service, pid, signal_num)

        if self.event_bus:
            await self.event_bus.emit("crash.recorded", {
                "report_id": report_id,
                "service": service,
            })

        # Enforce max reports
        self._cleanup_old_reports()

        return report.to_dict()

    def get_crash_reports(self, limit: int = 20) -> list[dict]:
        """Get recent crash reports."""
        reports = []
        for path in sorted(CRASH_DIR.glob("*.json"), reverse=True)[:limit]:
            try:
                reports.append(json.loads(path.read_text()))
            except (json.JSONDecodeError, OSError):
                continue
        return reports

    def get_crash_report(self, report_id: str) -> dict:
        """Get a specific crash report."""
        path = CRASH_DIR / f"{report_id}.json"
        if not path.exists():
            raise ValueError(f"Crash report not found: {report_id}")
        return json.loads(path.read_text())

    # --- System Diagnostics ---

    def run_diagnostics(self) -> dict:
        """
        Run a full system diagnostics check.

        Returns a comprehensive snapshot of system health that
        Claude can analyze to help troubleshoot issues.
        """
        diag = {
            "timestamp": time.time(),
            "cpu": self._diag_cpu(),
            "memory": self._diag_memory(),
            "storage": self._diag_storage(),
            "temperature": self._diag_temperature(),
            "processes": self._diag_processes(),
            "network": self._diag_network(),
            "services": self._diag_services(),
            "uptime": self._diag_uptime(),
            "kernel": self._diag_kernel(),
            "recent_crashes": len(list(CRASH_DIR.glob("*.json"))),
        }

        # Save diagnostics snapshot
        snap_path = DIAG_DIR / f"diag-{int(time.time())}.json"
        snap_path.write_text(json.dumps(diag, indent=2))

        return diag

    def _diag_cpu(self) -> dict:
        """CPU diagnostics."""
        try:
            with open("/proc/loadavg") as f:
                parts = f.read().split()
            return {
                "load_1m": float(parts[0]),
                "load_5m": float(parts[1]),
                "load_15m": float(parts[2]),
            }
        except (OSError, ValueError, IndexError):
            return {"error": "Could not read CPU info"}

    def _diag_memory(self) -> dict:
        """Memory diagnostics."""
        try:
            meminfo = Path("/proc/meminfo").read_text()
            info = {}
            for line in meminfo.split("\n"):
                if ":" in line:
                    key, _, val = line.partition(":")
                    parts = val.strip().split()
                    if parts:
                        info[key.strip()] = int(parts[0])

            total = info.get("MemTotal", 0)
            available = info.get("MemAvailable", 0)
            swap_total = info.get("SwapTotal", 0)
            swap_free = info.get("SwapFree", 0)

            return {
                "total_mb": total // 1024,
                "available_mb": available // 1024,
                "used_percent": round((total - available) / total * 100, 1) if total else 0,
                "swap_total_mb": swap_total // 1024,
                "swap_used_mb": (swap_total - swap_free) // 1024,
            }
        except OSError:
            return {"error": "Could not read memory info"}

    def _diag_storage(self) -> dict:
        """Storage diagnostics."""
        try:
            st = os.statvfs("/")
            total = st.f_blocks * st.f_frsize
            free = st.f_bfree * st.f_frsize
            return {
                "total_mb": total // (1024 * 1024),
                "free_mb": free // (1024 * 1024),
                "used_percent": round((total - free) / total * 100, 1) if total else 0,
            }
        except OSError:
            return {"error": "Could not read storage info"}

    def _diag_temperature(self) -> dict:
        """Thermal diagnostics."""
        temps = {}
        thermal_base = "/sys/class/thermal"
        if os.path.exists(thermal_base):
            for zone in os.listdir(thermal_base):
                temp_file = os.path.join(thermal_base, zone, "temp")
                type_file = os.path.join(thermal_base, zone, "type")
                try:
                    temp_mc = int(Path(temp_file).read_text().strip())
                    zone_type = Path(type_file).read_text().strip() if os.path.exists(type_file) else zone
                    temps[zone_type] = temp_mc / 1000.0  # millicelsius to celsius
                except (OSError, ValueError):
                    continue
        return temps if temps else {"available": False}

    def _diag_processes(self) -> dict:
        """Process diagnostics — top consumers."""
        try:
            result = subprocess.run(
                ["ps", "aux", "--sort=-%mem"],
                capture_output=True, text=True, timeout=5,
            )
            lines = result.stdout.strip().split("\n")
            return {
                "total": len(lines) - 1,  # minus header
                "top_by_memory": lines[:6],  # header + top 5
            }
        except (FileNotFoundError, subprocess.TimeoutExpired):
            return {"error": "Could not list processes"}

    def _diag_network(self) -> dict:
        """Network diagnostics."""
        result = {}
        try:
            for iface in os.listdir("/sys/class/net"):
                state_file = f"/sys/class/net/{iface}/operstate"
                state = Path(state_file).read_text().strip() if os.path.exists(state_file) else "unknown"
                result[iface] = {"state": state}
        except OSError:
            pass
        return result

    def _diag_services(self) -> dict:
        """Check status of Claude-OS systemd services."""
        services = [
            "wifi-manager", "claude-bridge", "claude-display",
            "claude-apps", "claude-notifications",
        ]
        status = {}
        for svc in services:
            try:
                result = subprocess.run(
                    ["systemctl", "is-active", svc],
                    capture_output=True, text=True, timeout=5,
                )
                status[svc] = result.stdout.strip()
            except (FileNotFoundError, subprocess.TimeoutExpired):
                status[svc] = "unknown"
        return status

    def _diag_uptime(self) -> dict:
        """System uptime."""
        try:
            uptime = float(Path("/proc/uptime").read_text().split()[0])
            days = int(uptime // 86400)
            hours = int((uptime % 86400) // 3600)
            minutes = int((uptime % 3600) // 60)
            return {
                "seconds": uptime,
                "formatted": f"{days}d {hours}h {minutes}m",
            }
        except (OSError, ValueError):
            return {"seconds": 0}

    def _diag_kernel(self) -> dict:
        """Kernel info."""
        try:
            return {
                "version": Path("/proc/version").read_text().strip(),
                "cmdline": Path("/proc/cmdline").read_text().strip(),
            }
        except OSError:
            return {}

    # --- Internal ---

    def _capture_system_state(self) -> dict:
        """Capture a snapshot of system state at crash time."""
        return {
            "memory": self._diag_memory(),
            "cpu": self._diag_cpu(),
            "storage": self._diag_storage(),
            "uptime": self._diag_uptime(),
        }

    def _setup_coredump_handler(self):
        """Configure the kernel to send coredumps to our handler."""
        core_pattern = f"|/usr/bin/python3 /opt/claude-os/crash-reporter/coredump_handler.py %p %s %e"
        try:
            Path("/proc/sys/kernel/core_pattern").write_text(core_pattern)
            logger.info("Coredump handler configured")
        except PermissionError:
            logger.debug("Cannot set core_pattern (not root)")

    async def _watch_coredumps(self):
        """Watch for new coredump files."""
        coredump_dir = Path("/var/lib/claude-os/coredumps")
        coredump_dir.mkdir(parents=True, exist_ok=True)
        known = set(coredump_dir.glob("*.core"))

        while self._running:
            current = set(coredump_dir.glob("*.core"))
            new_cores = current - known
            for core in new_cores:
                logger.warning("New coredump: %s", core.name)
            known = current
            await asyncio.sleep(5)

    async def _watch_journal(self):
        """Watch systemd journal for crash-related messages."""
        # In production, use systemd journal API
        await asyncio.sleep(3600)

    async def _periodic_diagnostics(self):
        """Run diagnostics periodically."""
        while self._running:
            await asyncio.sleep(300)  # Every 5 minutes
            # Lightweight check — full diagnostics on demand
            try:
                mem = self._diag_memory()
                if mem.get("used_percent", 0) > 90:
                    logger.warning("High memory usage: %s%%",
                                    mem["used_percent"])
                    if self.event_bus:
                        await self.event_bus.emit("system.memory_high", mem)
            except Exception:
                pass

    def _cleanup_old_reports(self):
        """Remove old crash reports beyond the limit."""
        reports = sorted(CRASH_DIR.glob("*.json"), reverse=True)
        for old in reports[MAX_CRASH_REPORTS:]:
            old.unlink(missing_ok=True)

    async def stop(self):
        """Stop the crash reporter."""
        self._running = False
        logger.info("Crash reporter stopped")
