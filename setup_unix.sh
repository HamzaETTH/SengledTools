#!/usr/bin/env bash
# setup_unix.sh
# Create or update a local Python virtual environment for SengledTools on Linux/macOS.
# Uses uv if available, otherwise python3 -m venv + pip.

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]:-$0}")" && pwd)"
cd "$SCRIPT_DIR"

# Detect uv
if command -v uv >/dev/null 2>&1; then
    UV_AVAILABLE=1
else
    UV_AVAILABLE=0
fi

# Check python3
if ! command -v python3 >/dev/null 2>&1; then
    echo "ERROR: Python 3.10+ is required but python3 was not found."
    echo "Please install it via your package manager or from https://www.python.org/downloads/"
    exit 1
fi

# Create .venv if missing
if [ ! -d ".venv" ]; then
    if [ "$UV_AVAILABLE" -eq 1 ]; then
        echo "Creating virtual environment using uv..."
        uv venv --seed .venv
    else
        echo "Creating virtual environment using python3 -m venv..."
        python3 -m venv --include-pip .venv
    fi
fi

# Install/refresh deps
echo "Installing/refreshing dependencies..."
if ! .venv/bin/python -m pip --version >/dev/null 2>&1; then
    echo "pip not found in venv. Bootstrapping with ensurepip..."
    if ! .venv/bin/python -m ensurepip --upgrade; then
        echo "ERROR: Failed to bootstrap pip (ensurepip)."
        echo "On many distros you need to install python3-venv or python3-ensurepip."
        exit 1
    fi
fi

.venv/bin/python -m pip install --upgrade pip
.venv/bin/python -m pip install -r requirements.txt

echo
echo "Environment setup complete. Run ./run_wizard.sh to start the wizard."
