#!/bin/bash
set -e

# Path to the mounted token
TOKEN_PATH="/collectu-core/git_access_token.txt"

# As root, make sure the appuser can at least READ the token
if [ -f "$TOKEN_PATH" ]; then
    chown appuser:appuser "$TOKEN_PATH"
    chmod 644 "$TOKEN_PATH"
fi

# Hand over to the Python app as appuser
exec gosu appuser python main.py
