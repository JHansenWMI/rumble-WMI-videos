# rumble-WMI-videos
Tool to fetch and list videos from WMI rumble channel
The main files are
generate_rumble_feed.py
publish_rumble_feed.sh

Feeds:
- docs/rumble-feed.json is generated from docs/rumble-urls.txt.
- docs/overcoming-feed.json is generated from docs/overcoming-urls.txt.
- URL list lines scrape one page by default. Add pages=2 after a URL when a specific source should fetch page 2.

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

Rumble HTML samples:
- samples/rumble-channel-pages/ stores dated snapshots of channel listing pages (see README there). Use when Rumble changes markup and the feed parser needs updating.
- Default behavior (production/safe mode, used by the prod Mac Mini after a plain pull): on parser failure the scheduled job prints a short message and exits. No auto-capture or git activity from that machine.
- On the dev MacBook (set `RUMBLE_FEED_MODE=development` in its launchd plist) you get auto-capture of `auto-...` sample dirs + the full instructions. In addition, the script runs a scoped headless Grok attempt (tight tool limits, max turns, stop conditions) that tries a contained fix to generate_rumble_feed.py and verifies with `--test-html` / `--compare-to-items`. Edits (if any) and a note are left for your manual review; the run still fails so no feed is updated. You can resume the session later with focus. Manually capture with the script in `samples/` if needed.
- `generate_rumble_feed.py --production` forces the short safe mode for direct runs. The `--test-html` etc. debug flags are always available.

Channel metadata:
- generate_rumble_feed.py collects channelName and channelUrl by fetching each selected video's detail page.
- Existing output JSON is used as a cache, keyed by link and guid, so the first enriched run will fetch details for current videos and later runs should only fetch details for new or missing videos.
- The default delay is intentionally slow, with jitter, to avoid hitting Rumble too quickly.
