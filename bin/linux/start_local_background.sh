#!/usr/bin/env bash
# Starts Collectu Core in the background, where it keeps running after the terminal is closed.
# Arguments are passed on to main.py. Stop it with stop_local_background.sh.
set -euo pipefail
source "$(dirname "$(readlink -f "${BASH_SOURCE[0]}")")/common.sh"

# What the app prints, for looking at it later: tail -f logs/console.log
# It starts empty with every start. The app writes its log files (warnings and above) itself.
CONSOLE_LOG="$ROOT/logs/console.log"

require_venv
# Not an error: this script is also what an autostart entry runs, which may find the app running.
if pid="$(background_pid)"; then
    echo "Collectu Core is already running in the background (PID $pid)."
    exit 0
fi

cd "$ROOT/src"
mkdir -p "$ROOT/logs"

echo "App is starting..."
nohup "$PYTHON" main.py "$@" > "$CONSOLE_LOG" 2>&1 &
echo $! > "$PID_FILE"

# Without a terminal, a start which fails goes unseen. So look again after a moment.
sleep 3
if ! pid="$(background_pid)"; then
    rm -f "$PID_FILE"
    echo "App failed to start. See $CONSOLE_LOG" >&2
    exit 1
fi
echo "App started (PID $pid). Stop it with stop_local_background.sh."
