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

XLSX="/Volumes/Office/Public/01 TV-Radio Spreadsheets/KAZQ.xlsx"

# Optional per-machine overrides (gitignored). A dev machine can set XLSX here.
if [ -f "$SCRIPT_DIR/local-config.sh" ]; then
  log "Loading local overrides from local-config.sh"
  source "$SCRIPT_DIR/local-config.sh"
fi

if [ ! -f "$XLSX" ]; then
  log "KAZQ.xlsx not found at $XLSX. Aborting."
  exit 1
fi

log "Running TV schedule update from Excel"
python3 "$SCRIPT_DIR/update_tv_schedule.py" \
  --xlsx "$XLSX" \
  --schedule "$SCRIPT_DIR/docs/tv-schedule.txt"

git add docs/tv-schedule.txt

if git diff --cached --quiet; then
  git restore --staged docs/tv-schedule.txt || true
  echo "$(date '+%Y-%m-%d %H:%M:%S') tv-schedule.txt did not change. Nothing to commit."
  exit 0
fi

git commit -m "Update TV schedule from KAZQ.xlsx"
log "Pushing to origin/main"
git push origin main
log "Done"
