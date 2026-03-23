"""
Saved network credential storage.

Stores WiFi network credentials (SSID, password, security type) in a JSON file.
Passwords are encrypted at rest using a machine-specific key derived from
/etc/machine-id.
"""

import base64
import hashlib
import json
import logging
import os
from pathlib import Path

logger = logging.getLogger("wifi-manager.storage")


class NetworkStorage:
    """Manages persistent storage of saved WiFi network credentials."""

    def __init__(self, storage_path: Path):
        self.storage_path = storage_path
        self.networks: dict[str, dict] = {}
        self._key = self._derive_key()

    def load(self):
        """Load saved networks from disk."""
        if not self.storage_path.exists():
            self.networks = {}
            return

        try:
            with open(self.storage_path, "r") as f:
                data = json.load(f)

            self.networks = {}
            for ssid, entry in data.items():
                decrypted = dict(entry)
                if "password" in decrypted and decrypted["password"]:
                    decrypted["password"] = self._decrypt(decrypted["password"])
                self.networks[ssid] = decrypted

            logger.info("Loaded %d saved networks", len(self.networks))
        except (json.JSONDecodeError, OSError) as e:
            logger.error("Failed to load saved networks: %s", e)
            self.networks = {}

    def save(self):
        """Persist saved networks to disk."""
        data = {}
        for ssid, entry in self.networks.items():
            encrypted = dict(entry)
            if "password" in encrypted and encrypted["password"]:
                encrypted["password"] = self._encrypt(encrypted["password"])
            data[ssid] = encrypted

        try:
            self.storage_path.parent.mkdir(parents=True, exist_ok=True)
            with open(self.storage_path, "w") as f:
                json.dump(data, f, indent=2)
            # Restrict file permissions to root only
            os.chmod(self.storage_path, 0o600)
            logger.info("Saved %d networks to disk", len(self.networks))
        except OSError as e:
            logger.error("Failed to save networks: %s", e)

    def save_network(self, ssid: str, password: str = None,
                     security: str = "wpa2"):
        """Save or update a network's credentials."""
        self.networks[ssid] = {
            "ssid": ssid,
            "password": password,
            "security": security,
            "auto_connect": True,
        }
        self.save()
        logger.info("Saved network '%s'", ssid)

    def remove_network(self, ssid: str) -> bool:
        """Remove a saved network. Returns True if it existed."""
        if ssid in self.networks:
            del self.networks[ssid]
            self.save()
            logger.info("Removed network '%s'", ssid)
            return True
        logger.warning("Network '%s' not found in saved networks", ssid)
        return False

    def get_network(self, ssid: str) -> dict | None:
        """Get saved credentials for a network, or None."""
        return self.networks.get(ssid)

    def list_networks(self) -> list[dict]:
        """List all saved networks (without passwords)."""
        result = []
        for ssid, entry in self.networks.items():
            safe = {
                "ssid": ssid,
                "security": entry.get("security", "unknown"),
                "auto_connect": entry.get("auto_connect", True),
            }
            result.append(safe)
        return result

    def _derive_key(self) -> bytes:
        """
        Derive an encryption key from the machine ID.

        This is not meant to be cryptographically strong against a local
        attacker with root access — it prevents casual reading of passwords
        from the JSON file and ensures credentials aren't portable between
        devices.
        """
        machine_id = "claude-os-default"
        try:
            machine_id = Path("/etc/machine-id").read_text().strip()
        except OSError:
            logger.warning("Could not read /etc/machine-id, using default key")

        return hashlib.sha256(
            f"claude-os-wifi-{machine_id}".encode()
        ).digest()

    def _encrypt(self, plaintext: str) -> str:
        """Simple XOR encryption with the machine key (base64 encoded)."""
        key = self._key
        data = plaintext.encode()
        encrypted = bytes(b ^ key[i % len(key)] for i, b in enumerate(data))
        return base64.b64encode(encrypted).decode()

    def _decrypt(self, ciphertext: str) -> str:
        """Decrypt a value encrypted with _encrypt."""
        key = self._key
        data = base64.b64decode(ciphertext)
        decrypted = bytes(b ^ key[i % len(key)] for i, b in enumerate(data))
        return decrypted.decode()
