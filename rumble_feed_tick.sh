#!/bin/zsh
# Scheduled tick (Mini launchd): cheap All+shorts tripwire, or a full proven scrape.
#
# :05 / :20 / :35 / :50 every hour.
# Offset +5 because videos are often posted on the hour; checking at :05
# usually sees them sooner than a :00 or :15 slot would.
#
# Full scrape (replaces the tripwire at that minute):
#   4:05am, 8:05am, 5:05pm, 8:05pm America/Los_Angeles
# Tripwire change -> same full scrape (publish_rumble_feed.sh).
# Tripwire fetch/parse failure -> log and skip (do not hammer Rumble).
#
# Launchd will not start the next tick while this one is still running.
# Each step has a time limit. On expiry, append a stack sample to
# rumble-feed-stuck.log and stop the process group.
set -euo pipefail

SCRIPT_DIR="${0:A:h}"
cd "$SCRIPT_DIR"

# Tripwire normally finishes in a few seconds. fetch_html's own cap is 30s.
TRIPWIRE_LIMIT_SECS=60
# Recent full scrapes finished in about 2 minutes. Pillow adds image downloads.
SCRAPE_LIMIT_SECS=900
STUCK_LOG="${RUMBLE_FEED_STUCK_LOG:-/Users/wmiadmin/Library/Logs/rumble-feed-stuck.log}"

log() {
  print -r -- "[$(date '+%Y-%m-%d %H:%M:%S')] $*"
}

# Run a command in its own process group. Return the command's status, or 124
# if it is still running after `secs`. On 124, sample the stuck Python (or the
# leader) before stopping the group so publish_rumble_feed.sh can run its
# EXIT trap (worktree + lock) on TERM.
# perl setpgrp, not zsh MONITOR: launchd has no terminal, and MONITOR cannot
# be turned on there. The perl process execs the command, so the pid we track
# is the command itself.
run_bounded() {
  local secs="$1"
  local label="$2"
  shift 2
  /usr/bin/perl -e 'setpgrp(0, 0); exec @ARGV or die "exec: $!\n"' -- "$@" &
  local pid=$!
  local waited=0
  while kill -0 "$pid" 2>/dev/null; do
    if (( waited >= secs )); then
      log "Time limit hit ($label, ${secs}s, pid $pid). Stopping it so the next tick can run. Stack sample: $STUCK_LOG"
      note_stuck_stack "$pid" "$label"
      stop_process_group "$pid"
      wait "$pid" 2>/dev/null || true
      return 124
    fi
    sleep 1
    waited=$((waited + 1))
  done
  wait "$pid"
}

note_stuck_stack() {
  setopt LOCAL_OPTIONS NO_XTRACE
  local root="$1"
  local label="$2"
  local -a pile
  pile=("$root")
  local i=1
  while (( i <= ${#pile} )); do
    local cur="${pile[i]}"
    i=$((i + 1))
    local kids k
    kids="$(pgrep -P "$cur" 2>/dev/null || true)"
    for k in ${(f)kids}; do
      [[ -n "$k" ]] || continue
      pile+=("$k")
    done
  done
  local target="$root"
  local p cmd seen=""
  for p in "${pile[@]}"; do
    cmd="$(ps -o command= -p "$p" 2>/dev/null || true)"
    if [[ "$cmd" == *[Pp]ython* ]]; then
      target="$p"
      seen="$cmd"
    fi
  done
  if [[ -z "$seen" ]]; then
    seen="$(ps -o command= -p "$target" 2>/dev/null || true)"
  fi
  {
    print -r -- ""
    print -r -- "===== $(date '+%Y-%m-%d %H:%M:%S') $label pid $target ====="
    print -r -- "$seen"
    sample "$target" 1 2>&1 | awk '
      /Call graph:/ { show = 1 }
      /Binary Images:/ { show = 0 }
      show { print }
    '
  } >> "$STUCK_LOG" || true
}

stop_process_group() {
  local pid="$1"
  local pgid my_pgid
  pgid="$(ps -o pgid= -p "$pid" 2>/dev/null | tr -d ' ' || true)"
  my_pgid="$(ps -o pgid= -p $$ 2>/dev/null | tr -d ' ' || true)"
  if [[ -n "$pgid" && "$pgid" != "$my_pgid" ]]; then
    kill -TERM -- -"$pgid" 2>/dev/null || kill -TERM "$pid" 2>/dev/null || true
  else
    kill -TERM "$pid" 2>/dev/null || true
  fi
  local grace=0
  while kill -0 "$pid" 2>/dev/null && (( grace < 10 )); do
    sleep 1
    grace=$((grace + 1))
  done
  if kill -0 "$pid" 2>/dev/null; then
    if [[ -n "$pgid" && "$pgid" != "$my_pgid" ]]; then
      kill -KILL -- -"$pgid" 2>/dev/null || true
    fi
    kill -KILL "$pid" 2>/dev/null || true
  fi
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
  local pending="$SCRIPT_DIR/.rumble-tripwire-state.pending"
  log "Full scrape ($why)"
  # A scheduled slot has no tripwire check in front of it. Snapshot the listing
  # now. A tripwire-triggered run already wrote that pending file.
  if [[ "$why" == scheduled* ]]; then
    rm -f "$pending"
    if ! run_bounded "$TRIPWIRE_LIMIT_SECS" "tripwire snapshot" python3 "$SCRIPT_DIR/rumble_tripwire.py" --snapshot; then
      log "Tripwire snapshot failed. Scraping, and leaving tripwire state unsaved."
    fi
  fi
  set +e
  run_bounded "$SCRAPE_LIMIT_SECS" "full scrape" "$SCRIPT_DIR/publish_rumble_feed.sh"
  local rc=$?
  set -e
  if [[ $rc -eq 75 ]]; then
    log "Full scrape skipped (lock held). Leaving tripwire state unsaved."
    rm -f "$pending"
    return 75
  fi
  if [[ $rc -eq 0 ]]; then
    set +e
    run_bounded "$TRIPWIRE_LIMIT_SECS" "tripwire save" python3 "$SCRIPT_DIR/rumble_tripwire.py" --save-if-matches
    local save_rc=$?
    set -e
    if [[ $save_rc -eq 3 ]]; then
      log "Listing changed during scrape. Tripwire state left unchanged so the next tick will scrape again."
    elif [[ $save_rc -ne 0 ]]; then
      log "Tripwire state save failed (exit $save_rc). Scrape already succeeded."
    fi
  else
    rm -f "$pending"
  fi
  return $rc
}

if is_full_slot; then
  run_full "scheduled $now"
  exit $?
fi

log "Tripwire check ($now)"
set +e
run_bounded "$TRIPWIRE_LIMIT_SECS" "tripwire" python3 "$SCRIPT_DIR/rumble_tripwire.py"
TW_RC=$?
set -e

if [[ $TW_RC -eq 0 ]]; then
  log "Tripwire unchanged"
  exit 0
fi
if [[ $TW_RC -eq 1 ]]; then
  run_full "tripwire changed"
  exit $?
fi
if [[ $TW_RC -eq 124 ]]; then
  log "Tripwire stopped on time limit. Skipping full scrape."
  exit 124
fi

log "Tripwire error (exit $TW_RC). Skipping full scrape."
exit $TW_RC
