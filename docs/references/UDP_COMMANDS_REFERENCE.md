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


