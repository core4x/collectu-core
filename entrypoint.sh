#!/bin/bash
set -e

# List of directories that need to be writable.
REQUIRED_DIRS=(
    "/collectu-core/configuration"
    "/collectu-core/logs"
    "/collectu-core/data"
    "/collectu-core/src/modules/inputs"
    "/collectu-core/src/modules/outputs"
    "/collectu-core/src/modules/processors"
    "/collectu-core/src/interface"
)

echo "Ensuring permissions for mounted volumes..."
for dir in "${REQUIRED_DIRS[@]}"; do
    # Create the directory if it doesn't exist (e.g., if volume wasn't mounted).
    mkdir -p "$dir"
    # Attempt chown — may fail if running as non-root (e.g. Kubernetes).
    chown -R appuser:appuser "$dir" 2>/dev/null || echo "Warning: Could not chown '$dir' (skipping)."
done

# Path to the mounted git access token.
GIT_ACCESS_TOKEN_PATH="/collectu-core/git_access_token.txt"
if [ -f "$GIT_ACCESS_TOKEN_PATH" ]; then
    chown appuser:appuser "$GIT_ACCESS_TOKEN_PATH" 2>/dev/null || echo "Warning: Could not chown git access token (skipping)."
    chmod 600 "$GIT_ACCESS_TOKEN_PATH" 2>/dev/null || echo "Warning: Could not chmod git access token (skipping)."
fi

echo "Starting Collectu Core..."

# Use gosu to drop to appuser if running as root, otherwise exec directly.
if [ "$(id -u)" = "0" ]; then
    if [ "${RUN_AS_ROOT}" = "1" ]; then
        echo "RUN_AS_ROOT=1 — running as root."
        exec python main.py
    else
        exec gosu appuser python main.py
    fi
else
    exec python main.py
fi
