"""
Storage bridge service — connects the Bridge API to the storage manager.
"""

import asyncio
import logging
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "../../storage-manager"))

from event_bus import EventBus
from storage_manager import StorageManager

logger = logging.getLogger("bridge.storage")


class StorageBridgeService:
    """Bridge service for storage operations."""

    def __init__(self, event_bus: EventBus):
        self.event_bus = event_bus
        self.manager = StorageManager(event_bus)

    async def handle_usage(self, body: dict) -> dict:
        """Get storage usage for all partitions."""
        return self.manager.get_usage()

    async def handle_user_dirs(self, body: dict) -> dict:
        """Get user directory info."""
        return self.manager.get_user_dirs()

    async def handle_list_files(self, body: dict) -> list:
        """List files in a directory."""
        directory = body.get("path")
        if not directory:
            raise ValueError("Missing required field: path")
        return self.manager.list_files(directory)

    async def handle_read_file(self, body: dict) -> dict:
        """Read a file's contents."""
        file_path = body.get("path")
        if not file_path:
            raise ValueError("Missing required field: path")
        return self.manager.read_file(file_path)

    async def handle_write_file(self, body: dict) -> dict:
        """Write content to a file."""
        file_path = body.get("path")
        content = body.get("content")
        if not file_path or content is None:
            raise ValueError("Missing required fields: path, content")
        return self.manager.write_file(file_path, content)

    async def handle_delete_file(self, body: dict) -> dict:
        """Delete a file or directory."""
        file_path = body.get("path")
        if not file_path:
            raise ValueError("Missing required field: path")
        return self.manager.delete_file(file_path)
