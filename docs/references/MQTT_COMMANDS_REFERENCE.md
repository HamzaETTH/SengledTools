# Sengled Wi-Fi Bulb MQTT Commands Reference

Complete reference for all MQTT commands that can be sent to Sengled Wi-Fi bulbs, based on analysis of the decompiled mobile app source code.

## 📋 Table of Contents

- [Command Line Examples](#command-line-examples)
- [Topic Structure](#topic-structure)
- [Basic Control Commands](#basic-control-commands)
- [Advanced Control Commands](#advanced-control-commands)
- [Scene Commands](#scene-commands)
- [Entertainment Sync Commands](#entertainment-sync-commands)
- [Device Management Commands](#device-management-commands)
- [Status & Query Commands](#status--query-commands)
- [Special Effects](#special-effects)
- [Firmware Updates](#firmware-updates)
- [Implementation Examples](#implementation-examples)

---

## 💻 Command Line Examples

### **Using sengled_tool.py**

**Basic Control Commands:**
```bash
# Turn bulb on
python sengled_tool.py --mac E8:DB:84:F9:BE:B4 --on

# Turn bulb off  
python sengled_tool.py --mac E8:DB:84:F9:BE:B4 --off

# Toggle bulb state
python sengled_tool.py --mac E8:DB:84:F9:BE:B4 --toggle

# Set brightness (0-100)
python sengled_tool.py --mac E8:DB:84:F9:BE:B4 --brightness 75

# Set RGB color (0-255 for each component)
python sengled_tool.py --mac E8:DB:84:F9:BE:B4 --color 255 0 0    # Red
python sengled_tool.py --mac E8:DB:84:F9:BE:B4 --color 0 255 0    # Green
python sengled_tool.py --mac E8:DB:84:F9:BE:B4 --color 0 0 255    # Blue
python sengled_tool.py --mac E8:DB:84:F9:BE:B4 --color 255 255 0  # Yellow
python sengled_tool.py --mac E8:DB:84:F9:BE:B4 --color 255 0 255  # Magenta
python sengled_tool.py --mac E8:DB:84:F9:BE:B4 --color 0 255 255  # Cyan

# Set color temperature (0-100 percent; 0=2700K, 100=6500K)
python sengled_tool.py --mac E8:DB:84:F9:BE:B4 --color-temp 50

# Set color mode (1=RGB, 2=white/temperature)
python sengled_tool.py --mac E8:DB:84:F9:BE:B4 --color-mode 1

# Set effect status (0=off, 7=audio sync, 100=video sync, 101=game sync)
python sengled_tool.py --mac E8:DB:84:F9:BE:B4 --effect-status 0

# Query bulb status
python sengled_tool.py --mac E8:DB:84:F9:BE:B4 --status
```

**Wi-Fi Setup Commands:**
```bash
# Interactive Wi-Fi setup
python sengled_tool.py --setup-wifi --broker-ip 192.168.0.100

# Non-interactive Wi-Fi setup
python sengled_tool.py --setup-wifi --broker-ip 192.168.0.100 --ssid "MyWiFi" --password "MyPassword"
```

**UDP Control Commands (Direct Network Control):**
```bash
# Turn on via UDP (requires bulb IP)
python sengled_tool.py --ip 192.168.0.247 --udp-on

# Turn off via UDP
python sengled_tool.py --ip 192.168.0.247 --udp-off

# Set brightness via UDP
python sengled_tool.py --ip 192.168.0.247 --udp-brightness 50

# Set color via UDP
python sengled_tool.py --ip 192.168.0.247 --udp-set-color 255 0 0
```

**Advanced Usage Examples:**
```bash
# Quick color cycling demo
python sengled_tool.py --mac E8:DB:84:F9:BE:B4 --color 255 0 0    # Red
sleep 2
python sengled_tool.py --mac E8:DB:84:F9:BE:B4 --color 0 255 0    # Green  
sleep 2
python sengled_tool.py --mac E8:DB:84:F9:BE:B4 --color 0 0 255    # Blue
sleep 2
python sengled_tool.py --mac E8:DB:84:F9:BE:B4 --off

# Brightness fade demo
python sengled_tool.py --mac E8:DB:84:F9:BE:B4 --on
python sengled_tool.py --mac E8:DB:84:F9:BE:B4 --brightness 25
sleep 1
python sengled_tool.py --mac E8:DB:84:F9:BE:B4 --brightness 50
sleep 1
python sengled_tool.py --mac E8:DB:84:F9:BE:B4 --brightness 75
sleep 1
python sengled_tool.py --mac E8:DB:84:F9:BE:B4 --brightness 100
```

**Troubleshooting Commands:**
```bash
# Check if bulb is online and responding
python sengled_tool.py --mac E8:DB:84:F9:BE:B4 --status

# Test UDP connectivity (if you know bulb IP)
python sengled_tool.py --ip 192.168.0.247 --udp-on
python sengled_tool.py --ip 192.168.0.247 --udp-off

# Monitor MQTT traffic (in separate terminal)
mosquitto_sub -h 192.168.0.100 -t "wifielement/E8:DB:84:F9:BE:B4/#"
```

**Help and Information:**
```bash
# Show all available options
python sengled_tool.py --help

# Show help for specific command groups
python sengled_tool.py --help | grep -A 10 "Bulb Control"
python sengled_tool.py --help | grep -A 10 "UDP Control"
```

---

## 🎯 Topic Structure

### **Topic Namespaces**
- **Bulb Control**: `wifielement/{MAC_ADDRESS}/update`
- **Status Query**: `wifielement/{MAC_ADDRESS}/status`
- **Firmware Update**: `wifielement/{MAC_ADDRESS}/update` (uses `"type": "update"`)

### **Payload Format**
- **Control Commands**: Plain JSON array published to `wifielement/{MAC}/update` (no `Os$` wrapper in this tool)
- **Firmware Updates**: JSON array with `"type": "update"` published to `wifielement/{MAC}/update`
- Note: the mobile app historically used `Os$[...]` and an HTTP proxy endpoint; this tool publishes directly to MQTT.

---

## 🎛️ Basic Control Commands

### **Power Control**

**Turn On:**
```json
{
  "topic": "wifielement/80:A0:36:E1:8E:B8/update",
  "downMsg": "Os$[{\"dn\":\"80:A0:36:E1:8E:B8\",\"type\":\"switch\",\"value\":\"1\",\"time\":1662036404644}]"
}
```

**Turn Off:**
```json
{
  "topic": "wifielement/80:A0:36:E1:8E:B8/update",
  "downMsg": "Os$[{\"dn\":\"80:A0:36:E1:8E:B8\",\"type\":\"switch\",\"value\":\"0\",\"time\":1662036404644}]"
}
```

### **Brightness Control**

**Set Brightness (0-100):**
```json
{
  "topic": "wifielement/80:A0:36:E1:8E:B8/update",
  "downMsg": "Os$[{\"dn\":\"80:A0:36:E1:8E:B8\",\"type\":\"brightness\",\"value\":\"75\",\"time\":1662036404644}]"
}
```

### **Color Control**

**Set RGB Color:**
```json
{
  "topic": "wifielement/80:A0:36:E1:8E:B8/update",
  "downMsg": "Os$[{\"dn\":\"80:A0:36:E1:8E:B8\",\"type\":\"color\",\"value\":\"FF0000\",\"time\":1662036404644}]"
}
```

**Color Values (Hex Format):**
- Red: `"FF0000"`
- Green: `"00FF00"`
- Blue: `"0000FF"`
- White: `"FFFFFF"`
- Yellow: `"FFFF00"`
- Purple: `"800080"`

**Color Values (Colon-Separated Format):**
- Red: `"255:0:0"`
- Green: `"0:255:0"`
- Blue: `"0:0:255"`
- White: `"255:255:255"`
- Yellow: `"255:255:0"`
- Purple: `"128:0:128"`

*Note: Both hex and colon-separated formats are supported by the bulbs.*

### **White Light Control**

**Set White Light (Color Temperature):**
```json
{
  "topic": "wifielement/80:A0:36:E1:8E:B8/update",
  "downMsg": "Os$[{\"dn\":\"80:A0:36:E1:8E:B8\",\"type\":\"white\",\"value\":\"2700\",\"time\":1662036404644}]"
}
```

---

## 🎛️ Advanced Control Commands

### **Color Temperature Control**

**Set Color Temperature (with auto-switch on):**
```json
{
  "topic": "wifielement/80:A0:36:E1:8E:B8/update",
  "downMsg": "Os$[{\"dn\":\"80:A0:36:E1:8E:B8\",\"type\":\"colorTemperature\",\"value\":\"2700\",\"time\":1662036404644},{\"dn\":\"80:A0:36:E1:8E:B8\",\"type\":\"switch\",\"value\":\"1\",\"time\":1662036404644}]"
}
```

**Color Temperature Values:**
- Values used in examples: `"2700"`, `"6500"`, `"5500"`

### **White Presets (App mapping)**

When using the app's White tab, the bundle sends `colorTemperature` on a 0–100 scale and also turns the bulb on in the same payload.

Presets mapping (from decompiled app bundle):

- Warm → `0`
- Soft → `17`
- White → `39`
- Daylight → `58`
- Cool → `100`

Example (set Daylight preset and turn on):

```json
{
  "topic": "wifielement/80:A0:36:E1:8E:B8/update",
  "downMsg": "Os$[{\"dn\":\"80:A0:36:E1:8E:B8\",\"type\":\"colorTemperature\",\"value\":\"58\",\"time\":1662036404644},{\"dn\":\"80:A0:36:E1:8E:B8\",\"type\":\"switch\",\"value\":\"1\",\"time\":1662036404644}]"
}
```

### **Effect Status Control**

**Set Effect Status:**
```json
{
  "topic": "wifielement/80:A0:36:E1:8E:B8/update",
  "downMsg": "Os$[{\"dn\":\"80:A0:36:E1:8E:B8\",\"type\":\"effectStatus\",\"value\":\"0\",\"time\":1662036404644}]"
}
```

**Effect Status Values:**
- **`"0"`**: No effect (normal mode)
- **`"7"`**: Audio synchronization mode
- **`"100"`**: Video synchronization mode
- **`"101"`**: Game synchronization mode

### **Group Control**

**Control Multiple Bulbs:**
```json
{
  "topic": "wifielement/80:A0:36:E1:8E:B8/update",
  "downMsg": "Os$[{\"dn\":\"80:A0:36:E1:8E:B8\",\"type\":\"groupSwitch\",\"value\":{\"switch\":\"1\",\"gradientTime\":5000,\"deviceUuidList\":[\"80:A0:36:E1:8E:B8\",\"80:A0:36:E1:8E:B9\"]},\"time\":1662036404644}]"
}
```

**Group Brightness:**
```json
{
  "topic": "wifielement/80:A0:36:E1:8E:B8/update",
  "downMsg": "Os$[{\"dn\":\"80:A0:36:E1:8E:B8\",\"type\":\"groupBrightness\",\"value\":{\"brightness\":\"75\",\"gradientTime\":3000,\"deviceUuidList\":[\"80:A0:36:E1:8E:B8\",\"80:A0:36:E1:8E:B9\"]},\"time\":1662036404644}]"
}
```

**Group Color Temperature:**
```json
{
  "topic": "wifielement/80:A0:36:E1:8E:B8/update",
  "downMsg": "Os$[{\"dn\":\"80:A0:36:E1:8E:B8\",\"type\":\"groupColorTemperature\",\"value\":{\"colorTemperature\":\"2700\",\"gradientTime\":5000,\"deviceUuidList\":[\"80:A0:36:E1:8E:B8\",\"80:A0:36:E1:8E:B9\"]},\"time\":1662036404644}]"
}
```

### **Gradient/Transition Control**

**Smooth Transition with Gradient Time:**
```json
{
  "topic": "wifielement/80:A0:36:E1:8E:B8/update",
  "downMsg": "Os$[{\"dn\":\"80:A0:36:E1:8E:B8\",\"type\":\"switch\",\"value\":\"1\",\"gradientTime\":3000,\"time\":1662036404644}]"
}
```

---

## 🎭 Scene Commands

### **Predefined Scenes**

**Activate Scene:**
```json
{
  "topic": "wifielement/80:A0:36:E1:8E:B8/update",
  "downMsg": "Os$[{\"dn\":\"80:A0:36:E1:8E:B8\",\"type\":\"scene\",\"value\":\"Sleep\",\"time\":1662036404644}]"
}
```

**Available Scenes:**
- **`"Sleep"`**: Night mode with Edison color (#e89543)
- **`"Read"`**: Reading mode with Warm color (#f8c18c)
- **`"TV"`**: TV mode with Neutral color (#ffe8cf)
- **`"Sunrise"`**: Sunrise mode with Cool color (#fffcdf)
- **`"Dinner"`**: Dinner mode with Daylight color (#fbfaf1)

### **System Scenes**

**System Scene Commands:**
```json
{
  "topic": "wifielement/80:A0:36:E1:8E:B8/update",
  "downMsg": "Os$[{\"dn\":\"80:A0:36:E1:8E:B8\",\"type\":\"scene\",\"value\":\"on\",\"time\":1662036404644}]"
}
```

**Available System Scenes:**
- **`"on"`**: Turn on
- **`"off"`**: Turn off
- **`"backhome"`**: Back home mode
- **`"leavehome"`**: Leave home mode
- **`"reading"`**: Reading mode
- **`"Bedroom"`**: Bedroom mode
- **`"tv"`**: TV mode
- **`"dinner"`**: Dinner mode

---

## 🎭 Entertainment Sync Commands

*These commands are specifically for **TV Boxes** and **Entertainment Systems** that support audio/video synchronization.*

### **Audio Sync Mode**

**Enable Audio Synchronization:**
```json
{
  "topic": "wifielement/80:A0:36:E1:8E:B8/update",
  "downMsg": "Os$[{\"dn\":\"80:A0:36:E1:8E:B8\",\"type\":\"audioSync\",\"value\":\"1\",\"time\":1662036404644}]"
}
```

### **Video Sync Mode**

**Enable Video Synchronization:**
```json
{
  "topic": "wifielement/80:A0:36:E1:8E:B8/update",
  "downMsg": "Os$[{\"dn\":\"80:A0:36:E1:8E:B8\",\"type\":\"videoSync\",\"value\":\"1\",\"time\":1662036404644}]"
}
```

### **Game Sync Mode**

**Enable Game Synchronization:**
```json
{
  "topic": "wifielement/80:A0:36:E1:8E:B8/update",
  "downMsg": "Os$[{\"dn\":\"80:A0:36:E1:8E:B8\",\"type\":\"gameSync\",\"value\":\"1\",\"time\":1662036404644}]"
}
```

### **Sync Mode Control**

**Set Sync Mode (for TV Boxes):**
```json
{
  "topic": "wifielement/80:A0:36:E1:8E:B8/update",
  "downMsg": "Os$[{\"dn\":\"80:A0:36:E1:8E:B8\",\"type\":\"syncMode\",\"value\":\"0\",\"time\":1662036404644}]"
}
```

**Sync Mode Values:**
- **`"0"`**: Video sync mode (effectStatus: 100)
- **`"1"`**: Game sync mode (effectStatus: 101)

---

## ⚙️ Device Management Commands

*These commands are for **device configuration**, **maintenance**, and **system management**.*

### **Device Configuration**

**Configure Device Settings:**
```json
{
  "topic": "wifielement/80:A0:36:E1:8E:B8/update",
  "downMsg": "Os$[{\"dn\":\"80:A0:36:E1:8E:B8\",\"type\":\"config\",\"value\":\"{CONFIG_DATA}\",\"time\":1662036404644}]"
}
```

### **Device Reset**

**Reset Device to Factory Settings:**
```json
{
  "topic": "wifielement/80:A0:36:E1:8E:B8/update",
  "downMsg": "Os$[{\"dn\":\"80:A0:36:E1:8E:B8\",\"type\":\"reset\",\"value\":\"1\",\"time\":1662036404644}]"
}
```

### **Device Information Query**

**Request Device Information:**
```json
{
  "topic": "wifielement/80:A0:36:E1:8E:B8/update",
  "downMsg": "Os$[{\"dn\":\"80:A0:36:E1:8E:B8\",\"type\":\"info\",\"value\":\"\",\"time\":1662036404644}]"
}
```

### **Device Update Command**

**Trigger Device Update:**
```json
{
  "topic": "wifielement/80:A0:36:E1:8E:B8/update",
  "downMsg": "Os$[{\"dn\":\"80:A0:36:E1:8E:B8\",\"type\":\"update\",\"value\":\"1\",\"time\":1662036404644}]"
}
```

---

## 📊 Status & Query Commands

### **Status Query**

**Request Bulb Status:**
```json
{
  "topic": "wifielement/80:A0:36:E1:8E:B8/status",
  "downMsg": "Os$[{\"dn\":\"80:A0:36:E1:8E:B8\",\"type\":\"status\",\"value\":\"\",\"time\":1662036404644}]"
}
```

**Expected Status Response:**
```json
{
  "dn": "80:A0:36:E1:8E:B8",
  "switch": "1",
  "brightness": "75",
  "color": "FF0000",
  "colorTemperature": "2700",
  "online": true,
  "time": 1662036404644
}
```

---

## 🌈 Special Effects

### **Color Cycle Effect**

**Start Color Cycling:**
```json
{
  "topic": "wifielement/80:A0:36:E1:8E:B8/update",
  "downMsg": "Os$[{\"dn\":\"80:A0:36:E1:8E:B8\",\"type\":\"effect\",\"value\":\"colorCycle\",\"time\":1662036404644}]"
}
```

### **Random Color Effect**

**Start Random Colors:**
```json
{
  "topic": "wifielement/80:A0:36:E1:8E:B8/update",
  "downMsg": "Os$[{\"dn\":\"80:A0:36:E1:8E:B8\",\"type\":\"effect\",\"value\":\"randomColor\",\"time\":1662036404644}]"
}
```

---

## 🎯 Firmware Updates

### **Firmware Update Command**

**Send Firmware Update:**
```json
{
  "topic": "wifielement/80:A0:36:E1:8E:B8/update",
  "message": [{"dn": "80:A0:36:E1:8E:B8", "type": "update", "value": "http://us-fm.cloud.sengled.com:8000/sengled/wifielement/W21-N13/firmware/firmware_info.xml", "time": 1662036404644}]
}
```

**Custom Firmware URL:**
```json
{
  "topic": "wifielement/80:A0:36:E1:8E:B8/update",
  "message": [{"dn": "80:A0:36:E1:8E:B8", "type": "update", "value": "http://192.168.1.100/custom-firmware.bin", "time": 1662036404644}]
}
```

---

## 🎯 Control Type Reference

### **Available Control Types**

#### **Basic Control Types**
- **`"switch"`**: Power on/off (`"0"` = off, `"1"` = on)
- **`"brightness"`**: Brightness level (`"0"` to `"100"`)
- **`"color"`**: RGB color (hex format)
- **`"colorTemperature"`**: Color temperature (Kelvin)
- (colorMode is reported-only; see Reported Attributes)
- **`"effectStatus"`**: Effect status (`"0"` = off, `"7"` = audio sync, `"100"` = video sync, `"101"` = game sync)
- **`"white"`**: White light control (alternative to colorTemperature)

#### **Group Control Types**
- **`"groupSwitch"`**: Multi-device power control
- **`"groupBrightness"`**: Multi-device brightness control
- **`"groupColorTemperature"`**: Multi-device color temperature control

#### **Scene & Effect Types**
- **`"scene"`**: Predefined scene activation
- **`"effect"`**: Special effects (colorCycle, randomColor)

#### **Entertainment Sync Types** *(TV Boxes Only)*
- **`"audioSync"`**: Audio synchronization mode (effectStatus: 7)
- **`"videoSync"`**: Video synchronization mode (effectStatus: 100)
- **`"gameSync"`**: Game synchronization mode (effectStatus: 101)
- **`"syncMode"`**: Sync mode control (0=video, 1=game)

#### **Device Management Types**
- **`"config"`**: Device configuration
- **`"reset"`**: Device reset to factory settings
- **`"info"`**: Device information query
- **`"update"`**: Device update command

#### **Query Types**
- **`"status"`**: Status query

## 🛰️ Reported Attributes (from bulb status)

- **colorMode**: reported by the bulb, indicates which LED engine is active. **NOT a control command.**
  - `1` = RGB color mode (RGB LED engine active)
  - `2` = White/color-temperature mode (White LED engine active)

**Note:** `colorMode` is **read-only** - it's reported by the bulb to show which LED system is currently active. You cannot send `colorMode` commands to switch between modes. The bulb automatically switches based on whether you're using RGB colors or white light.

---

### **ControlType Constants**
From the app source code:
- **`ControlType.BRIGHTNESS`**: Brightness control
- **`ControlType.WHITE`**: Color temperature control
- **`ControlType.COLOR`**: RGB color control
- **`ControlType.EFFECT`**: Special effects

### **Gradient Time Parameter**
- **`gradientTime`**: Transition time in milliseconds (e.g., 3000 = 3 seconds)
- Used in group commands and can be used for smooth transitions

---

## 💻 Implementation Examples

### **Python MQTT Client Example**

```python
import json
import time
from mqtt_client import MQTTClient

def send_bulb_command(mac: str, cmd_type: str, value: str, gradient_time: int = None):
    """Send a command to a Sengled Wi-Fi bulb."""
    client = MQTTClient("192.168.1.100")
    if not client.connect():
        return False
    
    # Subscribe to update topic
    update_topic = f"wifielement/{mac}/update"
    client.subscribe(update_topic)
    time.sleep(1)
    
    # Create payload with optional gradient time
    payload_data = {
        "dn": mac,
        "type": cmd_type,
        "value": value,
        "time": int(time.time() * 1000)
    }
    
    if gradient_time:
        payload_data["gradientTime"] = gradient_time
    
    payload = f'Os$[{json.dumps(payload_data)}]'
    
    # Send command
    success = client.publish(update_topic, payload)
    client.disconnect()
    return success

# Usage examples
send_bulb_command("80:A0:36:E1:8E:B8", "switch", "1")  # Turn on
send_bulb_command("80:A0:36:E1:8E:B8", "brightness", "75")  # Set brightness
send_bulb_command("80:A0:36:E1:8E:B8", "color", "FF0000")  # Set red color
send_bulb_command("80:A0:36:E1:8E:B8", "colorTemperature", "2700")  # Set color temperature
send_bulb_command("80:A0:36:E1:8E:B8", "colorMode", "1")  # Set RGB mode
send_bulb_command("80:A0:36:E1:8E:B8", "effectStatus", "0")  # Set normal mode
send_bulb_command("80:A0:36:E1:8E:B8", "scene", "Sleep")  # Activate Sleep scene
send_bulb_command("80:A0:36:E1:8E:B8", "switch", "1", 3000)  # Turn on with 3s fade

# TV Box specific commands
send_bulb_command("80:A0:36:E1:8E:B8", "audioSync", "1")  # Enable audio sync
send_bulb_command("80:A0:36:E1:8E:B8", "videoSync", "1")  # Enable video sync
send_bulb_command("80:A0:36:E1:8E:B8", "gameSync", "1")  # Enable game sync

# Device management commands
send_bulb_command("80:A0:36:E1:8E:B8", "info", "")  # Query device info
send_bulb_command("80:A0:36:E1:8E:B8", "reset", "1")  # Reset device
```

### **HTTP Endpoint Example**

```python
import requests
import json
import time

def send_via_http(mac: str, cmd_type: str, value: str, gradient_time: int = None):
    """Send command via HTTP executeMqttCommand endpoint."""
    topic = f"wifielement/{mac}/update"
    
    payload_data = {
        "dn": mac,
        "type": cmd_type,
        "value": value,
        "time": int(time.time() * 1000)
    }
    
    if gradient_time:
        payload_data["gradientTime"] = gradient_time
    
    payload = f'Os$[{json.dumps(payload_data)}]'
    
    command = {
        "topic": topic,
        "downMsg": payload
    }
    
    response = requests.post(
        "https://cloud.sengled.com/life2/device/executeMqttCommand.json",
        json=command,
        headers={"Content-Type": "application/json"}
    )
    return response.json()
```

---

## ⚠️ Important Notes

1. **Topic Consistency**: All commands including firmware updates use `wifielement/{MAC}/update`

2. **Payload Format**: This tool creates Python lists internally, converts them to JSON strings, and publishes those JSON strings directly to MQTT topics

3. **Auto-Switch Logic**: When setting `colorTemperature`, include a `switch: "1"` command in the same payload (the official app does this automatically)

4. **Color Temperature Requirement**: **CRITICAL** - When changing color temperature, you MUST send both commands together:
   ```
   wifielement/80:A0:36:E1:8E:B8/update
   [{"dn":"80:A0:36:E1:8E:B8","type":"colorTemperature","value":"58","time":1744263570952},{"dn":"80:A0:36:E1:8E:B8","type":"switch","value":"1","time":1744263570952}]
   ```

5. **Timestamp**: All commands include a `time` field with current epoch milliseconds

6. **Device ID**: All commands include `dn` (device name) field with the MAC address

7. **HTTP Endpoint**: All commands are sent via `POST /life2/device/executeMqttCommand.json` with `topic` and `downMsg` keys

8. **Gradient Time**: Use `gradientTime` parameter for smooth transitions between states

9. **Scene Commands**: Use predefined scenes for quick lighting presets

10. **TV Box Commands**: Entertainment sync commands (`audioSync`, `videoSync`, `gameSync`) are **only for TV Boxes** and entertainment systems

11. **Device Management**: Use device management commands carefully as they can reset or reconfigure devices

---

## 🔍 Troubleshooting

### **Common Issues**
- **"function not find" error**: Ensure bulb is connected to WiFi and online
- **No response**: Check MQTT broker connectivity and topic subscriptions
- **Invalid payload**: Verify `Os$` wrapper format and JSON structure
- **Firmware update fails**: Ensure firmware URL is accessible and returns valid .bin file
- **Scene not working**: Verify scene name matches exactly (case-sensitive)
- **TV sync not working**: Ensure device is a TV Box or supports entertainment sync features

### **Debug Commands**
```bash
# Test bulb connectivity
mosquitto_sub -h 192.168.1.100 -t "wifielement/+/status"

# Monitor all bulb traffic
mosquitto_sub -h 192.168.1.100 -t "wifielement/#"
```

---

*This reference is based on analysis of the decompiled Sengled mobile app source code and network packet captures.* 