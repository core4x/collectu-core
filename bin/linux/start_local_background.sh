#!/usr/bin/env bash
# Starts Collectu Core in the background, where it keeps running after the terminal is closed.
# Arguments are passed on to main.py. Stop it with stop_local_background.sh.
set -euo pipefail
source "$(dirname "$(readlink -f "${BASH_SOURCE[0]}")")/common.sh"

require_venv
# Not an error: this script is also what an autostart entry runs, which may find the app running.
if pid="$(background_pid)"; then
    echo "Collectu Core is already running in the background (PID $pid)."
    exit 0
fi

cd "$ROOT/src"

echo "App is starting..."
# Nothing the app prints is kept. It writes its log to logs/Logs.log itself (warnings and above, a new
# file every day, five days kept), and a file the shell redirects into is never rotated.
nohup "$PYTHON" main.py "$@" > /dev/null 2>&1 &
echo $! > "$PID_FILE"

# Without a terminal, a start which fails goes unseen. So look again after a moment.
sleep 3
if ! pid="$(background_pid)"; then
    rm -f "$PID_FILE"
    echo "App failed to start. See logs/Logs.log, or run start_local.sh to watch it." >&2
    exit 1
fi
echo "App started (PID $pid). Stop it with stop_local_background.sh."
