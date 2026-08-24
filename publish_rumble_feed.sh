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

# Unattended JSON recovery: Mini only, from ~/dev/thismac.env.
# MACHINE_ROLE=mac-mini-server and hostname -s must match HOSTNAME (fifo).
# Other Macs keep --ff-only with no reset. RUMBLE_FEED_MODE is parser/Grok only.
THISMAC_ENV="${HOME}/dev/thismac.env"
UNATTENDED_JSON_RECOVERY=0
THISMAC_HOST="$(hostname -s)"
# Identity keys only — thismac.env has unquoted paths with spaces, so do not source it.
thismac_key() {
  local key="$1" line
  [[ -f "$THISMAC_ENV" ]] || return 0
  line="$(grep -E "^${key}=" "$THISMAC_ENV" | tail -1 || true)"
  print -r -- "${line#*=}"
}
MACHINE_ROLE="$(thismac_key MACHINE_ROLE)"
ENV_HOSTNAME="$(thismac_key HOSTNAME)"
if [[ -f "$THISMAC_ENV" ]]; then
  if [[ "$MACHINE_ROLE" == "mac-mini-server" && -n "$ENV_HOSTNAME" && "$THISMAC_HOST" == "$ENV_HOSTNAME" ]]; then
    UNATTENDED_JSON_RECOVERY=1
    log "Unattended JSON recovery on (role=$MACHINE_ROLE host=$THISMAC_HOST)"
  else
    log "Unattended JSON recovery off (role=${MACHINE_ROLE:-unset} host=$THISMAC_HOST env-host=${ENV_HOSTNAME:-unset})"
  fi
else
  log "Unattended JSON recovery off (no $THISMAC_ENV)"
fi

