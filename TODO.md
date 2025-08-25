# TODO - Next Steps

## Project Description

**SengledTools** is a comprehensive tool for local control and firmware flashing of Sengled WiFi bulbs. The project has been restructured to prioritize the **setup wizard** as the main entry point, which handles WiFi pairing and firmware flashing in a user-friendly flow.

### What It Does
- **WiFi Pairing**: Connects bulbs to your local network by mimicking Sengled's cloud server
- **Firmware Flashing**: Installs custom firmware (like Tasmota) to "jailbreak" bulbs and enable full local control
- **Local Control**: MQTT/UDP control commands for bulbs after setup (advanced usage)

### Key Architecture Changes
- **The primary entry point is `sengled_tool.py`**. When run with no arguments, it should default to the setup wizard.
- **The main setup wizard is inside `sengled_tool.py`**. It handles both Wi-Fi pairing and firmware flashing.
- **The `sengled_setup_wizard.py` file is a deprecated, incomplete version** and should be ignored.
- **MQTT/UDP control is for advanced usage** (via `sengled_tool.py`).
- **Embedded MQTT broker** with TLS support for secure local communication.

### Target Users
- **Primary**: Users wanting to jailbreak Sengled bulbs and install custom firmware
- **Secondary**: Advanced users who want local MQTT/UDP control without firmware changes

## Project Tree
```
SengledTools/
├── docs/                                    # Documentation directory containing setup guides and protocol references
│   ├── examples/                            # Example configurations and setup procedures
│   │   ├── certificate_generation.md        # Guide for generating SSL certificates for MQTT broker
│   │   ├── mosquitto_setup.md               # Step-by-step Mosquitto MQTT broker installation and configuration
│   │   └── mosquitto.conf                   # Sample Mosquitto configuration file for MQTT broker setup
│   └── references/                          # Protocol command references for developers
│       ├── MQTT_COMMANDS_REFERENCE.md       # Complete MQTT command syntax and examples for Sengled devices
│       └── UDP_COMMANDS_REFERENCE.md        # Complete UDP command syntax and examples for Sengled devices
├── firmware/                                # Firmware files and ESP32 development project
│   ├── sengled_ota/                        # ESP32 firmware project for OTA (Over-The-Air) updates
│   ├── sengled-w31-n15-stock-firmware.bin  # Original stock firmware binary for backup/restore
│   └── shim.bin                            # Custom firmware shim for device control
├── INSTRUCTIONS.md                          # Advanced usage instructions (to be renamed to ADVANCED_INSTRUCTIONS.md)
├── README.md                                # Basic project overview and quick start guide
├── requirements.txt                         # Python package dependencies (unpinned versions)
├── sengled/                                # Main Python package containing core functionality
│   ├── __init__.py                         # Package initialization and version info
│   ├── crypto.py                           # Cryptographic functions for SSL/TLS and certificate handling
│   ├── http_server.py                      # HTTP server implementation for device discovery and OTA
│   ├── log.py                              # Logging configuration and utilities
│   ├── mqtt_broker.py                     # MQTT broker implementation for local device control
│   ├── mqtt_client.py                     # MQTT client for sending commands to devices
│   ├── utils.py                            # Utility functions for network, file operations, and device management
│   └── wifi_setup.py                      # WiFi configuration and device pairing functionality
├── sengled_setup_wizard.py                 # DEPRECATED: Incomplete wizard. The main wizard is in `sengled_tool.py`.
├── sengled_tool.py                         # Main command-line tool and official entry point for the setup wizard.
└── TODO.md                                 # This file - development roadmap and known issues
```

## 1. Fix All Bugs, Test Argument Combinations
- **Priority**: High
- **Scope**: Comprehensive testing of all command line arguments and their combinations
- **Files to check**: `sengled_tool.py` (main entry point)

- **Issues to Fix**: 


## 2. Restructure Documentation
- **Priority**: High
- **Scope**: Move basic instructions to README.md, rename INSTRUCTIONS.md to ADVANCED_INSTRUCTIONS.md and move advanced content there.
- **Files to check**: `README.md`, `INSTRUCTIONS.md`

### Plan Overview
The documentation will be split into two main files to serve different audiences:
1.  **`README.md`**: A user-friendly entry point for new users focused on the setup wizard.
2.  **`ADVANCED_INSTRUCTIONS.md`**: A comprehensive guide for developers and power users.

