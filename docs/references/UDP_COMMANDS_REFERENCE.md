# Sengled Bulb UDP Command Reference

UDP control is a smaller subset than MQTT control; use the MQTT reference for advanced features like scenes, effects, or device management.

## How to Send UDP Commands (using `sengled_tool.py`)

```bash
# Basic syntax
python sengled_tool.py --ip <BULB_IP> --udp-<COMMAND> [PARAMETERS]

# Supported examples
python sengled_tool.py --ip 192.168.8.1 --udp-on
python sengled_tool.py --ip 192.168.8.1 --udp-off
python sengled_tool.py --ip 192.168.8.1 --udp-brightness 50
python sengled_tool.py --ip 192.168.8.1 --udp-set-color 255 0 0
```

---

## Available Commands

| Command | CLI Flag | Parameters | Example |
|--------|----------|------------|---------|
| Power: On | `--udp-on` | none | `python sengled_tool.py --ip 192.168.8.1 --udp-on` |
| Power: Off | `--udp-off` | none | `python sengled_tool.py --ip 192.168.8.1 --udp-off` |
| Brightness | `--udp-brightness` | `0-100` | `python sengled_tool.py --ip 192.168.8.1 --udp-brightness 50` |
| Color (RGB) | `--udp-set-color` | `R G B` (0-255 each) | `python sengled_tool.py --ip 192.168.8.1 --udp-set-color 255 0 0` |
| Custom JSON | `--udp-json` | JSON object | `python sengled_tool.py --ip 192.168.8.1 --udp-json '{"func":"set_device_brightness","param":{"brightness":50}}'` |

---

## Command Payloads & Responses (for reference)

| Command | Request Payload | Response Payload |
|--------|------------------|------------------|
| `set_device_switch` | `{"func":"set_device_switch","param":{"switch":1}}` | `{"func":"set_device_switch","result":{"ret":0,"msg":"success"}}` |
| `set_device_brightness` | `{"func":"set_device_brightness","param":{"brightness":50}}` | `{"func":"set_device_brightness","result":{"ret":0,"msg":"success"}}` |
| `get_device_brightness` | `{"func":"get_device_brightness","param":{}}` | `{"func":"get_device_brightness","result":{"brightness":100,"ret":0,"msg":"success"}}` |
| `set_device_color` | `{"func":"set_device_color","param":{"red":255,"green":0,"blue":0}}` | `{"func":"set_device_color","result":{"ret":0,"msg":"success"}}` |
| `get_device_mode` | `{"func":"get_device_mode","param":{}}` | `{"func":"get_device_mode","result":{"mode":0,"ret":0,"msg":"success"}}` |
| `get_led_color` | `{"func":"get_led_color","param":{}}` | `{"func":"get_led_color","result":{"W":{"freq":0,"value":0},"ret":0,"msg":"success"}}` |
| `set_color_mode` | `{"func":"set_color_mode","param":{"mode":1}}` | `{"func":"set_color_mode","result":{"ret":0,"msg":"success"}}` |
| `set_device_mode` | `{"func":"set_device_mode","param":{"mode":1}}` | `{"func":"set_device_mode","result":{"ret":0,"msg":"success"}}` |
| `get_device_adc` | `{"func":"get_device_adc","param":{}}` | `{"func":"get_device_adc","result":{"adc":630.73,"msg":"success"}}` |
| `set_device_mac` | `{"func":"set_device_mac","param":{}}` | `<no response>` |
| `get_device_mac` | `{"func":"get_device_mac","param":{}}` | `{"func":"get_device_mac","result":{"mac":"00:00:00:00:00:00","ret":0,"msg":"success"}}` |
| `set_factory_mode` | `{"func":"set_factory_mode","param":{}}` | `{"func":"set_factory_mode","result":{"ret":0,"msg":"success"}}` |
| `get_factory_mode` | `{"func":"get_factory_mode","param":{}}` | `{"func":"get_factory_mode","result":{"mode":0,"ret":0,"msg":"success"}}` |
| `get_software_version` | `{"func":"get_software_version","param":{}}` | `{"func":"get_software_version","result":{"version":"RDSW2019004A0530_W21-N13_SYSTEM_V1.0.1.0_20200610_release","ret":0,"msg":"success"}}` |
| `set_device_colortemp` | `{"func":"set_device_colortemp","param":{"colorTemperature":100}}` | `{"func":"set_device_colortemp","result":{"ret":0,"msg":"success"}}` |
| `set_device_pwm` | `{"func":"set_device_pwm","param":{"r":0,"g":0,"b":0,"w":0}}` | `{"func":"set_device_pwm","result":{"ret":0,"msg":"success"}}` |
| `get_dimmer_info` | `{"func":"get_dimmer_info","param":{}}` | `{"func":"get_dimmer_info","result":{"dimer":0,"max":656,"count":0,"maxflag":0,"mini":0,"mini2_count":0,"adc":[...],"ret":0,"msg":"success"}}` |
| `set_device_light` | `{"func":"set_device_light","param":{}}` | `{"func":"set_device_light","result":{"ret":1,"msg":"get b error"}}` |
| `set_device_rgb` | `{"func":"set_device_rgb","param":{"red":255,"green":0,"blue":0}}` | `<no response>` |
| `search_devices` | `{"func":"search_devices","param":{}}` | `{"func":"search_devices","result":{"ret":0,"mac":"00:00:00:00:00:00","ip":"192.168.8.1","config_state":1,"bind_state":1,"mqtt_state":0,"version":"RDSW2019004A0530_W21-N13_SYSTEM_V1.0.1.0_20200610_release","R":{"freq":0,"value":0},"G":{"freq":0,"value":0},"B":{"freq":0,"value":0},"W":{"freq":0,"value":38},"msg":"success"}}` |
| `update_led_firmware` | `{"func":"update_led_firmware","param":{"ota_url":"..."}}` | `{"func":"update_led_firmware","result":{"ret":0,"msg":"success"}}` |
| `reboot` | `{"func":"reboot","param":{}}` | `{"func":"reboot","result":{"ret":0,"msg":"success"}}` |
| `set_device_reboot` | `{"func":"set_device_reboot","param":{}}` | `{"func":"set_device_reboot","result":{"ret":0,"msg":"success"}}` |
| `factory_reset` | `{"func":"factory_reset","param":{}}` | `{"func":"factory_reset","result":{"ret":0,"msg":"success"}}` |
| `set_factory_reset` | `{"func":"set_factory_reset","param":{}}` | `{"func":"set_factory_reset","result":{"ret":0,"msg":"success"}}` |

