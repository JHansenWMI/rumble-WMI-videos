#!/bin/zsh
# Open the local Dorcas Fund gallery preview (no CMS paste).
# Leave this window open while you look. Closing it stops the preview server
# if this window started it.

set -euo pipefail

SCRIPT_DIR="${0:A:h}"
cd "$SCRIPT_DIR/docs"

PORT=8765
URL="http://127.0.0.1:${PORT}/dorcas-fund-preview.html"

if lsof -nP -iTCP:"${PORT}" -sTCP:LISTEN >/dev/null 2>&1; then
  print -- "Preview already running: ${URL}"
  open "$URL"
  exit 0
fi

print -- "Dorcas gallery preview: ${URL}"
print -- "Leave this window open. Close it when you are done."
open "$URL"
exec python3 -m http.server "$PORT"
