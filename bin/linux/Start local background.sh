#!/bin/bash

cd .. || { echo "Failed to change directory."; exit 1; }

cd src || { echo "Failed to change to 'src' directory."; exit 1; }

echo "App is starting..."

source ../venv/bin/activate || { echo "Failed to activate virtual environment."; exit 1; }

nohup python main.py > app.log 2>&1 &

echo "App started."

read -p "Press Enter to exit."
