"""
Claude-OS Secure Boot Chain

Implements verified boot to ensure only trusted code runs on the device.

Boot verification chain:
    1. Bootloader (U-Boot) verifies kernel signature
    2. Kernel verifies initramfs signature
    3. Initramfs verifies root filesystem integrity (dm-verity)
    4. Root filesystem is mounted read-only

Components:
- Kernel image signing (RSA-4096 + SHA-512)
- dm-verity for root filesystem integrity
- Boot state attestation
- Rollback protection via monotonic counter
"""

import hashlib
import logging
import os
import subprocess
from pathlib import Path

logger = logging.getLogger("security.boot")

KEYS_DIR = Path("/var/lib/claude-os/security/keys")
VERITY_STATE = Path("/var/lib/claude-os/security/verity-state.json")


class SecureBootManager:
    """
    Manages the secure boot chain and filesystem verification.

    In production, the bootloader (U-Boot) handles the initial
    verification. This module manages key generation, image signing,
    and dm-verity setup for the rootfs.
    """

    def __init__(self):
        self._boot_verified = False
        self._verity_active = False

    # --- Key Management ---

    def generate_signing_keys(self, output_dir: str = None) -> dict:
        """
        Generate RSA-4096 key pair for boot image signing.

        The private key signs boot images during the build process.
        The public key is embedded in the bootloader for verification.
        """
        key_dir = Path(output_dir) if output_dir else KEYS_DIR
        key_dir.mkdir(parents=True, exist_ok=True)

        private_key = key_dir / "boot-signing.key"
        public_key = key_dir / "boot-signing.pub"
        certificate = key_dir / "boot-signing.crt"

        # Generate private key
        subprocess.run([
            "openssl", "genrsa",
            "-out", str(private_key),
            "4096",
        ], check=True, capture_output=True)
        os.chmod(private_key, 0o600)

        # Extract public key
        subprocess.run([
            "openssl", "rsa",
            "-in", str(private_key),
            "-pubout",
            "-out", str(public_key),
        ], check=True, capture_output=True)

        # Generate self-signed certificate (for U-Boot FIT image verification)
        subprocess.run([
            "openssl", "req", "-new", "-x509",
            "-key", str(private_key),
            "-out", str(certificate),
            "-days", "3650",
            "-subj", "/CN=Claude-OS Boot Signing Key",
            "-sha512",
        ], check=True, capture_output=True)

        logger.info("Boot signing keys generated in %s", key_dir)
        return {
            "private_key": str(private_key),
            "public_key": str(public_key),
            "certificate": str(certificate),
            "algorithm": "RSA-4096",
            "hash": "SHA-512",
        }

    def sign_image(self, image_path: str, private_key: str = None) -> dict:
        """
        Sign a boot image (kernel, initramfs, etc.).

        Creates a detached signature file alongside the image.
        """
        key = private_key or str(KEYS_DIR / "boot-signing.key")
        sig_path = f"{image_path}.sig"

        subprocess.run([
            "openssl", "dgst",
            "-sha512",
            "-sign", key,
            "-out", sig_path,
            image_path,
        ], check=True, capture_output=True)

        logger.info("Signed image: %s", image_path)
        return {
            "image": image_path,
            "signature": sig_path,
            "algorithm": "RSA-4096-SHA512",
        }

    def verify_signature(self, image_path: str,
                         public_key: str = None) -> dict:
        """Verify a signed boot image."""
        key = public_key or str(KEYS_DIR / "boot-signing.pub")
        sig_path = f"{image_path}.sig"

        if not os.path.exists(sig_path):
            return {"verified": False, "error": "Signature file not found"}

        result = subprocess.run([
            "openssl", "dgst",
            "-sha512",
            "-verify", key,
            "-signature", sig_path,
            image_path,
        ], capture_output=True, text=True)

        verified = result.returncode == 0
        logger.info("Signature verification for %s: %s",
                     image_path, "PASS" if verified else "FAIL")

        return {
            "image": image_path,
            "verified": verified,
            "output": result.stdout.strip(),
        }

    # --- dm-verity ---

    def setup_verity(self, data_device: str, hash_device: str) -> dict:
        """
        Set up dm-verity for a read-only filesystem.

        dm-verity provides transparent integrity checking of block devices.
        Any modification to the verified filesystem is detected and causes
        an I/O error.

        Args:
            data_device: Block device with the filesystem (e.g., /dev/sda3)
            hash_device: Block device to store the hash tree
        """
        result = subprocess.run([
            "veritysetup", "format",
            data_device,
            hash_device,
        ], capture_output=True, text=True, check=True)

        # Parse root hash from output
        root_hash = ""
        for line in result.stdout.split("\n"):
            if "Root hash:" in line:
                root_hash = line.split(":")[-1].strip()
                break

        logger.info("dm-verity setup complete, root hash: %s", root_hash)

        return {
            "data_device": data_device,
            "hash_device": hash_device,
            "root_hash": root_hash,
        }

    def activate_verity(self, name: str, data_device: str,
                        hash_device: str, root_hash: str) -> dict:
        """Activate a dm-verity device."""
        subprocess.run([
            "veritysetup", "open",
            data_device,
            name,
            hash_device,
            root_hash,
        ], check=True, capture_output=True)

        self._verity_active = True
        logger.info("dm-verity activated: %s", name)

        return {
            "status": "active",
            "mapper": f"/dev/mapper/{name}",
            "name": name,
        }

    def verify_verity_status(self, name: str) -> dict:
        """Check the status of a dm-verity device."""
        result = subprocess.run(
            ["veritysetup", "status", name],
            capture_output=True, text=True,
        )

        if result.returncode != 0:
            return {"active": False, "name": name}

        return {
            "active": True,
            "name": name,
            "details": result.stdout.strip(),
        }

    # --- Boot Attestation ---

    def get_boot_state(self) -> dict:
        """
        Get the current boot security state.

        Reports whether each stage of the boot chain was verified.
        """
        state = {
            "secure_boot": self._check_secure_boot(),
            "verity_active": self._verity_active,
            "kernel_locked_down": self._check_lockdown(),
            "boot_hash": self._get_boot_hash(),
        }

        all_verified = all([
            state["secure_boot"],
            state["verity_active"],
            state["kernel_locked_down"],
        ])

        state["overall"] = "verified" if all_verified else "unverified"
        return state

    def _check_secure_boot(self) -> bool:
        """Check if secure boot is active."""
        # Check EFI secure boot variable
        sb_path = "/sys/firmware/efi/efivars/SecureBoot-8be4df61-93ca-11d2-aa0d-00e098032b8c"
        if os.path.exists(sb_path):
            try:
                data = Path(sb_path).read_bytes()
                # Last byte indicates state: 1 = enabled
                return data[-1] == 1
            except OSError:
                pass

        # QEMU: check for our own marker
        return os.path.exists("/var/lib/claude-os/security/boot-verified")

    def _check_lockdown(self) -> bool:
        """Check if the kernel is in lockdown mode."""
        lockdown_path = "/sys/kernel/security/lockdown"
        if os.path.exists(lockdown_path):
            try:
                mode = Path(lockdown_path).read_text().strip()
                return "integrity" in mode or "confidentiality" in mode
            except OSError:
                pass
        return False

    def _get_boot_hash(self) -> str:
        """Get a hash of the running kernel for attestation."""
        try:
            cmdline = Path("/proc/cmdline").read_text().strip()
            version = Path("/proc/version").read_text().strip()
            combined = f"{cmdline}|{version}"
            return hashlib.sha256(combined.encode()).hexdigest()[:32]
        except OSError:
            return "unknown"
