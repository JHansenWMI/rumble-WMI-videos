# Feed JSONs and related files

This directory holds the generated Rumble feeds consumed by the website/CMS snippets, plus supporting lists and schedule data.

## Primary feeds (active / "latest")
- `rumble-feed.json`: Main feed (DrJonathanHansenWMI user account). Accumulates history from periodic first-page scrapes of /videos, /shorts, /livestreams. Capped at ~90 items; older ones move to the archive.
- `overcoming-feed.json`: Dedicated feed for the Overcoming channel (c/c-7899090 sources).

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
    },
    ...
  ]
}
```

- Items are sorted newest-first by timestamp.
- Per-item `"updated"` (Pacific) is used by the publish script to detect *real* content changes worth committing.
- Channel fields are enriched from video detail pages (cached across runs).

## Archives
- `rumble-feed-archive.json` (and `overcoming-...-archive.json` when present): Excess older videos moved here when the active feed exceeds its limit (default 90 via `--limit` / write_feed).
- `archive_excess()` in generate_rumble_feed.py handles the move after accumulation + enrichment.
- Archives are only added to the publish change-detection set if the file exists on disk.

## Source configuration
- `rumble-urls.txt` and `overcoming-urls.txt`: one URL per line.
  - Default: scrape 1 page.
  - Append `pages=3` (or `page=2`) on a line for deeper fetches (used for initial bulk population of history).
- In normal periodic operation the publish wrapper runs generate with these files (1 page each) + accumulation logic so history is retained without repeated deep scrapes.

## Generation & accumulation model (post Jul 2026 reorg)
- Scrape fresh items from configured sources.
- Merge new discoveries into prior JSON history (`merge_fresh_into_accumulated` + `merge_scraped_with_existing` for embed ids etc.).
- Apply `custom_update.py` (duplicate removal, title/date overrides).
- Enrich channel details (cached).
- Cap active list + archive excess.
- `publish_rumble_feed.sh` pulls, runs the above for both feeds, then uses `feed_has_meaningful_change()` (per-item updated > file's last git commit) to decide commit+push. Only real changes trigger updates.

This replaced the old "always fully regenerate + crude generatedAt diff" approach.

See top-level README.md for overall usage, production vs dev modes, and launchd setup. See `generate_rumble_feed.py` (especially main(), merge_*, archive_excess(), feed_has_meaningful_change) and `publish_rumble_feed.sh` for implementation.

## Other files
**Design principle:** Avoid display logic and parameters in data files.
- `tv-schedule.txt`: Managed separately by `update_tv_schedule.py` (merge from spreadsheet). Used by TVShowsSnippetNew.html.
- `radio-schedule.txt`: Generated from `radio_programs.csv` (slot=1 entries + title cleaning). Analogous to tv-schedule. Pure data (flat lines only — see design principle above). Used by RadioBroadcastSnippet.html (dynamic fetch + paging logic entirely in snippet).
- `shortwave-schedule.txt`: Generated from the same CSV (`program_number` ending in `SW` + shortwave-specific title cleaning). Same flat-line format. Used by ShortWaveBroadcastSnippet.html.
- `shortwave-schedule-static.txt`: One-time CMS extract for comparison; not used by the live snippet.
- `rumble-urls.txt`, `overcoming-urls.txt`: See above.

