#!/bin/bash

# Get the script's directory (even if symlinked)
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

# Change to that directory
cd "$SCRIPT_DIR"

cd ../.. || { echo "Failed to change directory."; exit 1; }

echo "Creating virtual environment 'venv'."
python3 -m venv venv || { echo "Failed to create virtual environment."; exit 1; }

echo "Activating virtual environment."
source venv/bin/activate || { echo "Failed to activate virtual environment."; exit 1; }

echo "Installing requirements."
pip install -r src/requirements.txt || { echo "Failed to install requirements."; deactivate; exit 1; }

echo "Deactivating virtual environment."
deactivate

echo "Installation successfully finished."
