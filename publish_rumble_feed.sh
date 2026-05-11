#!/bin/zsh
set -euo pipefail

SCRIPT_DIR="${0:A:h}"
cd "$SCRIPT_DIR"

log() {
  print -r -- "[$(date '+%Y-%m-%d %H:%M:%S')] $*"
}

if [ "$(git rev-parse --abbrev-ref HEAD)" != "main" ]; then
  log "Expected to run on branch main. Aborting."
  exit 1
fi

git update-index -q --refresh

if ! git diff --quiet || ! git diff --cached --quiet; then
  log "Working tree is not clean. Aborting so local changes are not mixed into the scheduled run."
  exit 1
fi

log "Pulling latest origin/main"
git fetch origin
git pull --ff-only origin main

log "Generating feed"
python3 "$SCRIPT_DIR/generate_rumble_feed.py"

git add docs/rumble-feed.json

if git diff --cached --ignore-matching-lines=generatedAt --quiet -- docs/rumble-feed.json; then
  git restore --staged docs/rumble-feed.json
  git restore docs/rumble-feed.json
  echo "$(date '+%Y-%m-%d %H:%M:%S') docs/rumble-feed.json did not change. Nothing to commit."
  exit 0
fi

git commit -m "Update docs/rumble-feed.json"
log "Pushing to origin/main"
git push origin main
log "Done"
