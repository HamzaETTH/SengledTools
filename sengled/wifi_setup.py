import json
import time
import socket
from pathlib import Path
from typing import Optional

from urllib.request import Request, urlopen
from urllib.error import URLError, HTTPError

from sengled.utils import get_mac_address

from sengled.utils import get_local_ip, save_bulb
from sengled.crypto import encrypt_wifi_payload, decrypt_wifi_payload
from sengled.log import say, step, info, warn as warn_, debug, section, subsection, success, waiting, get_indent, set_indent, is_verbose, cmd
from sengled.http_server import SetupHTTPServer
from sengled.mqtt_broker import EmbeddedBroker, BROKER_TLS_PORT
from sengled.mqtt_client import MQTTClient, create_mqtt_client
from sengled.udp import udp_toggle_until_success
from sengled.constants import BULB_IP, BULB_PORT, SUPPORTED_TYPECODES, COMPATIBLE_IDENTIFY_MARKERS


def _listen_for_bulb_attributes(
	mqtt_client: MQTTClient, bulb_mac: str, timeout: int = 10
) -> dict[str, str]:
	"""Listen on MQTT for bulb attributes after connection."""
	attributes = {}
	
	required_attributes = {"typeCode", "identifyNO", "supportAttributes"}
	
	def on_message(client, userdata, msg):
		nonlocal attributes
		try:
			payload = json.loads(msg.payload.decode())
			if isinstance(payload, list):
				for item in payload:
					if "type" in item and "value" in item:
						attr_type = item["type"]
						if attr_type in required_attributes:
							attributes[attr_type] = item["value"]
							
		except (json.JSONDecodeError, UnicodeDecodeError):
			pass

	topic = f"wifielement/{bulb_mac}/status"
	mqtt_client.client.subscribe(topic)
	mqtt_client.client.on_message = on_message

	start_time = time.time()
	while time.time() - start_time < timeout:
		if required_attributes.issubset(attributes.keys()):
			break
		time.sleep(0.5)

	mqtt_client.client.unsubscribe(topic)
	return attributes


def _print_udp_failure_warning(bulb_mac: str):
	"""Prints a standardized warning when UDP control fails."""
	warn_("UDP control test failed (non-fatal). If this keeps happening, "
		"check Windows Firewall/antivirus and allow UDP on port 9080."
	)
	info("You can still try controlling the bulb via MQTT from another terminal:")
	say(f"  MQTT ON:  python sengled_tool.py --mac {bulb_mac} --on")
	say(f"  MQTT OFF: python sengled_tool.py --mac {bulb_mac} --off")

def _probe_server(host: str, port: int, timeout: float = 1.0) -> bool:
    try:
        with socket.create_connection((host, port), timeout=timeout):
            return True
    except OSError:
        return False

# Helpers for external HTTP server in another instance
def fetch_status(url: str, timeout: float = 3.0) -> Optional[dict]:
	"""GET {url}, expect JSON: {"last_client_ip": "...", "hit_both_points": bool}."""
	req = Request(url, headers={"Accept": "application/json"})
	try:
		with urlopen(req, timeout=timeout) as resp:
			body = resp.read().decode("utf-8", errors="replace")
		data = json.loads(body)
		if isinstance(data, dict):
			return data
	except (HTTPError, URLError, json.JSONDecodeError, TimeoutError):
		pass
	return None

def _poll_status_until_both_hit(
	url: str,
	total_timeout_sec: float = 180.0,
	interval_sec: float = 1.0,
)-> tuple[bool, Optional[str]]:
	"""
	Poll /status until hit_both_points == True or timeout.
	Returns (both_hit, last_client_ip_or_None).
	"""
	deadline = time.monotonic() + total_timeout_sec
	last_ip = None
	while time.monotonic() < deadline:
		st = fetch_status(url)
		if st is not None:
			last_ip = st.get("last_client_ip")
			if st.get("hit_both_points") is True:
				return True, last_ip
		time.sleep(interval_sec)
	return False, last_ip

