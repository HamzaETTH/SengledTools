"""
Lightweight HTTP server used during Sengled Wi-Fi setup.
Serves two endpoints bulbs call:
  • /life2/device/accessCloud.json
  • /jbalancer/new/bimqtt
Also serves firmware files (.bin) for OTA updates.
"""

import json
import os
import socket
import threading
import time
from http.server import BaseHTTPRequestHandler, HTTPServer
import socketserver
from typing import Optional
from urllib.parse import urlparse

from sengled.log import debug, info, ok, say, warn, success, is_verbose, get_indent, set_indent, waiting, stop


class SetupHTTPServer:
    """Lightweight HTTP server used during Wi‑Fi setup.

    - Serves two endpoints the bulb calls:
      • /life2/device/accessCloud.json
      • /jbalancer/new/bimqtt
    - Stops after both endpoints have been hit at least once (any method).
    """

    def __init__(self, mqtt_host: str, mqtt_port: int, preferred_port: int = 57542):
        self.mqtt_host = mqtt_host
        self.mqtt_port = mqtt_port
        self.preferred_port = preferred_port
        self.server: Optional[HTTPServer] = None
        self.thread: Optional[threading.Thread] = None
        self.port: Optional[int] = None

        # Endpoint hit tracking
        self._hit_access_cloud = threading.Event()
        self._hit_bimqtt = threading.Event()
        self.last_client_ip: Optional[str] = None
        self._hit_access_cloud_ip: Optional[str] = None
        self._hit_bimqtt_ip: Optional[str] = None
        self.active: bool = False
        # Firmware download tracking
        self._firmware_served = threading.Event()
        self.last_firmware_filename: Optional[str] = None

    def _make_handler(self):
        outer = self

        class Handler(BaseHTTPRequestHandler):
            def _client_ip(self) -> str:
                return str(self.client_address[0])

            def _should_count_hit(self, ip: str) -> bool:
                # Don't let local manual testing (curl/browser) satisfy verification.
                return ip not in ("127.0.0.1", "::1")

            def _send_json(self, data: dict):
                self.send_response(200)
                self.send_header("Content-Type", "application/json")
                payload = json.dumps(data).encode("utf-8")
                self.send_header("Content-Length", str(len(payload)))
                self.end_headers()
                self.wfile.write(payload)
                debug(f"sent: {payload}")

            def _handle_endpoint(self, method: str) -> bool:
                """Handle bulb endpoints. Respond for GET/POST/PUT; only COUNT hits for expected methods."""
                parsed_url = urlparse(self.path)
                ip = self._client_ip()
                count = self._should_count_hit(ip)

                if parsed_url.path == "/life2/device/accessCloud.json":
                    # Historically seen as POST/PUT. Respond to GET for convenience but do not count it.
                    if count and method in ("POST", "PUT"):
                        outer._hit_access_cloud.set()
                        outer._hit_access_cloud_ip = ip
                    self._send_json(
                        {
                            "messageCode": "200",
                            "info": "OK",
                            "description": "正常",
                            "success": True,
                        }
                    )
                    success(f"Served {method} on /life2/device/accessCloud.json")
                    return True

                if parsed_url.path == "/jbalancer/new/bimqtt":
                    # Historically seen as GET (sometimes POST). Do not count PUT.
                    if count and method in ("GET", "POST"):
                        outer._hit_bimqtt.set()
                        outer._hit_bimqtt_ip = ip
                    self._send_json(
                        {
                            "protocal": "mqtt",
                            "host": outer.mqtt_host,
                            "port": outer.mqtt_port,
                        }
                    )
                    success(f"Served {method} on /jbalancer/new/bimqtt")
                    return True

                return False

            def do_POST(self):  # noqa: N802 (stdlib signature)
                length = int(self.headers.get("Content-Length", 0) or 0)
                _ = self.rfile.read(length) if length > 0 else b""

                debug(
                    f"Received POST request on {self.path} from {self.client_address[0]}"
                )
                
                if self._handle_endpoint("POST"):
                    return

                self.send_error(404, "Not Found")

            def do_PUT(self):  # noqa: N802 (stdlib signature)
                length = int(self.headers.get("Content-Length", 0) or 0)
                _ = self.rfile.read(length) if length > 0 else b""

                debug(
                    f"Received PUT request on {self.path} from {self.client_address[0]}"
                )

                if self._handle_endpoint("PUT"):
                    return

                self.send_error(404, "Not Found")

            def do_GET(self):
                debug(f"Received GET request on {self.path} from {self.client_address[0]}")
                parsed_url = urlparse(self.path)

                # Handle bulb endpoints (both GET and POST supported)
                if self._handle_endpoint("GET"):
                    return

                if parsed_url.path == "/status":
                    both_hit = (
                        outer._hit_access_cloud.is_set()
                        and outer._hit_bimqtt.is_set()
                        and outer._hit_access_cloud_ip is not None
                        and outer._hit_access_cloud_ip == outer._hit_bimqtt_ip
                    )
                    if both_hit:
                        outer.last_client_ip = outer._hit_access_cloud_ip
                    self._send_json(
                        {
                            "last_client_ip": outer.last_client_ip,
                            "hit_both_points": both_hit,
                        }
                    )
                    return
                if parsed_url.path == "/reset":
                    outer._hit_bimqtt.clear()
                    outer._hit_access_cloud.clear()
                    outer.last_client_ip = None
                    outer._hit_access_cloud_ip = None
                    outer._hit_bimqtt_ip = None
                    self._send_json(
                        {
                            "reset": "success"
                        }
                    )
                    return

                # Firmware download handler
                # Security: Only allow .bin files from root directory to prevent path traversal
                if parsed_url.path.endswith(".bin"):
                    requested = os.path.basename(parsed_url.path)
                    # Only allow direct root requests, not any path structure
                    if "/" in parsed_url.path.strip("/").replace(requested, ""):
                        warn(
                            f"Refused firmware download with path component: {parsed_url.path}"
                        )
                        self.send_error(400, "Invalid firmware path")
                        return
                    # Prevent dangerous names and empty
                    if not requested or requested in (".", ".."):
                        warn(
                            f"Refused firmware download with dangerous name: {requested}"
                        )
                        self.send_error(400, "Invalid firmware filename")
                        return
                    local_file = os.path.join(os.path.dirname(__file__), requested)
                    if not os.path.isfile(local_file):
                        warn(f"Firmware file not found: {requested}")
                        self.send_error(404, "Firmware file not found")
                        return
                    try:
                        with open(local_file, "rb") as fw:
                            data = fw.read()
                        self.send_response(200)
                        self.send_header("Content-Type", "application/octet-stream")
                        self.send_header(
                            "Content-Disposition", f'attachment; filename="{requested}"'
                        )
                        self.send_header("Content-Length", str(len(data)))
                        self.end_headers()
                        self.wfile.write(data)
                        success(f"Served firmware: {requested} ({len(data)} bytes)")
                        outer.last_firmware_filename = requested
                        outer._firmware_served.set()
                    except Exception as e:
                        warn(f"Error sending firmware: {e}")
                        self.send_error(500, "Error sending firmware file")
                    return

                self.send_error(404, "Not Found")

            def log_message(self, fmt, *args):  # silence stdlib noisy logger
                return

        return Handler

    @staticmethod
    def _port_in_use(port: int) -> bool:
        try:
            with socket.create_connection(("127.0.0.1", port), timeout=0.5):
                return True
        except OSError:
            return False

    def start(self) -> bool:
        # Use only the specified port
        waiting("Starting HTTP server...")
        try:
            if self._port_in_use(self.preferred_port):
                stop(
                    f"HTTP server failed on port {self.preferred_port}. Port is already in use."
                )
                stop("Please specify another port with --http-port.")
                return False
            # Avoid slow DNS reverse lookup in HTTPServer.server_bind on Windows
            # by skipping socket.getfqdn() for '0.0.0.0'.
            class FastHTTPServer(HTTPServer):
                def server_bind(self):
                    socketserver.TCPServer.server_bind(self)
                    host, port = self.server_address[:2]
                    # Set directly without potentially blocking getfqdn()
                    self.server_name = host
                    self.server_port = port

            self.server = FastHTTPServer(("0.0.0.0", self.preferred_port), self._make_handler())
            self.port = self.preferred_port
        except OSError as e:
            if e.errno in (13, 98, 48, 10048, 10013):
                stop(f"HTTP server failed on port {self.preferred_port}. Port may be in use or require administrator privileges.")
                stop("Please specify another port with --http-port.")
            else:
                stop(f"HTTP server failed on port {self.preferred_port}: {e}")
            return False

        self.active = True
        self.thread = threading.Thread(target=self.server.serve_forever, daemon=True)
        self.thread.start()
        success(f"HTTP server running on 0.0.0.0:{self.port} (HTTP)", extra_indent=4)
        if is_verbose():
            info("")
            info("Keep this window open. You'll see logs when the bulb hits:")
            info("       - /life2/device/accessCloud.json")
            info("       - /jbalancer/new/bimqtt")
        self.active = True
        return True

    def wait_until_both_endpoints_hit(self, timeout_seconds: int = 120) -> bool:
        start = time.time()
        # Wait for both flags with overall timeout
        while time.time() - start < timeout_seconds:
            if self._hit_access_cloud.is_set() and self._hit_bimqtt.is_set():
                return True
            time.sleep(0.25)
        return self._hit_access_cloud.is_set() and self._hit_bimqtt.is_set()

    def wait_for_firmware_download(self, timeout_seconds: int = 300) -> bool:
        return self._firmware_served.wait(timeout_seconds)

    def stop(self):
        if self.server:
            try:
                self.server.shutdown()
                self.server.server_close()
            finally:
                self.server = None
                success("HTTP server stopped")
