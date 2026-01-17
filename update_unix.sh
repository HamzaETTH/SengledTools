#!/usr/bin/env bash
# update_unix.sh
# Update the SengledTools repo via git pull and refresh Python dependencies in .venv on Linux/macOS.

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]:-$0}")" && pwd)"
cd "$SCRIPT_DIR"

# Check for Git
if ! git rev-parse --is-inside-work-tree >/dev/null 2>&1; then
    echo "ERROR: Not a Git repository. Cannot update."
    exit 1
fi

# Check for local changes
if [[ -n "$(git status --porcelain)" ]]; then
    echo "WARNING: You have local changes. git pull may fail or merge."
    echo
fi

# Pull updates
echo "Pulling latest changes from Git..."
git pull --ff-only

# Refresh dependencies
echo
echo "Refreshing dependencies..."
./setup_unix.sh

echo
echo "Update complete."
