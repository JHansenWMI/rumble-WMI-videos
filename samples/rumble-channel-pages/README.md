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
- Runs a bounded headless Grok attempt (`--max-turns`, `--effort low`, edit only `generate_rumble_feed.py`).
  - If it cannot extract quickly, it writes `fix-attempt-note.md` and stops.
- Parser edits are saved as `generate_rumble_feed.py.diff` in the sample dir, then the working tree is restored. The run still fails so no feed is published. Resume session `rumble-parser-fix-<iteration>` if needed.

See the top-level README and the plist.example for setup details (the Mini launchd job runs `rumble_feed_tick.sh`; a full scrape still calls `publish_rumble_feed.sh`. Dev MacBook can set `RUMBLE_FEED_MODE=development` for auto-capture).

## Fixing the parser after a change (with Grok)

On the **production Mac Mini** (default mode): the log will contain only a short failure message. No sample is auto-captured/pushed by that machine.

On your **dev MacBook** (with `RUMBLE_FEED_MODE=development` in its plist, or when you run the sh/generate manually):
- `publish_rumble_feed.sh` auto-captures a sample dir and may leave a `.diff` / note there.
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
- Review any `generate_rumble_feed.py.diff` / `fix-attempt-note.md` in the sample dir, or continue the named Grok session. Verify with `--test-html` against the new sample and `2026-06-04-embedded-json-listing/` before committing.

Commit the parser fix from the dev machine. The prod mini will pick it up on its next pull.

## Adding a manual sample (rare)

Only needed if auto-capture didn't trigger (e.g. one-off run). Use the capture command shown earlier, choosing a descriptive `--iteration` like `2027-01-15-new-json-shape`.
