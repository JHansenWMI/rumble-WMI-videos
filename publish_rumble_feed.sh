#!/bin/zsh
set -euo pipefail

SCRIPT_DIR="${0:A:h}"
cd "$SCRIPT_DIR"

python3 "$SCRIPT_DIR/generate_rumble_feed.py"

git add docs/rumble-feed.json

if git diff --cached --ignore-matching-lines=generatedAt --quiet -- docs/rumble-feed.json; then
  echo "$(date '+%Y-%m-%d %H:%M:%S') docs/rumble-feed.json did not change. Nothing to commit."
  exit 0
fi

git commit -m "Update docs/rumble-feed.json"
git push origin main
