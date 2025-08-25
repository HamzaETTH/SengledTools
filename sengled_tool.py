#!/usr/bin/env python3
"""
Sengled Firmware Flashing & WiFi Pairing Tool
A tool for flashing custom firmware (jailbreak) and managing WiFi pairing on Sengled Wi-Fi bulbs.
"""

import argparse
import json
import os
import sys
import shutil
import time
import socket
from urllib.parse import urlparse
import warnings
import threading
from http.server import HTTPServer, BaseHTTPRequestHandler
from typing import Optional
from pathlib import Path
from sengled.utils import get_mac_address

# Suppress SSL and certificate warnings
warnings.filterwarnings("ignore", message=".*SSL.*", category=Warning)
warnings.filterwarnings("ignore", message=".*certificate.*", category=Warning)

from sengled.crypto import (
    SengledWiFiCrypto,
    encrypt_wifi_payload,
    decrypt_wifi_payload,
)
from sengled.mqtt_broker import BROKER_TLS_PORT, EmbeddedBroker
from sengled.mqtt_client import (
    MQTTClient,
    create_mqtt_client as _factory_create_mqtt_client,
    publish_topic,
)
from sengled.utils import (
    get_local_ip,
    save_bulb,
    load_bulbs,
    get_current_epoch_ms,
    get_bulb_broker,
    normalize_mac_address,
)
from sengled.log import configure, say, step, info, warn, debug, send, recv, section, subsection, success, waiting, result, rule, is_verbose, stop, cmd
from sengled.http_server import SetupHTTPServer
from sengled.wifi_setup import run_wifi_setup
from sengled.firmware_upgrade import (
    prepare_firmware_bin,
    print_upgrade_safety_warning,
    print_morpheus_last_chance,
    print_upgrade_post_send_instructions,
    run_firmware_upgrade,
)
from sengled.udp import send_udp_command
from sengled.constants import BULB_IP, BULB_PORT, DEFAULT_BROKER_PORT
from sengled.command_handler import CommandHandler


def _print_post_pairing_summary(bulb_mac: str, udp_target_ip: Optional[str]):
    section("Pairing Setup Complete")
    info("")
    info("You should now be able to control the bulb with UDP/MQTT commands in another terminal")
    subsection("Examples:")
    if udp_target_ip:
        cmd(f"python sengled_tool.py --ip {udp_target_ip} --udp-on", extra_indent=4)
    cmd(f"python sengled_tool.py --mac {bulb_mac} --on", extra_indent=4)
    cmd(f"python sengled_tool.py --mac {bulb_mac} --reset", extra_indent=4)
    
    success("HTTP server ready for firmware updates")


def _print_final_summary_and_hold(bulb_mac: str, udp_target_ip: Optional[str]):
    """Prints the final summary for Wi-Fi setup and holds until user input."""
    success("Wi-Fi setup complete.")
    info("")
    info(
        "You can control the bulb as long as the script is running, "
        "if stopped you can resume control with:"
    )
    cmd("python sengled_tool.py --run-servers (and wait for up to a minute for the bulb to reconnect)")
    info("")

    subsection("Example Commands")
    if udp_target_ip:
        cmd(f"UDP OFF:         python sengled_tool.py --ip {udp_target_ip} --udp-off")
        cmd(f"UDP ON:          python sengled_tool.py --ip {udp_target_ip} --udp-on")
        cmd(f"UDP BRIGHTNESS:  python sengled_tool.py --ip {udp_target_ip} --udp-brightness 50")
        cmd(f"UDP COLOR:       python sengled_tool.py --ip {udp_target_ip} --udp-color 255 0 0")
        info("")

    cmd(f"MQTT ON:         python sengled_tool.py --mac {bulb_mac} --on")
    cmd(f"MQTT OFF:        python sengled_tool.py --mac {bulb_mac} --off")
    cmd(f"MQTT BRIGHTNESS: python sengled_tool.py --mac {bulb_mac} --brightness 50")
    cmd(f"MQTT COLOR:      python sengled_tool.py --mac {bulb_mac} --color 255 0 0")
    cmd(f"MQTT COLOR-TEMP: python sengled_tool.py --mac {bulb_mac} --color-temp 50")
    cmd(f"MQTT RESET:      python sengled_tool.py --mac {bulb_mac} --reset")
    info("")

    try:
        input("Press Enter to quit...")
    except KeyboardInterrupt:
        info("\nExiting.")


