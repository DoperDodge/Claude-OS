"""
WiFi connection manager.

Handles connecting to networks, disconnecting, monitoring connection state,
and automatic reconnection on signal loss.
"""

import asyncio
import logging
import subprocess

from storage import NetworkStorage

logger = logging.getLogger("wifi-manager.connection")

# How often to check connection health (seconds)
MONITOR_INTERVAL = 10

# How many consecutive failures before attempting reconnect
FAILURE_THRESHOLD = 3


class ConnectionManager:
    """Manages WiFi connections via wpa_supplicant."""

    def __init__(self, interface: str, storage: NetworkStorage):
        self.interface = interface
        self.storage = storage
        self._current_ssid: str | None = None
        self._failure_count = 0
        self._reconnecting = False

    async def connect(self, ssid: str, password: str = None,
                      security: str = "wpa2") -> bool:
        """
        Connect to a WiFi network.

        Args:
            ssid: Network name
            password: Network password (None for open networks)
            security: Security type (open, wep, wpa, wpa2, wpa3)

        Returns:
            True if connection succeeded
        """
        logger.info("Connecting to '%s' (security: %s)", ssid, security)

        # Remove any existing configuration for this network
        await self._remove_wpa_network(ssid)

        # Add network to wpa_supplicant
        net_id = await self._wpa_cli("add_network")
        if not net_id or not net_id.strip().isdigit():
            logger.error("Failed to add network")
            return False

        net_id = net_id.strip()

        # Configure the network
        await self._wpa_cli(f'set_network {net_id} ssid \\"{ssid}\\"')

        if security == "open":
            await self._wpa_cli(f"set_network {net_id} key_mgmt NONE")
        elif security in ("wpa", "wpa2"):
            await self._wpa_cli(f'set_network {net_id} psk \\"{password}\\"')
            await self._wpa_cli(f"set_network {net_id} key_mgmt WPA-PSK")
        elif security == "wpa3":
            await self._wpa_cli(f'set_network {net_id} psk \\"{password}\\"')
            await self._wpa_cli(f"set_network {net_id} key_mgmt SAE")
            await self._wpa_cli(f"set_network {net_id} ieee80211w 2")

        # Enable and select the network
        await self._wpa_cli(f"enable_network {net_id}")
        await self._wpa_cli(f"select_network {net_id}")

        # Wait for connection (up to 15 seconds)
        connected = await self._wait_for_connection(timeout=15)

        if connected:
            self._current_ssid = ssid
            self._failure_count = 0
            logger.info("Connected to '%s'", ssid)

            # Request DHCP lease
            await self._request_dhcp()
        else:
            logger.error("Failed to connect to '%s'", ssid)
            await self._wpa_cli(f"remove_network {net_id}")

        return connected

    async def disconnect(self) -> bool:
        """Disconnect from the current network."""
        if not self._current_ssid:
            logger.info("Not connected to any network")
            return True

        logger.info("Disconnecting from '%s'", self._current_ssid)
        await self._wpa_cli("disconnect")
        await self._release_dhcp()
        self._current_ssid = None
        self._failure_count = 0
        return True

    def is_connected(self) -> bool:
        """Check if currently connected to a network."""
        try:
            result = subprocess.run(
                ["wpa_cli", "-i", self.interface, "status"],
                capture_output=True, text=True, timeout=5,
            )
            return "wpa_state=COMPLETED" in result.stdout
        except (subprocess.TimeoutExpired, FileNotFoundError):
            return False

    def get_status(self) -> dict:
        """Get detailed connection status."""
        try:
            result = subprocess.run(
                ["wpa_cli", "-i", self.interface, "status"],
                capture_output=True, text=True, timeout=5,
            )
            status = self._parse_status(result.stdout)
            status["connected"] = status.get("wpa_state") == "COMPLETED"

            # Get signal strength
            if status["connected"]:
                signal = self._get_signal_strength()
                status["signal_dbm"] = signal
                status["signal_quality"] = self._dbm_to_quality(signal)

            return status
        except (subprocess.TimeoutExpired, FileNotFoundError):
            return {"connected": False, "error": "wpa_supplicant not available"}

    async def monitor_loop(self):
        """
        Continuously monitor connection health and auto-reconnect.

        Runs as a background task for the lifetime of the daemon.
        """
        logger.info("Connection monitor started (interval: %ds)", MONITOR_INTERVAL)

        while True:
            await asyncio.sleep(MONITOR_INTERVAL)

            if self._reconnecting:
                continue

            if self._current_ssid and not self.is_connected():
                self._failure_count += 1
                logger.warning(
                    "Connection lost (failure %d/%d)",
                    self._failure_count, FAILURE_THRESHOLD,
                )

                if self._failure_count >= FAILURE_THRESHOLD:
                    await self._attempt_reconnect()
            else:
                self._failure_count = 0

    async def _attempt_reconnect(self):
        """Try to reconnect to the current or any known network."""
        self._reconnecting = True
        ssid = self._current_ssid

        logger.info("Attempting reconnect...")

        # First try the current network
        if ssid:
            saved = self.storage.get_network(ssid)
            if saved:
                success = await self.connect(
                    ssid, saved.get("password"), saved.get("security")
                )
                if success:
                    self._reconnecting = False
                    return

        # Try other saved networks
        from scanner import WiFiScanner
        scanner = WiFiScanner(self.interface)
        available = await scanner.scan()

        for net in available:
            saved = self.storage.get_network(net["ssid"])
            if saved:
                logger.info("Trying saved network '%s'", net["ssid"])
                success = await self.connect(
                    net["ssid"], saved.get("password"), saved.get("security")
                )
                if success:
                    self._reconnecting = False
                    return

        logger.warning("Reconnect failed — no known networks available")
        self._failure_count = 0
        self._reconnecting = False

    async def _wait_for_connection(self, timeout: int = 15) -> bool:
        """Poll wpa_supplicant until connected or timeout."""
        for _ in range(timeout):
            if self.is_connected():
                return True
            await asyncio.sleep(1)
        return False

    async def _request_dhcp(self):
        """Request a DHCP lease for the interface."""
        logger.info("Requesting DHCP lease on %s", self.interface)
        try:
            proc = await asyncio.create_subprocess_exec(
                "dhcpcd", self.interface,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
            )
            await proc.communicate()
        except FileNotFoundError:
            logger.warning("dhcpcd not found, skipping DHCP")

    async def _release_dhcp(self):
        """Release the DHCP lease."""
        try:
            proc = await asyncio.create_subprocess_exec(
                "dhcpcd", "-k", self.interface,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
            )
            await proc.communicate()
        except FileNotFoundError:
            pass

    async def _remove_wpa_network(self, ssid: str):
        """Remove existing wpa_supplicant entries for an SSID."""
        output = await self._wpa_cli("list_networks")
        for line in output.strip().split("\n")[1:]:
            parts = line.split("\t")
            if len(parts) >= 2 and parts[1] == ssid:
                await self._wpa_cli(f"remove_network {parts[0]}")

    async def _wpa_cli(self, command: str) -> str:
        """Execute a wpa_cli command."""
        full_cmd = f"wpa_cli -i {self.interface} {command}"
        try:
            proc = await asyncio.create_subprocess_shell(
                full_cmd,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
            )
            stdout, _ = await proc.communicate()
            return stdout.decode().strip()
        except Exception as e:
            logger.error("wpa_cli command failed: %s", e)
            return ""

    def _get_signal_strength(self) -> int:
        """Get current signal strength in dBm."""
        try:
            result = subprocess.run(
                ["wpa_cli", "-i", self.interface, "signal_poll"],
                capture_output=True, text=True, timeout=5,
            )
            for line in result.stdout.split("\n"):
                if line.startswith("RSSI="):
                    return int(line.split("=")[1])
        except (subprocess.TimeoutExpired, FileNotFoundError, ValueError):
            pass
        return -100

    @staticmethod
    def _dbm_to_quality(dbm: int) -> str:
        """Convert dBm signal strength to a human-readable quality label."""
        if dbm >= -50:
            return "excellent"
        if dbm >= -60:
            return "good"
        if dbm >= -70:
            return "fair"
        return "weak"

    @staticmethod
    def _parse_status(output: str) -> dict:
        """Parse wpa_cli status output into a dict."""
        status = {}
        for line in output.strip().split("\n"):
            if "=" in line:
                key, _, value = line.partition("=")
                status[key] = value
        return status
