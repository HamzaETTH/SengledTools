## Sengled UDP (Home Assistant custom component)

This is a Home Assistant custom integration that controls Sengled Wi-Fi bulbs directly over UDP on your LAN (no cloud). It exposes a `light` entity with on/off, brightness, RGB color, and color temperature support using the same UDP protocol documented in this repo.

Setup: copy this folder into your Home Assistant `config/custom_components/sengled_udp`, restart Home Assistant, then add the "Sengled UDP" integration and enter the bulb IP (and optional name). The bulb must be reachable on UDP port 9080 from Home Assistant.

Notes: this integration talks to the bulb directly; it does not use MQTT and does not pair the bulb for you.