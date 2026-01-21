#!/usr/bin/env python3
"""
Test script to verify UDP commands with Sengled bulbs.
This helps verify command accuracy from UDP_COMMANDS_REFERENCE.md
"""

import json
import socket
import sys
from typing import Optional

def send_udp_command(bulb_ip: str, command: dict, timeout: int = 3) -> Optional[dict]:
    """Send a UDP command to the bulb and return response."""
    try:
        with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as s:
            s.settimeout(timeout)
            json_payload = json.dumps(command)
            encoded_payload = json_payload.encode("utf-8")

            print(f"\n[SEND] To {bulb_ip}:9080")
            print(f"       {json_payload}")

            s.sendto(encoded_payload, (bulb_ip, 9080))

            try:
                data, _ = s.recvfrom(4096)
                response_str = data.decode("utf-8")
                print(f"[RECV] {response_str}")
                try:
                    return json.loads(response_str)
                except json.JSONDecodeError:
                    print(f"[ERROR] Could not parse as JSON")
                    return None
            except socket.timeout:
                print("[ERROR] No response (timeout)")
                return None
    except Exception as e:
        print(f"[ERROR] Exception: {e}")
        return None


def test_status_commands(bulb_ip: str):
    """Test commands that query device state."""
    print("\n" + "="*60)
    print("TESTING STATUS COMMANDS")
    print("="*60)

    commands = [
        ("search_devices", {"func": "search_devices", "param": {}}),
        ("get_device_brightness", {"func": "get_device_brightness", "param": {}}),
        ("get_led_color", {"func": "get_led_color", "param": {}}),
        ("get_device_mode", {"func": "get_device_mode", "param": {}}),
    ]

    for name, cmd in commands:
        print(f"\n--- {name} ---")
        response = send_udp_command(bulb_ip, cmd)
        if response:
            # Pretty print the result
            print("\nParsed response:")
            print(json.dumps(response, indent=2))


def test_control_commands(bulb_ip: str):
    """Test control commands - be careful, these will change bulb state!"""
    print("\n" + "="*60)
    print("TESTING CONTROL COMMANDS")
    print("="*60)
    print("\n⚠️  WARNING: These commands will change bulb state!")
    input("Press Enter to continue (Ctrl+C to cancel)...")

    # Test power control
    print("\n--- set_device_switch (ON) ---")
    response = send_udp_command(bulb_ip, {"func": "set_device_switch", "param": {"switch": 1}})
    if response:
        print("\nParsed response:")
        print(json.dumps(response, indent=2))

    import time
    time.sleep(1)

    print("\n--- set_device_brightness (50%) ---")
    response = send_udp_command(bulb_ip, {"func": "set_device_brightness", "param": {"brightness": 50}})
    if response:
        print("\nParsed response:")
        print(json.dumps(response, indent=2))

    time.sleep(1)

    # Query state after changes
    print("\n--- Querying state after changes ---")
    response = send_udp_command(bulb_ip, {"func": "search_devices", "param": {}})
    if response:
        print("\nParsed response:")
        print(json.dumps(response, indent=2))

    # For white bulb, test turning off
    print("\n--- set_device_switch (OFF) ---")
    response = send_udp_command(bulb_ip, {"func": "set_device_switch", "param": {"switch": 0}})
    if response:
        print("\nParsed response:")
        print(json.dumps(response, indent=2))


def test_info_commands(bulb_ip: str):
    """Test commands that return device info."""
    print("\n" + "="*60)
    print("TESTING INFO COMMANDS")
    print("="*60)

    commands = [
        ("get_device_mac", {"func": "get_device_mac", "param": {}}),
        ("get_software_version", {"func": "get_software_version", "param": {}}),
        ("get_device_adc", {"func": "get_device_adc", "param": {}}),
        ("get_dimmer_info", {"func": "get_dimmer_info", "param": {}}),
        ("get_factory_mode", {"func": "get_factory_mode", "param": {}}),
    ]

    for name, cmd in commands:
        print(f"\n--- {name} ---")
        response = send_udp_command(bulb_ip, cmd)
        if response:
            print("\nParsed response:")
            print(json.dumps(response, indent=2))


