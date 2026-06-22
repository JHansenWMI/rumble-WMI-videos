#!/usr/bin/env python3
"""
Temporary test script: list videos from a Rumble channel page, then fetch each
video's description from its detail page.

Does not modify the production feed pipeline. Output goes to a temp JSON file.
"""

from __future__ import annotations

import argparse
import json
import random
import re
import sys
import time
from dataclasses import dataclass
from datetime import datetime, timezone
from email.utils import format_datetime
from html import unescape
from pathlib import Path
from typing import Iterable
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

# Copied from generate_rumble_feed.py (listing + fetch helpers).
RUMBLE_BASE = "https://rumble.com"
DEFAULT_CHANNEL_URL = "https://rumble.com/user/DrJonathanHansenWMI/videos"
DEFAULT_OUTPUT = "temp-video-descriptions-test.json"


@dataclass(frozen=True)
class FeedItem:
    title: str
    link: str
    pub_date: str
    thumb: str
    source_page: str
    video_id: str
    timestamp: float


def clean_text(value: str) -> str:
    return re.sub(r"\s+", " ", unescape(value)).strip()


def clean_link(raw_link: str) -> str:
    from urllib.parse import urlparse, urlunparse
    from urllib.parse import urljoin

    absolute = urljoin(RUMBLE_BASE, raw_link)
    parsed = urlparse(absolute)
    return urlunparse(parsed._replace(query="", fragment=""))


def fetch_html(url: str, timeout: int = 30) -> str:
    req = Request(
        url,
        headers={
            "User-Agent": (
                "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
                "AppleWebKit/537.36 (KHTML, like Gecko) "
                "Chrome/124.0 Safari/537.36"
            ),
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
        },
    )
    with urlopen(req, timeout=timeout) as response:
        charset = response.headers.get_content_charset() or "utf-8"
        return response.read().decode(charset, errors="replace")


def parse_datetime(value: str) -> tuple[str, float]:
    from email.utils import parsedate_to_datetime

    if not value:
        return "", float("-inf")

    dt = None
    try:
        dt = datetime.fromisoformat(value)
    except ValueError:
        try:
            dt = parsedate_to_datetime(value)
        except (TypeError, ValueError):
            return value, float("-inf")

    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)

    utc = dt.astimezone(timezone.utc)
    return format_datetime(utc), utc.timestamp()


def parse_embedded_listing_items(html: str, source_page: str) -> list[FeedItem]:
    items: list[FeedItem] = []
    decoder = json.JSONDecoder()

    for match in re.finditer(r'\{"items":\[', html):
        try:
            payload, _ = decoder.raw_decode(html[match.start():])
        except json.JSONDecodeError:
            continue

        if not isinstance(payload, dict):
            continue

        for entry in payload.get("items", []):
            if not isinstance(entry, dict):
                continue

            object_type = entry.get("object_type")
            if object_type and object_type != "video":
                continue

            title = clean_text(str(entry.get("title") or ""))
            raw_url = str(entry.get("url") or entry.get("relative_url") or "")
            link = clean_link(raw_url) if raw_url else ""
            thumb = str(entry.get("thumb") or "")
            video_id = str(entry.get("id") or "")
            pub_date, timestamp = parse_datetime(str(entry.get("upload_date") or ""))

            if not title or not link or not pub_date:
                continue

            items.append(
                FeedItem(
                    title=title,
                    link=link,
                    pub_date=pub_date,
                    thumb=thumb,
                    source_page=source_page,
                    video_id=video_id,
                    timestamp=timestamp,
                )
            )

        if items:
            return items

    return items


def unique_by_link(items: Iterable[FeedItem]) -> list[FeedItem]:
    seen: set[str] = set()
    unique: list[FeedItem] = []
    for item in items:
        if item.link in seen:
            continue
        seen.add(item.link)
        unique.append(item)
    return unique


def polite_sleep(delay: float) -> None:
    if delay <= 0:
        return
    time.sleep(delay * random.uniform(0.75, 1.25))


def strip_html(fragment: str) -> str:
    text = re.sub(r"<br\s*/?>", "\n", fragment, flags=re.IGNORECASE)
    text = re.sub(r"</p\s*>", "\n", text, flags=re.IGNORECASE)
    text = re.sub(r"<[^>]+>", " ", text)
    return clean_text(text)