### `README.md` (Quick-Start Guide)
This file will be simplified to focus on getting a new user started with the wizard.
- **Project Description**: Keep the introduction and the bulb compatibility table.
- **Installation**: Keep `pip install` instructions.
- **Quick Start**: Focus on the main entry point (`sengled_tool.py` with no arguments defaults to setup wizard). Update references from deprecated `sengled_setup_wizard.py` to correct main tool.
- **Basic Control Examples**: Keep some basic control examples that new users need after setup completion to verify successful setup.
- **Firmware Flashing**: Include the main entry point setup which handles wifi pairing and asks for firmware flashing.
- **`--help` Output**: Place the full output of `python sengled_tool.py --help` inside a collapsed `<details>` block for reference.
- **Link to Advanced Guide**: Add a clear link to `ADVANCED_INSTRUCTIONS.md`.
- **Content to Remove**: Move "Advanced CLI Usage," "Server Management," detailed "Troubleshooting," and complex Mermaid diagrams to the advanced guide.

### `ADVANCED_INSTRUCTIONS.md` (Power-User Guide)
This file (renamed from `INSTRUCTIONS.md`) will consolidate all technical information.
- **Advanced Setup**: Explain the manual Wi-Fi pairing process using `sengled_tool.py`.
- **CLI Command Reference**: Create detailed sections for MQTT, UDP, and Group commands with examples. This will be the core of the document.
- **Firmware Flashing**: Move the detailed "Jailbreaking" section from current INSTRUCTIONS.md here, including Tasmota templates and the `shim.bin` explanation.
- **Server Management**: Move the guide for running the embedded servers (`--run-servers`, etc.) here.
- **Technical Diagrams**: Move the `Setup & Control Flow` and `Wi-Fi Setup Sequence` diagrams here.
- **Advanced Troubleshooting**: Move the detailed guide for fixing unresponsive bulbs here.
- **Reference Links**: Update links to point to the existing `docs/references/MQTT_COMMANDS_REFERENCE.md` and `docs/references/UDP_COMMANDS_REFERENCE.md` files in the advanced guide.

## 3. Package for pip Distribution
- **Priority**: Medium
- **Scope**: Make installable via pip using a modern `pyproject.toml` configuration.
- **Files to check**: `requirements.txt`, `sengled/__init__.py`, `sengled_tool.py`

### Plan
- **Create `pyproject.toml`**:
  - Use `pyproject.toml` for all package configuration (build system, project metadata, dependencies).
  - Set the package name to `sengled-tool` to avoid conflicts on PyPI.
  - Define all package metadata (`version`, `author`, `description`, `license`) within this file.
  - Configure it to use `README.md` as the `long_description`.
  - Add appropriate PyPI classifiers (Python version, OS, topic).

- **Restructure for Distribution**:
  - Create a `console_scripts` entry point in `pyproject.toml` (e.g., `sengled-tool = sengled.cli:main`).
  - Refactor the logic from `sengled_tool.py` into a new `sengled/cli.py` module containing the `main` function for the entry point.
  - Delete the now-redundant `sengled_tool.py` from the root directory.
  - Delete the deprecated `sengled_setup_wizard.py`.

- **Manage Dependencies and Data**:
  - Move dependencies from `requirements.txt` into `pyproject.toml`, specifying minimum versions instead of pinning (e.g., `paho-mqtt>=1.6`).
  - Configure `pyproject.toml` to automatically find the `sengled` package.
  - Include essential firmware binaries (`.bin` files) as package data, but exclude documentation and firmware source code.

## 4. Improve the Main Setup Wizard
- **Priority**: High
- **Scope**: Improve the user experience of the main wizard in `sengled_tool.py`
- **Files to check**: `sengled_tool.py`
- **Details needed**:
  - **Conditional exit logic**: The wizard currently waits indefinitely. It should be updated to exit gracefully after its tasks are complete.
    - **After pairing only**: The script should stop the local servers and exit.
    - **After successful flashing**: The script should stop the local servers and exit.
  - **Conditional "next steps" guidance**: The final output should depend on the user's choice to flash firmware.
    - **If firmware was NOT flashed**: Display example MQTT/UDP commands for local control. Point the user to `README.md` for basic instructions and `ADVANCED_INSTRUCTIONS.md` for a full command reference.
    - **If firmware WAS flashed**: Do not show the built-in control commands, as they are no longer applicable. Instead, instruct the user on how to connect to the newly flashed device (e.g., look for the 'Sengled-Rescue' AP) and point them to the post-flashing section in `ADVANCED_INSTRUCTIONS.md`.

## 6. Ensure Linux Compatibility
- **Priority**: Medium
- **Scope**: Make sure tool works on Linux as well as Windows
- **Files to check**: `sengled_tool.py`, `sengled/wifi_setup.py`, `sengled/http_server.py`
- **Details needed**:
  - **Port binding permissions**: The default HTTP port will be changed to 8080 on Linux to avoid requiring root privileges. On other platforms, it will remain 80.
  - **Certificate directory**: The certificate directory will be created at `~/.sengled/certs` on all platforms, which is standard and does not require changes.
  - **File path handling**: Verify that `Path.home()` and other file operations work correctly on Linux.
  - **Dependency compatibility**: Ensure `psutil`, `pathlib`, and `socket` packages behave as expected on Linux.
