#!/bin/zsh
# Double-click launcher → real script is publish_rumble_feed.sh (edit only that file).
set -euo pipefail
SCRIPT_DIR="${0:A:h}"
exec "$SCRIPT_DIR/publish_rumble_feed.sh" "$@"
