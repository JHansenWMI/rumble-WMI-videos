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
        "https://rumble.com/c/c-7899090/shorts" \
        "https://rumble.com/c/c-7899090/livestreams"
    fi
  fi
  log "Overcoming feed generation failed (exit $OVER_STATUS)"
  exit $OVER_STATUS
fi

git add docs/rumble-feed.json docs/overcoming-feed.json

if git diff --cached --ignore-matching-lines=generatedAt --quiet -- docs/rumble-feed.json docs/overcoming-feed.json; then
  git restore --staged docs/rumble-feed.json docs/overcoming-feed.json
  git restore docs/rumble-feed.json docs/overcoming-feed.json
  echo "$(date '+%Y-%m-%d %H:%M:%S') feed files did not change. Nothing to commit."
  exit 0
fi

git commit -m "Update Rumble feed JSON files"
log "Pushing to origin/main"
git push origin main
log "Done"
