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

XLSX="/Volumes/Office/Public/01 TV-Radio Spreadsheets/Warning! Radio - Air Date Record.xlsx"

log "Running radio + shortwave schedule update from Excel"
python3 "$SCRIPT_DIR/update_radio_programs.py" \
  --xlsx "$XLSX" \
  --csv "$SCRIPT_DIR/Intra Support Files/radio_programs.csv" \
  --schedule "$SCRIPT_DIR/docs/radio-schedule.txt"

git add \
  "Intra Support Files/radio_programs.csv" \
  docs/radio-schedule.txt \
  docs/shortwave-schedule.txt

if git diff --cached --quiet; then
  git restore --staged \
    "Intra Support Files/radio_programs.csv" \
    docs/radio-schedule.txt \
    docs/shortwave-schedule.txt 2>/dev/null || true
  echo "$(date '+%Y-%m-%d %H:%M:%S') radio/shortwave schedules did not change. Nothing to commit."
  exit 0
fi

git commit -m "Update radio and shortwave schedules from Warning! Radio spreadsheet"
log "Pushing to origin/main"
git push origin main
log "Done"