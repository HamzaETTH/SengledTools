import json
import os
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

    def __init__(self, mqtt_host: str, mqtt_port: int, preferred_port: int = 8080):
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
        self.active: bool = False
        # Firmware download tracking
        self._firmware_served = threading.Event()
        self.last_firmware_filename: Optional[str] = None

    def _make_handler(self):
        outer = self

        class Handler(BaseHTTPRequestHandler):
            def _send_json(self, data: dict):
                self.send_response(200)
                self.send_header("Content-Type", "application/json")
                payload = json.dumps(data).encode("utf-8")
                self.send_header("Content-Length", str(len(payload)))
                self.end_headers()
                self.wfile.write(payload)

            def do_POST(self):  # noqa: N802 (stdlib signature)
                length = int(self.headers.get("Content-Length", 0) or 0)
                _ = self.rfile.read(length) if length > 0 else b""

                debug(
                    f"Received PUT request on {self.path} from {self.client_address[0]}"
                )
                parsed_url = urlparse(self.path)

                if parsed_url.path == "/life2/device/accessCloud.json":
                    outer.last_client_ip = self.client_address[0]
                    outer._hit_access_cloud.set()
                    self._send_json(
                        {
                            "messageCode": "200",
                            "info": "OK",
                            "description": "正常",
                            "success": True,
                        }
                    )
                    return

                if parsed_url.path == "/jbalancer/new/bimqtt":
                    outer.last_client_ip = self.client_address[0]
                    outer._hit_bimqtt.set()
                    self._send_json(
                        {
                            "protocal": "mqtt",
                            "host": outer.mqtt_host,
                            "port": outer.mqtt_port,
                        }
                    )
                    return

                self.send_error(404, "Not Found")

            def do_GET(self):  # noqa: N802 (stdlib signature)
                debug(
                    f"Received GET request on {self.path} from {self.client_address[0]}"
                )
                parsed_url = urlparse(self.path)

                # Treat GET the same for robustness
                if parsed_url.path == "/life2/device/accessCloud.json":
                    outer.last_client_ip = self.client_address[0]
                    outer._hit_access_cloud.set()
                    self._send_json(
                        {
                            "messageCode": "200",
                            "info": "OK",
                            "description": "正常",
                            "success": True,
                        }
                    )
                    return

                if parsed_url.path == "/jbalancer/new/bimqtt":
                    outer.last_client_ip = self.client_address[0]
                    outer._hit_bimqtt.set()
                    self._send_json(
                        {
                            "protocal": "mqtt",
                            "host": outer.mqtt_host,
                            "port": outer.mqtt_port,
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

    def start(self) -> bool:
        # Use only the specified port
        waiting("Starting HTTP server...")
        try:
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
            if e.errno in (13, 98, 48, 10048, 10013): # EACCES, EADDRINUSE on win/linux/mac
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
