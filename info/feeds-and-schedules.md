# Feeds and schedules (`docs/` data)

Detail for files under [`docs/`](../docs/). That folder is **website data** (GitHub Pages). Keep analysis and long write-ups in `info/`, not in `docs/`.

**Design principle:** Avoid display logic and parameters in data files. Hosted widgets (`docs/widgets/*.js`) own paging/UI; data files are flat lists or JSON feeds.

**CMS vs GitHub Pages:** CMS paste sources live at the **repo root**, named from the page title with hyphens (e.g. **Warning Social Media Video** → `Warning-Social-Media-Video-cms.html`). Pushing those files does **not** update the live CMS — paste by hand. `docs/*` on GitHub Pages *is* live after push: feeds, schedules, and `docs/widgets/`.

## Hosted widgets (`docs/widgets/`)

| CMS page | Shell (repo root) | Widget assets | Data |
|----------|-------------------|---------------|------|
| Warning Social Media Video | `Warning-Social-Media-Video-cms.html` | `Warning-Social-Media-Video.{css,js}` | `rumble-feed.json` |
| The Overcoming Women TV | `The-Overcoming-Women-TV-cms.html` | `The-Overcoming-Women-TV.{css,js}` | `overcoming-feed.json` |
| Warning TV Broadcasts | `Warning-TV-Broadcasts-cms.html` | `Warning-TV-Broadcasts.{css,js}` | `tv-feed.json`, `tv-schedule.txt` (+ optional site thumbs) |
| Warning Radio Broadcast | `Warning-Radio-Broadcast-cms.html` | `Warning-Radio-Broadcast.{css,js}` | `radio-schedule.txt` |
| Shortwave Broadcasts | `Shortwave-Broadcasts-cms.html` | `Shortwave-Broadcasts.{css,js}` | `shortwave-schedule.txt` |

Logic/style changes: edit `docs/widgets/*` and push (no CMS re-paste). Shell/chrome changes: edit `*-cms.html` and paste into CMS again.

## Primary Rumble feeds (active / “latest”)

- `rumble-feed.json`: Main feed (DrJonathanHansenWMI user account). Accumulates history from periodic first-page scrapes of `/videos`, `/shorts`, `/livestreams`. Capped at ~90 items; older ones move to the archive.
- `overcoming-feed.json`: Dedicated feed for the Overcoming channel (`c/c-7899090` sources).

Both are FetchRSS-style:

```json
{
  "title": "Rumble videos",
  "generatedAt": "...",
  "updated": "2026-07-03 08:58:23 PDT",
  "itemCount": 90,
  "items": [
    {
      "title": "...",
      "link": "https://rumble.com/...",
      "pubDate": "...",
      "media:content": "https://...thumb...",
      "guid": "video_id",
      "sourcePage": "https://rumble.com/...",
      "channelName": "The Overcoming Women",
      "channelUrl": "https://rumble.com/c/c-7899090",
      "videoId": "v...",
      "updated": "2026-07-03 08:58:23 PDT"
    }
  ]
}
```

- Items are sorted newest-first by timestamp.
- Per-item `"updated"` (Pacific) is used by the publish script to detect *real* content changes worth committing.
- Channel fields are enriched from video detail pages (cached across runs). See root README / `generate_rumble_feed.py` for when detail pages are fetched.

## Archives

- `rumble-feed-archive.json` (and `overcoming-...-archive.json` when present): Excess older videos moved here when the active feed exceeds its limit (default 90 via `--limit` / `write_feed`).
- `archive_excess()` in `generate_rumble_feed.py` handles the move after accumulation + enrichment.
- Archives are only added to the publish change-detection set if the file exists on disk.

## Source configuration

- `rumble-urls.txt` and `overcoming-urls.txt`: one URL per line.
  - Default: scrape 1 page.
  - Append `pages=3` (or `page=2`) on a line for deeper fetches (used for initial bulk population of history).
- In normal periodic operation the publish wrapper runs generate with these files (1 page each) + accumulation logic so history is retained without repeated deep scrapes.

## Generation & accumulation model (post Jul 2026 reorg)

- Scrape fresh items from configured sources.
- Merge new discoveries into prior JSON history (`merge_fresh_into_accumulated` + `merge_scraped_with_existing` for embed ids etc.).
- Apply `custom_update.py` (hide list + title/date overrides). `REMOVE_GUIDS` hides a video that is still on Rumble. After a Rumble deletion, purge stored JSON with `delete_from_feed.py` instead of adding the guid there.
- `feed_has_meaningful_change()` treats a changed guid/link set (add or delete) as a real update, not only a newer per-item `updated`.
- Enrich channel details (cached).
- Cap active list + archive excess.
- `publish_rumble_feed.sh` pulls, runs the above for both feeds, then runs `generate_tv_feed.py` (TV-only subset, no extra scrape), then uses `feed_has_meaningful_change()` to decide commit+push. Only real changes trigger updates.

This replaced the old “always fully regenerate + crude generatedAt diff” approach.

See root [`README.md`](../README.md) for overall usage, production vs dev modes, and launchd setup. Implementation: `generate_rumble_feed.py`, `publish_rumble_feed.sh`.

## TV broadcast feed

- `tv-feed.json`: TV feed for the **Warning TV Broadcasts** widget (`docs/widgets/Warning-TV-Broadcasts.js`). Includes titles ending in `TV{YYYYMMDD}`, and channel **WMI TV Broadcast History** even without that suffix. Generated by `generate_tv_feed.py` from rumble/overcoming feeds (no separate Rumble scrape). Full accumulation without the main feed’s 90-item cap.
- Matching: `TV{YYYYMMDD}` titles map to `tv-schedule.txt` by air date in the suffix. Broadcast History without `TV{date}` maps by normalized title; display date comes from the schedule (not Rumble `pubDate`).
- Fallback thumbs (no Rumble match): probe in order (1) GitHub `…/tv-thumbs/{YYYYMMDD}.jpg`, (2) CMS `…/Userfiles/video-thumbs/{YYYYMMDD}.jpg` for the schedule Friday air date; show non-clickable card if an image loads. Files live in repo `docs/tv-thumbs/` for the GitHub path.

## Schedules and related lists

- `tv-schedule.txt`: Managed by `update_tv_schedule.py` (merge from KAZQ spreadsheet). Trailing record dates in sheet titles (e.g. `06/19/26`) are stripped. Used by the Warning TV Broadcasts widget.
- `radio-schedule.txt`: Generated from `radio_programs.csv` (slot=1 + title cleaning). Flat lines only. Used by **Warning Radio Broadcast** (`docs/widgets/Warning-Radio-Broadcast.js`).
- `podbean-radio-matches.json` / `podbean-radio-matches-archive.json`: Podbean↔radio match maps from `match_podbean_to_radio.py` (available; not currently loaded by the radio schedule widget).
- `shortwave-schedule.txt`: Same CSV, `program_number` ending in `SW`. Used by **Shortwave Broadcasts** (`docs/widgets/Shortwave-Broadcasts.js`).
- `shortwave-schedule-static.txt`: One-time CMS extract for comparison; not used by the live widget.
- `rumble-urls.txt`, `overcoming-urls.txt`: Scrape source lists (see above).

## Week headers in the radio spreadsheet

Week ranges on **WATV Radio NOTES** may use an en-dash (`–`) from Excel/Word, not ASCII `-`. `update_radio_programs.py` accepts both. Fix real date typos in the sheet (e.g. wrong year); do not special-case bad years in code.
