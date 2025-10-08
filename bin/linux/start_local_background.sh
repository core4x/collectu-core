#!/bin/bash

# Get the script's directory (even if symlinked)
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

# Change to that directory
cd "$SCRIPT_DIR"

cd ../.. || { echo "Failed to change directory."; exit 1; }

cd src || { echo "Failed to change to 'src' directory."; exit 1; }

echo "App is starting..."

source ../venv/bin/activate || { echo "Failed to activate virtual environment."; exit 1; }

nohup python main.py > app.log 2>&1 &

echo "App started."

read -p "Press Enter to exit."
