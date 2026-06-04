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