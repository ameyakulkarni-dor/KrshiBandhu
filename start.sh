#!/usr/bin/env bash
# Startup script for Linux, macOS, and Raspberry Pi
set -e

DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$DIR"

echo "=========================================="
echo "  🌾 Launching KrshiBandhu Farm Guardian  "
echo "=========================================="

# Check if Python is installed
if command -v python3 &>/dev/null; then
    PY_BIN="python3"
elif command -v python &>/dev/null; then
    PY_BIN="python"
else
    echo "Error: Python 3 is not installed. Please install Python 3.10+."
    exit 1
fi

# Create virtual environment if it doesn't exist
if [ ! -d ".venv" ]; then
    echo "Creating virtual environment in .venv..."
    $PY_BIN -m venv .venv
    echo "Installing PyTorch (CPU) and dependencies..."
    .venv/bin/python -m pip install --upgrade pip
    .venv/bin/python -m pip install torch torchvision --index-url https://download.pytorch.org/whl/cpu
    .venv/bin/python -m pip install -r requirements.txt
fi

echo "Starting KrshiBandhu..."
.venv/bin/python run.py "$@"