class SengledTool:
    def __init__(self, args):
        self.wifi_crypto = SengledWiFiCrypto()
        self.args = args
        self._embedded_broker: EmbeddedBroker | None = None
        self.cert_dir = Path.home() / ".sengled" / "certs"

    def create_mqtt_client(
        self, broker_host: Optional[str] = None, broker_port: Optional[int] = None
    ) -> MQTTClient:
        return _factory_create_mqtt_client(
            self.args, broker_host=broker_host, broker_port=broker_port
        )

    def _probe_broker(self, host: str, port: int, timeout: float = 1.0) -> bool:
        try:
            with socket.create_connection((host, port), timeout=timeout):
                return True
        except OSError:
            return False

    def _ensure_embedded_broker(
        self, force_regenerate: bool = False
    ) -> tuple[str, int, bool]:
        """Start embedded broker if possible.

        Returns (lan_ip, port, started_now). If port is busy, returns lan_ip and port with started_now=False.
        Prints standardized messages for both paths.
        """
        lan_ip = get_local_ip()
        port = BROKER_TLS_PORT

        if self._probe_broker("127.0.0.1", port):
            info(
                "Port 8883 is in use; assuming your MQTT broker is running on this PC."
            )
            return lan_ip, port, False

        try:
            self._embedded_broker = EmbeddedBroker(
                self.cert_dir, force_regenerate=force_regenerate, verbose=getattr(self.args, 'verbose', False)
            )
            self._embedded_broker.start()
            return lan_ip, port, True
        except Exception as e:
            stop(f"Failed to start broker: {e}")
            stop("Exiting. Free port 8883 or provide --broker-ip/--broker-port.")
            sys.exit(1)

    def _resolve_mqtt_target(
        self, prefer_embedded: bool, context: str
    ) -> tuple[str, int, str]:
        """Resolve MQTT host/port and mode for setup/control.

        Returns (host_for_bulb, port, mode). host_for_bulb is always LAN-reachable (never 127.0.0.1).
        Mode is one of: 'embedded', 'local', 'explicit'.
        """
        if getattr(self.args, "broker_ip", None):
            host = self.args.broker_ip
            try:
                port = int(
                    getattr(self.args, "broker_port", DEFAULT_BROKER_PORT)
                    or DEFAULT_BROKER_PORT
                )
            except (TypeError, ValueError):
                port = DEFAULT_BROKER_PORT
            info(f"Using explicit MQTT broker {host}:{port} (from --broker-ip)")
            return host, port, "explicit"

        if prefer_embedded:
            # For setup, we always want to start the embedded broker if it's not running
            lan_ip, port, started = self._ensure_embedded_broker()
            return lan_ip, port, "embedded" if started else "existing"

        lan_ip = get_local_ip()
        port = int(
            getattr(self.args, "broker_port", DEFAULT_BROKER_PORT)
            or DEFAULT_BROKER_PORT
        )

        info(f"No --broker-ip provided. Assuming broker on this PC at {lan_ip}:{port}.")
        if self._probe_broker(lan_ip, port):
            return lan_ip, port, "local"

        warn(
            f"Could not reach MQTT broker at {lan_ip}:{port}. Start your broker or use '--setup-wifi' to use the embedded one."
        )
        return lan_ip, port, "local"

    def _pick_local_connect_host(self, host_for_bulb: str, port: int) -> str:
        """If the target is the local IP, connect via 127.0.0.1 for consistency."""
        lan_ip = get_local_ip()
        # Optimization: When connecting to local broker, use 127.0.0.1 instead of LAN IP
        # This avoids potential routing issues and ensures consistent local connections
        if host_for_bulb == lan_ip and port == BROKER_TLS_PORT:
            return "127.0.0.1"
        return host_for_bulb

    def perform_wifi_setup(
        self,
        broker_ip: str,
        broker_port: int,
        wifi_ssid: str,
        wifi_pass: str,
        wifi_bssid: str | None = None,
        interactive: bool = True,
        udp_bulb_ip: str = BULB_IP,
        keep_servers_alive: bool = False,
    ) -> None:
        run_wifi_setup(self.args, interactive=interactive)

    def interactive_wifi_setup(self, broker_ip: str):
        run_wifi_setup(self.args, interactive=True)

    def non_interactive_wifi_setup(self, broker_ip: str, ssid: str, password: str):
        run_wifi_setup(self.args, interactive=False)

    def _stop_servers(self, setup_server: Optional[SetupHTTPServer]):
        if setup_server:
            setup_server.stop()
        broker = self._embedded_broker or getattr(setup_server, "embedded_broker", None)
        if broker:
            broker.stop()

