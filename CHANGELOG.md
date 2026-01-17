# Changelog

## Major Changes

### Architecture Overhaul
- **Complete code reorganization**: Moved from monolithic `sengled_tool.py` to modular `sengled/` package structure
- **Replaced Mosquitto dependency**: Now uses embedded MQTT broker (`amqtt`) instead of external Mosquitto
- **Local certificate generation**: Built-in TLS certificate generation using `cryptography` library (no OpenSSL needed)
- **Modular design**: Split functionality into focused modules (wifi_setup, command_handler, firmware_upgrade, etc.)

### New Core Features
- **Embedded MQTT broker**: Self-contained broker that runs on port 8883 with TLS
- **Wi-Fi setup wizard**: Interactive setup process for pairing bulbs to local network
- **Firmware flashing support**: Built-in firmware upgrade capability with safety warnings
- **Bulb model detection**: MQTT client that detects bulb type and compatibility
- **Command handler**: Unified interface for both UDP and MQTT bulb control

### New Command Line Features
- **`--run-servers`**: Start both embedded MQTT broker and HTTP server simultaneously
- **`--regen-certs`**: Force regeneration of TLS certificates in unified location
- **`--force-flash`**: Allow flashing even on unsupported models (bypass safety checks)
- **`--verbose`**: Enable debug logging and error details
- **`--http-server-ip`**: Specify custom IP for HTTP URLs sent to bulbs

### Improved User Experience
- **Enhanced logging system**: New structured logging with emoji support, indentation, and verbose modes
- **Setup wizard**: Interactive flow that guides users through Wi-Fi pairing and firmware flashing
- **Better error handling**: More informative error messages and user guidance
- **Cross-platform support**: Improved terminal compatibility (Windows, Linux, macOS)
- **Default behavior change**: Tool now defaults to setup wizard instead of REPL mode

### Firmware & Jailbreaking
- **Sengled-Rescue system**: New web-based firmware flasher that runs on ESP8266 bulbs
- **Dual-OTA support**: Handles both `ota_0` and `ota_1` partitions safely
- **Web UI**: Browser-based interface for flashing, backup, and partition management
- **Safety features**: Prevents overwriting running firmware, validates write windows
- **ESP8266 RTOS SDK**: Built with modern ESP-IDF toolchain instead of Arduino

### Dependencies Changed
- **Removed**: `getmac`, `mosquitto.conf` 
- **Added**: `psutil`, `amqtt`, `cryptography`
- **Kept**: `paho-mqtt` (still used for client connections)

### File Structure Changes
- **New**: `sengled/` package with 13 new Python modules
- **Moved**: Firmware files from root to `firmware/` subdirectory
- **Moved**: Reference documentation to `docs/references/` folder
- **Deleted**: Old monolithic files (`sengled_local_server.py`, `sengled_wifi_crypto.py`, `utils.py`)
- **New documentation**: Added `docs/examples/` with setup guides and `docs/references/` with command references

### Documentation Improvements
- **New examples**: Added certificate generation and Mosquitto setup guides
- **Updated README**: Simplified for new users with focus on setup wizard
- **Updated INSTRUCTIONS**: Streamlined for advanced users with new embedded broker workflow
- **Reference docs**: Moved command references to organized `docs/references/` structure

## Notes
- **Massive refactoring**: Main tool reduced from ~1270 lines to ~639 lines (50% reduction)
- **New modular architecture**: 13 focused Python modules instead of monolithic design
- **Embedded broker**: No more external Mosquitto dependency, self-contained TLS broker
- **Setup wizard focus**: Tool now defaults to guided setup instead of command-line REPL
- **Firmware flashing**: Built-in support for jailbreaking bulbs with safety checks
- **Cross-platform**: Improved compatibility across Windows, Linux, and macOS
