"""
Claude-OS Storage Manager

Manages file system access, storage monitoring, and file operations.
Provides a controlled interface for apps (and Claude) to read/write
files within permitted directories.

Features:
- Storage usage monitoring (total, used, free per partition)
- Sandboxed file access — apps can only access their own data dirs
- User file management (downloads, photos, documents)
- USB/SD card mount detection and handling
- Disk usage alerts when storage is low
"""

import asyncio
import json
import logging
import os
import shutil
import stat
import time
from pathlib import Path

logger = logging.getLogger("storage")

# Standard user-accessible directories
USER_DIRS = {
    "downloads": "/home/user/Downloads",
    "documents": "/home/user/Documents",
    "photos": "/home/user/Photos",
    "music": "/home/user/Music",
    "videos": "/home/user/Videos",
}

# App data directory template
APP_DATA_DIR = "/var/lib/claude-os/apps/{app_id}/data"

# Low storage thresholds
LOW_STORAGE_PERCENT = 90
CRITICAL_STORAGE_PERCENT = 95


class StorageManager:
    """
    Manages file system access and storage monitoring.

    Enforces sandboxing — each app only has access to its own data
    directory plus shared user directories (with permission).
    """

    def __init__(self, event_bus=None):
        self.event_bus = event_bus
        self._mount_watchers: list = []
        self._last_usage = {}

    async def start(self):
        """Start the storage manager daemon."""
        logger.info("Storage manager started")

        # Ensure user directories exist
        for name, path in USER_DIRS.items():
            os.makedirs(path, exist_ok=True)

        # Start monitoring
        await asyncio.gather(
            self._monitor_usage(),
            self._watch_mounts(),
        )

    # --- Storage Info ---

    def get_usage(self) -> dict:
        """Get storage usage for all mounted filesystems."""
        partitions = {}

        # Read /proc/mounts for mounted filesystems
        try:
            mounts = Path("/proc/mounts").read_text()
        except OSError:
            mounts = ""

        # Track which mount points we've seen
        seen = set()

        for line in mounts.split("\n"):
            parts = line.split()
            if len(parts) < 3:
                continue

            device, mount_point, fs_type = parts[0], parts[1], parts[2]

            # Skip virtual filesystems
            if fs_type in ("proc", "sysfs", "tmpfs", "devtmpfs", "devpts",
                           "cgroup", "cgroup2", "pstore", "securityfs",
                           "debugfs", "configfs", "fusectl", "hugetlbfs",
                           "mqueue", "binfmt_misc", "rpc_pipefs"):
                continue

            if mount_point in seen:
                continue
            seen.add(mount_point)

            try:
                st = os.statvfs(mount_point)
                total = st.f_blocks * st.f_frsize
                free = st.f_bfree * st.f_frsize
                available = st.f_bavail * st.f_frsize
                used = total - free

                partitions[mount_point] = {
                    "device": device,
                    "fs_type": fs_type,
                    "mount_point": mount_point,
                    "total_bytes": total,
                    "used_bytes": used,
                    "free_bytes": free,
                    "available_bytes": available,
                    "total_mb": total // (1024 * 1024),
                    "used_mb": used // (1024 * 1024),
                    "free_mb": free // (1024 * 1024),
                    "percent_used": round(used / total * 100, 1) if total else 0,
                }
            except OSError:
                continue

        return partitions

    def get_user_dirs(self) -> dict:
        """Get user directories and their sizes."""
        result = {}
        for name, path in USER_DIRS.items():
            if os.path.exists(path):
                size = self._dir_size(path)
                file_count = sum(1 for _ in Path(path).rglob("*") if _.is_file())
                result[name] = {
                    "path": path,
                    "size_bytes": size,
                    "size_mb": size // (1024 * 1024),
                    "file_count": file_count,
                }
            else:
                result[name] = {"path": path, "exists": False}
        return result

    # --- File Operations ---

    def list_files(self, directory: str, app_id: str = None) -> list[dict]:
        """
        List files in a directory.

        Args:
            directory: Path to list (must be within allowed paths)
            app_id: Requesting app's ID (for sandboxing)

        Returns:
            List of file info dicts
        """
        path = Path(directory).resolve()
        self._check_access(path, app_id)

        if not path.is_dir():
            raise FileNotFoundError(f"Not a directory: {directory}")

        files = []
        try:
            for entry in sorted(path.iterdir()):
                try:
                    st = entry.stat()
                    files.append({
                        "name": entry.name,
                        "path": str(entry),
                        "is_dir": entry.is_dir(),
                        "size_bytes": st.st_size if entry.is_file() else 0,
                        "modified": st.st_mtime,
                        "permissions": stat.filemode(st.st_mode),
                    })
                except OSError:
                    continue
        except PermissionError:
            raise PermissionError(f"Cannot read directory: {directory}")

        return files

    def read_file(self, file_path: str, app_id: str = None) -> dict:
        """
        Read a file's contents (text files only, with size limit).

        Args:
            file_path: Path to the file
            app_id: Requesting app's ID

        Returns:
            Dict with file content and metadata
        """
        path = Path(file_path).resolve()
        self._check_access(path, app_id)

        if not path.is_file():
            raise FileNotFoundError(f"Not a file: {file_path}")

        size = path.stat().st_size
        max_size = 1024 * 1024  # 1MB limit for text reads

        if size > max_size:
            raise ValueError(f"File too large ({size} bytes, max {max_size})")

        try:
            content = path.read_text(errors="replace")
        except UnicodeDecodeError:
            raise ValueError("File is binary, cannot read as text")

        return {
            "path": str(path),
            "size_bytes": size,
            "content": content,
        }

    def write_file(self, file_path: str, content: str,
                   app_id: str = None) -> dict:
        """
        Write content to a file.

        Args:
            file_path: Destination path
            content: Text content to write
            app_id: Requesting app's ID
        """
        path = Path(file_path).resolve()
        self._check_access(path.parent, app_id, write=True)

        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(content)

        return {
            "path": str(path),
            "size_bytes": path.stat().st_size,
            "written": True,
        }

    def delete_file(self, file_path: str, app_id: str = None) -> dict:
        """Delete a file."""
        path = Path(file_path).resolve()
        self._check_access(path, app_id, write=True)

        if path.is_dir():
            shutil.rmtree(path)
        elif path.is_file():
            path.unlink()
        else:
            raise FileNotFoundError(f"Not found: {file_path}")

        return {"deleted": str(path)}

    def get_app_data_dir(self, app_id: str) -> str:
        """Get or create the data directory for an app."""
        data_dir = APP_DATA_DIR.format(app_id=app_id)
        os.makedirs(data_dir, exist_ok=True)
        return data_dir

    # --- Access Control ---

    def _check_access(self, path: Path, app_id: str = None,
                      write: bool = False):
        """
        Verify that the requested path is within allowed boundaries.

        Rules:
        - System app (app_id=None) can access user dirs
        - Regular apps can only access their own data dir
        - Nobody can access /etc, /sys, /proc, etc.
        """
        resolved = str(path.resolve())

        # Block sensitive system paths
        blocked = ("/etc", "/sys", "/proc", "/dev", "/boot",
                   "/root", "/run", "/sbin", "/bin", "/usr")
        for b in blocked:
            if resolved.startswith(b):
                raise PermissionError(f"Access denied: {resolved}")

        # System app (Claude) can access user dirs
        if app_id is None:
            allowed = list(USER_DIRS.values()) + ["/var/lib/claude-os"]
            if any(resolved.startswith(a) for a in allowed):
                return
            raise PermissionError(f"Access denied: {resolved}")

        # Regular apps: only their data dir
        app_dir = APP_DATA_DIR.format(app_id=app_id)
        if not resolved.startswith(app_dir):
            raise PermissionError(
                f"App '{app_id}' cannot access {resolved} "
                f"(allowed: {app_dir})"
            )

    # --- Monitoring ---

    async def _monitor_usage(self):
        """Periodically check storage usage and emit alerts."""
        while True:
            usage = self.get_usage()

            for mount, info in usage.items():
                percent = info.get("percent_used", 0)
                prev = self._last_usage.get(mount, 0)

                if percent >= CRITICAL_STORAGE_PERCENT and prev < CRITICAL_STORAGE_PERCENT:
                    logger.warning("CRITICAL: %s is %s%% full", mount, percent)
                    if self.event_bus:
                        await self.event_bus.emit("storage.critical", info)
                elif percent >= LOW_STORAGE_PERCENT and prev < LOW_STORAGE_PERCENT:
                    logger.warning("Low storage: %s is %s%% full", mount, percent)
                    if self.event_bus:
                        await self.event_bus.emit("storage.low", info)

                self._last_usage[mount] = percent

            await asyncio.sleep(60)

    async def _watch_mounts(self):
        """Watch for USB/SD card mount events."""
        media_dir = "/media"
        known_mounts = set()

        while True:
            if os.path.exists(media_dir):
                current = set(os.listdir(media_dir))
                new_mounts = current - known_mounts
                removed = known_mounts - current

                for mount in new_mounts:
                    mount_path = os.path.join(media_dir, mount)
                    logger.info("External storage mounted: %s", mount_path)
                    if self.event_bus:
                        await self.event_bus.emit("storage.mounted", {
                            "path": mount_path,
                            "name": mount,
                        })

                for mount in removed:
                    logger.info("External storage removed: %s", mount)
                    if self.event_bus:
                        await self.event_bus.emit("storage.unmounted", {
                            "name": mount,
                        })

                known_mounts = current

            await asyncio.sleep(5)

    @staticmethod
    def _dir_size(path: str) -> int:
        """Calculate total size of a directory."""
        total = 0
        for dirpath, _, filenames in os.walk(path):
            for f in filenames:
                fp = os.path.join(dirpath, f)
                try:
                    total += os.path.getsize(fp)
                except OSError:
                    pass
        return total


def main():
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    )
    manager = StorageManager()
    asyncio.run(manager.start())


if __name__ == "__main__":
    main()
