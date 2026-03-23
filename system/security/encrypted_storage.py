"""
Claude-OS Encrypted Storage

Manages full-disk encryption and per-user encrypted partitions using
LUKS (Linux Unified Key Setup) via dm-crypt.

Boot flow:
    1. Root filesystem boots (unencrypted /boot + encrypted /)
    2. User prompted for passphrase (or uses TPM-backed key)
    3. LUKS volume unlocked, user data mounted at /home/user

Features:
- LUKS2 encryption for user data partition
- Passphrase and keyfile support
- Secure key storage in kernel keyring
- Encrypted swap
- Remote wipe capability (destroy LUKS header)
"""

import asyncio
import logging
import os
import subprocess
from pathlib import Path

logger = logging.getLogger("security.encryption")

LUKS_HEADER_BACKUP = "/var/lib/claude-os/security/luks-header.bak"
KEYRING_DESC = "claude-os:user-data"


class EncryptedStorageManager:
    """
    Manages LUKS-encrypted storage volumes.

    Handles volume creation, unlocking, locking, and key management.
    """

    def __init__(self):
        self._unlocked_volumes: dict[str, str] = {}  # name -> mount_point

    # --- Volume Management ---

    def create_encrypted_volume(self, device: str, passphrase: str,
                                label: str = "claude-os-data") -> dict:
        """
        Initialize LUKS encryption on a block device.

        WARNING: This destroys all data on the device.

        Args:
            device: Block device path (e.g., /dev/sda2)
            passphrase: Encryption passphrase
            label: LUKS volume label
        """
        if not os.path.exists(device):
            raise FileNotFoundError(f"Device not found: {device}")

        logger.info("Initializing LUKS on %s", device)

        # Format with LUKS2
        self._run_cryptsetup([
            "luksFormat",
            "--type", "luks2",
            "--cipher", "aes-xts-plain64",
            "--key-size", "512",
            "--hash", "sha512",
            "--iter-time", "5000",
            "--label", label,
            "--batch-mode",
            device,
        ], passphrase=passphrase)

        # Backup LUKS header
        self._backup_header(device)

        return {
            "device": device,
            "label": label,
            "cipher": "aes-xts-plain64",
            "key_size": 512,
            "status": "created",
        }

    def unlock(self, device: str, passphrase: str,
               name: str = "claude-data") -> dict:
        """
        Unlock a LUKS volume and make it available.

        Args:
            device: Encrypted block device
            passphrase: Decryption passphrase
            name: Mapper name (appears as /dev/mapper/<name>)
        """
        mapper_path = f"/dev/mapper/{name}"

        if os.path.exists(mapper_path):
            logger.info("Volume already unlocked: %s", name)
            return {"status": "already_unlocked", "mapper": mapper_path}

        logger.info("Unlocking LUKS volume: %s -> %s", device, name)

        self._run_cryptsetup([
            "luksOpen",
            device,
            name,
        ], passphrase=passphrase)

        # Store key in kernel keyring for session
        self._store_key_in_keyring(name, passphrase)

        self._unlocked_volumes[name] = mapper_path

        return {
            "status": "unlocked",
            "mapper": mapper_path,
            "name": name,
        }

    def lock(self, name: str = "claude-data") -> dict:
        """Lock (close) a LUKS volume."""
        mapper_path = f"/dev/mapper/{name}"

        if not os.path.exists(mapper_path):
            return {"status": "not_unlocked"}

        logger.info("Locking LUKS volume: %s", name)

        # Unmount first if mounted
        self._unmount_mapper(mapper_path)

        self._run_cryptsetup(["luksClose", name])
        self._unlocked_volumes.pop(name, None)

        # Remove key from keyring
        self._clear_key_from_keyring(name)

        return {"status": "locked", "name": name}

    def mount_encrypted(self, name: str = "claude-data",
                        mount_point: str = "/home/user") -> dict:
        """Mount an unlocked LUKS volume."""
        mapper_path = f"/dev/mapper/{name}"

        if not os.path.exists(mapper_path):
            raise RuntimeError(f"Volume not unlocked: {name}")

        os.makedirs(mount_point, exist_ok=True)

        subprocess.run(
            ["mount", mapper_path, mount_point],
            check=True, capture_output=True,
        )

        logger.info("Mounted %s at %s", mapper_path, mount_point)
        return {"status": "mounted", "mount_point": mount_point}

    # --- Key Management ---

    def add_key(self, device: str, existing_passphrase: str,
                new_passphrase: str) -> dict:
        """Add an additional passphrase to a LUKS volume."""
        # LUKS supports up to 8 key slots
        proc = subprocess.run(
            ["cryptsetup", "luksAddKey", device, "--batch-mode"],
            input=f"{existing_passphrase}\n{new_passphrase}\n".encode(),
            capture_output=True,
        )

        if proc.returncode != 0:
            raise RuntimeError(f"Failed to add key: {proc.stderr.decode()}")

        logger.info("Added new key slot to %s", device)
        return {"status": "key_added"}

    def remove_key(self, device: str, passphrase: str) -> dict:
        """Remove a passphrase from a LUKS volume."""
        self._run_cryptsetup([
            "luksRemoveKey",
            "--batch-mode",
            device,
        ], passphrase=passphrase)

        logger.info("Removed key slot from %s", device)
        return {"status": "key_removed"}

    def change_passphrase(self, device: str, old_passphrase: str,
                          new_passphrase: str) -> dict:
        """Change the passphrase on a LUKS volume."""
        proc = subprocess.run(
            ["cryptsetup", "luksChangeKey", device, "--batch-mode"],
            input=f"{old_passphrase}\n{new_passphrase}\n".encode(),
            capture_output=True,
        )

        if proc.returncode != 0:
            raise RuntimeError(f"Failed to change key: {proc.stderr.decode()}")

        logger.info("Changed passphrase on %s", device)
        return {"status": "passphrase_changed"}

    # --- Security Operations ---

    def get_volume_info(self, device: str) -> dict:
        """Get LUKS volume information."""
        proc = subprocess.run(
            ["cryptsetup", "luksDump", device],
            capture_output=True, text=True,
        )

        if proc.returncode != 0:
            raise RuntimeError(f"Not a LUKS device: {device}")

        info = {"device": device, "raw_dump": proc.stdout}

        # Parse key fields
        for line in proc.stdout.split("\n"):
            line = line.strip()
            if line.startswith("Cipher:"):
                info["cipher"] = line.split(":", 1)[1].strip()
            elif line.startswith("Key size:"):
                info["key_size"] = line.split(":", 1)[1].strip()
            elif line.startswith("Version:"):
                info["version"] = line.split(":", 1)[1].strip()
            elif line.startswith("Label:"):
                info["label"] = line.split(":", 1)[1].strip()

        # Don't include raw dump in API response
        del info["raw_dump"]
        return info

    def emergency_wipe(self, device: str) -> dict:
        """
        Emergency wipe — destroys the LUKS header, making data
        permanently irrecoverable.

        USE WITH EXTREME CAUTION.
        """
        logger.critical("EMERGENCY WIPE initiated on %s", device)

        # Overwrite LUKS header (first 16MB) with random data
        subprocess.run(
            ["dd", "if=/dev/urandom", f"of={device}",
             "bs=1M", "count=16", "conv=notrunc"],
            capture_output=True,
        )

        return {"status": "wiped", "device": device}

    def setup_encrypted_swap(self, device: str) -> dict:
        """
        Set up encrypted swap with a random key (re-encrypted each boot).

        The swap key is never stored — generated fresh from /dev/urandom
        at each boot, so swap contents are irrecoverable after shutdown.
        """
        logger.info("Setting up encrypted swap on %s", device)

        # Add to /etc/crypttab for auto-setup at boot
        crypttab_line = f"swap {device} /dev/urandom swap,cipher=aes-xts-plain64,size=256\n"

        crypttab = Path("/etc/crypttab")
        existing = crypttab.read_text() if crypttab.exists() else ""

        if "swap" not in existing:
            with open(crypttab, "a") as f:
                f.write(crypttab_line)

        return {"status": "configured", "device": device}

    # --- Internal ---

    def _run_cryptsetup(self, args: list[str], passphrase: str = None):
        """Run a cryptsetup command."""
        cmd = ["cryptsetup"] + args
        proc = subprocess.run(
            cmd,
            input=passphrase.encode() if passphrase else None,
            capture_output=True,
        )

        if proc.returncode != 0:
            error = proc.stderr.decode().strip()
            raise RuntimeError(f"cryptsetup failed: {error}")

    def _backup_header(self, device: str):
        """Backup the LUKS header for recovery."""
        os.makedirs(os.path.dirname(LUKS_HEADER_BACKUP), exist_ok=True)
        subprocess.run(
            ["cryptsetup", "luksHeaderBackup", device,
             "--header-backup-file", LUKS_HEADER_BACKUP],
            capture_output=True,
        )
        os.chmod(LUKS_HEADER_BACKUP, 0o600)
        logger.info("LUKS header backed up to %s", LUKS_HEADER_BACKUP)

    def _unmount_mapper(self, mapper_path: str):
        """Unmount a mapper device if mounted."""
        subprocess.run(
            ["umount", mapper_path],
            capture_output=True,
        )

    def _store_key_in_keyring(self, name: str, passphrase: str):
        """Store the encryption key in the kernel session keyring."""
        try:
            subprocess.run(
                ["keyctl", "add", "user", f"{KEYRING_DESC}:{name}",
                 passphrase, "@s"],
                capture_output=True,
            )
        except FileNotFoundError:
            logger.debug("keyctl not available, skipping keyring storage")

    def _clear_key_from_keyring(self, name: str):
        """Remove the encryption key from the kernel keyring."""
        try:
            result = subprocess.run(
                ["keyctl", "search", "@s", "user", f"{KEYRING_DESC}:{name}"],
                capture_output=True, text=True,
            )
            if result.returncode == 0:
                key_id = result.stdout.strip()
                subprocess.run(["keyctl", "unlink", key_id, "@s"],
                               capture_output=True)
        except FileNotFoundError:
            pass
