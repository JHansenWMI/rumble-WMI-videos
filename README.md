# rumble-WMI-videos
Tool to fetch and list videos from WMI rumble channel
The main files are
generate_rumble_feed.py
publish_rumble_feed.sh

Feeds:
- docs/rumble-feed.json is generated from docs/rumble-urls.txt.
- docs/overcoming-feed.json is generated from docs/overcoming-urls.txt.
- URL list lines scrape one page by default. Add pages=2 after a URL when a specific source should fetch page 2.

Rumble HTML samples:
- samples/rumble-channel-pages/ stores dated snapshots of channel listing pages (see README there). Use when Rumble changes markup and the feed parser needs updating.
- Default behavior (production/safe mode, used by the prod Mac Mini after a plain pull): on parser failure the scheduled job prints a short message and exits. No auto-capture or git activity from that machine.
- On the dev MacBook (set `RUMBLE_FEED_MODE=development` in its launchd plist) you get auto-capture of `auto-...` sample dirs + the full instructions. In addition, the script runs a scoped headless Grok attempt (tight tool limits, max turns, stop conditions) that tries a contained fix to generate_rumble_feed.py and verifies with `--test-html` / `--compare-to-items`. Edits (if any) and a note are left for your manual review; the run still fails so no feed is updated. You can resume the session later with focus. Manually capture with the script in `samples/` if needed.
- `generate_rumble_feed.py --production` forces the short safe mode for direct runs. The `--test-html` etc. debug flags are always available.

Channel metadata:
- generate_rumble_feed.py collects channelName and channelUrl by fetching each selected video's detail page.
- Existing output JSON is used as a cache, keyed by link and guid, so the first enriched run will fetch details for current videos and later runs should only fetch details for new or missing videos.
- The default delay is intentionally slow, with jitter, to avoid hitting Rumble too quickly.
