#!/usr/bin/env bash
# Stops the Collectu Core which start_local_background.sh started - that process, and no other.
set -euo pipefail
source "$(dirname "$(readlink -f "${BASH_SOURCE[0]}")")/common.sh"

# How long the app is given to end by itself, in seconds.
TIMEOUT=30

if ! pid="$(background_pid)"; then
    rm -f "$PID_FILE"
    echo "App is not running in the background."
    exit 0
fi

echo "App is stopping (PID $pid)..."
if ! kill "$pid"; then
    echo "App could not be stopped. Run this script as the user who started it, or with sudo." >&2
    exit 1
fi

for ((waited = 0; waited < TIMEOUT; waited++)); do
    if ! kill -0 "$pid" 2>/dev/null; then
        break
    fi
    sleep 1
done

if kill -0 "$pid" 2>/dev/null; then
    echo "App did not end within $TIMEOUT seconds. Ending it by force."
    kill -9 "$pid" 2>/dev/null || true
fi

rm -f "$PID_FILE"
echo "App stopped."
