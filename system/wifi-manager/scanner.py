"""
WiFi network scanner.

Uses wpa_supplicant via wpa_cli to scan for available networks and parse
the results into structured data.
"""

import asyncio
import logging
import re

logger = logging.getLogger("wifi-manager.scanner")


class WiFiScanner:
    """Scans for available WiFi networks using wpa_supplicant."""

    def __init__(self, interface: str = "wlan0"):
        self.interface = interface
        self._scan_lock = asyncio.Lock()

    async def scan(self) -> list[dict]:
        """
        Scan for available WiFi networks.

        Returns a list of dicts with keys:
            bssid, ssid, frequency, signal, security
        Sorted by signal strength (strongest first).
        """
        async with self._scan_lock:
            logger.info("Starting WiFi scan on %s", self.interface)

            # Trigger a scan
            await self._wpa_cli("scan")

            # Wait for scan results (wpa_supplicant needs a moment)
            await asyncio.sleep(3)

            # Get results
            output = await self._wpa_cli("scan_results")
            networks = self._parse_scan_results(output)

            logger.info("Found %d networks", len(networks))
            return networks

    async def _wpa_cli(self, command: str) -> str:
        """Execute a wpa_cli command and return stdout."""
        cmd = ["wpa_cli", "-i", self.interface, command]
        try:
            proc = await asyncio.create_subprocess_exec(
                *cmd,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
            )
            stdout, stderr = await proc.communicate()

            if proc.returncode != 0:
                logger.error("wpa_cli %s failed: %s", command, stderr.decode().strip())
                return ""

            return stdout.decode().strip()
        except FileNotFoundError:
            logger.error("wpa_cli not found. Is wpa_supplicant installed?")
            return ""

    def _parse_scan_results(self, output: str) -> list[dict]:
        """
        Parse wpa_cli scan_results output.

        Format:
        bssid / frequency / signal level / flags / ssid
        aa:bb:cc:dd:ee:ff   2412   -45   [WPA2-PSK-CCMP][ESS]   MyNetwork
        """
        networks = []
        lines = output.strip().split("\n")

        for line in lines[1:]:  # Skip header line
            parts = re.split(r"\t+", line.strip())
            if len(parts) < 5:
                continue

            bssid, freq, signal, flags, ssid = (
                parts[0], parts[1], parts[2], parts[3], parts[4]
            )

            # Skip hidden networks
            if not ssid:
                continue

            networks.append({
                "bssid": bssid,
                "ssid": ssid,
                "frequency": int(freq),
                "channel": self._freq_to_channel(int(freq)),
                "signal": int(signal),
                "security": self._parse_security(flags),
                "flags": flags,
            })

        # Sort by signal strength (strongest first, values are negative dBm)
        networks.sort(key=lambda n: n["signal"], reverse=True)

        # Deduplicate by SSID (keep strongest signal)
        seen = set()
        unique = []
        for net in networks:
            if net["ssid"] not in seen:
                seen.add(net["ssid"])
                unique.append(net)

        return unique

    @staticmethod
    def _parse_security(flags: str) -> str:
        """Determine security type from wpa_supplicant flags."""
        if "WPA2" in flags and "SAE" in flags:
            return "wpa3"
        if "WPA2" in flags:
            return "wpa2"
        if "WPA" in flags:
            return "wpa"
        if "WEP" in flags:
            return "wep"
        return "open"

    @staticmethod
    def _freq_to_channel(freq: int) -> int:
        """Convert WiFi frequency (MHz) to channel number."""
        if 2412 <= freq <= 2484:
            if freq == 2484:
                return 14
            return (freq - 2412) // 5 + 1
        if 5170 <= freq <= 5825:
            return (freq - 5170) // 5 + 34
        return 0