def startLocalServer(mqtt_host, mqtt_port, preferred_port):
    print("Starting Sengled local server...")
    server = _SetupHTTPServer(mqtt_host,mqtt_port,preferred_port)
    started = server.start()
    if not started:
        print("Could not start HTTP server, exiting.")
        return

    success(f"Server running on port {server.port}")
    info("")
    subsection("Endpoints")
    info("  /life2/device/accessCloud.json")
    info("  /jbalancer/new/bimqtt")
    info("  GET  /firmware.bin (or any .bin in script's directory)")
    info("Press Ctrl+C to stop")

    try:
        while True:
            time.sleep(1)
    except KeyboardInterrupt:
        server.stop()
        success("Server stopped")


def handle_run_servers(args, resolved_broker_ip: str):
    """Start embedded MQTT broker and HTTP server for bulb control."""
    from sengled.mqtt_broker import EmbeddedBroker
    from sengled.http_server import SetupHTTPServer
    from pathlib import Path
    
    section("Starting Servers")
    
    # Start embedded MQTT broker
    cert_dir = Path.home() / ".sengled" / "certs"
    broker = EmbeddedBroker(cert_dir, verbose=args.verbose)
    broker.start()
    success(f"MQTT broker running on port 8883 (TLS)", extra_indent=4)
    
    # Start HTTP server
    http_port = args.http_port or 8080
    http_server_ip = args.http_server_ip or resolved_broker_ip
    
    server = SetupHTTPServer(
        mqtt_host=resolved_broker_ip,
        mqtt_port=8883,
        preferred_port=http_port
    )
    server.start()
    success(f"HTTP server running on port {server.port}")
    
    say(f"Servers are running. Bulbs can connect to:")
    say(f"  MQTT: {resolved_broker_ip}:8883")
    say(f"  HTTP: {http_server_ip}:{server.port}")
    say("Press Ctrl+C to stop both servers")
    
    try:
        while True:
            time.sleep(1)
    except KeyboardInterrupt:
        server.stop()
        broker.stop()
        success("Servers stopped.")





