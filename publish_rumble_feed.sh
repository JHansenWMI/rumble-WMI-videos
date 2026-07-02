#!/bin/zsh
set -euo pipefail

SCRIPT_DIR="${0:A:h}"
cd "$SCRIPT_DIR"

log() {
  print -r -- "[$(date '+%Y-%m-%d %H:%M:%S')] $*"
}

# Default to "production" (safe/dumb mode) when unset.
# Production Mac Mini can leave this unset after a plain pull.
# Dev MacBook sets RUMBLE_FEED_MODE=development in its launchd plist
# to enable auto-capture + full dev/Grok instructions on failure.
MODE="${RUMBLE_FEED_MODE:-production}"
PROD_FLAG=""
if [ "$MODE" = "production" ]; then
  PROD_FLAG="--production"
fi

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

capture_on_parser_failure() {
  local urls=("$@")
  local iteration="auto-$(date '+%Y-%m-%d-%H%M')-rumble-html-change"
  log "Parser failure detected - auto-capturing sample to $iteration for later Grok fix"
  local captured=0
  for url in "${urls[@]}"; do
    if python3 "$SCRIPT_DIR/samples/capture_rumble_channel_page.py" --iteration "$iteration" --url "$url"; then
      captured=$((captured + 1))
    fi
  done
  if [ "$captured" -gt 0 ]; then
    git add "samples/rumble-channel-pages/$iteration" || true
    if ! git diff --cached --quiet; then
      git commit -m "Auto-captured Rumble sample(s) after 'No Rumble items found' parser error.
See samples/rumble-channel-pages/$iteration/
This provides the HTML snapshot needed for Grok to update generate_rumble_feed.py and test the fix.
Scheduled feed updates are paused until parser is repaired."
      log "Pushing auto-captured sample"
      git push origin main || true
    fi

    # Scoped headless Grok attempt (development mode only).
    # Goal: bounded investigation + limited fix attempt on the parser.
    # Uses strict tool scoping, max turns, and explicit stop conditions so the
    # run stays contained while the dev machine may be used for other work.
    # On success: edits are left in the working tree for manual review/commit.
    # On "too complicated": writes a short note in the sample dir and stops.
    log "Attempting scoped headless Grok parser fix for $iteration"
    PROMPT=$(cat <<'PROMPT_EOF'
The Rumble parser in generate_rumble_feed.py hit "No Rumble items found. Rumble may have changed its page HTML."

A fresh sample has been captured to samples/rumble-channel-pages/ITERATION/

This directory contains:
- Raw .html page response(s)
- .items.json (structured listing data if the {"items":[ pattern was present)
- capture-meta.json (marker counts showing the nature of the change)

Task: Analyze the new data structure in the captured HTML and update the parser logic in generate_rumble_feed.py so the core fields (title, link, pubDate, thumb, id, and channel info when available) extract correctly.

Use the existing verification commands for testing (adapt the slug/filename for shorts, livestreams, or overcoming sources as needed):

  python generate_rumble_feed.py --test-html samples/rumble-channel-pages/ITERATION/DrJonathanHansenWMI-videos.html \
    --test-source https://rumble.com/user/DrJonathanHansenWMI/videos \
    --compare-to-items samples/rumble-channel-pages/ITERATION/DrJonathanHansenWMI-videos.items.json

Also run equivalent commands against the previous known-good sample (samples/rumble-channel-pages/2026-06-04-embedded-json-listing/) to protect against regressions.

Scope and focus (strict):
- Work primarily inside generate_rumble_feed.py (the parse_items, parse_embedded_*, parse_channel_info functions and close helpers).
- Prefer small, targeted additions or modifications to extraction logic.
- Keep existing fallback paths if they remain useful.
- Use the --test-html / --compare-to-items commands above for all verification.

Stop conditions (do not ignore):
- You have not identified a viable extraction strategy for the core fields after a modest number of steps, OR
- The changes required appear significantly broader than focused updates inside generate_rumble_feed.py (e.g. large refactors, many new files, new infrastructure).

If either stop condition is met:
  STOP immediately.
  Write a short, focused note to samples/rumble-channel-pages/ITERATION/fix-attempt-note.md with:
    - What the new page structure appears to be (from the .html and .items.json)
    - What extraction approaches you tried
    - The specific complication
    - Any partial findings useful for later human work
  Then finish cleanly. Do not keep iterating or making further edits.

Tool restrictions (enforced):
- Allowed: reading relevant files, grep, the specific test commands shown above, editing generate_rumble_feed.py or the note file.
- Everything else is disallowed (no web tools, no sub-agents, no broad shell or edits).

You may use --session-id rumble-parser-fix-ITERATION for resumability if a human wants to continue later with full focus.
PROMPT_EOF
)
    PROMPT=$(echo "$PROMPT" | sed "s|ITERATION|$iteration|g")

    grok -p "$PROMPT" \
      --yolo \
      --output-format json \
      --max-turns 12 \
      --effort low \
      --session-id "rumble-parser-fix-$iteration" \
      --cwd "$SCRIPT_DIR" \
      --disallowed-tools "web_search,web_fetch,Agent" \
      --allow 'Edit(generate_rumble_feed.py)' \
      --allow 'Bash(python generate_rumble_feed.py --test-html*--compare-to-items*)' \
      --deny 'Edit(*)' \
      > "samples/rumble-channel-pages/$iteration/grok-fix-output.json" 2>&1 || true

    log "Headless Grok parser fix attempt for $iteration complete. Review any edits to generate_rumble_feed.py and the note (if written) in the sample directory before committing. The scheduled run will still exit with failure."
  fi
}

log "Generating feed (rumble)"
set +e
RUMBLE_OUT=$(python3 "$SCRIPT_DIR/generate_rumble_feed.py" $PROD_FLAG \
  --input "$SCRIPT_DIR/docs/rumble-urls.txt" 2>&1)
RUMBLE_STATUS=$?
set -e
print -r -- "$RUMBLE_OUT"
if [ $RUMBLE_STATUS -ne 0 ]; then
  if echo "$RUMBLE_OUT" | grep -q "Rumble may have changed its page HTML"; then
    if [ "$MODE" = "development" ]; then
      capture_on_parser_failure \
        "https://rumble.com/user/DrJonathanHansenWMI/videos" \
        "https://rumble.com/user/DrJonathanHansenWMI/shorts" \
        "https://rumble.com/user/DrJonathanHansenWMI/livestreams"
    fi
  fi
  log "Rumble feed generation failed (exit $RUMBLE_STATUS)"
  exit $RUMBLE_STATUS
fi

log "Generating feed (overcoming)"
set +e
OVER_OUT=$(python3 "$SCRIPT_DIR/generate_rumble_feed.py" $PROD_FLAG \
  --input "$SCRIPT_DIR/docs/overcoming-urls.txt" \
  --output "$SCRIPT_DIR/docs/overcoming-feed.json" 2>&1)
OVER_STATUS=$?
set -e
print -r -- "$OVER_OUT"
if [ $OVER_STATUS -ne 0 ]; then
  if echo "$OVER_OUT" | grep -q "Rumble may have changed its page HTML"; then
    if [ "$MODE" = "development" ]; then
      capture_on_parser_failure \
        "https://rumble.com/c/c-7899090/videos" \
        "https://rumble.com/c/c-7899090/livestreams"
    fi
  fi
  log "Overcoming feed generation failed (exit $OVER_STATUS)"
  exit $OVER_STATUS
fi

# Determine which feed JSON files (and their archives) to manage for this run.
# We load the list of *primary* feeds from Python (single source of truth)
# and only include the corresponding archive if it actually exists on disk
# (using the same get_archive_path logic the generator uses).
# This avoids hardcoding non-existent files such as docs/overcoming-feed-archive.json.
PRIMARY_FEEDS=()
while IFS= read -r line; do
    [[ -n $line ]] && PRIMARY_FEEDS+=("$line")
done < <(python3 -c '
from generate_rumble_feed import PRIMARY_FEED_FILES
for p in PRIMARY_FEED_FILES:
    print(p)
' )

# Build the actual list of files to manage for this run.
# Always include primaries. Include an archive only if it was created on disk
# (using the exact same get_archive_path logic the generator uses).
FEED_FILES=()
for primary in "${PRIMARY_FEEDS[@]}"; do
    FEED_FILES+=("$primary")
    archive=$(python3 -c '
from pathlib import Path
from generate_rumble_feed import get_archive_path
import sys
print(get_archive_path(Path(sys.argv[1])))
' "$primary" 2>/dev/null || true)
    if [[ -f $archive ]]; then
        FEED_FILES+=("$archive")
    fi
done

git add "${FEED_FILES[@]}" 2>/dev/null || true

# Use per-item "updated" timestamps vs the file's last commit time.
# A record only gets a fresh updated (in stamp_item_json) when its content actually changed.
# This replaces the old --ignore-matching-lines git-diff heuristic.
# The list of files is built dynamically above (primaries + archives that exist).
paths_py=$(printf '"%s",' "${FEED_FILES[@]}")
paths_py="[${paths_py%,}]"

if python3 -c "
import sys
sys.path.insert(0, '.')
from generate_rumble_feed import feed_has_meaningful_change
paths = $paths_py
if any(feed_has_meaningful_change(p) for p in paths):
    sys.exit(1)  # at least one file has a meaningfully newer record
sys.exit(0)
"; then
  git restore --staged "${FEED_FILES[@]}" 2>/dev/null || true
  git restore "${FEED_FILES[@]}" 2>/dev/null || true
  echo "$(date '+%Y-%m-%d %H:%M:%S') feed files did not change. Nothing to commit."
  exit 0
fi

git commit -m "Update Rumble feed JSON files"
log "Pushing to origin/main"
git push origin main
log "Done"
