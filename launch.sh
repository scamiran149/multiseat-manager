#!/bin/bash
set -e

# Determine the directory where this script is located and cd into it
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" &> /dev/null && pwd)"
cd "$SCRIPT_DIR"

VENV_DIR=".venv"

# Check if the virtual environment exists
if [ ! -d "$VENV_DIR" ]; then
    echo "First run detected, setting up environment..."
    python3 -m venv "$VENV_DIR"
    
    # Activate the new environment and install dependencies quietly
    source "$VENV_DIR/bin/activate"
    echo "Installing dependencies..."
    export CC=gcc
    pip install -r requirements.txt --quiet
else
    # Activate the existing environment
    source "$VENV_DIR/bin/activate"
fi

# Pass any command-line arguments to the Python application
exec "$VENV_DIR/bin/python3" app.py "$@"
