"""
Command handling for Sengled bulb control.
Handles both UDP and MQTT commands for individual and group control,
including power, brightness, color, firmware updates, and custom payloads.
"""

import json
import sys
import time
import os
from pathlib import Path
from typing import Optional

from .log import warn, info, step, debug, say, success, result, section, subsection
from .mqtt_client import (
    MQTTClient,
    send_update_command,
    publish_topic,
)
from .utils import (
    get_local_ip,
    get_current_epoch_ms,
)
from .http_server import SetupHTTPServer
from .udp import send_udp_command
from .diagnose import Diagnostics
from .firmware_upgrade import (
    prepare_firmware_bin,
    print_upgrade_safety_warning,
    print_morpheus_last_chance,
    print_upgrade_post_send_instructions,
)
from .constants import BROKER_TLS_PORT, DEFAULT_BROKER_PORT


def build_cmd(dn: str, cmd_type: str, value: str, ts: int | None = None) -> dict:
    if ts is None:
        ts = get_current_epoch_ms()
    return {"dn": dn, "type": cmd_type, "value": value, "time": ts}


def build_cmd_list(dn: str, cmd_type: str, value: str, ts: int | None = None) -> list:
    return [build_cmd(dn, cmd_type, value, ts)]


def build_group_cmd(
    group_id: str,
    cmd_type: str,
    value_fields: dict,
    device_uuid_list: list[str],
    gradient_time: int,
    ts: int | None = None,
) -> list:
    if ts is None:
        ts = get_current_epoch_ms()
    value_obj = dict(value_fields or {})
    value_obj["gradientTime"] = gradient_time
    value_obj["deviceUuidList"] = device_uuid_list
    return [{"dn": group_id, "type": cmd_type, "value": value_obj, "time": ts}]


