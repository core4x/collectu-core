#!/usr/bin/env bash
# What the scripts of this folder share. They source this file, it is not run on its own.

# The root directory lies two levels above the scripts - wherever they are called from, and also
# when they are called through a symlink.
ROOT="$(cd "$(dirname "$(readlink -f "${BASH_SOURCE[0]}")")/../.." && pwd)"

# The interpreter of the virtual environment. Calling it directly is all "activating" amounts to.
PYTHON="$ROOT/venv/bin/python"

# Written by start_local_background.sh, so that stop_local_background.sh ends that process and no other.
PID_FILE="$ROOT/collectu.pid"

# Exits if the virtual environment is missing.
require_venv() {
    if [ ! -x "$PYTHON" ]; then
        echo "The virtual environment was not found. Run install_local.sh first." >&2
        exit 1
    fi
}

# Prints the PID of the Collectu Core running in the background and succeeds, or fails if there is none.
#
# A PID file outlives its process after a crash or a reboot, and the PID may have been given to another
# process since. So the process is asked for its command line as well.
background_pid() {
    local pid
    [ -f "$PID_FILE" ] || return 1
    pid="$(cat "$PID_FILE")"
    [[ "$pid" =~ ^[0-9]+$ ]] || return 1
    ps -p "$pid" -o args= 2>/dev/null | grep -q "main\.py" || return 1
    echo "$pid"
}