---

## Quick Examples

### Power Control
```bash
python sengled_tool.py --ip 192.168.8.1 --udp-on
python sengled_tool.py --ip 192.168.8.1 --udp-off
```

### Brightness Control
```bash
python sengled_tool.py --ip 192.168.8.1 --udp-brightness 50
```

### Color Control
```bash
python sengled_tool.py --ip 192.168.8.1 --udp-set-color 255 0 0
python sengled_tool.py --ip 192.168.8.1 --udp-set-color 0 255 0
python sengled_tool.py --ip 192.168.8.1 --udp-set-color 0 0 255
```

### Custom JSON Payload
```bash
# Turn on
python sengled_tool.py --ip 192.168.8.1 --udp-json '{"func":"set_device_switch","param":{"switch":1}}'

# Brightness 50
python sengled_tool.py --ip 192.168.8.1 --udp-json '{"func":"set_device_brightness","param":{"brightness":50}}'

# Color red
python sengled_tool.py --ip 192.168.8.1 --udp-json '{"func":"set_device_color","param":{"red":255,"green":0,"blue":0}}'

# Get hardware version
python sengled_tool.py --ip 192.168.0.196 --udp-json '{"func":"get_hardver","param":{}}'
```

---

## PWM Command Details

### Hardware Architecture

RGBW bulbs have **two separate LED systems**:
- **RGB LEDs** (Red, Green, Blue) - controlled by `r`, `g`, `b` parameters
- **Warm White LED** (separate chip) - controlled by `w` parameter

```
┌─────────────────────────────────────┐
│        RGB LED Array          │  ← Red, Green, Blue LEDs
│  (Cool white when mixed)      │
├─────────────────────────────────────┤
│    Warm White LED (W)         │  ← Separate warm white chip
│  (Yellowish white light)        │
└─────────────────────────────────────┘
```

### Parameter Ranges

| Parameter | Range | Notes |
|-----------|---------|--------|
| `r` (red) | 0-100 | RGB red LED; 0-2 = OFF, >100 saturates |
| `g` (green) | 0-100 | RGB green LED; 0-2 = OFF, >100 saturates |
| `b` (blue) | 0-100 | RGB blue LED; 0-2 = OFF, >100 saturates |
| `w` (warm white) | 0-100 | Warm white LED; 0-2 = OFF, >100 saturates |

**Important:** Values >100 are clamped internally (no effect). Values 0-2 turn LEDs OFF (below threshold).

### Color Mixing Guide