def run_wifi_setup(
	args,
	interactive: bool = True,
) -> tuple[Optional[str], Optional[object], Optional[bool]]:
	"""
	Performs Wi‑Fi setup.

	Returns a 3-tuple: (bulb_mac, meta, using_external_http_server)
	  - meta is a SetupHTTPServer instance when we started the server,
	    or a dict with keys {"last_client_ip", "support_info"} when using an external server.
	"""
	# Capture LAN IP before switching to bulb AP; use this for URLs the bulb will hit
	lan_ip_before_ap = get_local_ip()
	local_wifi_ip = lan_ip_before_ap
	section("Wi-Fi Setup")
	subsection("Preparation")
	info(f"Local IP address: {local_wifi_ip}")

	# HTTP endpoint URLs given to the bulb must be reachable after it joins your LAN
	http_host_for_urls = getattr(args, "http_server_ip", None) or lan_ip_before_ap
	waiting("Connect to bulb's 'Sengled_Wi-Fi Bulb_XXXXXX' network")
	print("")
	try:
		input("Press Enter to continue — you can connect to your bulb's Wi-Fi before or after (Ctrl+C to cancel)...")
		from sengled.log import waiting as _waiting
		_waiting("Looking for bulb...")
	except KeyboardInterrupt:
		print("")  # New line after Ctrl+C
		warn_("Setup cancelled by user")
		return None, None, None

	# Refresh local Wi‑Fi IP after user connects to bulb AP (server still binds 0.0.0.0)
	local_wifi_ip = get_local_ip()

	# MQTT broker will be started after successful bulb connection
	_embedded_broker: EmbeddedBroker | None = None
	lan_ip = get_local_ip()

	server_started = False
	setup_server: SetupHTTPServer | None = None
	retry_notice_last_ts = 0.0

	try:
		while True:
			try:
				with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as s:
					s.settimeout(2)

					# Step 1: Initial Handshake
					start_req = {"name": "startConfigRequest", "totalStep": 1, "curStep": 1, "payload": {"protocol": 1}}
					s.sendto(json.dumps(start_req).encode("utf-8"), (BULB_IP, BULB_PORT))
					data, _ = s.recvfrom(4096)
					handshake_resp = json.loads(data.decode("utf-8"))

					if "mac" not in handshake_resp.get("payload", {}) and getattr(args, 'mac', None):
						say("MAC address not provided by bulb, using command line option --mac")
						handshake_resp.setdefault("payload", {})["mac"] = args.mac

					if "payload" not in handshake_resp or "mac" not in handshake_resp["payload"]:
						bulb_mac = get_mac_address(ip=BULB_IP)
					else:
						bulb_mac = handshake_resp["payload"]["mac"]

					if not bulb_mac or len(bulb_mac) != 17:
						warn_(f"Connection failed: {handshake_resp}")
						return None, None, None

					s.settimeout(15)
					success(f"Connected to bulb MAC: {bulb_mac}")
					time.sleep(1)
					info("")

					# Resolve MQTT target
					mqtt_host_for_bulb: str
					mqtt_port_for_bulb: int
					if _probe_server("127.0.0.1", 8883):
						info("MQTT server port 8883 is already listening. We'll use the running instance.")
						mqtt_host_for_bulb = local_wifi_ip
						mqtt_port_for_bulb = 8883
						_embedded_broker = None
					else:
						if getattr(args, "broker_ip", None):
							# External broker is specified
							mqtt_host_for_bulb = args.broker_ip
							mqtt_port_for_bulb = getattr(args, "broker_port", BROKER_TLS_PORT)
							success(
								f"Using external MQTT broker: {mqtt_host_for_bulb}:{mqtt_port_for_bulb}"
							)
							_embedded_broker = None
						else:
							# No external broker, start the embedded one
							try:
								_embedded_broker = EmbeddedBroker(
									Path.home() / ".sengled" / "certs",
									verbose=getattr(args, "verbose", False),
								)
								_embedded_broker.start()
								# Use LAN IP captured before AP switch so bulb can reach us on home network
								mqtt_host_for_bulb = lan_ip_before_ap
								mqtt_port_for_bulb = BROKER_TLS_PORT
								success(
									f"MQTT broker running on {lan_ip}:{BROKER_TLS_PORT} (TLS)",
									extra_indent=4,
								)
							except Exception as e:
								warn_(str(e)) # Display the clean message from the broker
								info(
									"If you are running a custom broker, use the --broker-ip and --broker-port arguments."
								)
								return None, None

					if _probe_server("127.0.0.1", 57542):
						info("HTTP server port 57542 is already listening. We'll use the running instance.")
						preferred_http_port = 57542
						server_started = True
						using_external_http_server = True
					else:
						# Start HTTP server for endpoints
						preferred_http_port = int(getattr(args, "http_port", 57542) or 57542)
						setup_server = SetupHTTPServer(
							mqtt_host=mqtt_host_for_bulb,
							mqtt_port=mqtt_port_for_bulb,
							preferred_port=preferred_http_port,
						)
						server_started = setup_server.start()
						using_external_http_server = False

					if _embedded_broker:
						setattr(setup_server, "embedded_broker", _embedded_broker)

					if interactive:
						# Step 2+3: Scan + list with refresh option
						info("")
						from sengled.log import set_indent as _si
						_si(0)
						subsection("Wi-Fi Access Points")
						from sengled.log import get_indent as _gi, set_indent as _si
						while True:
							_base = 2  # Start from subsection level
							_si(_base + 4)
							info("Getting available networks AP from bulb...")
							scan_req = {"name": "scanWifiRequest", "totalStep": 1, "curStep": 1, "payload": {}}
							s.sendto(json.dumps(scan_req).encode("utf-8"), (BULB_IP, BULB_PORT))
							time.sleep(5)
							ap_req = {"name": "getAPListRequest", "totalStep": 1, "curStep": 1, "payload": {}}
							s.sendto(json.dumps(ap_req).encode("utf-8"), (BULB_IP, BULB_PORT))
							data, _ = s.recvfrom(4096)
							ap_list_resp = json.loads(data.decode("utf-8"))
							routers = ap_list_resp.get("payload", {}).get("routers", [])

							info("")
							info("Available networks found (enter 0 to rescan):")

							# List entries indented further
							if not routers:
								_si(_base + 10)
								info("(none found)")
							else:
								max_len = max(len(r.get('ssid','')) for r in routers)
								_si(_base + 10)
								for i, router in enumerate(routers):
									ssid = router.get('ssid','')
									pad = " " * max(1, max_len - len(ssid) + 2)
									signal_bars = "▂▄▆█"[0:min(int(router.get("signal", 0)), 4)]
									info(f"[{i+1}] {ssid}{pad}{signal_bars}")

							# Prompt slightly less indented than items
							_si(_base + 6)
							info("")
							prompt_shown = False
							while True:
								# Keep prompting until valid selection or explicit rescan
								try:
									prompt_range = f"(1-{len(routers)})" if len(routers) > 0 else "(none)"
									prompt_text = f"      Select network {prompt_range} or 0 to rescan: " if not prompt_shown else ""
									choice_input = input(prompt_text).strip()
									prompt_shown = True
								except KeyboardInterrupt:
									raise
								if choice_input == "0":
									# Explicit rescan
									break
								try:
									choice = int(choice_input or "-1")
								except ValueError:
									# Invalid input; re-prompt without rescanning
									continue
								if 1 <= choice <= len(routers):
									chosen_router = routers[choice - 1]
									wifi_ssid = chosen_router.get("ssid", "")
									wifi_bssid = chosen_router.get("bssid", "")
									_si(_base + 6)
									info(f"Selected network: {wifi_ssid}")
									# Exit both prompt loop and scan loop
									break
							# If we got here, user asked to rescan; restart outer loop
							if choice_input == "0":
								continue
							else:
								# Valid selection was made; break outer loop
								break

						# Get password interactively
						wifi_pass = input(f"        Password for '{wifi_ssid}': ").strip()

					else:
						# Non-interactive path
						wifi_ssid = getattr(args, 'ssid', None)
						wifi_pass = getattr(args, 'password', None)
						wifi_bssid = None  # BSSID is not available in non-interactive mode.

						if not wifi_ssid or not wifi_pass:
							warn_("Non-interactive Wi-Fi setup requires --ssid and --password arguments.")
							return None, None, None

						# For non-interactive, we must assume the SSID is ASCII.
						# The bulb protocol requires BSSID for non-ASCII SSIDs.
						if not all(ord(c) < 128 for c in wifi_ssid):
							warn_("Non-ASCII SSIDs are not supported in non-interactive mode because BSSID cannot be determined.")
							warn_("Please run the setup in interactive mode.")
							return None, None, None

						info("")
						info(f"Using provided Wi-Fi network: {wifi_ssid}")

					# Re-Handshake for configuration
					# The bulb requires a fresh handshake before accepting network config
					# This ensures the setup session is still valid and the bulb is ready
					rehandshake_step = "[4/6]" if interactive else "[2/4]"
					s.sendto(json.dumps(start_req).encode("utf-8"), (BULB_IP, BULB_PORT))
					data, addr = s.recvfrom(4096)
					re_handshake_resp = json.loads(data.decode("utf-8"))
					if not re_handshake_resp.get("payload", {}).get("result"):
						warn_("Configuration prep failed")
						return None, None, None

					# Configure Network
					config_step = "[5/6]" if interactive else "[3/4]"
					from sengled.log import set_indent as _si
					_si(10)
					say(">> Sending WiFi credentials to bulb...")

					# Build router config based on SSID content
					ascii_only = all(ord(c) < 128 for c in wifi_ssid)
					if ascii_only:
						router_info = {"ssid": wifi_ssid, "password": wifi_pass}
					else:
						router_info = {"ssid": "", "bssid": wifi_bssid.upper(), "password": wifi_pass}

					# Use the actual HTTP setup server port we bound and the remembered WiFi IP address
					http_port = str(preferred_http_port)
					http_host = http_host_for_urls
					# Use local timezone instead of hardcoding
					local_tz = time.tzname[0] if time.tzname else "UTC"
					params_payload = {
						"name": "setParamsRequest",
						"totalStep": 1,
						"curStep": 1,
						"payload": {
							"userID": "618",
							"appServerDomain": f"http://{http_host}:{http_port}/life2/device/accessCloud.json",
							"jbalancerDomain": f"http://{http_host}:{http_port}/jbalancer/new/bimqtt",
							"timeZone": local_tz,
							"routerInfo": router_info,
						},
					}

					if interactive:
						debug(f"Sending unencrypted payload:\n{json.dumps(params_payload, indent=2)}")

					encrypted_params = encrypt_wifi_payload(params_payload)
					s.sendto(encrypted_params.encode("utf-8"), (BULB_IP, BULB_PORT))

					try:
						data, _ = s.recvfrom(4096)
						response_str = data.decode("utf-8")
						if interactive:
							debug(f"Received raw response from bulb:\n{response_str}")

						try:
							# First, try to parse as JSON (plaintext response)
							# We handle both cases for maximum compatibility
							response_json = json.loads(response_str)
							if interactive:
								debug("Parsed response as plaintext JSON.")
							if response_json.get("payload", {}).get("result") is not True:
								warn_("Bulb rejected credentials (plaintext error).")
								return None, None
						except json.JSONDecodeError:
							# If JSON parsing fails, assume it's encrypted
							if interactive:
								debug("Could not parse as JSON, attempting decryption...")
							decrypted_resp = decrypt_wifi_payload(response_str)
							if interactive:
								debug(f"Decrypted response:\n{json.dumps(decrypted_resp, indent=2)}")
							if not isinstance(decrypted_resp, dict) or not decrypted_resp.get("payload", {}).get("result"):
								warn_("Bulb rejected credentials (decryption failed).")
								return None, None
					except socket.timeout:
						pass  # Timeout is expected here

					success("Wi-Fi credentials accepted by bulb", extra_indent=6)

					# End Configuration
					end_step = "[6/6]" if interactive else "[4/4]"
					end_req = {"name": "endConfigRequest", "totalStep": 1, "curStep": 1, "payload": {}}
					s.sendto(json.dumps(end_req).encode("utf-8"), (BULB_IP, BULB_PORT))

					try:
						s.recvfrom(4096)
					except (socket.timeout, ConnectionResetError):
						pass  # Also expected

					if interactive:
						save_bulb(bulb_mac, lan_ip)
						success(f"Wi-Fi setup complete for {bulb_mac}", extra_indent=6)
					else:
						save_bulb(bulb_mac, lan_ip)
						success(f"Wi-Fi setup complete for {bulb_mac}", extra_indent=6)

					# 8) Wait for the bulb to contact both endpoints, then keep server running
					from sengled.log import set_indent as _si
					_si(0)
					section("Verification")
					waiting("Waiting for bulb to verify setup endpoints, the bulb will be flashing...")
					if is_verbose():
						info("Expected endpoints: /life2/device/accessCloud.json and /jbalancer/new/bimqtt")
					
					if not using_external_http_server:
						both_hit = setup_server.wait_until_both_endpoints_hit(timeout_seconds=180)
						client_ip = setup_server.last_client_ip
					else:
						info("Checking external server /status until both endpoints are hit…")
						both_hit, client_ip = _poll_status_until_both_hit(
							"http://127.0.0.1:57542/status", total_timeout_sec=180.0, interval_sec=1.0
						)

					# Initialize support_info regardless of path, so it's always defined
					support_info = None

					if both_hit:
						success(f"Bulb at {client_ip} contacted both endpoints", extra_indent=2)
							
						# Listen for bulb attributes
						mqtt_client = create_mqtt_client(args, mqtt_host_for_bulb, mqtt_port_for_bulb)
						if mqtt_client.connect():
							try:
								info("")
								subsection("Device Attributes")
								waiting(f"Listening for attributes from {bulb_mac}...")
								attrs = _listen_for_bulb_attributes(mqtt_client, bulb_mac)
								if attrs:
									for key, value in attrs.items():
										cmd(f"{key}: {value}", extra_indent=4)
									# Determine flashing support category and store for later prompt
									type_code = str(attrs.get("typeCode", "") or "")
									identify_no = str(attrs.get("identifyNO", "") or "")
									category = "unknown"
									if type_code in SUPPORTED_TYPECODES:
										category = "supported"
									elif any(marker in identify_no.upper() for marker in COMPATIBLE_IDENTIFY_MARKERS):
										category = "untested"
									else:
										category = "not_supported"
									if setup_server:
										setattr(setup_server, "support_info", {
											"model": type_code or "Unknown",
											"module": identify_no or "Unknown",
											"category": category,
										})
								else:
									warn_("Could not retrieve all bulb attributes.", extra_indent=4)
							finally:
								mqtt_client.disconnect()
						else:
							warn_("Could not connect to MQTT broker to retrieve attributes.")
					else:
						warn_("Timeout waiting for endpoints")


					# Reset external HTTP server
					if using_external_http_server:
						fetch_status("http://127.0.0.1:57542/reset")

					# 9) Try UDP until both OFF and ON succeed; report elapsed time
					if server_started:
						info("")  # Add blank line before UDP test
						try:
							udp_target_ip = client_ip or BULB_IP
							if client_ip:
								_ok = udp_toggle_until_success(udp_target_ip, max_wait_seconds=60)
								if not _ok:
									_print_udp_failure_warning(bulb_mac)
						except Exception:
							_print_udp_failure_warning(bulb_mac)
					else:
						warn_("HTTP server was not started (port busy). Skipping UDP test.")

					break
			except (socket.timeout, ConnectionResetError, OSError):
				# Auto-retry silently; we already showed a single 'Looking for bulb...' line
				continue

		# Keep internal server running so we can flash right away; external server isn't ours.
		if using_external_http_server:
			meta = {"last_client_ip": client_ip, "support_info": support_info}
		else:
			meta = setup_server

		return bulb_mac, meta, using_external_http_server

	except KeyboardInterrupt:
		if server_started and setup_server and setup_server.active:
			print("")  # Add newline before stopping servers
			setup_server.stop()
		if _embedded_broker is not None:
			try:
				_embedded_broker.stop()
			except Exception:
				pass
		warn_("Interrupted by user. Exiting setup.")
		return None, None, None
	except Exception as e:
		if setup_server and setup_server.active:
			setup_server.stop()
		if _embedded_broker is not None:
			try:
				_embedded_broker.stop()
			except Exception:
				pass
		warn_(f"Setup failed: {e}")
		return None, None, None