is_feed_json_path() {
  local p="$1"
  [[ "$p" == docs/*-feed.json || "$p" == docs/*-feed-archive.json ]]
}

# Drop unique local commits that are only feed JSON, then hard-reset to origin/main.
# Returns 0 if reset happened. Does not merge. One caller-level retry only.
# Caller must have fetched origin. Reset only when histories diverged (origin/main
# is not an ancestor of HEAD). Ahead-only (failed push, origin unchanged) keeps
# the unpublished scrape.
recover_feed_json_divergence() {
  local why="$1"
  if [[ "$UNATTENDED_JSON_RECOVERY" != 1 ]]; then
    log "JSON recovery skipped ($why; not Mini unattended host)"
    return 1
  fi
  git update-index -q --refresh
  if ! git diff --quiet || ! git diff --cached --quiet; then
    log "JSON recovery skipped ($why; working tree not clean)"
    return 1
  fi

  local n s f
  n="$(git rev-list --count origin/main..HEAD)"
  if [[ "$n" -eq 0 ]]; then
    log "JSON recovery skipped ($why; no unique local commits)"
    return 1
  fi
  if git merge-base --is-ancestor origin/main HEAD; then
    log "JSON recovery skipped ($why; not diverged from origin/main)"
    return 1
  fi
  while IFS= read -r s; do
    if [[ "$s" != "Update Rumble feed JSON files" ]]; then
      log "JSON recovery skipped ($why; local commit is not a feed JSON update: $s)"
      return 1
    fi
  done < <(git log --format=%s origin/main..HEAD)

  while IFS= read -r f; do
    [[ -z "$f" ]] && continue
    if ! is_feed_json_path "$f"; then
      log "JSON recovery skipped ($why; local commit touches $f)"
      return 1
    fi
  done < <(git diff --name-only origin/main..HEAD)

  log "JSON recovery ($why): dropping $n local feed-JSON commit(s), reset --hard origin/main"
  git reset --hard origin/main
  return 0
}

sync_origin_main() {
  log "Pulling latest origin/main"
  git fetch origin
  if git pull --ff-only origin main; then
    return 0
  fi
  if recover_feed_json_divergence "pull"; then
    return 0
  fi
  log "Cannot fast-forward onto origin/main. Aborting."
  exit 1
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

sync_origin_main

urls_from_list() {
  python3 -c '
from pathlib import Path
from generate_rumble_feed import read_urls
import sys
for source in read_urls(Path(sys.argv[1])):
    print(source.url)
' "$1"
}

capture_on_parser_failure() {
  local list_file="$1"
  local urls=() u
  while IFS= read -r u; do
    [[ -n $u ]] && urls+=("$u")
  done < <(urls_from_list "$list_file")
  if (( ${#urls[@]} == 0 )); then
    log "Parser failure capture skipped (no URLs in $list_file)"
    return 0
  fi
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
    # Bounded investigation + limited parser fix (tool scope, max turns, stop conditions).
    # Parser edits are copied into the sample dir as a diff, then the working tree
    # is restored so the next scheduled run is not blocked by a dirty tree.
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

    local sample_dir="samples/rumble-channel-pages/$iteration"
    local parser="generate_rumble_feed.py"
    local parser_diff="$sample_dir/generate_rumble_feed.py.diff"
    git update-index -q --refresh
    if ! git diff --quiet -- "$parser"; then
      git diff -- "$parser" > "$parser_diff" || true
      if [[ -f "$sample_dir/fix-attempt-note.md" ]]; then
        log "Grok left uncommitted $parser edits; saved $parser_diff (see $sample_dir/fix-attempt-note.md)."
      else
        log "Grok left uncommitted $parser edits; saved $parser_diff."
      fi
      log "Restoring $parser so the next scheduled run is not blocked. Review $sample_dir (session rumble-parser-fix-$iteration) before committing a parser fix."
      git restore -- "$parser"
    fi

    log "Headless Grok parser fix attempt for $iteration complete. The scheduled run will still exit with failure."
  fi
}

generate_all_feeds() {
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
        capture_on_parser_failure "$SCRIPT_DIR/docs/rumble-urls.txt"
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
        capture_on_parser_failure "$SCRIPT_DIR/docs/overcoming-urls.txt"
      fi
    fi
    log "Overcoming feed generation failed (exit $OVER_STATUS)"
    exit $OVER_STATUS
  fi

  log "Generating feed (tv)"
  set +e
  TV_OUT=$(python3 "$SCRIPT_DIR/generate_tv_feed.py" $PROD_FLAG 2>&1)
  TV_STATUS=$?
  set -e
  print -r -- "$TV_OUT"
  if [ $TV_STATUS -ne 0 ]; then
    log "TV feed generation failed (exit $TV_STATUS)"
    exit $TV_STATUS
  fi
}

# Determine which feed JSON files (and their archives) to manage for this run.
# We load the list of *primary* feeds from Python (single source of truth)
# and only include the corresponding archive if it actually exists on disk
# (using the same get_archive_path logic the generator uses).
# This avoids hardcoding non-existent files such as docs/overcoming-feed-archive.json.
collect_feed_files() {
  PRIMARY_FEEDS=()
  while IFS= read -r line; do
      [[ -n $line ]] && PRIMARY_FEEDS+=("$line")
  done < <(python3 -c '
from generate_rumble_feed import PRIMARY_FEED_FILES
for p in PRIMARY_FEED_FILES:
    print(p)
' )

  FEED_FILES=()
  FEED_FILES+=("docs/tv-feed.json")

  local primary archive
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
}

# Sets COMMITTED=1 if a feed JSON commit was made, else 0 (restores generated clocks).
commit_feeds_if_changed() {
  collect_feed_files
  git add "${FEED_FILES[@]}" 2>/dev/null || true

  # Use per-item "updated" timestamps vs the file's last commit time.
  # A record only gets a fresh updated (in stamp_item_json) when its content actually changed.
  local paths_py
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
    log "feed files did not change. Nothing to commit."
    COMMITTED=0
    return 0
  fi

  git commit -m "Update Rumble feed JSON files"
  COMMITTED=1
  return 0
}

push_main() {
  local attempt="$1"
  log "Pushing to origin/main${attempt:+ ($attempt)}"
  git push origin main
}

generate_all_feeds
commit_feeds_if_changed
if [[ "$COMMITTED" == 1 ]]; then
  if ! git push origin main; then
    log "Push rejected; fetching origin"
    git fetch origin
    if recover_feed_json_divergence "push"; then
      generate_all_feeds
      commit_feeds_if_changed
      if [[ "$COMMITTED" == 1 ]]; then
        push_main "after recovery"
      fi
    else
      log "Push failed and JSON recovery did not apply. Aborting."
      exit 1
    fi
  fi
fi
log "Done"
