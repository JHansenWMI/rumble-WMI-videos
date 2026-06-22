# Video description fetch test (2026-06-16)

Exploratory step toward putting website-usage instructions in Rumble video descriptions.

## What was done

- Added `test_video_descriptions.py` (standalone; no changes to production scripts).
- Ran against `https://rumble.com/user/DrJonathanHansenWMI/videos`.
- Wrote results to `temp-video-descriptions-test.json`.

## Findings

- **Channel listing** returns title, link, date, thumb — not per-video descriptions.
- **Video detail pages** do have descriptions:
  - Full text: `media-description--first` + `media-description--more` HTML blocks.
  - Fallback: schema.org `VideoObject` JSON-LD (~200 chars, truncated).
- Test run: 25 videos on listing; fetched 5 detail pages; **5/5 had a description** (4 full HTML, 1 schema-only).
- Many descriptions include a standard WMI footer (program links, contact, newsletter, etc.) — may need stripping if parsing site-specific instructions.

## Resume later

```bash
python3 test_video_descriptions.py --verbose --limit 10
```

Flags: `--url`, `--output`, `--delay`.

## Next steps (not started)

- Decide instruction format to embed in Rumble descriptions.
- Integrate description fetch into feed pipeline (if desired), with caching like channel details.
- Strip boilerplate footer before parsing instructions.