def parse_video_description(html: str) -> dict[str, str]:
    """Extract description from a Rumble video detail page."""
    parts: list[str] = []

    for class_name in ("media-description--first", "media-description--more"):
        for match in re.finditer(
            rf'<p\b[^>]*\bclass="[^"]*\b{re.escape(class_name)}\b[^"]*"[^>]*>(.*?)</p>',
            html,
            re.DOTALL | re.IGNORECASE,
        ):
            text = strip_html(match.group(1))
            if text:
                parts.append(text)

    full_description = "\n\n".join(parts)

    schema_description = ""
    for script_match in re.finditer(
        r'<script[^>]*type=application/ld\+json[^>]*>(.*?)</script>',
        html,
        re.DOTALL | re.IGNORECASE,
    ):
        try:
            payload = json.loads(script_match.group(1))
        except json.JSONDecodeError:
            continue

        entries = payload if isinstance(payload, list) else [payload]
        for entry in entries:
            if isinstance(entry, dict) and entry.get("@type") == "VideoObject":
                schema_description = clean_text(str(entry.get("description") or ""))
                break
        if schema_description:
            break

    return {
        "description": full_description,
        "descriptionSchema": schema_description,
        "descriptionSource": "html" if full_description else ("schema.org" if schema_description else ""),
    }


def build_listing(channel_url: str, verbose: bool) -> list[FeedItem]:
    if verbose:
        print(f"Fetching listing: {channel_url}", file=sys.stderr)

    html = fetch_html(channel_url)
    items = parse_embedded_listing_items(html, channel_url)
    unique = unique_by_link(items)
    unique.sort(key=lambda item: item.timestamp, reverse=True)
    return unique


def enrich_with_descriptions(
    items: list[FeedItem],
    limit: int,
    delay: float,
    verbose: bool,
) -> list[dict]:
    results: list[dict] = []

    for index, item in enumerate(items[:limit]):
        if index:
            polite_sleep(delay)

        if verbose:
            print(f"Fetching description for {item.link}", file=sys.stderr)

        record = {
            "title": item.title,
            "link": item.link,
            "videoId": item.video_id,
            "pubDate": item.pub_date,
            "thumb": item.thumb,
            "description": "",
            "descriptionSchema": "",
            "descriptionSource": "",
            "descriptionError": "",
        }

        try:
            detail_html = fetch_html(item.link)
            description_info = parse_video_description(detail_html)
            record.update(description_info)
        except (HTTPError, URLError, TimeoutError) as exc:
            record["descriptionError"] = f"{type(exc).__name__}: {exc}"

        results.append(record)

    return results


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Test fetching Rumble video descriptions after listing a channel page."
    )
    parser.add_argument(
        "--url",
        default=DEFAULT_CHANNEL_URL,
        help=f"Rumble channel listing URL. Default: {DEFAULT_CHANNEL_URL!r}",
    )
    parser.add_argument(
        "--output",
        default=DEFAULT_OUTPUT,
        help=f"Temp JSON output file. Default: {DEFAULT_OUTPUT!r}",
    )
    parser.add_argument(
        "--limit",
        type=int,
        default=5,
        help="Number of videos to fetch descriptions for. Default: 5",
    )
    parser.add_argument(
        "--delay",
        type=float,
        default=2.0,
        help="Base delay between detail-page requests, with jitter. Default: 2.0",
    )
    parser.add_argument("--verbose", action="store_true", help="Print fetch progress.")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    limit = max(1, args.limit)

    try:
        listing = build_listing(args.url, verbose=args.verbose)
    except (HTTPError, URLError, TimeoutError) as exc:
        print(f"Failed to fetch listing page: {type(exc).__name__}: {exc}", file=sys.stderr)
        return 1

    if not listing:
        print("No videos found on listing page.", file=sys.stderr)
        return 1

    if args.verbose:
        print(f"Found {len(listing)} videos on listing page; fetching {limit} descriptions", file=sys.stderr)

    enriched = enrich_with_descriptions(
        listing,
        limit=limit,
        delay=max(0, args.delay),
        verbose=args.verbose,
    )

    with_description = sum(1 for item in enriched if item["description"] or item["descriptionSchema"])
    payload = {
        "generatedAt": format_datetime(datetime.now(timezone.utc)),
        "sourcePage": args.url,
        "listingCount": len(listing),
        "fetchedCount": len(enriched),
        "withDescriptionCount": with_description,
        "items": enriched,
    }

    output_path = Path(args.output)
    output_path.write_text(json.dumps(payload, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")

    print(
        f"Wrote {len(enriched)} items to {output_path} "
        f"({with_description} with a description)"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())