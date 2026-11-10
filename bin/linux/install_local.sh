#!/usr/bin/env bash
# Installs Collectu Core: creates the virtual environment 'venv' in the root directory and installs
# the requirements into it. It can be run again at any time, e.g. to repair an installation.
set -euo pipefail
source "$(dirname "$(readlink -f "${BASH_SOURCE[0]}")")/common.sh"

trap 'echo "Installation failed. See the messages above." >&2' ERR

cd "$ROOT"

# An environment which is there and runs is kept. One whose Python was removed since is not.
if "$PYTHON" -c "" 2>/dev/null; then
    echo "Using the existing virtual environment 'venv'."
else
    if ! command -v python3 >/dev/null; then
        echo "python3 was not found. Install Python 3.11 or newer." >&2
        exit 1
    fi
    if ! python3 -c "import sys; sys.exit(sys.version_info < (3, 11))"; then
        echo "Python 3.11 or newer is required, but python3 is $(python3 -V 2>&1)." >&2
        exit 1
    fi
    echo "Creating the virtual environment 'venv'..."
    if ! python3 -m venv venv; then
        echo "On Debian and Ubuntu the venv module is a package of its own: sudo apt install python3-venv" >&2
        exit 1
    fi
fi

echo "Installing the requirements..."
"$PYTHON" -m pip install --upgrade pip || echo "Could not update pip. Continuing with the installed version."
"$PYTHON" -m pip install -r src/requirements.txt

echo "Installation successfully finished. Start the application with start_local.sh."
