#!/bin/zsh
# Scheduled tick (Mini launchd): cheap All-page tripwire, or a full proven scrape.
#
# :05 / :20 / :35 / :50 every hour.
# Offset +5 because videos are often posted on the hour; checking at :05
# usually sees them sooner than a :00 or :15 slot would.
#
# Full scrape (replaces the tripwire at that minute):
#   4:05am, 8:05am, 5:05pm, 8:05pm America/Los_Angeles
# Tripwire change -> same full scrape (publish_rumble_feed.sh).
# Tripwire fetch/parse failure -> log and skip (do not hammer Rumble).
set -euo pipefail

SCRIPT_DIR="${0:A:h}"
cd "$SCRIPT_DIR"

log() {
  print -r -- "[$(date '+%Y-%m-%d %H:%M:%S')] $*"
}

FULL_SLOTS=(
  04:05
  08:05
  17:05
  20:05
)

now="$(TZ=America/Los_Angeles date +%H:%M)"

is_full_slot() {
  local slot
  for slot in "${FULL_SLOTS[@]}"; do
    if [[ "$now" == "$slot" ]]; then
      return 0
    fi
  done
  return 1
}

run_full() {
  local why="$1"
  log "Full scrape ($why)"
  set +e
  "$SCRIPT_DIR/publish_rumble_feed.sh"
  local rc=$?
  set -e
  if [[ $rc -eq 75 ]]; then
    log "Full scrape skipped (lock held). Leaving tripwire state unsaved."
    return 75
  fi
  if [[ $rc -eq 0 ]]; then
    python3 "$SCRIPT_DIR/rumble_tripwire.py" --save || log "Tripwire state save failed (scrape already succeeded)"
  fi
  return $rc
}

if is_full_slot; then
  run_full "scheduled $now"
  exit $?
fi

log "Tripwire check ($now)"
set +e
TW_OUT="$(python3 "$SCRIPT_DIR/rumble_tripwire.py" 2>&1)"
TW_RC=$?
set -e
print -r -- "$TW_OUT"

if [[ $TW_RC -eq 0 ]]; then
  log "Tripwire unchanged"
  exit 0
fi
if [[ $TW_RC -eq 1 ]]; then
  run_full "tripwire changed"
  exit $?
fi

log "Tripwire error (exit $TW_RC). Skipping full scrape."
exit $TW_RC
