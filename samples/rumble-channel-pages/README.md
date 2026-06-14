# Rumble channel page samples

Frozen HTML (and extracted listing JSON) from Rumble channel listing pages. These snapshots document the page shape `generate_rumble_feed.py` was written against, so future Rumble markup changes can be compared without guessing.

## Layout

Each iteration lives in its own dated folder:

```
samples/rumble-channel-pages/
  README.md
  2026-06-04-embedded-json-listing/
    capture-meta.json
    DrJonathanHansenWMI-videos.html
    DrJonathanHansenWMI-videos.items.json
```

| File | Purpose |
|------|---------|
| `capture-meta.json` | When/where captured, byte size, marker counts for old vs new HTML |
| `*.html` | Full page response (same as `fetch_html()` in the generator) |
| `*.items.json` | Extracted `{"items":[...]}` block the script parses today |

## Iterations

| Folder | Parser expectation |
|--------|-------------------|
| `2026-06-04-embedded-json-listing` | Listing videos in embedded JSON (`upload_date`, `title`, `url`, `by`, …). No `videostream` / `thumbnail__*` cards. |

When Rumble changes again, add a new folder with today’s date and a short label, e.g. `2027-01-15-new-layout`.

## Capture a new sample

From the repo root:

```bash
python3 samples/capture_rumble_channel_page.py \
  --iteration 2026-06-04-embedded-json-listing \
  --url https://rumble.com/user/DrJonathanHansenWMI/videos
```

Optional: `--slug DrJonathanHansenWMI-videos` overrides the output basename (default: last path segment of the URL).

## Auto-captured failure samples

`publish_rumble_feed.sh` (when run with `RUMBLE_FEED_MODE=development` on the dev machine) detects the "No Rumble items found. Rumble may have changed its page HTML." error.

**Default behavior (RUMBLE_FEED_MODE unset or "production")** — used by the production Mac Mini after a plain pull:
- Short error message only.
- No auto-capture, no git commit/push of a sample dir from that machine.
- The scheduled job just fails cleanly.

**Rich behavior** (set `RUMBLE_FEED_MODE=development` in the launchd plist on your dev MacBook):
- Auto-captures to `samples/rumble-channel-pages/auto-YYYY-MM-DD-HHMM-rumble-html-change/`
- Commits + pushes the sample.
- Emits the full "ACTION REQUIRED" instructions.
- Then runs a **scoped headless Grok attempt** (using `grok -p ... --yolo` with tight tool restrictions, --max-turns, --effort low, and explicit stop conditions).
  - The agent is limited to reading the new sample + old good sample, running the `--test-html` verification commands, and editing only `generate_rumble_feed.py` (plus writing a note).
  - Goal: contained diagnosis + small targeted parser fix.
  - If it cannot produce a clean extraction path quickly, it writes a short `fix-attempt-note.md` describing the new structure, what it tried, and the complication, then stops.
- Any source edits are left uncommitted for manual review (the run still exits with failure so no feed update occurs). You can resume the named session later with full focus when you have time.

See the top-level README and the plist.example for setup details (the dev MacBook's launchd job runs `publish_rumble_feed.sh` in development mode to perform auto-capture and monitoring).

## Fixing the parser after a change (with Grok)

On the **production Mac Mini** (default mode): the log will contain only a short failure message. No sample is auto-captured/pushed by that machine.

On your **dev MacBook** (with `RUMBLE_FEED_MODE=development` in its plist, or when you run the sh/generate manually):
- You will see the full instructions + (if using the sh) an auto-captured sample dir in git.
- Or manually capture:
  ```bash
  python samples/capture_rumble_channel_page.py \
    --iteration "$(date +%Y-%m-%d)-html-change" \
    --url https://rumble.com/user/DrJonathanHansenWMI/videos
  ```
- Reproduce + verify with the debug CLI (works offline):
  ```bash
  python generate_rumble_feed.py \
    --test-html samples/rumble-channel-pages/.../DrJonathanHansenWMI-videos.html \
    --test-source https://rumble.com/user/DrJonathanHansenWMI/videos \
    --compare-to-items .../DrJonathanHansenWMI-videos.items.json
  ```
- Give the Grok CLI (in this workspace) the prompt from the error output (or a concise version of it). It will inspect the new HTML (using grep/read_file/etc.), update the parser in `generate_rumble_feed.py`, use the `--test-html` commands to verify against the new + old sample, show a diff, and hand off for your review.

Commit the parser fix from the dev machine. The prod mini will pick it up on its next pull.

## Adding a manual sample (rare)

Only needed if auto-capture didn't trigger (e.g. one-off run). Use the capture command shown earlier, choosing a descriptive `--iteration` like `2027-01-15-new-json-shape`.
