"""
Claude-OS Over-The-Air (OTA) Update System

Manages downloading, verifying, and applying system updates.
Uses an A/B partition scheme for safe, rollback-capable updates.

Update flow:
    1. Check update server for new version
    2. Download update package (delta or full image)
    3. Verify signature (RSA-4096 + SHA-512)
    4. Write to inactive partition (A/B scheme)
    5. Mark inactive partition as bootable
    6. Reboot into updated partition
    7. If boot fails → automatic rollback to previous partition

A/B partitions:
    Slot A: /dev/mmcblk0p3  (rootfs-a)
    Slot B: /dev/mmcblk0p4  (rootfs-b)
    Active slot tracked in /etc/claude-os/boot-slot
"""

import asyncio
import hashlib
import json
import logging
import os
import subprocess
import time
from dataclasses import dataclass
from pathlib import Path
from urllib.request import urlopen, Request
from urllib.error import URLError

logger = logging.getLogger("ota")

CONFIG_DIR = Path(os.environ.get("CLAUDE_OS_CONFIG", "/etc/claude-os"))
DATA_DIR = Path(os.environ.get("CLAUDE_OS_DATA", "/var/lib/claude-os"))
OTA_DIR = DATA_DIR / "ota"
SLOT_FILE = CONFIG_DIR / "boot-slot"

UPDATE_SERVER = "https://updates.claude-os.dev"


@dataclass
class UpdateInfo:
    """Metadata about an available update."""
    version: str
    build_id: str
    size_bytes: int
    sha256: str
    signature_url: str
    download_url: str
    changelog: str
    release_date: str
    is_delta: bool = False
    min_version: str = ""


