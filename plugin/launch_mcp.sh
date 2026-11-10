#!/bin/sh
set -eu
PLUGIN_DIR=$(CDPATH= cd -- "$(dirname -- "$0")/.." && pwd)
cd "$PLUGIN_DIR/server"
for PYTHON_BIN in /opt/homebrew/bin/python3 /usr/local/bin/python3 /usr/bin/python3; do
    if [ -x "$PYTHON_BIN" ] && "$PYTHON_BIN" -c 'import sys; sys.exit(sys.version_info < (3, 10))'; then
        exec "$PYTHON_BIN" -B -m safari_tabs.mcp
    fi
done
echo 'Smarten for Safari requires an installed Python 3.10 or later.' >&2
exit 1
