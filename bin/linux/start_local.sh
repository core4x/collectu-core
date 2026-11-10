#!/usr/bin/env bash
# Starts Collectu Core in this terminal and starts it again when it crashes.
# Arguments are passed on to main.py. Ctrl+C stops the application.
set -euo pipefail
source "$(dirname "$(readlink -f "${BASH_SOURCE[0]}")")/common.sh"

RESTART_DELAY=60

require_venv
if pid="$(background_pid)"; then
    echo "Collectu Core is already running in the background (PID $pid). Stop it first: stop_local_background.sh" >&2
    exit 1
fi

cd "$ROOT/src"

while true; do
    echo "App is starting..."
    exit_code=0
    "$PYTHON" main.py "$@" || exit_code=$?

    # Exit code 0 is a stop somebody asked for (Ctrl+C, or a command line option which only prints).
    # A restart after an update is none: the app replaces its process, which keeps running here.
    if [ "$exit_code" -eq 0 ]; then
        echo "App stopped."
        exit 0
    fi

    echo "App stopped unexpectedly (exit code $exit_code). Restarting in $RESTART_DELAY seconds. Press Ctrl+C to prevent that."
    sleep "$RESTART_DELAY"
done
