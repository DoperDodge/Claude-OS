"""
Permission manager for the Bridge API.

Controls which actions the Claude app is allowed to perform.
Users grant/revoke permissions through the settings UI or CLI.

Permission format: "category.action"
Examples: "wifi.connect", "power.shutdown", "audio.volume"
"""

import json
import logging
import os
from pathlib import Path

logger = logging.getLogger("bridge.permissions")

# Default permissions — safe actions are granted by default
DEFAULT_PERMISSIONS = {
    # WiFi
    "wifi.scan": {"granted": True, "description": "Scan for WiFi networks"},
    "wifi.status": {"granted": True, "description": "View WiFi connection status"},
    "wifi.connect": {"granted": True, "description": "Connect to WiFi networks"},
    "wifi.disconnect": {"granted": True, "description": "Disconnect from WiFi"},
    "wifi.modify": {"granted": True, "description": "Save/forget WiFi networks"},

    # System
    "system.info": {"granted": True, "description": "View system information"},
    "system.battery": {"granted": True, "description": "View battery status"},
    "system.display": {"granted": True, "description": "Adjust screen brightness"},

    # Power — requires explicit user consent
    "power.shutdown": {"granted": False, "description": "Shut down the device"},
    "power.reboot": {"granted": False, "description": "Reboot the device"},
    "power.suspend": {"granted": True, "description": "Suspend/sleep the device"},

    # Audio
    "audio.volume": {"granted": True, "description": "Adjust volume"},
    "audio.mute": {"granted": True, "description": "Mute/unmute audio"},

    # Sensitive — never granted by default
    "messages.read": {"granted": False, "description": "Read notifications/messages"},
    "location.access": {"granted": False, "description": "Access device location"},
    "camera.access": {"granted": False, "description": "Access camera"},
    "files.read": {"granted": False, "description": "Read files on device"},
    "files.write": {"granted": False, "description": "Write/delete files on device"},
}


class PermissionManager:
    """Manages permissions for Bridge API actions."""

    def __init__(self, config_path: Path):
        self.config_path = config_path
        self.permissions: dict[str, dict] = {}

    def load(self):
        """Load permissions from disk, merging with defaults."""
        self.permissions = dict(DEFAULT_PERMISSIONS)

        if self.config_path.exists():
            try:
                with open(self.config_path, "r") as f:
                    saved = json.load(f)
                # Overlay saved permissions on top of defaults
                for key, value in saved.items():
                    if key in self.permissions:
                        self.permissions[key]["granted"] = value.get(
                            "granted", self.permissions[key]["granted"]
                        )
                    else:
                        self.permissions[key] = value
                logger.info("Loaded permissions from %s", self.config_path)
            except (json.JSONDecodeError, OSError) as e:
                logger.error("Failed to load permissions: %s", e)
        else:
            logger.info("Using default permissions")

    def save(self):
        """Persist current permissions to disk."""
        try:
            self.config_path.parent.mkdir(parents=True, exist_ok=True)
            with open(self.config_path, "w") as f:
                json.dump(self.permissions, f, indent=2)
            os.chmod(self.config_path, 0o600)
        except OSError as e:
            logger.error("Failed to save permissions: %s", e)

    def check(self, permission: str) -> bool:
        """Check if a permission is granted."""
        entry = self.permissions.get(permission)
        if entry is None:
            logger.warning("Unknown permission checked: %s (denying)", permission)
            return False
        return entry.get("granted", False)

    def grant(self, permission: str) -> bool:
        """Grant a permission. Returns True if it exists."""
        if permission in self.permissions:
            self.permissions[permission]["granted"] = True
            self.save()
            logger.info("Permission granted: %s", permission)
            return True
        return False

    def revoke(self, permission: str) -> bool:
        """Revoke a permission. Returns True if it exists."""
        if permission in self.permissions:
            self.permissions[permission]["granted"] = False
            self.save()
            logger.info("Permission revoked: %s", permission)
            return True
        return False

    def list_all(self) -> dict:
        """List all permissions grouped by category."""
        categories = {}
        for key, entry in self.permissions.items():
            category = key.split(".")[0]
            if category not in categories:
                categories[category] = []
            categories[category].append({
                "permission": key,
                "granted": entry["granted"],
                "description": entry.get("description", ""),
            })
        return categories
