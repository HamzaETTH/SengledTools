# Sengled Bulb UDP Command Reference

## How to Send UDP Commands (using `sengled_tool.py`)

```bash
# Basic syntax
python sengled_tool.py --ip <BULB_IP> --udp-<COMMAND> [PARAMETERS]

# Supported examples
python sengled_tool.py --ip 192.168.8.1 --udp-on
python sengled_tool.py --ip 192.168.8.1 --udp-off
python sengled_tool.py --ip 192.168.8.1 --udp-brightness 50
python sengled_tool.py --ip 192.168.8.1 --udp-color 255 0 0
```

---

## Available Commands

| Command | CLI Flag | Parameters | Example |
|--------|----------|------------|---------|
| Power: On | `--udp-on` | none | `python sengled_tool.py --ip 192.168.8.1 --udp-on` |
| Power: Off | `--udp-off` | none | `python sengled_tool.py --ip 192.168.8.1 --udp-off` |
| Brightness | `--udp-brightness` | `0-100` | `python sengled_tool.py --ip 192.168.8.1 --udp-brightness 50` |
| Color (RGB) | `--udp-color` | `R G B` (0-255 each) | `python sengled_tool.py --ip 192.168.8.1 --udp-color 255 0 0` |
| Custom JSON | `--udp-json` | JSON object | `python sengled_tool.py --ip 192.168.8.1 --udp-json '{"func":"set_device_brightness","param":{"brightness":50}}'` |

---

## Command Payloads & Responses (for reference)

| Command | Request Payload | Response Payload |
|--------|------------------|------------------|
| `set_device_switch` | `{"func":"set_device_switch","param":{"switch":1}}` | `{"func":"set_device_switch","result":{"ret":0,"msg":"success"}}` |
| `set_device_brightness` | `{"func":"set_device_brightness","param":{"brightness":50}}` | `{"func":"set_device_brightness","result":{"ret":0,"msg":"success"}}` |
| `set_device_color` | `{"func":"set_device_color","param":{"color":"255:0:0"}}` | `{"func":"set_device_color","result":{"ret":0,"msg":"success"}}` |

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
python sengled_tool.py --ip 192.168.8.1 --udp-color 255 0 0
python sengled_tool.py --ip 192.168.8.1 --udp-color 0 255 0
python sengled_tool.py --ip 192.168.8.1 --udp-color 0 0 255
```

### Custom JSON Payload
```bash
# Turn on
python sengled_tool.py --ip 192.168.8.1 --udp-json '{"func":"set_device_switch","param":{"switch":1}}'

# Brightness 50
python sengled_tool.py --ip 192.168.8.1 --udp-json '{"func":"set_device_brightness","param":{"brightness":50}}'

# Color red (255:0:0 format)
python sengled_tool.py --ip 192.168.8.1 --udp-json '{"func":"set_device_color","param":{"color":"255:0:0"}}'
```

---

## Notes

- Default IP: `192.168.8.1` (bulb AP mode)
- Port: `9080` (UDP)
- Timeout: 3 seconds (fixed inside tool)
- Color values: RGB 0-255
- Brightness: 0-100


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


