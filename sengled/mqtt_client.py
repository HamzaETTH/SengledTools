"""
MQTT client wrapper for Sengled bulb communication.
Wraps paho-mqtt with TLS support, handles connection management,
topic subscription/publishing, and update command delivery.
"""

import paho.mqtt.client as mqtt
from typing import Optional
import time
import ssl
import threading
import json

from sengled.log import success, warn, debug
from pathlib import Path


def send_update_command(client: "MQTTClient", mac_address: str, command_list: list):
    """
    Sends a command to the bulb's update topic using a "fire-and-forget" approach.
    """
    update_topic = f"wifielement/{mac_address}/update"
    payload = json.dumps(command_list)

    debug(f"Topic: {update_topic}")
    debug(f"Payload: {payload}")

    # Just publish the command. Do not subscribe or wait.
    publish_success = client.publish(update_topic, payload, qos=1)

    if publish_success:
        success("Command sent successfully")
        # Brief pause to ensure the message is sent before the script potentially exits
        time.sleep(0.5)
        return payload
    else:
        warn("Failed to send command")
        return None


def publish_topic(client: "MQTTClient", topic: str, payload, qos: int = 1, json_encode: bool = False) -> bool:
    """Publish to any topic, optionally JSON-encoding payload."""
    body = json.dumps(payload) if json_encode and not isinstance(payload, str) else payload
    return bool(client.publish(topic, body, qos=qos))


class MQTTClient:
    def __init__(self, broker: str, port: int = 8883, keepalive: int = 60, use_tls: bool = True,
                 ca_certs: str | None = None, certfile: str | None = None, keyfile: str | None = None):
        self.broker = broker
        self.port = port
        self.keepalive = keepalive
        self.use_tls = use_tls
        # Do not force default cert file paths; only use what was provided
        self.ca_certs = ca_certs
        self.certfile = certfile
        self.keyfile = keyfile
        # Generate a client ID for amqtt compatibility
        import uuid
        client_id = f"sengled_client_{str(uuid.uuid4())[:8]}"
        self.client = mqtt.Client(mqtt.CallbackAPIVersion.VERSION1, client_id=client_id)
        self.received_messages = []
        self.client.on_message = self._on_message
        self.client.on_connect = self._on_connect
        self.client.on_disconnect = self._on_disconnect
        self.client.on_log = self._on_log
        self._connected_event = threading.Event()
        self._connect_rc = None  # Store result code for inspection

    def _on_connect(self, client, userdata, flags, rc):
        self._connect_rc = rc
        if rc == 0:
            try:
                info("")
                debug(f"MQTT client connected to broker at {self.broker}:{self.port}")
            except Exception:
                pass
        else:
            try:
                warn(f"Failed to connect to MQTT broker, return code: {rc}")
            except Exception:
                pass
        self._connected_event.set()

    def _on_message(self, client, userdata, msg):
        """Callback when message is received"""
        message = {
            'topic': msg.topic,
            'payload': msg.payload.decode('utf-8'),
            'qos': msg.qos,
            'retain': msg.retain
        }
        self.received_messages.append(message)
        try:
            debug(f"Received message on {msg.topic}: {msg.payload.decode('utf-8')}")
        except Exception:
            pass

    def _on_disconnect(self, client, userdata, rc):
        try:
            debug(f"MQTT client disconnected with return code: {rc}")
        except Exception:
            pass

    def _on_log(self, client, userdata, level, buf):
        try:
            debug(f"MQTT log [{level}]: {buf}")
        except Exception:
            pass

    def connect(self, timeout: float = 10.0) -> bool:
        """Connects to the MQTT broker and waits until connection is established or fails."""
        try:
            self._connected_event.clear()
            if self.use_tls:
                # Only pass certfile/keyfile if both are provided
                if self.certfile and self.keyfile:
                    try:
                        debug(f"Setting up TLS with client certificates")
                        debug(f"ca_certs: {self.ca_certs}")
                        debug(f"certfile: {self.certfile}")
                        debug(f"keyfile: {self.keyfile}")
                        
                        # Check if files actually exist and are readable
                        import os
                        if self.certfile and os.path.exists(self.certfile):
                            debug(f"Certfile exists and size: {os.path.getsize(self.certfile)} bytes")
                        else:
                            debug(f"Certfile issue: exists={os.path.exists(self.certfile) if self.certfile else 'None'}")
                            
                        if self.keyfile and os.path.exists(self.keyfile):
                            debug(f"Keyfile exists and size: {os.path.getsize(self.keyfile)} bytes")
                        else:
                            debug(f"Keyfile issue: exists={os.path.exists(self.keyfile) if self.keyfile else 'None'}")
                        
                        debug(f"About to call tls_set with:")
                        debug(f"  ca_certs={self.ca_certs}")
                        debug(f"  certfile={self.certfile}")
                        debug(f"  keyfile={self.keyfile}")
                        debug(f"  cert_reqs=ssl.CERT_NONE")
                        debug(f"  tls_version=ssl.PROTOCOL_TLSv1_2")
                        
                        # Configure TLS to match amqtt broker expectations
                        # amqtt documentation shows it needs proper CA verification
                        self.client.tls_set(
                            ca_certs=self.ca_certs,
                            certfile=self.certfile,
                            keyfile=self.keyfile,
                            cert_reqs=ssl.CERT_REQUIRED if self.ca_certs else ssl.CERT_NONE,
                            tls_version=ssl.PROTOCOL_TLS
                        )
                        debug("TLS setup completed successfully")
                        debug(f"Client TLS context: {self.client._ssl_context}")
                        debug(f"About to connect to {self.broker}:{self.port}")
                    except Exception as e:
                        debug(f"TLS setup with client certs failed: {e}")
                        raise
                else:
                    try:
                        debug("Setting up TLS without client certificates")
                        # Try most permissive TLS settings for amqtt compatibility
                        self.client.tls_set(
                            ca_certs=None,  # Don't verify server cert
                            certfile=None,
                            keyfile=None,
                            cert_reqs=ssl.CERT_NONE,
                            tls_version=ssl.PROTOCOL_TLS
                        )
                    except Exception as e:
                        debug(f"TLS setup without client certs failed: {e}")
                        raise
                self.client.tls_insecure_set(True)
            debug(f"Attempting MQTT connect to {self.broker}:{self.port}")
            self.client.connect(self.broker, self.port, self.keepalive)
            self.client.loop_start()
            debug("MQTT client loop started, waiting for connection...")
            connected = self._connected_event.wait(timeout)
            if not connected:
                warn(f"Timed out waiting for MQTT connection to {self.broker}:{self.port}")
                debug(f"Connection state: connected={self.client.is_connected()}, rc={self._connect_rc}")
                return False
            debug(f"Connection completed with return code: {self._connect_rc}")
            return self._connect_rc == 0
        except (ConnectionRefusedError, OSError) as e:
            warn(f"MQTT connection to {self.broker}:{self.port} failed: {e}")
            return False

    def subscribe(self, topic: str, qos: int = 0) -> bool:
        """Subscribes to a topic."""
        if not self.client.is_connected():
            warn("MQTT client is not connected.")
            return False
        
        result = self.client.subscribe(topic, qos)
        if result[0] == mqtt.MQTT_ERR_SUCCESS:
            success(f"Subscribed to {topic}")
            return True
        else:
            warn(f"Failed to subscribe to {topic}")
            return False

    def publish(self, topic: str, payload: str, qos: int = 0, retain: bool = False) -> bool:
        """Publishes a message to a given topic."""
        if not self.client.is_connected():
            warn("MQTT client is not connected.")
            return False
        
        result = self.client.publish(topic, payload, qos, retain)
        result.wait_for_publish(timeout=5)
        
        if result.is_published():
            return True
        else:
            warn(f"Failed to publish message to topic: {topic}")
            return False

    def has_message(self) -> bool:
        """Check if any messages have been received."""
        return len(self.received_messages) > 0

    def get_message(self) -> Optional[dict]:
        """Get the next received message."""
        if self.received_messages:
            return self.received_messages.pop(0)
        return None

    def clear_messages(self):
        """Clear all received messages."""
        self.received_messages.clear()

    def disconnect(self):
        """Disconnects from the MQTT broker."""
        self.client.loop_stop()
        self.client.disconnect()


