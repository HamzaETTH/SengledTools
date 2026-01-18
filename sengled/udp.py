"""
UDP protocol implementation for direct Sengled bulb control.
Sends JSON commands to bulbs on port 9080 for power, brightness,
color, and other settings without requiring MQTT infrastructure.
"""

import json
import socket
import time
from typing import Optional

from sengled.log import send, recv, info, warn, success, waiting, set_indent
from sengled.constants import BULB_IP, BULB_PORT


def send_udp_command(bulb_ip: str, payload_dict: dict, timeout: int = 3) -> Optional[dict]:
    """Send a UDP command to the bulb using the simple JSON protocol.

    Returns the parsed JSON response dict, or None on failure.
    """
    try:
        with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as s:
            s.settimeout(timeout)

            json_payload = json.dumps(payload_dict)
            encoded_payload = json_payload.encode("utf-8")

            send("UDP", json_payload)
            s.sendto(encoded_payload, (bulb_ip, BULB_PORT))

            try:
                data, _ = s.recvfrom(4096)
                response_str = data.decode("utf-8")
                recv("UDP", response_str)
                try:
                    return json.loads(response_str)
                except json.JSONDecodeError:
                    warn(f"Could not parse response as JSON: {response_str}")
                    return None
            except socket.timeout:
                return None
    except Exception as e:
        warn(f"Error sending UDP command: {e}")
        return None


def udp_toggle_until_success(bulb_ip: str, max_wait_seconds: int = 60) -> bool:
    """Test UDP control by turning OFF, then ON. Retries up to 3 times. Returns True on success."""
    set_indent(0)
    waiting("Proceeding to UDP control test in 5 seconds...")
    time.sleep(5)

    attempts = 3
    for attempt in range(1, attempts + 1):
        info("Testing power OFF command...", extra_indent=2)
        off_payload = {"func": "set_device_switch", "param": {"switch": 0}}
        off_response = send_udp_command(bulb_ip, off_payload)
        if not off_response or not isinstance(off_response, dict):
            warn("OFF command failed - no response")
            if attempt < attempts:
                time.sleep(1)
                continue
            set_indent(0)
            return False
        off_result = off_response.get("result", {})
        # Bulb protocol: ret=0 means success, any other value indicates failure
        # The result object contains additional status information from the bulb
        if not isinstance(off_result, dict) or off_result.get("ret") != 0:
            warn("OFF command failed - bulb rejected")
            if attempt < attempts:
                time.sleep(1)
                continue
            set_indent(0)
            return False
        success("Power OFF command succeeded", extra_indent=4)

        time.sleep(1)

        info("Testing power ON command...", extra_indent=2)
        on_payload = {"func": "set_device_switch", "param": {"switch": 1}}
        on_response = send_udp_command(bulb_ip, on_payload)
        if not on_response or not isinstance(on_response, dict):
            warn("ON command failed - no response")
            if attempt < attempts:
                time.sleep(1)
                continue
            set_indent(0)
            return False
        on_result = on_response.get("result", {})
        # Bulb protocol: ret=0 means success, any other value indicates failure
        # The result object contains additional status information from the bulb
        if not isinstance(on_result, dict) or on_result.get("ret") != 0:
            warn("ON command failed - bulb rejected")
            if attempt < attempts:
                time.sleep(1)
                continue
            set_indent(0)
            return False
        success("Power ON command succeeded", extra_indent=4)

        success("UDP control test passed")
        set_indent(0)
        return True

    # If we somehow fall through the loop without returning True
    set_indent(0)
    return False