def main():
    parser = argparse.ArgumentParser(
        description="Sengled Local Control Tool",
        formatter_class=argparse.RawTextHelpFormatter,
    )

    parser.add_argument(
        "--setup-wifi", action="store_true", help="Start interactive Wi-Fi setup."
    )
    
    parser.add_argument(
        "--broker-ip",
        default=None,
        help="IP address of your MQTT broker (defaults to this PC's local IP if omitted).",
    )
    parser.add_argument(
        "--broker-port",
        type=int,
        default=DEFAULT_BROKER_PORT,
        help="MQTT broker port (default: 8883).",
    )
    parser.add_argument("--ca-crt", help="Path to CA certificate (default: ca.crt)")
    parser.add_argument(
        "--server-crt", help="Path to server certificate (default: server.crt)"
    )
    parser.add_argument(
        "--server-key", help="Path to server private key (default: server.key)"
    )
    parser.add_argument("--ssid", help="Wi-Fi SSID for non-interactive setup.")
    parser.add_argument("--password", help="Wi-Fi password for non-interactive setup.")
    parser.add_argument(
        "--embedded",
        action="store_true",
        help="Force control publishes to 127.0.0.1:8883 (embedded broker). Not used for Wi-Fi setup.",
    )
    parser.add_argument(
        "--regen-certs",
        action="store_true",
        help="Force regeneration of TLS certificates in the unified location.",
    )

    parser.add_argument(
        "--status", action="store_true", help="Send status command (no payload)"
    )

    control_group = parser.add_argument_group("Bulb Control (MQTT)")
    control_group.add_argument("--mac", help="MAC address of the bulb to control.")
    control_group.add_argument("--on", action="store_true", help="Turn the bulb on.")
    control_group.add_argument("--off", action="store_true", help="Turn the bulb off.")
    control_group.add_argument(
        "--toggle", action="store_true", help="Toggle the bulb's power state."
    )
    control_group.add_argument("--brightness", type=int, help="Set brightness (0-100).")
    control_group.add_argument(
        "--color", nargs=3, metavar=("R", "G", "B"), help="Set color (0-255 for each)."
    )
    control_group.add_argument(
        "--color-temp",
        type=int,
        help="Set color temperature (0-100 percent; 0=2700K, 100=6500K).",
    )
    control_group.add_argument("--reset", action="store_true", help="Reset the bulb.")
    control_group.add_argument(
        "--custom-payload", help="Send custom JSON payload to bulb."
    )

    control_group.add_argument(
        "--upgrade", help="Send firmware upgrade command with URL."
    )

    # Group control arguments (untested)
    control_group.add_argument(
        "--group-macs", nargs="+", help="List of MAC addresses for group control."
    )
    control_group.add_argument(
        "--group-switch", choices=["on", "off"], help="Control multiple bulbs on/off."
    )
    control_group.add_argument(
        "--group-brightness",
        type=int,
        help="Set brightness for multiple bulbs (0-100).",
    )
    control_group.add_argument(
        "--group-color-temp", type=int, help="Set color temperature for multiple bulbs."
    )
    control_group.add_argument(
        "--gradient-time",
        type=int,
        default=10,
        help="Transition time for group commands (default: 10).",
    )

    # Effect status (untested)
    control_group.add_argument(
        "--effect-status",
        type=int,
        help="Set effect status (0=off, 7=audio sync, 100=video sync, 101=game sync).",
    )

    udp_group = parser.add_argument_group("UDP Control (Local Network)")
    udp_group.add_argument("--ip", help="IP address of the bulb for UDP control.")
    udp_group.add_argument(
        "--udp-on", action="store_true", help="Turn the bulb on via UDP."
    )
    udp_group.add_argument(
        "--udp-off", action="store_true", help="Turn the bulb off via UDP."
    )
    udp_group.add_argument(
        "--udp-brightness", type=int, help="Set brightness via UDP (0-100)."
    )
    udp_group.add_argument(
        "--udp-color",
        nargs=3,
        metavar=("R", "G", "B"),
        help="Set color via UDP (0-255 for each).",
    )
    udp_group.add_argument("--udp-json", help="Send a custom JSON payload via UDP.")

    control_group.add_argument("--topic", help="Custom MQTT topic to publish to.")
    control_group.add_argument(
        "--payload", help="Custom payload to send (raw string, not JSON)."
    )
    parser.add_argument(
        "--force-flash",
        action="store_true",
        help="Allow flashing even if model/module is not recognized as supported.",
    )

    parser.add_argument(
        "--run-http-server",
        action="store_true",
        help="Run the Sengled local server only (for firmware update testing).",
    )
    parser.add_argument(
        "--run-servers",
        action="store_true",
        help="Start embedded MQTT broker and HTTP server for bulb control.",
    )
    parser.add_argument(
        "--http-port",
        type=int,
        default=8080,
        help="HTTP server port (default: 8080).",
    )
    parser.add_argument(
        "--http-server-ip",
        default=None,
        help="IP/host to embed in HTTP URLs sent to the bulb (defaults to LAN IP).",
    )
    parser.add_argument(
        "--verbose", action="store_true", help="Show debug + error logs"
    )

    args = parser.parse_args()
    configure(verbose=args.verbose)

    # Normalize and validate MAC inputs early
    if getattr(args, "mac", None):
        try:
            args.mac = normalize_mac_address(args.mac)
            debug(f"Normalized MAC address: {args.mac}")
        except ValueError as e:
            warn(f"Invalid --mac: {e}")
            sys.exit(2)

    if getattr(args, "group_macs", None):
        try:
            args.group_macs = [normalize_mac_address(m) for m in args.group_macs]
            debug(f"Normalized group MACs: {args.group_macs}")
        except ValueError as e:
            warn(f"Invalid --group-macs entry: {e}")
            sys.exit(2)

    # Handle certificate regeneration
    if args.regen_certs:
        cert_dir = Path.home() / ".sengled" / "certs"
        info(f"Regenerating TLS certificates in {cert_dir}")
        try:
            # Instantiate broker with force_regenerate=True. This handles the logic.
            # We don't need to start it, just trigger the cert generation.
            EmbeddedBroker(cert_dir, force_regenerate=True, verbose=getattr(args, 'verbose', False))
            success("Certificates regenerated successfully.")
        except Exception as e:
            warn(f"Failed to regenerate certificates: {e}")

        # If ONLY regen-certs was specified (no other actions), exit
        if not any(
            [
                args.setup_wifi,
                args.mac,
                args.group_macs,
                args.ip,
                args.run_http_server,
            ]
        ):
            return

    # Resolve broker IP: use provided value or fall back to local IP
    resolved_broker_ip = args.broker_ip or get_local_ip()
    tool = SengledTool(args)

    if args.run_http_server:
        startLocalServer(resolved_broker_ip, args.mqtt_port, args.http_port)
        try:
            while True:
                time.sleep(1)
        except KeyboardInterrupt:
            print("\nStopping HTTP server...")
            server.stop()
            print("Server stopped.")
        return
        
    if args.run_servers:
        handle_run_servers(args, resolved_broker_ip)
        return



    # Create command handler
    cmd_handler = CommandHandler(args, tool)

    # Handle UDP commands first (they take precedence)
    if args.ip:
        cmd_handler.handle_udp_commands()
    elif args.setup_wifi or (args.ssid and args.password):
        is_interactive = not (args.ssid and args.password)
        section("SengledTool")
        info(
            "This tool will guide you through Wi-Fi network setup, bulb control, and firmware flashing."
        )

        bulb_mac, setup_server = run_wifi_setup(args, interactive=is_interactive)

        if bulb_mac and setup_server:
            # For --setup-wifi, show hold summary; otherwise prompt for flashing.
            if args.setup_wifi:
                _print_final_summary_and_hold(bulb_mac, setup_server.last_client_ip)
                tool._stop_servers(setup_server)
            else:
                tool._post_wifi_setup_flow(bulb_mac, setup_server)
        else:
            # run_wifi_setup prints its own errors, so we just add a final status
            warn("Wi-Fi setup did not complete.")
        return
    elif args.group_macs:
        # Handle group commands (including single MAC)
        if not (args.group_switch or args.group_brightness or args.group_color_temp):
            warn(
                "--group-macs requires a group command (--group-switch, --group-brightness, or --group-color-temp)"
            )
            sys.exit(2)

        cmd_handler.handle_group_mqtt_control()
    elif args.mac:
        cmd_handler.handle_single_mqtt_control()
    else:
        # Default to the setup wizard instead of REPL
        tool.run_setup_wizard()
        return


if __name__ == "__main__":
    main()