- **Recommended grep keywords**:
  - **Dependency compatibility**: `psutil`, `pathlib`, `socket` package behavior differences
  - **File path handling**: `Path.home()` behavior differences between Linux and Windows
  - **File system operations**: `cert_dir.mkdir(exist_ok=True)` and file writing permissions
  - **Certificate directory permissions**: `~/.sengled/certs`, `Path.home() / ".sengled" / "certs"` directory creation
  - **Port binding permissions**: `port 80`, `port 8080`, `HTTPServer(("0.0.0.0", port))` root privileges needed
  - **Network interface detection**: `get_local_ip()` function with `socket.connect(("8.8.8.8", 80))` approach
  - **Socket operations**: socket timeout and error handling across platforms

## 7. Add Module Detection for Flashing Safety
- **Priority**: High
- **Scope**: Detect bulb hardware module during WiFi setup to determine if flashing is safe
- **Files to check**: `sengled_tool.py`, `sengled/wifi_setup.py`, `sengled/mqtt_client.py`
- **Details needed**:
  - **Integration point**: Add module detection after successful WiFi setup and MQTT broker connection, before firmware flashing prompt in wizard mode
  - **MQTT subscription**: Subscribe to bulb's status topic (`wifielement/{MAC}/status`) and parse both `identifyNO` (module) and `typeCode` (model) fields from status messages
  - **Safety database**: Maintain list of known safe combinations - both chip/module (ESP8266) and model (W31-N11, W31-N15) must match confirmed working bulbs
  - **User warnings**: Show clear warnings for unsupported chip/model combinations that flashing may brick the device
  - **Bypass option**: Add `--force-flash` or `--bypass-module-check` argument to skip safety checks for advanced users
  - **Status message format**: Parse JSON array containing `{"type":"identifyNO","value":"ESP8266"}` (chip/module) and `{"type":"typeCode","value":"W31-N11"}` (bulb model) fields
  - **Timeout handling**: Handle cases where status detection fails or times out
  - **Terminology clarity**: ESP8266 is the chip/module (not board) - document this distinction in warnings
- **Recommended grep keywords**:
  - **Current flashing logic**: `wizard_mode`, `firmware`, `flash`, `shim.bin`, `upgrade` command handling
  - **Status message parsing**: `status`, `identifyNO`, `typeCode`, JSON parsing in MQTT messages
  - **Chip/model safety checks**: ESP8266+W31-N11, ESP8266+W31-N15, WF863, WF864, MXCHIP combinations referenced in existing code or docs
  - **Bypass arguments**: `--force-flash`, `--bypass-module-check`, `--skip-safety` command line argument handling
  # "C:\Program Files\mosquitto\mosquitto_sub.exe" -h 192.168.0.100 -p 8883 --cafile "C:\Users\User\.sengled\certs\ca.crt" -v -t "#"
wifielement/30:83:98:9F:92:D9/status [{"dn":"30:83:98:9F:92:D9","type":"supportAttributes","value":"brightness","time":"677"}]
wifielement/30:83:98:9F:92:D9/status [{"dn":"30:83:98:9F:92:D9","type":"brightness","value":"100","time":"677"},{"dn":"30:83:98:9F:92:D9","type":"version","value":"V1.0.0.4","time":"677"},{"dn":"30:83:98:9F:92:D9","type":"switch","value":"1","time":"677"},{"dn":"30:83:98:9F:92:D9","type":"productCode","value":"wifielement","time":"677"},{"dn":"30:83:98:9F:92:D9","type":"typeCode","value":"W31-N11","time":"677"},{"dn":"30:83:98:9F:92:D9","type":"identifyNO","value":"ESP8266","time":"677"},{"dn":"30:83:98:9F:92:D9","type":"ip","value":"192.168.0.24","time":"677"},{"dn":"30:83:98:9F:92:D9","type":"deviceRssi","value":"-56","time":"677"},{"dn":"30:83:98:9F:92:D9","type":"saveFlag","value":"1","time":"677"}]
wifielement/30:83:98:9F:92:D9/status [{"dn":"30:83:98:9F:92:D9","type":"timeZone","value":"America/Chicago","time":"677"}]
wifielement/30:83:98:9F:92:D9/consumption [{"dn":"30:83:98:9F:92:D9","type":"consumption","value":"163","time":"678"}]
wifielement/30:83:98:9F:92:D9/consumptionTime [{"dn":"30:83:98:9F:92:D9","type":"consumptionTime","value":"7214","time":"678"}]
wifielement/30:83:98:9F:92:D9/update [{"dn": "30:83:98:9F:92:D9", "type": "switch", "value": "0", "time": 1755780619175}]
wifielement/30:83:98:9F:92:D9/status [{"dn":"30:83:98:9F:92:D9","type":"switch","value":"0","time":"734"}]
