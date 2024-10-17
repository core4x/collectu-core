#!/bin/bash

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
