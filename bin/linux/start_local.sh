#!/bin/bash

# Get the script's directory (even if symlinked)
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

# Change to that directory
cd "$SCRIPT_DIR"

cd ../.. || { echo "Failed to change directory."; exit 1; }

cd src || { echo "Failed to change to 'src' directory."; exit 1; }

while true
do
    echo "App is starting..."

    source ../venv/bin/activate && python main.py
    deactivate

    echo "App crashed. Restarting..."

    sleep 60
done