def analyze_color_mode_detection(response: dict):
    """Analyze how the integration detects RGB vs White mode."""
    print("\n" + "="*60)
    print("COLOR MODE DETECTION ANALYSIS")
    print("="*60)

    if not response or "result" not in response:
        print("No valid response to analyze")
        return

    result = response["result"]

    # Check for RGB channels (from light.py line 154)
    has_r = "R" in result
    has_g = "G" in result
    has_b = "B" in result
    has_w = "W" in result

    is_rgb = has_r and has_g and has_b

    print(f"\nChannel Detection:")
    print(f"  R channel present: {has_r}")
    print(f"  G channel present: {has_g}")
    print(f"  B channel present: {has_b}")
    print(f"  W channel present: {has_w}")

    print(f"\nMode Detection (per light.py line 154):")
    print(f"  Detected as RGB: {is_rgb}")
    print(f"  Detected as White-only: {not is_rgb}")

    # Analyze current state
    if is_rgb:
        print(f"\nRGB Bulb State:")
        r = result.get("R", {})
        g = result.get("G", {})
        b = result.get("B", {})
        w = result.get("W", {})

        r_val = r.get("value", 0)
        g_val = g.get("value", 0)
        b_val = b.get("value", 0)
        w_val = w.get("value", 0)

        r_freq = r.get("freq", 1)
        g_freq = g.get("freq", 1)
        b_freq = b.get("freq", 1)
        w_freq = w.get("freq", 1)

        print(f"  R: value={r_val}, freq={r_freq}")
        print(f"  G: value={g_val}, freq={g_freq}")
        print(f"  B: value={b_val}, freq={b_freq}")
        print(f"  W: value={w_val}, freq={w_freq}")

        # Power state detection (from light.py line 344)
        is_on = any(freq == 0 for freq in [r_freq, g_freq, b_freq, w_freq])
        print(f"\n  Power State (freq==0 means on): {is_on}")

        # Color mode detection (from light.py lines 355-385)
        if is_on and w_val > 0:
            print(f"  Color Mode: COLOR TEMPERATURE (W LED active, value={w_val})")
            print(f"    → Integration uses W>0 as indicator for CT mode")
        elif is_on:
            print(f"  Color Mode: RGB (W LED not active)")
            print(f"    → RGB color: ({r_val}, {g_val}, {b_val})")
    else:
        print(f"\nWhite Bulb State:")
        w = result.get("W", {})
        w_val = w.get("value", 0)
        w_freq = w.get("freq", 1)
        print(f"  W: value={w_val}, freq={w_freq}")
        print(f"  Power State: {w_freq == 0}")


def main():
    if len(sys.argv) < 2:
        print("Usage: python test_udp_commands.py <bulb_ip> [test_type]")
        print("\nTest types:")
        print("  status    - Test status/query commands (default)")
        print("  control   - Test control commands (changes bulb state!)")
        print("  info      - Test device info commands")
        print("  analyze   - Analyze color mode detection from search_devices")
        print("\nExample:")
        print("  python test_udp_commands.py 192.168.0.65")
        print("  python test_udp_commands.py 192.168.0.65 control")
        sys.exit(1)

    bulb_ip = sys.argv[1]
    test_type = sys.argv[2] if len(sys.argv) > 2 else "status"

    print(f"Testing UDP commands with {bulb_ip}")
    print("="*60)

    if test_type == "status":
        test_status_commands(bulb_ip)
    elif test_type == "control":
        test_control_commands(bulb_ip)
    elif test_type == "info":
        test_info_commands(bulb_ip)
    elif test_type == "analyze":
        print("\n--- search_devices ---")
        response = send_udp_command(bulb_ip, {"func": "search_devices", "param": {}})
        analyze_color_mode_detection(response)
    else:
        print(f"Unknown test type: {test_type}")
        sys.exit(1)

    print("\n" + "="*60)
    print("Test complete")
    print("="*60)


if __name__ == "__main__":
    main()
