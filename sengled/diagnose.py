"""
UDP diagnostic sweep for Sengled devices.
Tests device capabilities and state behavior for integration debugging.
"""

import json
import time
import re
import sys
import os
import tempfile
import platform
import subprocess
from typing import Optional, Dict, Any
from .udp import send_udp_command
from .utils import get_current_epoch_ms
from .log import info, warn, result, success


def _open_editor_with_default_app(temp_path: str):
    """Open temp file in system default text editor."""
    system = platform.system()

    if system == "Windows":
        os.startfile(temp_path)
    elif system == "Darwin":  # macOS
        subprocess.run(["open", "-a", "TextEdit", temp_path])
    else:  # Linux/Unix
        # Try common editors in order of preference
        for editor in ["nano", "vim", "gedit", "kate", "mousepad"]:
            if os.system(f"which {editor} > /dev/null 2>&1") == 0:
                if editor in ["nano", "vim"]:
                    # Terminal-based editor
                    subprocess.call([editor, temp_path])
                else:
                    # GUI editor
                    subprocess.Popen([editor, temp_path])
                return
        # Fallback to xdg-open
        try:
            subprocess.run(["xdg-open", temp_path])
        except:
            pass


class Diagnostics:
    """Comprehensive UDP diagnostic for Sengled devices."""

    def __init__(self, device_ip: str, no_pause: bool = False):
        self.device_ip = device_ip
        self.no_pause = no_pause
        self.report = {
            "target_ip": device_ip,
            "timestamp": get_current_epoch_ms(),
            "tests": []
        }

    def run_full_diagnostic(self):
        """Run complete diagnostic sweep."""
        try:
            info("=" * 60)
            info("Sengled UDP Diagnostic Sweep")
            info("=" * 60)
            info(f"Target: {self.device_ip}:9080")
            info("This will test various commands and observe how the device responds.")
            info("The device's physical state will change during this test.")
            info("")

            self._step_1_device_info()
            self._step_2_initial_state()
            self._step_3_power_on()
            self._step_4_brightness()
            self._step_5_color_temp()
            self._step_6_rgb_colors()
            self._step_7_power_off()
            self._step_8_analysis()
        except Exception as e:
            warn(f"[!] Diagnostic interrupted by error: {e}")
            warn("    Attempting to save partial report...")

        # Save report (even if partial)
        report_filename = f"sengled_diagnostic_{self.device_ip.replace('.', '_')}.json"
        try:
            with open(report_filename, 'w', encoding='utf-8') as f:
                json.dump(self.report, f, indent=2, ensure_ascii=False)
            info("")
            info(f"Full diagnostic report saved to: {report_filename}")
            info("Please share this file when reporting issues with your device!")
        except Exception as e:
            warn(f"Could not save report file: {e}")

        info("")
        info("=" * 60)
        info("Diagnostic complete")
        info("=" * 60)

        # Step 9: Restore initial state
        info("-" * 60)
        info("Step 9: Restore Initial State")
        info("-" * 60)
        info("Restoring device to its initial state...")

        # Check if we have an initial state to restore
        initial_test = None
        for test in self.report["tests"]:
            if test.get("step") == "initial_state":
                initial_test = test
                break

        if initial_test and "response" in initial_test:
            initial_state = initial_test["response"]

            try:
                sd = initial_state.get("search_devices", {})
                brightness_info = initial_state.get("brightness", {})

                # 1. Extract raw channel values and brightness
                r_raw = sd.get("R", {}).get("value", 0) if isinstance(sd.get("R"), dict) else 0
                g_raw = sd.get("G", {}).get("value", 0) if isinstance(sd.get("G"), dict) else 0
                b_raw = sd.get("B", {}).get("value", 0) if isinstance(sd.get("B"), dict) else 0
                w_raw = sd.get("W", {}).get("value", 0) if isinstance(sd.get("W"), dict) else 0

                init_bri = 100
                if isinstance(brightness_info, dict) and "brightness" in brightness_info:
                    init_bri = brightness_info.get("brightness", 100)

                # Avoid division by zero
                calc_bri = max(1, init_bri)

                # 2. Determine Power State
                was_on = (r_raw > 0 or g_raw > 0 or b_raw > 0 or w_raw > 0)

                # 3. Mode Detection & Restoration Logic
                # Findings: PWM is volatile. We must use persistent commands.
                # W=0 -> RGB Mode. W>0 -> Color Temp Mode.

                if w_raw == 0:
                    # --- RGB MODE RESTORATION ---
                    # Normalize values (reverse brightness scaling)
                    r_norm = int(min(255, r_raw * 100 / calc_bri))
                    g_norm = int(min(255, g_raw * 100 / calc_bri))
                    b_norm = int(min(255, b_raw * 100 / calc_bri))

                    info(f"Detected RGB Mode (W=0). Restoring Color (R:{r_norm}, G:{g_norm}, B:{b_norm})...")
                    send_udp_command(self.device_ip, {
                        "func": "set_device_color",
                        "param": {"red": r_norm, "green": g_norm, "blue": b_norm}
                    })

                else:
                    # --- COLOR TEMP RESTORATION ---
                    # Mapping based on fingerprinting:
                    # Warm (0): High R, Low G/B. (R > G and R > B)
                    # Cool (100): High B, High G. (B > W)
                    # Neutral (50): High W, Balanced G/B. (Default)

                    target_ct = 50 # Default to Neutral

                    if r_raw > g_raw and r_raw > b_raw:
                        target_ct = 0   # Warm
                    elif b_raw > w_raw and g_raw > 0:
                        target_ct = 100 # Cool

                    info(f"Detected White Mode (W:{w_raw}). Restoring Color Temp (Approx: {target_ct})...")
                    send_udp_command(self.device_ip, {
                        "func": "set_device_colortemp",
                        "param": {"colorTemperature": target_ct}
                    })

                time.sleep(1.0)

                # 4. Restore Brightness
                if init_bri is not None:
                    info(f"Restoring brightness to {init_bri}%...")
                    send_udp_command(self.device_ip, {
                        "func": "set_device_brightness",
                        "param": {"brightness": init_bri}
                    })
                    time.sleep(0.5)

                # 5. Restore Power State
                if was_on:
                    # Implicitly turned ON by color/brightness commands.
                    # Do NOT send explicit ON (avoids firmware mode reset).
                    info("Device is already ON from restore commands. Skipping explicit Power ON.")
                    result("[OK] Power ON restored")
                else:
                    info("Device was initially OFF, turning it back off...")
                    response = send_udp_command(self.device_ip, {"func": "set_device_switch", "param": {"switch": 0}})
                    if response and response.get("result", {}).get("ret") == 0:
                        result("[OK] Power OFF restored")
                    else:
                        warn("[FAIL] Could not restore power state")

                info("")
                info("Device should now be back to its initial state.")
            except Exception as e:
                warn(f"[!] Error restoring initial state: {e}")
                warn("    Manual restore may be required")
        else:
            info("No initial state captured, skipping restore step.")

    def _step_1_device_info(self):
        """Query initial device information."""
        info("-" * 60)
        info("Step 1: Device Information")
        info("-" * 60)
        info("Querying device info...")

        info_queries = [
            ("get_device_mac", {"func": "get_device_mac", "param": {}}),
            ("get_software_version", {"func": "get_software_version", "param": {}}),
            ("get_factory_mode", {"func": "get_factory_mode", "param": {}}),
            ("get_device_mode", {"func": "get_device_mode", "param": {}}),
        ]

        device_info = {}
        for name, cmd in info_queries:
            response = send_udp_command(self.device_ip, cmd)
            if response and "result" in response:
                device_info[name] = response["result"]
                result(f"[OK] {name}")
            else:
                device_info[name] = None
                warn(f"[FAIL] {name}")

        # Extract useful info
        mac = device_info.get("get_device_mac", {}).get("mac", "unknown")
        version = device_info.get("get_software_version", {}).get("version", "unknown")
        model_match = None
        if version:
            m = re.search(r"_(W\d{2}-[A-Z]\d{2})_", version)
            if m:
                model_match = m.group(1)

        info(f"MAC: {mac}")
        if model_match:
            info(f"Model detected: {model_match}")
        info(f"Version: {version}")

        # Detect device type using search_devices for accurate fingerprinting
        info("Detecting device type...")
        sd_response = send_udp_command(self.device_ip, {"func": "search_devices", "param": {}})
        sd_data = {}
        if sd_response and "result" in sd_response:
            sd_data = sd_response["result"]
            device_info["search_devices_sample"] = sd_data

        # Check for RGBW based on presence of R, G, B keys
        has_r = "R" in sd_data
        has_g = "G" in sd_data
        has_b = "B" in sd_data
        is_rgbw = has_r and has_g and has_b

        self.report["device_info"] = device_info
        self.device_type = "rgbw" if is_rgbw else "white"

        if is_rgbw:
            info("[OK] Device Type: RGBW (RGB + white channel)")
        else:
            info("[OK] Device Type: White-only")

        self.report["device_type"] = self.device_type
        info("")

    def _step_2_initial_state(self):
        """Query initial state."""
        info("-" * 60)
        info("Step 2: Initial State")
        info("-" * 60)
        info("Querying device state...")
        initial_state = self._query_full_state()

        if initial_state:
            try:
                sd = initial_state.get("search_devices", {})
                brightness = initial_state.get("brightness", {}).get("brightness", "unknown")
                result("[OK] State captured")

                # Determine power state using value-based logic (same as Step 9)
                r_val = sd.get("R", {}).get("value", 0) if isinstance(sd.get("R"), dict) else 0
                g_val = sd.get("G", {}).get("value", 0) if isinstance(sd.get("G"), dict) else 0
                b_val = sd.get("B", {}).get("value", 0) if isinstance(sd.get("B"), dict) else 0
                w_val = sd.get("W", {}).get("value", 0) if isinstance(sd.get("W"), dict) else 0

                is_on = (r_val > 0 or g_val > 0 or b_val > 0 or w_val > 0)

                # Show basic info
                info(f"Power: {'ON' if is_on else 'OFF'}")
                if brightness != "unknown":
                    info(f"Brightness: {brightness}%")
            except Exception as e:
                warn(f"[!] Error displaying state info: {e}")
                warn("    Raw state saved to report for analysis")
        else:
            warn("[FAIL] Could not query state")

        self.report["tests"].append({
            "step": "initial_state",
            "description": "Query device before any changes",
            "response": initial_state
        })
        info("")

    def _step_3_power_on(self):
        """Test power ON."""
        info("-" * 60)
        info("Step 3: Power ON Test")
        info("-" * 60)
        info("Sending set_device_switch(1)...")

        response = send_udp_command(self.device_ip, {"func": "set_device_switch", "param": {"switch": 1}})
        if response and response.get("result", {}).get("ret") == 0:
            result("[OK] Power ON command accepted")
        else:
            warn("[FAIL] Power ON command failed")

        # Delay to allow device to update its state
        time.sleep(2.0)

        state_after_on = self._query_full_state()
        diag_entry = {
            "step": "power_on",
            "description": "Turn on and observe state",
            "command_response": response,
            "state_after": state_after_on
        }
        self.report["tests"].append(diag_entry)
        info("")

        observation = self._pause_and_prompt("Is the device ON?")
        if observation:
            diag_entry["observations"] = observation

    def _step_4_brightness(self):
        """Test brightness changes."""
        info("-" * 60)
        info("Step 4: Brightness Test")
        info("-" * 60)
        brightness_tests = [100, 50, 25]

        for brightness in brightness_tests:
            info(f"Setting brightness to {brightness}%...")
            response = send_udp_command(self.device_ip, {
                "func": "set_device_brightness",
                "param": {"brightness": brightness}
            })

            if response and response.get("result", {}).get("ret") == 0:
                result(f"[OK] Brightness {brightness}% accepted")
            else:
                warn(f"[FAIL] Brightness {brightness}% failed")

            # Delay to allow device to update its state
            time.sleep(2.0)

            state = self._query_full_state()
            diag_entry = {
                "step": f"brightness_{brightness}",
                "description": f"Brightness set to {brightness}%",
                "command_response": response,
                "state_after": state
            }
            self.report["tests"].append(diag_entry)
            info("")

    def _step_5_color_temp(self):
        """Test color temperature."""
        info("-" * 60)
        info("Step 5: Color Temperature Test")
        info("-" * 60)
        color_temp_tests = [100, 50, 0]  # Cold, mid, warm

        for ct in color_temp_tests:
            info(f"Setting color temperature to {ct} (0-100 scale)...")
            response = send_udp_command(self.device_ip, {
                "func": "set_device_colortemp",
                "param": {"colorTemperature": ct}
            })

            if response:
                if response.get("result", {}).get("ret") == 0:
                    result(f"[OK] Color temp {ct} accepted")
                else:
                    # Some white devices might not support color temp
                    warn(f"[FAIL] Color temp {ct} rejected (may not be supported)")
                    self.report["tests"].append({
                        "step": f"colortemp_{ct}",
                        "description": f"Color temp {ct} (not supported)",
                        "command_response": response,
                        "supported": False
                    })
                    info("")
                    break
            else:
                warn(f"[FAIL] Color temp {ct} no response")

            # Delay to allow device to update its state
            time.sleep(2.0)

            state = self._query_full_state()
            diag_entry = {
                "step": f"colortemp_{ct}",
                "description": f"Color temp {ct} (0-100 scale)",
                "command_response": response,
                "state_after": state,
                "supported": True
            }
            self.report["tests"].append(diag_entry)
            info("")

    def _step_6_rgb_colors(self):
        """Test RGB colors."""
        info("-" * 60)
        info("Step 6: RGB Color Test")
        info("-" * 60)
        rgb_tests = [
            ("Red", (255, 0, 0)),
            ("Green", (0, 255, 0)),
            ("Blue", (0, 0, 255)),
            ("White", (255, 255, 255))
        ]

        for color_name, (r, g, b) in rgb_tests:
            info(f"Setting RGB to {color_name} ({r},{g},{b})...")
            response = send_udp_command(self.device_ip, {
                "func": "set_device_color",
                "param": {"red": r, "green": g, "blue": b}
            })

            if response:
                if response.get("result", {}).get("ret") == 0:
                    result(f"[OK] RGB {color_name} accepted")
                else:
                    # White devices might reject RGB commands
                    warn(f"[FAIL] RGB {color_name} rejected (may be white-only)")
                    self.report["tests"].append({
                        "step": f"rgb_{color_name.lower()}",
                        "description": f"RGB color {color_name} (not supported)",
                        "command_response": response,
                        "supported": False
                    })
                    info("")
                    break
            else:
                warn(f"[FAIL] RGB {color_name} no response")

            # Delay to allow device to update its state
            time.sleep(2.0)

            state = self._query_full_state()
            diag_entry = {
                "step": f"rgb_{color_name.lower()}",
                "description": f"RGB color {color_name} ({r},{g},{b})",
                "command_response": response,
                "state_after": state,
                "supported": True
            }
            self.report["tests"].append(diag_entry)
            info("")

    def _step_7_power_off(self):
        """Test power OFF."""
        info("-" * 60)
        info("Step 7: Power OFF Test")
        info("-" * 60)
        info("Sending set_device_switch(0)...")

        response = send_udp_command(self.device_ip, {"func": "set_device_switch", "param": {"switch": 0}})
        if response and response.get("result", {}).get("ret") == 0:
            result("[OK] Power OFF command accepted")
        else:
            warn("[FAIL] Power OFF command failed")

        # Delay to allow device to update its state
        time.sleep(2.0)

        state_after_off = self._query_full_state()
        diag_entry = {
            "step": "power_off",
            "description": "Turn off and observe state",
            "command_response": response,
            "state_after": state_after_off
        }
        self.report["tests"].append(diag_entry)
        info("")

    def _pause_and_prompt(self, prompt_text):
        """Pause and prompt for observation, unless --no-pause was given."""
        # Auto-skip if not running in interactive terminal
        if not sys.stdin.isatty():
            self.no_pause = True

        if not self.no_pause:
            info("")
            info("[PAUSE] Check Home Assistant and Google Home state now...")
            info("")
            info(f"Physical Light: {prompt_text}")
            info("")
            observation = {}

            try:
                # Simple physical observation (single line)
                if self.device_type == "rgbw":
                    physical = input("What does physical device show? (e.g., 'red', 'white', 'warm white', ignore if not used or n/a): ")
                    if physical.strip():
                        observation["physical"] = physical.strip()
                else:
                    if "ON?" in prompt_text or "OFF?" in prompt_text:
                        physical_prompt = "Is the device ON or OFF? (ignore if not used or n/a): "
                    elif "brightness" in prompt_text.lower():
                        physical_prompt = "How bright is it? (e.g., '100%', 'dim', ignore if not used or n/a): "
                    elif "color" in prompt_text.lower() or "color temp" in prompt_text.lower():
                        physical_prompt = "Is it warm or cool white? (e.g., 'warm', 'cool', 'neutral', ignore if not used or n/a): "
                    else:
                        physical_prompt = f"{prompt_text} (ignore if not used or n/a): "
                    physical = input(f"What does physical device show? {physical_prompt}")
                    if physical.strip():
                        observation["physical"] = physical.strip()

                # Use temp file for multi-line Home Assistant input
                use_editor = input("Paste multi-line Home Assistant data? (y/n, default n): ").strip().lower() == 'y'
                if use_editor:
                    info("Opening editor to paste Home Assistant data...")
                    info("  SAVE and CLOSE the editor when done.")

                    temp_file = None
                    try:
                        temp_file = tempfile.NamedTemporaryFile(mode='w', delete=False, suffix='.txt', encoding='utf-8')

                        # Write instructions + template to file
                        temp_file.write("=" * 70 + "\n")
                        temp_file.write("HOME ASSISTANT DATA COLLECTION\n")
                        temp_file.write("=" * 70 + "\n")
                        temp_file.write("\n")
                        temp_file.write("INSTRUCTIONS:\n")
                        temp_file.write("1. Click 'Developer Tools' in Home Assistant left sidebar\n")
                        temp_file.write("2. Click 'States' tab\n")
                        temp_file.write("3. In 'Filter entities', search for your device\n")
                        temp_file.write("4. Click on your device entity\n")
                        temp_file.write("5. Scroll down to 'Attributes' section\n")

                        if self.device_type == "rgbw":
                            temp_file.write("6. Copy and paste these attributes below:\n")
                            temp_file.write("   - rgb_color\n")
                            temp_file.write("   - color_mode\n")
                            temp_file.write("   - color_temp_kelvin\n")
                        else:
                            temp_file.write("6. Note brightness and color temp if shown\n")

                        temp_file.write("\n")
                        temp_file.write("-" * 70 + "\n")
                        temp_file.write("PASTE HOME ASSISTANT DATA BELOW THIS LINE:\n")
                        temp_file.write("-" * 70 + "\n")
                        temp_file.write("\n")

                        temp_file.close()

                        _open_editor_with_default_app(temp_file.name)

                        # Wait for editor to close
                        input("Press Enter after you have SAVED and CLOSED the editor...")

                        # Read what user typed
                        with open(temp_file.name, 'r', encoding='utf-8') as f:
                            content = f.read()

                        # Clean up
                        os.unlink(temp_file.name)

                        # Parse content - skip instructions and separators, keep only pasted data
                        lines = []
                        in_paste_area = False

                        for line in content.split('\n'):
                            if 'PASTE HOME ASSISTANT DATA BELOW' in line:
                                in_paste_area = True
                                continue
                            if not in_paste_area:
                                continue

                            stripped = line.strip()
                            # Skip empty lines and markers
                            if not stripped or stripped.startswith('-'):
                                continue
                            # Keep real content
                            lines.append(line)

                        ha_text = '\n'.join(lines)

                        if ha_text.strip():
                            observation["home_assistant"] = ha_text.strip()
                            info("[OK] Home Assistant data saved")

                        # Google Home - simple single-line input after editor closes
                        gh_simple = input("What does Google Home show? (ignore if not used or n/a): ")
                        if gh_simple.strip():
                            observation["google_home"] = gh_simple.strip()

                    except Exception as e:
                        warn(f"[!] Editor error: {e}")
                        warn("    Falling back to single-line input...")
                        if temp_file and os.path.exists(temp_file.name):
                            try:
                                os.unlink(temp_file.name)
                            except:
                                pass
                        ha_fallback = input("What does Home Assistant show? (single line, ignore if not used or n/a): ")
                        if ha_fallback.strip():
                            observation["home_assistant"] = ha_fallback.strip()
                        gh_fallback = input("What does Google Home show? (ignore if not used or n/a): ")
                        if gh_fallback.strip():
                            observation["google_home"] = gh_fallback.strip()
                else:
                    # No editor, use single-line prompts
                    ha_simple = input("What does Home Assistant show? (single line, ignore if not used or n/a): ")
                    if ha_simple.strip():
                        observation["home_assistant"] = ha_simple.strip()
                    gh_simple = input("What does Google Home show? (ignore if not used or n/a): ")
                    if gh_simple.strip():
                        observation["google_home"] = gh_simple.strip()

            except EOFError:
                # User pressed Ctrl+D or similar - continue gracefully
                pass
            except Exception as e:
                warn(f"Pause interrupted: {e}")

            return observation
        info("")
        return None

    def _step_8_analysis(self):
        """Analyze diagnostic report."""
        info("-" * 60)
        info("Diagnostic Summary")
        info("-" * 60)
        info("")

        # Use device type detected in Step 1
        device_type = getattr(self, 'device_type', 'unknown')
        info(f"[OK] Device Type: {device_type.upper()}")

        # Initialize support flags
        rgb_supported = False
        colortemp_supported = False

        # Check command support (only for RGBW devices)
        info("")
        info("Command Support:")

        if device_type == "rgbw":
            colortemp_supported = any(
                test.get("supported", False)
                for test in self.report["tests"]
                if test["step"].startswith("colortemp")
            )

            rgb_supported = any(
                test.get("supported", False)
                for test in self.report["tests"]
                if test["step"].startswith("rgb")
            )

            if colortemp_supported:
                info("[OK] Color Temperature: Supported")
            else:
                warn("[FAIL] Color Temperature: Not supported")

            if rgb_supported:
                info("[OK] RGB Colors: Supported")
            else:
                warn("[FAIL] RGB Colors: Not supported")

        # Analyze state behavior
        if device_type == "rgbw" and rgb_supported:
            info("")
            info("RGB Mode Detection Analysis:")

            for test in self.report["tests"]:
                try:
                    if test["step"].startswith("rgb") and test.get("state_after"):
                        state = test["state_after"]
                        sd = state.get("search_devices", {})
                        w_value = sd.get("W", {}).get("value", 0) if isinstance(sd.get("W"), dict) else 0
                        r_val = sd.get("R", {}).get("value", 0) if isinstance(sd.get("R"), dict) else 0
                        g_val = sd.get("G", {}).get("value", 0) if isinstance(sd.get("G"), dict) else 0
                        b_val = sd.get("B", {}).get("value", 0) if isinstance(sd.get("B"), dict) else 0

                        info("")
                        info(f"  {test['description']}:")
                        info(f"    R: {r_val}, G: {g_val}, B: {b_val}, W: {w_value}")
                        if w_value > 10:
                            warn("    [!] W > 0 in RGB mode - this may confuse color mode detection!")
                            warn("        Integration might incorrectly report this as color temperature mode")
                except Exception as e:
                    warn(f"  [!] Could not analyze {test.get('step', 'unknown')}: {e}")
                    continue

        if device_type == "rgbw" and colortemp_supported:
            info("")
            info("Color Temperature Mode Detection Analysis:")

            for test in self.report["tests"]:
                try:
                    if test["step"].startswith("colortemp") and test.get("state_after"):
                        state = test["state_after"]
                        sd = state.get("search_devices", {})
                        w_value = sd.get("W", {}).get("value", 0) if isinstance(sd.get("W"), dict) else 0
                        r_val = sd.get("R", {}).get("value", 0) if isinstance(sd.get("R"), dict) else 0
                        g_val = sd.get("G", {}).get("value", 0) if isinstance(sd.get("G"), dict) else 0
                        b_val = sd.get("B", {}).get("value", 0) if isinstance(sd.get("B"), dict) else 0

                        info("")
                        info(f"  {test['description']}:")
                        info(f"    R: {r_val}, G: {g_val}, B: {b_val}, W: {w_value}")
                        if w_value == 0:
                            warn("    [!] W == 0 in color temp mode - integration might miss this!")
                except Exception as e:
                    warn(f"  [!] Could not analyze {test.get('step', 'unknown')}: {e}")
                    continue

        info("")
        info("Potential Issues:")

        issues_found = False

        if device_type == "rgbw":
            for test in self.report["tests"]:
                try:
                    if test["step"].startswith("rgb") and test.get("state_after"):
                        state = test["state_after"]
                        sd = state.get("search_devices", {})
                        w_value = sd.get("W", {}).get("value", 0) if isinstance(sd.get("W"), dict) else 0

                        if w_value > 10:
                            warn(f"  - W channel active ({w_value}) when set to RGB color")
                            warn("      This may cause integration to detect as color temp mode instead of RGB")
                            issues_found = True
                except Exception as e:
                    warn(f"  [!] Could not check issues for {test.get('step', 'unknown')}: {e}")
                    continue
        
        if not issues_found:
            info("  No obvious issues detected in state reporting")
        else:
            info("")
            warn("Issues were detected! The full JSON report has all the details.")
            info("Consider adjusting detection thresholds in light.py if needed.")

    def _query_full_state(self):
        """Query all relevant state information from device."""
        state = {}

        try:
            # Query search_devices (main state)
            response = send_udp_command(self.device_ip, {"func": "search_devices", "param": {}})
            if response and "result" in response:
                state["search_devices"] = response["result"]

            # Query brightness separately
            response = send_udp_command(self.device_ip, {"func": "get_device_brightness", "param": {}})
            if response and "result" in response:
                state["brightness"] = response["result"]

            # Query LED color state - wrap in try/except as this function may not exist
            try:
                response = send_udp_command(self.device_ip, {"func": "get_led_color", "param": {}})
                if response and "result" in response and response["result"].get("ret") == 0:
                    state["led_color"] = response["result"]
                else:
                    # Function not supported or failed
                    state["led_color"] = None
            except Exception:
                # Don't spam warnings for this expected failure
                state["led_color"] = None
        except Exception as e:
            warn(f"[!] Error querying device state: {e}")

        return state

