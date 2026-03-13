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
)

echo "Ensuring permissions for mounted volumes..."

for dir in "${REQUIRED_DIRS[@]}"; do
    # Create the directory if it doesn't exist (e.g., if volume wasn't mounted).
    mkdir -p "$dir"
    # Change ownership to appuser (UID 1000)
    chown -R appuser:appuser "$dir"
done

# Path to the mounted token.
GIT_ACCESS_TOKEN_PATH="/collectu-core/git_access_token.txt"
if [ -f "$GIT_ACCESS_TOKEN_PATH" ]; then
    chown appuser:appuser "$GIT_ACCESS_TOKEN_PATH"
    chmod 600 "$GIT_ACCESS_TOKEN_PATH"
fi

echo "Starting Collectu Core..."

# Hand over to the Python app as appuser.
exec gosu appuser python main.py
