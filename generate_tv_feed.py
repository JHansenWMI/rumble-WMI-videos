#!/usr/bin/env python3
"""
Generate docs/tv-feed.json — TV broadcast videos for Warning-TV-Broadcasts widget.

Includes:
  - Any video whose title ends with TV{YYYYMMDD}
  - Videos on channel "WMI TV Broadcast History" even without that suffix
    (snippet matches those to tv-schedule.txt by title; schedule date is display date)

Reads from already-generated rumble/overcoming feed JSON files (no extra Rumble scrape).
Unlike those feeds (capped at ~90 with archiving), tv-feed.json accumulates every
eligible TV video ever seen so older broadcasts stay available.
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from datetime import datetime, timezone
from pathlib import Path

from generate_rumble_feed import (
    FeedItem,
    _dict_to_feeditem,
    enrich_channel_details,
    feed_timestamps,
    load_channel_cache,
    load_existing_items,
    merge_fresh_into_accumulated,
    merge_scraped_with_existing,
    previous_items_by_link,
    stamp_item_json,
)

DEFAULT_OUTPUT = "docs/tv-feed.json"

TV_TITLE_RE = re.compile(r"TV\d{8}\s*$", re.I)
CHANNEL_BROADCAST_HISTORY = "WMI TV Broadcast History"

DEFAULT_SOURCE_FEEDS = [
    "docs/rumble-feed.json",
    "docs/rumble-feed-archive.json",
    "docs/overcoming-feed.json",
    "docs/overcoming-feed-archive.json",
]


def is_tv_title(title: str) -> bool:
    return bool(TV_TITLE_RE.search(str(title or "").strip()))


def is_broadcast_history_channel(channel_name: str) -> bool:
    return str(channel_name or "").strip() == CHANNEL_BROADCAST_HISTORY


def is_tv_item(item: FeedItem) -> bool:
    if is_tv_title(item.title):
        return True
    return is_broadcast_history_channel(item.channel_name)


def is_tv_dict(item: dict) -> bool:
    if is_tv_title(str(item.get("title") or "")):
        return True
    return is_broadcast_history_channel(str(item.get("channelName") or ""))


def filter_tv_items(items: list[FeedItem]) -> list[FeedItem]:
    return [item for item in items if is_tv_item(item)]


def filter_tv_dicts(items: list[dict]) -> list[dict]:
    return [item for item in items if is_tv_dict(item)]


def collect_tv_items_from_feeds(paths: list[Path]) -> list[FeedItem]:
    """Collect TV items from rumble/overcoming feed JSON files."""
    collected: list[FeedItem] = []
    seen_links: set[str] = set()

    for path in paths:
        if not path.exists():
            continue
        for item_dict in filter_tv_dicts(load_existing_items(path)):
            link = item_dict.get("link")
            if not link or link in seen_links:
                continue
            reconstructed = _dict_to_feeditem(item_dict)
            if not reconstructed or not is_tv_item(reconstructed):
                continue
            seen_links.add(link)
            collected.append(reconstructed)

    return collected


def dicts_to_tv_feed_items(items: list[dict]) -> list[FeedItem]:
    result: list[FeedItem] = []
    for item_dict in items:
        reconstructed = _dict_to_feeditem(item_dict)
        if reconstructed and is_tv_item(reconstructed):
            result.append(reconstructed)
    return result


def write_tv_feed(path: Path, items: list[FeedItem]) -> None:
    previous_by_link = previous_items_by_link(path)
    now_utc = datetime.now(timezone.utc)
    payload = {
        "title": "TV broadcast videos",
        **feed_timestamps(),
        "itemCount": len(items),
        "items": [
            stamp_item_json(item, previous_by_link.get(item.link), now_utc)
            for item in items
        ],
    }
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description=(
            "Generate tv-feed.json from rumble/overcoming feed JSON "
            "(TV{YYYYMMDD} titles, plus WMI TV Broadcast History channel)."
        )
    )
    parser.add_argument(
        "--output",
        default=DEFAULT_OUTPUT,
        help=f"JSON output file. Default: {DEFAULT_OUTPUT!r}",
    )
    parser.add_argument(
        "--from-feeds",
        nargs="*",
        default=DEFAULT_SOURCE_FEEDS,
        help="Source feed JSON files to read TV items from.",
    )
    parser.add_argument(
        "--enrich-channel-details",
        action="store_true",
        help="Fetch missing channel/embed details from Rumble (off by default; source feeds are usually already enriched).",
    )
    parser.add_argument(
        "--delay",
        type=float,
        default=2.0,
        help="Base delay between Rumble requests when --enrich-channel-details is used. Default: 2.0",
    )
    parser.add_argument("--verbose", action="store_true", help="Print progress.")
    parser.add_argument(
        "--production",
        action="store_true",
        help="Accepted for parity with generate_rumble_feed.py (no extra behavior here).",
    )
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    _ = args.production

    print(f"[{datetime.now().isoformat()}] Starting TV feed generation")
    output_path = Path(args.output)
    source_paths = [Path(p) for p in args.from_feeds]

    source_items = collect_tv_items_from_feeds(source_paths)
    if source_items:
        print(f"Found {len(source_items)} TV items in source feed JSON files")

    existing = load_existing_items(output_path)

    if not source_items and not existing:
        print(
            "No TV broadcast items found "
            "(titles ending in TV{YYYYMMDD}, or WMI TV Broadcast History channel).",
            file=sys.stderr,
        )
        return 1

    if source_items and existing:
        source_items = merge_scraped_with_existing(source_items, existing)
        items = merge_fresh_into_accumulated(source_items, existing)
    elif source_items:
        items = source_items
    else:
        items = dicts_to_tv_feed_items(existing)

    items = filter_tv_items(items)

    if not items:
        print("No TV broadcast items remain after filtering.", file=sys.stderr)
        return 1

    if args.enrich_channel_details:
        channel_cache = load_channel_cache(output_path)
        items = enrich_channel_details(
            items,
            limit=100000,
            delay=max(0, args.delay),
            verbose=args.verbose,
            channel_cache=channel_cache,
        )

    write_tv_feed(output_path, items)
    print(f"Wrote {len(items)} TV items to {output_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())