def create_mqtt_client(
    args,
    broker_host: str | None = None,
    broker_port: int | None = None,
):
    """Unified MQTT client factory (TLS-only) used across the tool.

    Rules:
    - Always use TLS
    - If broker_host is 127.0.0.1, force TLS port 8883 (embedded broker)
    - Else use broker_port if provided, otherwise args.broker_port (default 8883)
    - Certs are optional and pulled from args when present
    - Auto-detect embedded broker CA when connecting to 127.0.0.1
    """
    from sengled.mqtt_broker import BROKER_TLS_PORT

    host = broker_host or getattr(args, "broker_ip", None)
    if not host:
        # Fallback to local IP from utils to match original behavior
        from sengled.utils import get_local_ip
        host = get_local_ip()

    if host == "127.0.0.1":
        port = BROKER_TLS_PORT
    else:
        try:
            port = int(broker_port if broker_port is not None else getattr(args, "broker_port", BROKER_TLS_PORT) or BROKER_TLS_PORT)
        except (TypeError, ValueError):
            port = BROKER_TLS_PORT

    ca_certs = getattr(args, "ca_crt", None)
    certfile = getattr(args, "server_crt", None)
    keyfile = getattr(args, "server_key", None)

    if host == "127.0.0.1" and not certfile and not keyfile:
        cert_dir = Path.home() / ".sengled" / "certs"
        embedded_ca = cert_dir / "ca.crt"
        if embedded_ca.exists():
            try:
                debug("Auto-detected local broker CA certificate")
            except Exception:
                pass
            ca_certs = str(embedded_ca)
            certfile = None
            keyfile = None

    return MQTTClient(
        host,
        port=port,
        use_tls=True,
        ca_certs=ca_certs,
        certfile=certfile,
        keyfile=keyfile,
    )
