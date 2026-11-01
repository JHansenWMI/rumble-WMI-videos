#!/bin/zsh
set -euo pipefail

SCRIPT_DIR="${0:A:h}"
cd "$SCRIPT_DIR"

log() {
  print -r -- "[$(date '+%Y-%m-%d %H:%M:%S')] $*"
}

# Time limits. On Oct 30 2026 both weekly runs sat for 2+ days in open() on the
# spreadsheet, and launchd will not start the next run while one is still going.
# Copy the xlsx to a local temp file under a short limit, parse the local copy
# under a longer limit. Same pattern as rumble_feed_tick.sh: run the step in its
# own process group (perl setpgrp; launchd has no terminal for zsh MONITOR),
# and on expiry log a stack sample, then TERM and finally KILL the group.
COPY_LIMIT_SECS=60
PYTHON_LIMIT_SECS=300

run_bounded() {
  local secs="$1"
  local label="$2"
  shift 2
  /usr/bin/perl -e 'setpgrp(0, 0); exec @ARGV or die "exec: $!\n"' -- "$@" &
  local pid=$!
  local waited=0
  while kill -0 "$pid" 2>/dev/null; do
    if (( waited >= secs )); then
      log "Time limit hit ($label, ${secs}s, pid $pid). Stack sample follows, then stopping it."
      sample "$pid" 1 2>&1 | awk '
        /Call graph:/ { show = 1 }
        /Binary Images:/ { show = 0 }
        show { print }
      ' || true
      stop_process_group "$pid"
      wait "$pid" 2>/dev/null || true
      return 124
    fi
    sleep 1
    waited=$((waited + 1))
  done
  wait "$pid"
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

# Copy $XLSX into $WORK_DIR under COPY_LIMIT_SECS. Sets LOCAL_XLSX.
# Exits non-zero (124 on time limit) if the copy hangs, fails, or is empty.
copy_xlsx_local() {
  LOCAL_XLSX="$WORK_DIR/${XLSX:t}"
  log "Copying spreadsheet to local temp file (limit ${COPY_LIMIT_SECS}s): $XLSX"
  local rc=0
  run_bounded "$COPY_LIMIT_SECS" "copy xlsx" /bin/cp "$XLSX" "$LOCAL_XLSX" || rc=$?
  if (( rc != 0 )) || [ ! -s "$LOCAL_XLSX" ]; then
    (( rc != 0 )) || rc=1
    log "Could not copy $XLSX to $LOCAL_XLSX (exit $rc). Aborting; nothing changed."
    exit $rc
  fi
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

# Private temp dir for the local copy. Trap at top level: in zsh an EXIT trap
# set inside a function fires when that function returns.
WORK_DIR="$(mktemp -d "${TMPDIR:-/tmp}/radio-schedule.XXXXXX")"
trap 'rm -rf "$WORK_DIR"' EXIT
copy_xlsx_local

log "Running radio + shortwave schedule update from Excel (limit ${PYTHON_LIMIT_SECS}s)"
py_rc=0
run_bounded "$PYTHON_LIMIT_SECS" "update_radio_programs.py" \
  python3 "$SCRIPT_DIR/update_radio_programs.py" \
  --xlsx "$LOCAL_XLSX" \
  --csv "$SCRIPT_DIR/Intra Support Files/radio_programs.csv" \
  --schedule "$SCRIPT_DIR/docs/radio-schedule.txt" || py_rc=$?
if (( py_rc != 0 )); then
  log "update_radio_programs.py failed (exit $py_rc). Aborting before commit."
  exit $py_rc
fi

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