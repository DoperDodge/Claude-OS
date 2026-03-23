"""
Claude-OS Package Manager

Handles installing and uninstalling apps from .cpk (Claude Package) files.

A .cpk file is a tar.gz archive containing:
    manifest.json   — App metadata (app_id, name, exec, permissions)
    icon.png        — App icon (optional)
    bin/            — Executable files
    lib/            — Shared libraries
    data/           — Default data files

Package operations:
    install(path)   — Extract .cpk to /opt/claude-os/apps/{app_id}/
    uninstall(id)   — Remove app directory and data
    list_installed  — List all installed packages
    verify(path)    — Check .cpk integrity without installing
"""

import json
import logging
import os
import shutil
import tarfile
import time
from dataclasses import dataclass, field
from pathlib import Path

logger = logging.getLogger("package_manager")

APPS_DIR = Path("/opt/claude-os/apps")
APP_DATA_DIR = Path("/var/lib/claude-os/apps")


@dataclass
class PackageInfo:
    """Metadata about an installed or pending package."""
    app_id: str
    name: str
    version: str = "1.0.0"
    author: str = ""
    description: str = ""
    size_bytes: int = 0
    installed_at: float = 0
    permissions: list[str] = field(default_factory=list)

    def to_dict(self) -> dict:
        return {
            "app_id": self.app_id,
            "name": self.name,
            "version": self.version,
            "author": self.author,
            "description": self.description,
            "size_bytes": self.size_bytes,
            "installed_at": self.installed_at,
            "permissions": self.permissions,
        }


class PackageError(Exception):
    """Error during package operations."""
    pass


class PackageManager:
    """
    Manages .cpk package installation and removal.
    """

    REQUIRED_MANIFEST_KEYS = {"app_id", "name", "exec"}

    def __init__(self, apps_dir: Path = None, data_dir: Path = None):
        self.apps_dir = apps_dir or APPS_DIR
        self.data_dir = data_dir or APP_DATA_DIR
        self._installed: dict[str, PackageInfo] = {}
        self._load_installed()

    def _load_installed(self):
        """Scan apps directory for installed packages."""
        self._installed.clear()
        if not self.apps_dir.exists():
            return

        for app_dir in self.apps_dir.iterdir():
            if not app_dir.is_dir():
                continue
            manifest_path = app_dir / "manifest.json"
            if manifest_path.exists():
                try:
                    data = json.loads(manifest_path.read_text())
                    info = PackageInfo(
                        app_id=data["app_id"],
                        name=data["name"],
                        version=data.get("version", "1.0.0"),
                        author=data.get("author", ""),
                        description=data.get("description", ""),
                        permissions=data.get("permissions", []),
                    )
                    # Calculate installed size
                    info.size_bytes = sum(
                        f.stat().st_size
                        for f in app_dir.rglob("*") if f.is_file()
                    )
                    self._installed[info.app_id] = info
                except (json.JSONDecodeError, KeyError) as e:
                    logger.warning("Invalid manifest in %s: %s", app_dir, e)

    def verify(self, package_path: str) -> PackageInfo:
        """
        Verify a .cpk package without installing.

        Returns PackageInfo if valid, raises PackageError if not.
        """
        path = Path(package_path)
        if not path.exists():
            raise PackageError(f"Package not found: {path}")

        if not path.suffix == ".cpk" and not tarfile.is_tarfile(str(path)):
            raise PackageError(f"Not a valid package: {path}")

        try:
            with tarfile.open(str(path), "r:gz") as tar:
                # Check for manifest
                names = tar.getnames()
                manifest_name = None
                for n in names:
                    if n == "manifest.json" or n.endswith("/manifest.json"):
                        manifest_name = n
                        break

                if not manifest_name:
                    raise PackageError("Missing manifest.json")

                # Parse manifest
                f = tar.extractfile(manifest_name)
                if not f:
                    raise PackageError("Cannot read manifest.json")
                data = json.loads(f.read())

                # Validate required fields
                missing = self.REQUIRED_MANIFEST_KEYS - set(data.keys())
                if missing:
                    raise PackageError(f"Manifest missing fields: {missing}")

                # Security: check for path traversal
                for name in names:
                    if name.startswith("/") or ".." in name:
                        raise PackageError(f"Unsafe path in package: {name}")

                return PackageInfo(
                    app_id=data["app_id"],
                    name=data["name"],
                    version=data.get("version", "1.0.0"),
                    author=data.get("author", ""),
                    description=data.get("description", ""),
                    permissions=data.get("permissions", []),
                    size_bytes=sum(m.size for m in tar.getmembers()),
                )

        except tarfile.TarError as e:
            raise PackageError(f"Invalid package archive: {e}")

    def install(self, package_path: str, force: bool = False) -> PackageInfo:
        """
        Install a .cpk package.

        Extracts to apps_dir/{app_id}/ and registers the package.
        """
        info = self.verify(package_path)

        if info.app_id in self._installed and not force:
            raise PackageError(
                f"Already installed: {info.app_id}. Use force=True to overwrite."
            )

        target_dir = self.apps_dir / info.app_id
        target_dir.mkdir(parents=True, exist_ok=True)

        try:
            with tarfile.open(package_path, "r:gz") as tar:
                tar.extractall(path=str(target_dir))
        except tarfile.TarError as e:
            # Clean up on failure
            if target_dir.exists():
                shutil.rmtree(target_dir)
            raise PackageError(f"Extraction failed: {e}")

        # Create data directory
        data_dir = self.data_dir / info.app_id / "data"
        data_dir.mkdir(parents=True, exist_ok=True)

        info.installed_at = time.time()
        self._installed[info.app_id] = info

        logger.info("Installed: %s v%s", info.name, info.version)
        return info

    def uninstall(self, app_id: str, keep_data: bool = False) -> bool:
        """
        Uninstall a package.

        Removes the app directory and optionally its data.
        """
        if app_id not in self._installed:
            raise PackageError(f"Not installed: {app_id}")

        # Remove app files
        app_dir = self.apps_dir / app_id
        if app_dir.exists():
            shutil.rmtree(app_dir)

        # Remove data unless asked to keep
        if not keep_data:
            data_dir = self.data_dir / app_id
            if data_dir.exists():
                shutil.rmtree(data_dir)

        del self._installed[app_id]

        logger.info("Uninstalled: %s", app_id)
        return True

    # --- Queries ---

    def is_installed(self, app_id: str) -> bool:
        return app_id in self._installed

    def get_info(self, app_id: str) -> PackageInfo | None:
        return self._installed.get(app_id)

    def list_installed(self) -> list[PackageInfo]:
        return list(self._installed.values())

    @property
    def installed_count(self) -> int:
        return len(self._installed)
