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

Channel metadata:
- generate_rumble_feed.py collects channelName and channelUrl by fetching each selected video's detail page.
- Existing output JSON is used as a cache, keyed by link and guid, so the first enriched run will fetch details for current videos and later runs should only fetch details for new or missing videos.
- The default delay is intentionally slow, with jitter, to avoid hitting Rumble too quickly.
