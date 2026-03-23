"""
Claude-OS Security Module

Provides app sandboxing, encrypted storage, secure boot verification,
and TLS certificate pinning for API communication.
"""

from sandbox import Sandbox, SandboxProfile
from encrypted_storage import EncryptedStorageManager
from secure_boot import SecureBootManager
from tls_pinning import TLSPinningManager

__all__ = [
    "Sandbox",
    "SandboxProfile",
    "EncryptedStorageManager",
    "SecureBootManager",
    "TLSPinningManager",
]
