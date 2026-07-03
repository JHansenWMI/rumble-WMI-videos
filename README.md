# rumble-WMI-videos
Tool to fetch and list videos from WMI rumble channel
The main files are
generate_rumble_feed.py
publish_rumble_feed.sh

Feeds:
- `docs/rumble-feed.json` (main) is produced from `docs/rumble-urls.txt` (DrJonathanHansenWMI user account: videos/shorts/livestreams).
- `docs/overcoming-feed.json` is produced from `docs/overcoming-urls.txt` (specific Overcoming channel).
- **Current generation model (post reorg ~Jul 2026)**: Periodic runs scrape the configured sources (normally just page 1 of each URL for efficiency). Newly discovered items are *merged* into the existing history in the JSON (accumulate; do not replace/redo the whole list). Fresh scrape data is preferred for overlaps. Older items are kept until archiving.
  - One-time bulk population (e.g. initial history) can use `pages=N` in the URL list or higher `--pages` / direct runs.
  - After merge/enrichment, excess items beyond the active limit (default 90) are moved to the corresponding `*-archive.json`.
- URL list syntax: `https://...` (1 page) or `https://... pages=3`.
- Per-item `"updated"` (Pacific time) timestamps are stamped on records that change; `publish_rumble_feed.sh` uses these (via `feed_has_meaningful_change`) to decide whether a real content change warrants a git commit+push (replaced older generatedAt-only heuristic).
- Archives (`docs/rumble-feed-archive.json`, and overcoming when present) are managed dynamically when they exist on disk.

TV schedule (for TVShowsSnippetNew.html):
- docs/tv-schedule.txt contains the ordered list of upcoming/past TV broadcast entries (one line per entry in the form "MMM DD, YYYY: Title").
- The list is maintained by merging from the station spreadsheet.
- Use `update_tv_schedule.py` (run on a machine that can see the file):
    python update_tv_schedule.py --xlsx "/Volumes/Office/Public/01 TV-Radio Spreadsheets/KAZQ.xlsx" --schedule docs/tv-schedule.txt
  It looks at the last few usable rows, converts the (Sunday) air date codes to actual Friday air dates, and merges only new entries.
- On the production Mac Mini this runs automatically every Friday at 4am via launchd (`update_tv_schedule.sh` + `com.jhansenwmi.tv-schedule.plist`).
  The wrapper handles git pull, runs the updater, and commits/pushes only if the schedule changed.
- To install on the Mac Mini (or similar):
  1. `pip3 install openpyxl` (or ensure your `python3` has it)
  2. Copy `com.jhansenwmi.tv-schedule.plist` (or the .example, customized) to `~/Library/LaunchAgents/`
  3. `launchctl load ~/Library/LaunchAgents/com.jhansenwmi.tv-schedule.plist`
- Manual runs (or on other machines) still work with the python command above; follow with `git add + commit + push` if desired.

Radio schedule (for RadioBroadcastSnippet.html):
- `docs/radio-schedule.txt` contains the ordered list of radio broadcast entries (one line per entry in the form "Day, Mon DD, YYYY: Title").
- Generated from `Intra Support Files/radio_programs.csv` (primary slot-1 programs + cleaning). Pure data file — no display logic or paging info (see design principle in docs/README.md).
- `RadioBroadcastSnippet.html` fetches it dynamically and handles all paging client-side (50 items/page, buttons, last-page special case, scroll stabilization).
- See WorkToDo/Radio Program Parsing.MD for generation details, seed comparison, and snippet implementation notes.

Rumble HTML samples:
- samples/rumble-channel-pages/ stores dated snapshots of channel listing pages (see README there). Use when Rumble changes markup and the feed parser needs updating.
- Default behavior (production/safe mode, used by the prod Mac Mini after a plain pull): on parser failure the scheduled job prints a short message and exits. No auto-capture or git activity from that machine.
- On the dev MacBook (set `RUMBLE_FEED_MODE=development` in its launchd plist) you get auto-capture of `auto-...` sample dirs + the full instructions. In addition, the script runs a scoped headless Grok attempt (tight tool limits, max turns, stop conditions) that tries a contained fix to generate_rumble_feed.py and verifies with `--test-html` / `--compare-to-items`. Edits (if any) and a note are left for your manual review; the run still fails so no feed is updated. You can resume the session later with focus. Manually capture with the script in `samples/` if needed.
- `generate_rumble_feed.py --production` forces the short safe mode for direct runs. The `--test-html` etc. debug flags are always available.

Channel metadata + inclusion:
- `generate_rumble_feed.py` collects/enriches `channelName` and `channelUrl` (and `videoId` embed) by fetching detail pages for items that need it.
- Channel cache is loaded from the prior output JSON (keyed by link/guid) so later runs only re-fetch for new or missing videos.
- Main rumble feed accumulates videos from the DrJonathanHansenWMI account (which surfaces content across associated channels, tagged by channelName/Url in the items). A separate feed is maintained for the Overcoming channel.
- The default delay is intentionally slow, with jitter, to avoid hitting Rumble too quickly.
- Custom overrides/filters live in `custom_update.py` (REMOVE_GUIDS, OVERRIDES_BY_GUID) and are applied after merge.
