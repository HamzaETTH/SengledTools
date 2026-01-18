"""
Utility functions for Sengled tool.
Provides IP/MAC address detection, configuration file management,
MAC address normalization, and timestamp generation.
"""

import json
import socket
import time
import re
from pathlib import Path
from typing import Dict, Optional

def get_local_ip() -> str:
    """Get the local IP address of this computer."""
    try:
        s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        s.connect(("8.8.8.8", 80))
        local_ip = s.getsockname()[0]
        s.close()
        return local_ip
    except OSError:
        return "127.0.0.1"

def get_mac_address(ip: Optional[str] = None, interface: Optional[str] = None) -> Optional[str]:
    """Get MAC address using psutil (cross-platform, more reliable than getmac).
    
    Args:
        ip: IP address to find MAC for (not fully supported, use interface instead)
        interface: Network interface name (e.g., 'eth0', 'wlan0')
    
    Returns:
        MAC address string or None if not found
    """
    try:
        import psutil
        
        if interface:
            # Get MAC for specific interface
            addrs = psutil.net_if_addrs().get(interface, [])
            for addr in addrs:
                if addr.family == psutil.AF_LINK:
                    return addr.address
        else:
            # Get first non-loopback interface MAC
            for name, addrs in psutil.net_if_addrs().items():
                if name != 'lo' and addrs:
                    for addr in addrs:
                        if addr.family == psutil.AF_LINK:
                            return addr.address
        
        return None
    except ImportError:
        return None

def get_config_dir() -> Path:
    """Gets the configuration directory for the application."""
    return Path.home() / ".sengled"

def load_bulbs() -> Dict[str, Dict]:
    """Loads bulb information from the configuration file."""
    config_dir = get_config_dir()
    bulbs_file = config_dir / "bulbs.json"
    if not bulbs_file.exists():
        return {}
    with open(bulbs_file, "r") as f:
        return json.load(f)

def save_bulb(mac: str, broker_ip: str):
    """Saves a bulb's MAC address and broker IP to the configuration file."""
    config_dir = get_config_dir()
    config_dir.mkdir(exist_ok=True)
    bulbs_file = config_dir / "bulbs.json"
    bulbs = load_bulbs()
    bulbs[mac] = {"broker": broker_ip}
    with open(bulbs_file, "w") as f:
        json.dump(bulbs, f, indent=2)

def get_bulb_broker(mac: str) -> Optional[str]:
    """Retrieves the broker IP for a given bulb MAC address."""
    bulbs = load_bulbs()
    return bulbs.get(mac, {}).get("broker")

def normalize_mac_address(mac: str) -> str:
    """Return MAC in canonical uppercase colon-delimited form (XX:XX:XX:XX:XX:XX).

    Raises ValueError if input is empty or not 12 hex digits (colons/hyphens optional).
    """
    if not mac:
        raise ValueError("MAC address cannot be empty")

    candidate = mac.strip().upper()
    # remove common separators
    hex_only = re.sub(r"[:-]", "", candidate)

    if not re.fullmatch(r"[0-9A-F]{12}", hex_only):
        raise ValueError(f"Invalid MAC address format: {mac}")

    return ":".join(hex_only[i:i+2] for i in range(0, 12, 2))

def get_current_epoch_ms() -> int:
    """Returns the current time in milliseconds since the epoch."""
    return int(time.time() * 1000)