class CommandHandler:
    def __init__(self, args, tool):
        self.args = args
        self.tool = tool

    def handle_udp_commands(self):
        """Handle UDP commands for direct bulb control."""
        if self.args.udp_on:
            payload = {"func": "set_device_switch", "param": {"switch": 1}}
            response = send_udp_command(self.args.ip, payload)
            if response:
                result(json.dumps(response, indent=2))
        elif self.args.udp_off:
            payload = {"func": "set_device_switch", "param": {"switch": 0}}
            response = send_udp_command(self.args.ip, payload)
            if response:
                result(json.dumps(response, indent=2))
        elif self.args.udp_set_brightness is not None:
            if 0 <= self.args.udp_set_brightness <= 100:
                payload = {
                    "func": "set_device_brightness",
                    "param": {"brightness": self.args.udp_set_brightness},
                }
                response = send_udp_command(self.args.ip, payload)
                if response:
                    result(json.dumps(response, indent=2))
            else:
                warn("Brightness must be between 0 and 100")
                sys.exit(2)
        elif self.args.udp_get_brightness:
            payload = {"func": "get_device_brightness", "param": {}}
            response = send_udp_command(self.args.ip, payload)
            if response:
                result(json.dumps(response, indent=2))
        elif self.args.udp_set_color:
            try:
                r, g, b = self.args.udp_set_color
                r, g, b = int(r), int(g), int(b)
                if all(0 <= val <= 255 for val in [r, g, b]):
                    payload = {"func": "set_device_color", "param": {"red": r, "green": g, "blue": b}}
                    response = send_udp_command(self.args.ip, payload)
                    if response:
                        result(json.dumps(response, indent=2))
                else:
                    warn("Color values must be between 0 and 255")
                    sys.exit(2)
            except ValueError as ve:
                warn(
                    f"Could not convert input to integer for --udp-set-color: {self.args.udp_set_color}. Exception: {ve}"
                )
                sys.exit(2)
            except TypeError as te:
                warn(f"TypeError: Bad type in color arguments {self.args.udp_set_color}: {te}")
                sys.exit(2)
        elif self.args.udp_get_adc:
            payload = {"func": "get_device_adc", "param": {}}
            response = send_udp_command(self.args.ip, payload)
            if response:
                result(json.dumps(response, indent=2))
        elif self.args.udp_get_mac:
            payload = {"func": "get_device_mac", "param": {}}
            response = send_udp_command(self.args.ip, payload)
            if response:
                result(json.dumps(response, indent=2))
        elif self.args.udp_set_factory_mode:
            payload = {"func": "set_factory_mode", "param": {}}
            response = send_udp_command(self.args.ip, payload)
            if response:
                result(json.dumps(response, indent=2))
        elif self.args.udp_get_factory_mode:
            payload = {"func": "get_factory_mode", "param": {}}
            response = send_udp_command(self.args.ip, payload)
            if response:
                result(json.dumps(response, indent=2))
        elif self.args.udp_get_software_version:
            payload = {"func": "get_software_version", "param": {}}
            response = send_udp_command(self.args.ip, payload)
            if response:
                result(json.dumps(response, indent=2))
        elif self.args.udp_set_colortemp is not None:
            if 0 <= self.args.udp_set_colortemp <= 100:
                payload = {"func": "set_device_colortemp", "param": {"colorTemperature": self.args.udp_set_colortemp}}
                response = send_udp_command(self.args.ip, payload)
                if response:
                    result(json.dumps(response, indent=2))
            else:
                warn("Color temperature must be between 0 and 100")
                sys.exit(2)
        elif self.args.udp_set_pwm:
            try:
                r, g, b, w = self.args.udp_set_pwm
                r, g, b, w = int(r), int(g), int(b), int(w)
                if all(0 <= val <= 255 for val in [r, g, b, w]):
                    payload = {"func": "set_device_pwm", "param": {"r": r, "g": g, "b": b, "w": w}}
                    response = send_udp_command(self.args.ip, payload)
                    if response:
                        result(json.dumps(response, indent=2))
                else:
                    warn("PWM values must be between 0 and 255")
                    sys.exit(2)
            except ValueError as ve:
                warn(
                    f"Could not convert input to integer for --udp-set-pwm: {self.args.udp_set_pwm}. Exception: {ve}"
                )
                sys.exit(2)
            except TypeError as te:
                warn(f"TypeError: Bad type in PWM arguments {self.args.udp_set_pwm}: {te}")
                sys.exit(2)
        elif self.args.udp_search_devices:
            payload = {"func": "search_devices", "param": {}}
            response = send_udp_command(self.args.ip, payload)
            if response:
                result(json.dumps(response, indent=2))
        elif self.args.udp_reboot:
            payload = {"func": "reboot", "param": {}}
            response = send_udp_command(self.args.ip, payload)
            if response:
                result(json.dumps(response, indent=2))
        elif self.args.udp_factory_reset:
            payload = {"func": "factory_reset", "param": {}}
            response = send_udp_command(self.args.ip, payload)
            if response:
                result(json.dumps(response, indent=2))
        elif self.args.udp_json:
            try:
                custom = self.args.udp_json
                if not isinstance(custom, dict):
                    warn("--udp-json must be a JSON object")
                    sys.exit(2)
                else:
                    response = send_udp_command(self.args.ip, custom)
                    if response:
                        result(json.dumps(response, indent=2))
            except json.JSONDecodeError:
                warn("Invalid JSON for --udp-json")
                sys.exit(2)
        elif self.args.udp_diagnose:
            self.handle_udp_diagnose()
        else:
            warn(
                "--ip requires a UDP command (--udp-on, --udp-off, --udp-set-brightness, --udp-get-brightness, --udp-set-color, --udp-get-adc, --udp-get-mac, --udp-set-factory-mode, --udp-get-factory-mode, --udp-get-software-version, --udp-set-colortemp, --udp-set-pwm, --udp-search-devices, --udp-reboot, --udp-factory-reset, --udp-json, or --diagnose)"
            )
            sys.exit(2)

    def handle_udp_diagnose(self):
        """Run comprehensive diagnostic sweep of bulb capabilities and behavior."""
        no_pause = getattr(self.args, "no_pause", False)
        diag = Diagnostics(self.args.ip, no_pause)
        diag.run_full_diagnostic()

    @staticmethod
    def send_reset_command(client: MQTTClient, mac: str) -> None:
        """Send a reset command to a single bulb via MQTT."""
        command = build_cmd_list(mac, "reset", "1")
        send_update_command(client, mac, command)

    def handle_group_mqtt_control(self):
        """Handle MQTT commands for group control."""
        # Initialize MQTT client for group control (TLS via factory)
        # Resolve target for control; prefer embedded when not explicitly provided
        ctrl_host_for_bulb, ctrl_port, mode = self.tool._resolve_mqtt_target(
            prefer_embedded=not bool(self.args.broker_ip), context="control"
        )
        connect_host = self.tool._pick_local_connect_host(ctrl_host_for_bulb, ctrl_port)
        client = self.tool.create_mqtt_client(broker_host=connect_host, broker_port=ctrl_port)
        if not client.connect():
            warn(
                "Failed to connect to MQTT broker. Make sure your MQTT broker is running and reachable (see README)."
            )
            return

        try:
            # Use first MAC as group ID (like the app does)
            group_id = self.args.group_macs[0]
            ts = get_current_epoch_ms()

            if self.args.group_switch:
                switch_value = "1" if self.args.group_switch == "on" else "0"
                command = build_group_cmd(
                    group_id,
                    "groupSwitch",
                    {"switch": switch_value},
                    self.args.group_macs,
                    self.args.gradient_time,
                    ts,
                )
                send_update_command(client, group_id, command)

            elif self.args.group_brightness is not None:
                if 0 <= self.args.group_brightness <= 100:
                    command = build_group_cmd(
                        group_id,
                        "groupBrightness",
                        {"brightness": str(self.args.group_brightness)},
                        self.args.group_macs,
                        self.args.gradient_time,
                        ts,
                    )
                    send_update_command(client, group_id, command)
                else:
                    warn("Group brightness must be between 0 and 100")
                    sys.exit(2)

            elif self.args.group_color_temp is not None:
                if 0 <= self.args.group_color_temp <= 100:
                    command = build_group_cmd(
                        group_id,
                        "groupColorTemperature",
                        {"colorTemperature": str(self.args.group_color_temp)},
                        self.args.group_macs,
                        self.args.gradient_time,
                        ts,
                    )
                    send_update_command(client, group_id, command)
                else:
                    warn("Group color temperature must be between 0 and 100 (percent)")
                    sys.exit(2)
        finally:
            client.disconnect()

    def handle_single_mqtt_control(self):
        """Handle MQTT commands for single bulb control."""
        prefer_embedded = self.args.embedded or not bool(self.args.broker_ip)
        ctrl_host_for_bulb, ctrl_port, mode = self.tool._resolve_mqtt_target(
            prefer_embedded=prefer_embedded, context="control"
        )
        info(f"MQTT control target (for bulb): {ctrl_host_for_bulb}:{ctrl_port} [{mode}]")
        connect_host = self.tool._pick_local_connect_host(ctrl_host_for_bulb, ctrl_port)
        info(f"Connecting from this PC to: {connect_host}:{ctrl_port}")
        client = self.tool.create_mqtt_client(broker_host=connect_host, broker_port=ctrl_port)
        if not client.connect():
            warn(
                "Failed to connect to MQTT broker. Make sure your MQTT broker is running and reachable (see README)."
            )
            return

        try:
            if self.args.topic and self.args.payload:
                info("Publishing custom message...")
                debug(f"Topic: {self.args.topic}")
                debug(f"Payload: {self.args.payload}")

                success = publish_topic(client, self.args.topic, self.args.payload, qos=1, json_encode=False)
                if success:
                    success("Custom message sent successfully.")
                else:
                    warn("Failed to send custom message.")
                return

            if self.args.on:
                command = build_cmd_list(self.args.mac, "switch", "1")
                send_update_command(client, self.args.mac, command)

            elif self.args.off:
                command = build_cmd_list(self.args.mac, "switch", "0")
                send_update_command(client, self.args.mac, command)

            elif self.args.brightness is not None:
                if 0 <= self.args.brightness <= 100:
                    command = build_cmd_list(self.args.mac, "brightness", str(self.args.brightness))
                    send_update_command(client, self.args.mac, command)
                else:
                    warn("Brightness must be between 0 and 100")
                    sys.exit(2)

            elif self.args.color:
                debug(f"args.color = {self.args.color} (type: {type(self.args.color)})")
                try:
                    r, g, b = self.args.color
                    r, g, b = int(r), int(g), int(b)
                    if all(0 <= val <= 255 for val in [r, g, b]):
                        color_dec = f"{r:d}:{g:d}:{b:d}"
                        commands = build_cmd_list(self.args.mac, "color", color_dec)
                        send_update_command(client, self.args.mac, commands)
                    else:
                        warn("Color values must be between 0 and 255")
                        sys.exit(2)
                except ValueError as ve:
                    warn(
                        f"Could not convert input to integer for --color: {self.args.color}. Exception: {ve}"
                    )
                    sys.exit(2)
                except TypeError as te:
                    warn(f"TypeError: Bad type in color arguments {self.args.color}: {te}")
                    sys.exit(2)

            elif self.args.color_temp is not None:
                if 0 <= self.args.color_temp <= 100:
                    cmds = []
                    cmds += build_cmd_list(self.args.mac, "colorTemperature", str(self.args.color_temp))
                    cmds += build_cmd_list(self.args.mac, "switch", "1")
                    commands = cmds
                    send_update_command(client, self.args.mac, commands)
                else:
                    warn("Color temperature must be between 0 and 100 (percent)")
                    sys.exit(2)

            elif self.args.effect_status is not None:
                command = build_cmd_list(self.args.mac, "effectStatus", str(self.args.effect_status))
                send_update_command(client, self.args.mac, command)

            elif self.args.upgrade:
                step("Firmware: flashing")
                print_upgrade_safety_warning()
                firmware_path = os.path.expanduser(self.args.upgrade)
                if not os.path.isfile(firmware_path):
                    warn(f"Firmware file '{firmware_path}' does not exist.")
                    sys.exit(2)
                if not self.tool._probe_broker("127.0.0.1", 8883):
                    warn("Port 8883 is not listening on your PC. Start sengled_tool.py --run-servers in another terminal first. Also good to test MQTT commands like --brightness before flashing.")
                    sys.exit(2)
                firmware_bin = prepare_firmware_bin(self.args.upgrade)
                if not firmware_bin:
                    sys.exit(2)  # Abort if validation or copy fails
                upgrade_broker_host = get_local_ip()
                upgrade_broker_port = 8883
                local_ip = get_local_ip()
                http_port = 57542
                firmware_filename = os.path.basename(firmware_path)
                firmware_url = f"http://{local_ip}:{http_port}/{firmware_filename}"
                info(f"Will request firmware upgrade URL: {firmware_url}")

                print_morpheus_last_chance()
                command = build_cmd_list(self.args.mac, "update", firmware_url)
                send_update_command(client, self.args.mac, command)
                print_upgrade_post_send_instructions()

            elif self.args.reset:
                command = build_cmd_list(self.args.mac, "reset", "1")
                send_update_command(client, self.args.mac, command)

            elif self.args.custom_payload:
                try:
                    payload_list = json.loads(self.args.custom_payload)
                    if not isinstance(payload_list, list):
                        warn("Custom payload must be a JSON array (a list of objects).")
                        sys.exit(2)

                    info(f"Sending custom payload: {self.args.custom_payload}")
                    send_update_command(client, self.args.mac, payload_list)

                except json.JSONDecodeError:
                    warn("Invalid JSON payload for --custom-payload.")
                    sys.exit(2)



            else:
                warn(
                    "No command specified. Use --on, --off, --brightness, --color, --color-temp, or --reset"
                )
        finally:
            client.disconnect()
