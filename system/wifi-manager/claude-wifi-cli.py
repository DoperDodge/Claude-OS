#!/usr/bin/env python3
"""
claude-wifi — CLI tool for managing WiFi on Claude-OS.

Usage:
    claude-wifi scan                    List available networks
    claude-wifi connect <ssid> [pass]   Connect to a network
    claude-wifi disconnect              Disconnect from current network
    claude-wifi status                  Show connection status
    claude-wifi saved                   List saved networks
    claude-wifi forget <ssid>           Forget a saved network
    claude-wifi help                    Show this help
"""

import json
import os
import socket
import sys

SOCK_PATH = "/run/claude-os/wifi.sock"


def send_request(method: str, params: dict = None) -> dict:
    """Send a JSON request to the WiFi manager daemon via Unix socket."""
    request = {"method": method, "params": params or {}}

    sock = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
    try:
        sock.connect(SOCK_PATH)
        sock.sendall(json.dumps(request).encode())
        response = sock.recv(65536)
        return json.loads(response.decode())
    except FileNotFoundError:
        print("Error: WiFi manager is not running.")
        print("Start it with: systemctl start wifi-manager")
        sys.exit(1)
    except ConnectionRefusedError:
        print("Error: Cannot connect to WiFi manager.")
        sys.exit(1)
    finally:
        sock.close()


def cmd_scan():
    """Scan for available WiFi networks."""
    print("Scanning for networks...\n")
    result = send_request("scan")
    networks = result.get("result", [])

    if not networks:
        print("No networks found.")
        return

    # Header
    print(f"{'SSID':<30} {'SIGNAL':>8} {'QUALITY':>10} {'SECURITY':>10} {'CH':>4}")
    print("-" * 66)

    for net in networks:
        print(
            f"{net['ssid']:<30} "
            f"{net['signal']:>5} dBm "
            f"{signal_bar(net['signal']):>10} "
            f"{net['security']:>10} "
            f"{net.get('channel', '?'):>4}"
        )

    print(f"\n{len(networks)} network(s) found.")


def cmd_connect(ssid: str, password: str = None):
    """Connect to a WiFi network."""
    security = "open" if password is None else "wpa2"
    print(f"Connecting to '{ssid}'...")

    result = send_request("connect", {
        "ssid": ssid,
        "password": password or "",
        "security": security,
    })

    if result.get("result"):
        print(f"Connected to '{ssid}'.")
    else:
        print(f"Failed to connect to '{ssid}'.")
        sys.exit(1)


def cmd_disconnect():
    """Disconnect from the current network."""
    result = send_request("disconnect")
    if result.get("result"):
        print("Disconnected.")
    else:
        print("Failed to disconnect.")


def cmd_status():
    """Show current connection status."""
    result = send_request("status")
    status = result.get("result", {})

    if status.get("connected"):
        print(f"Status:   Connected")
        print(f"Network:  {status.get('ssid', 'unknown')}")
        print(f"BSSID:    {status.get('bssid', 'unknown')}")
        print(f"IP:       {status.get('ip_address', 'unknown')}")
        print(f"Signal:   {status.get('signal_dbm', '?')} dBm "
              f"({status.get('signal_quality', 'unknown')})")
        print(f"Freq:     {status.get('freq', '?')} MHz")
    else:
        print("Status:   Not connected")


def cmd_saved():
    """List saved networks."""
    result = send_request("saved_networks")
    networks = result.get("result", [])

    if not networks:
        print("No saved networks.")
        return

    print(f"{'SSID':<30} {'SECURITY':>10} {'AUTO-CONNECT':>14}")
    print("-" * 56)

    for net in networks:
        auto = "yes" if net.get("auto_connect", True) else "no"
        print(f"{net['ssid']:<30} {net['security']:>10} {auto:>14}")

    print(f"\n{len(networks)} saved network(s).")


def cmd_forget(ssid: str):
    """Forget a saved network."""
    result = send_request("forget", {"ssid": ssid})
    if result.get("result"):
        print(f"Forgot network '{ssid}'.")
    else:
        print(f"Network '{ssid}' not found in saved networks.")


def signal_bar(dbm: int) -> str:
    """Convert dBm to a visual signal bar."""
    if dbm >= -50:
        return "████ great"
    if dbm >= -60:
        return "███  good"
    if dbm >= -70:
        return "██   fair"
    if dbm >= -80:
        return "█    weak"
    return "▁    poor"


def usage():
    print(__doc__.strip())


def main():
    if len(sys.argv) < 2:
        usage()
        sys.exit(1)

    command = sys.argv[1].lower()

    if command == "scan":
        cmd_scan()
    elif command == "connect":
        if len(sys.argv) < 3:
            print("Usage: claude-wifi connect <ssid> [password]")
            sys.exit(1)
        ssid = sys.argv[2]
        password = sys.argv[3] if len(sys.argv) > 3 else None
        cmd_connect(ssid, password)
    elif command == "disconnect":
        cmd_disconnect()
    elif command == "status":
        cmd_status()
    elif command == "saved":
        cmd_saved()
    elif command == "forget":
        if len(sys.argv) < 3:
            print("Usage: claude-wifi forget <ssid>")
            sys.exit(1)
        cmd_forget(sys.argv[2])
    elif command in ("help", "--help", "-h"):
        usage()
    else:
        print(f"Unknown command: {command}")
        usage()
        sys.exit(1)


if __name__ == "__main__":
    main()
