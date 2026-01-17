#!/usr/bin/env bash
# run_wizard.sh
# Run the Sengled WiFi Bulb setup wizard using the local .venv environment on Linux/macOS.

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]:-$0}")" && pwd)"
cd "$SCRIPT_DIR"

# Check for .venv
if [ ! -f ".venv/bin/python" ]; then
    echo ".venv not found. Running ./setup_unix.sh first..."
    ./setup_unix.sh
fi

# Run the wizard
echo "Starting Sengled WiFi Bulb setup wizard..."
.venv/bin/python sengled_tool.py