| Color | R | G | B | W | Result |
|--------|---|---|---|--------|
| Pure Red | 100 | 0 | 0 | 0 | Red |
| Pure Green | 0 | 100 | 0 | 0 | Green |
| Pure Blue | 0 | 0 | 100 | 0 | Blue |
| Warm White | 0 | 0 | 0 | 100 | Yellowish white (2700K-3000K) |
| Cool White | 100 | 100 | 100 | 0 | Cool white (no tint) |
| Neutral White | 80 | 80 | 80 | 100 | Mix of cool+warm white |
| Orange | 100 | 50 | 0 | 0 | Red+Green |
| Purple | 100 | 0 | 100 | 0 | Red+Blue |
| Cyan | 0 | 100 | 100 | 0 | Green+Blue |
| Green+White | 0 | 100 | 0 | 100 | Green with warm white boost |

### Important Limitations

#### 1. PWM Mode is Temporary (Volatile)
- **PWM values do NOT persist** to flash memory
- PWM is a "preview/test" mode - works until mode changes
- Any stateful command exits PWM mode:
  - `set_device_brightness`
  - `set_device_color`
  - `set_device_colortemp`
  - `set_device_switch`
- When mode exits, firmware reloads saved state (RGB or colortemp mode)

#### 2. Brightness Reloads Saved State
```bash
# This sequence will NOT work as expected:
python sengled_tool.py --ip <IP> --udp-json '{"func":"set_device_pwm","param":{"r":0,"g":100,"b":0,"w":100}}'  # PWM green+white
python sengled_tool.py --ip <IP> --udp-set-brightness 50  # ← Exits PWM mode, reloads saved state
```
**Result:** Brightness change will exit PWM mode and display saved RGB/colortemp state, NOT PWM values.

#### 3. State Query Cannot Read PWM
```bash
python sengled_tool.py --ip <IP> --udp-json '{"func":"search_devices","param":{}}'
```
`search_devices` returns cached RGB/colortemp values, **NOT current PWM state**. This is a protocol limitation.

#### 4. For Persistent Color, Use RGB or Colortemp Mode

**Recommended:**
- Use `set_device_color` for RGB colors (persistent)
- Use `set_device_colortemp` for white light (persistent)
- Use `set_device_pwm` only for testing/preview (temporary)

**Avoid:** Mixing PWM with other commands. Once you use PWM, avoid brightness/color/colortemp/switch commands to maintain the effect.

### Comparison of Control Modes

| Mode | Command | Persists? | `search_devices` Accurate? | Best For |
|-------|---------|-------------|-------------------------|-----------|
| RGB Mode | `set_device_color` | ✅ Yes | ✅ Yes | Pure RGB colors |
| Colortemp Mode | `set_device_colortemp` | ✅ Yes | ✅ Yes | White light (2700K-6500K) |
| PWM Mode | `set_device_pwm` | ❌ No | ❌ No | Testing/preview only |

---

- Default IP: `192.168.8.1` (bulb AP mode)
- Port: `9080` (UDP)
- Timeout: 3 seconds (fixed inside tool)
- Color values: RGB 0-255 (see [PWM Command Details](#pwm-command-details) for PWM 0-100 range)
- Brightness: 0-100

## Discovery (find bulbs on your LAN)

The bulb responds to `search_devices`. If you send it as a **UDP broadcast** and listen for replies, you can usually discover bulbs on the **same LAN/VLAN**.

Limitations:
- Broadcast discovery typically **will not cross subnets/VLANs**
- Some routers/AP isolation settings will block it

Example Python snippet:

```python
import json
import socket
import time

msg = json.dumps({"func": "search_devices", "param": {}}).encode()

sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
sock.setsockopt(socket.SOL_SOCKET, socket.SO_BROADCAST, 1)
sock.settimeout(0.3)

sock.sendto(msg, ("255.255.255.255", 9080))

end = time.time() + 2.0
while time.time() < end:
    try:
        data, addr = sock.recvfrom(2048)
    except socket.timeout:
        continue
    try:
        payload = json.loads(data.decode(errors="ignore"))
    except Exception:
        continue
    print(addr[0], payload)
```


## Function discovery and errors

- There may be more UDP functions than listed here. You can send any known payload via `--udp-json`.
- If you call a non-existent function, the bulb responds like:
```json
{"result":{"ret":1,"msg":"function not find"}}
```
- If the function exists but parameters are wrong, you'll see an error tied to that function, e.g.:
```json
{"func":"set_device_brightness","result":{"ret":1,"msg":"get brightness error"}}
```
- **Function discovery tip**: Send unknown function names to discover what's available:
  - Unknown function → returns `{"result":{"ret":1,"msg":"function not find"}}`
  - Valid function with wrong params → returns function-specific error message
  - Use this pattern to find new functions and figure out their parameters


