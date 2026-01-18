"""
Shared constants for the Sengled local control tool.
Contains network settings, port configurations, and device compatibility matrices.
"""

# Static IP of the bulb when it's in AP mode for initial setup.
BULB_IP = "192.168.8.1"
BULB_PORT = 9080

# MQTT Configuration
DEFAULT_BROKER_PORT = 8883  # Default for TLS brokers
BROKER_TLS_PORT = 8883  # TLS port for embedded broker

# Compatibility / Support Matrix
# Exact model codes that are confirmed supported by the current shim/flow
# These are the only models we can guarantee will work with firmware flashing
SUPPORTED_TYPECODES = {
	"W31-N11",
	"W31-N15",
}

# Identify markers that indicate the module is likely compatible (best-effort)
# These are ESP8266-based bulbs that should work but haven't been fully tested
# Use with caution - MQTT/UDP control should work, but firmware flashing is untested
COMPATIBLE_IDENTIFY_MARKERS = (
	"ESP8266",
)