class OTAUpdater:
    """
    Manages the OTA update lifecycle.

    Uses A/B partitioning for safe updates with automatic rollback.
    """

    SLOTS = {"a": "/dev/mmcblk0p3", "b": "/dev/mmcblk0p4"}

    def __init__(self, event_bus=None):
        self.event_bus = event_bus
        self.current_version = self._read_version()
        self.active_slot = self._read_active_slot()
        self._download_progress = 0
        self._update_in_progress = False

    # --- Check & Download ---

    async def check_for_update(self) -> dict:
        """Check the update server for a new version."""
        logger.info("Checking for updates (current: %s)", self.current_version)

        try:
            url = f"{UPDATE_SERVER}/api/v1/check"
            payload = json.dumps({
                "current_version": self.current_version,
                "device": "qemu-aarch64",
                "slot": self.active_slot,
            }).encode()

            req = Request(
                url, data=payload, method="POST",
                headers={"Content-Type": "application/json"},
            )

            def fetch():
                with urlopen(req, timeout=30) as resp:
                    return json.loads(resp.read().decode())

            data = await asyncio.to_thread(fetch)

            if data.get("update_available"):
                info = UpdateInfo(
                    version=data["version"],
                    build_id=data["build_id"],
                    size_bytes=data["size_bytes"],
                    sha256=data["sha256"],
                    signature_url=data["signature_url"],
                    download_url=data["download_url"],
                    changelog=data.get("changelog", ""),
                    release_date=data.get("release_date", ""),
                    is_delta=data.get("is_delta", False),
                    min_version=data.get("min_version", ""),
                )
                return {
                    "update_available": True,
                    "version": info.version,
                    "size_mb": info.size_bytes // (1024 * 1024),
                    "changelog": info.changelog,
                    "is_delta": info.is_delta,
                }
            else:
                return {"update_available": False, "current": self.current_version}

        except (URLError, json.JSONDecodeError, KeyError) as e:
            logger.error("Update check failed: %s", e)
            return {"update_available": False, "error": str(e)}

    async def download_and_apply(self, update_url: str, expected_sha256: str,
                                 signature_url: str) -> dict:
        """
        Download an update, verify it, and write to the inactive slot.

        Args:
            update_url: URL to download the update image
            expected_sha256: Expected SHA-256 hash of the image
            signature_url: URL to download the signature file
        """
        if self._update_in_progress:
            return {"error": "Update already in progress"}

        self._update_in_progress = True
        self._download_progress = 0
        inactive_slot = self._get_inactive_slot()

        try:
            OTA_DIR.mkdir(parents=True, exist_ok=True)
            image_path = OTA_DIR / "update.img"
            sig_path = OTA_DIR / "update.img.sig"

            # Step 1: Download image
            logger.info("Downloading update from %s", update_url)
            if self.event_bus:
                await self.event_bus.emit("ota.downloading", {"progress": 0})

            await self._download_file(update_url, image_path)

            # Step 2: Download signature
            await self._download_file(signature_url, sig_path)

            # Step 3: Verify SHA-256
            logger.info("Verifying update integrity...")
            actual_hash = self._sha256_file(image_path)
            if actual_hash != expected_sha256:
                raise ValueError(
                    f"Hash mismatch: expected {expected_sha256}, "
                    f"got {actual_hash}"
                )

            # Step 4: Verify signature
            logger.info("Verifying update signature...")
            self._verify_signature(image_path, sig_path)

            # Step 5: Write to inactive partition
            device = self.SLOTS[inactive_slot]
            logger.info("Writing update to %s (slot %s)", device, inactive_slot)
            if self.event_bus:
                await self.event_bus.emit("ota.installing", {
                    "slot": inactive_slot,
                })

            await self._write_image(image_path, device)

            # Step 6: Mark inactive slot as next boot target
            self._set_next_boot_slot(inactive_slot)

            # Clean up download
            image_path.unlink(missing_ok=True)
            sig_path.unlink(missing_ok=True)

            if self.event_bus:
                await self.event_bus.emit("ota.ready", {
                    "slot": inactive_slot,
                    "reboot_required": True,
                })

            logger.info("Update installed to slot %s — reboot to activate",
                         inactive_slot)

            return {
                "status": "installed",
                "slot": inactive_slot,
                "reboot_required": True,
            }

        except Exception as e:
            logger.error("Update failed: %s", e)
            if self.event_bus:
                await self.event_bus.emit("ota.failed", {"error": str(e)})
            return {"status": "failed", "error": str(e)}
        finally:
            self._update_in_progress = False

    async def _download_file(self, url: str, dest: Path):
        """Download a file with progress tracking."""
        def _do_download():
            req = Request(url)
            with urlopen(req, timeout=600) as resp:
                total = int(resp.headers.get("Content-Length", 0))
                downloaded = 0
                chunk_size = 256 * 1024  # 256KB chunks

                with open(dest, "wb") as f:
                    while True:
                        chunk = resp.read(chunk_size)
                        if not chunk:
                            break
                        f.write(chunk)
                        downloaded += len(chunk)
                        if total:
                            self._download_progress = int(
                                downloaded / total * 100
                            )

        await asyncio.to_thread(_do_download)

    async def _write_image(self, image_path: Path, device: str):
        """Write an image to a block device."""
        def _do_write():
            subprocess.run(
                ["dd", f"if={image_path}", f"of={device}",
                 "bs=4M", "conv=fsync"],
                check=True, capture_output=True,
            )
            subprocess.run(["sync"], check=True, capture_output=True)

        await asyncio.to_thread(_do_write)

    def _verify_signature(self, image_path: Path, sig_path: Path):
        """Verify the update image signature."""
        pub_key = CONFIG_DIR / "ota-signing.pub"
        if not pub_key.exists():
            logger.warning("OTA signing key not found, skipping verification")
            return

        result = subprocess.run([
            "openssl", "dgst", "-sha512",
            "-verify", str(pub_key),
            "-signature", str(sig_path),
            str(image_path),
        ], capture_output=True, text=True)

        if result.returncode != 0:
            raise ValueError("Update signature verification FAILED")

    # --- A/B Slot Management ---

    def _get_inactive_slot(self) -> str:
        """Get the inactive slot (the one we'll write updates to)."""
        return "b" if self.active_slot == "a" else "a"

    def _read_active_slot(self) -> str:
        """Read which slot is currently active."""
        try:
            return SLOT_FILE.read_text().strip()
        except OSError:
            return "a"

    def _set_next_boot_slot(self, slot: str):
        """Mark a slot as the next boot target."""
        next_boot = CONFIG_DIR / "next-boot-slot"
        next_boot.write_text(slot)
        logger.info("Next boot slot set to: %s", slot)

    def _read_version(self) -> str:
        """Read the current OS version."""
        version_file = Path("/etc/claude-os/version")
        try:
            return version_file.read_text().strip()
        except OSError:
            return "0.1.0"

    # --- Rollback ---

    async def rollback(self) -> dict:
        """Roll back to the previous slot."""
        previous = self._get_inactive_slot()
        self._set_next_boot_slot(previous)
        logger.warning("Rollback requested — next boot: slot %s", previous)

        return {
            "status": "rollback_scheduled",
            "target_slot": previous,
            "reboot_required": True,
        }

    def mark_boot_successful(self):
        """
        Mark the current boot as successful.

        Called after the system boots and all services are healthy.
        Prevents automatic rollback on next boot.
        """
        SLOT_FILE.write_text(self.active_slot)
        success_marker = CONFIG_DIR / "boot-success"
        success_marker.write_text(str(time.time()))
        logger.info("Boot marked successful (slot %s)", self.active_slot)

    # --- Status ---

    def get_status(self) -> dict:
        """Get OTA update status."""
        return {
            "current_version": self.current_version,
            "active_slot": self.active_slot,
            "inactive_slot": self._get_inactive_slot(),
            "update_in_progress": self._update_in_progress,
            "download_progress": self._download_progress,
        }

    @staticmethod
    def _sha256_file(path: Path) -> str:
        """Calculate SHA-256 hash of a file."""
        h = hashlib.sha256()
        with open(path, "rb") as f:
            while True:
                chunk = f.read(1024 * 1024)
                if not chunk:
                    break
                h.update(chunk)
        return h.hexdigest()
