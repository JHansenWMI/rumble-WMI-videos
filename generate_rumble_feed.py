#!/usr/bin/env python3
"""
Generate a FetchRSS-compatible JSON feed from Rumble channel pages.

The CMS snippet currently expects:
  {
    "items": [
      {
        "title": "...",
        "link": "...",
        "pubDate": "...",
        "media:content": "..."
      }
    ]
  }
"""

from __future__ import annotations

import argparse
import importlib.util
import json
import re
import sys
import time
from dataclasses import dataclass
from datetime import datetime
from email.utils import format_datetime
from html import unescape
from pathlib import Path
from typing import Iterable
from urllib.error import HTTPError, URLError
from urllib.parse import parse_qsl, urlencode, urljoin, urlparse, urlunparse
from urllib.request import Request, urlopen


RUMBLE_BASE = "https://rumble.com"
DEFAULT_OUTPUT = "docs/rumble-feed.json"
DEFAULT_URLS = [
    "https://rumble.com/c/WarningTVJonathanHansen/videos",
    "https://rumble.com/c/WarningTVJonathanHansen/shorts",
    "https://rumble.com/c/WarningTVJonathanHansen/livestreams",
]


CARD_RE = re.compile(
    r'<div\s+[^>]*class="[^"]*\bvideostream\b[^"]*"[^>]*data-video-id="(?P<id>\d+)"[^>]*>'
    r"(?P<body>.*?)"
    r'(?=<div\s+[^>]*class="[^"]*\bvideostream\b[^"]*"[^>]*data-video-id="|\n\s*</section>|\n\s*<nav|\n\s*</main>)',
    re.DOTALL | re.IGNORECASE,
)


@dataclass(frozen=True)
class FeedItem:
    title: str
    link: str
    pub_date: str
    thumb: str
    source_page: str
    video_id: str
    timestamp: float

    def as_json(self) -> dict[str, str]:
        return {
            "title": self.title,
            "link": self.link,
            "pubDate": self.pub_date,
            "media:content": self.thumb,
            "guid": self.video_id,
            "sourcePage": self.source_page,
        }


def read_urls(path: Path) -> list[str]:
    urls: list[str] = []
    for raw_line in path.read_text(encoding="utf-8").splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#"):
            continue
        urls.append(line)
    return urls


def page_url(base_url: str, page: int) -> str:
    if page <= 1:
        return base_url

    parsed = urlparse(base_url)
    params = dict(parse_qsl(parsed.query, keep_blank_values=True))
    params["page"] = str(page)
    return urlunparse(parsed._replace(query=urlencode(params)))


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


def attr_value(fragment: str, attr: str) -> str:
    # Handles quoted attributes. Rumble currently uses quoted values for the fields we need.
    match = re.search(rf'\b{re.escape(attr)}\s*=\s*(["\'])(.*?)\1', fragment, re.DOTALL)
    return unescape(match.group(2)).strip() if match else ""


def clean_text(value: str) -> str:
    return re.sub(r"\s+", " ", unescape(value)).strip()


def clean_link(raw_link: str) -> str:
    absolute = urljoin(RUMBLE_BASE, raw_link)
    parsed = urlparse(absolute)
    # Rumble appends tracking query params such as e9s. The plain URL is cleaner for a public feed.
    return urlunparse(parsed._replace(query="", fragment=""))


def parse_datetime(value: str) -> tuple[str, float]:
    if not value:
        return "", float("-inf")

    try:
        dt = datetime.fromisoformat(value)
    except ValueError:
        return value, float("-inf")

    return format_datetime(dt), dt.timestamp()


def extract_first(pattern: str, text: str) -> str:
    match = re.search(pattern, text, re.DOTALL | re.IGNORECASE)
    return match.group(1) if match else ""


def parse_items(html: str, source_page: str) -> list[FeedItem]:
    items: list[FeedItem] = []

    for card in CARD_RE.finditer(html):
        video_id = card.group("id")
        body = card.group("body")

        img_tag = extract_first(r"(<img\b[^>]*\bclass=\"[^\"]*\bthumbnail__image\b[^\"]*\"[^>]*>)", body)
        title_tag = extract_first(r"(<h3\b[^>]*\bclass=\"[^\"]*\bthumbnail__title\b[^\"]*\"[^>]*>)", body)
        link_tag = extract_first(r"(<a\b[^>]*\bclass=\"[^\"]*\btitle__link\b[^\"]*\"[^>]*>)", body)
        time_tag = extract_first(r"(<time\b[^>]*\bdatetime=\"[^\"]+\"[^>]*>)", body)

        title = clean_text(attr_value(title_tag, "title") or attr_value(img_tag, "alt"))
        link = clean_link(attr_value(link_tag, "href"))
        thumb = attr_value(img_tag, "src")
        pub_date, timestamp = parse_datetime(attr_value(time_tag, "datetime"))

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

    return items


def unique_by_link(items: Iterable[FeedItem]) -> list[FeedItem]:
    seen: set[str] = set()
    unique: list[FeedItem] = []
    for item in items:
        key = item.link
        if key in seen:
            continue
        seen.add(key)
        unique.append(item)
    return unique


def build_feed(urls: list[str], max_pages: int, delay: float, verbose: bool) -> list[FeedItem]:
    all_items: list[FeedItem] = []

    for base_url in urls:
        for page in range(1, max_pages + 1):
            url = page_url(base_url, page)
            if verbose:
                print(f"Fetching {url}", file=sys.stderr)

            try:
                html = fetch_html(url)
            except (HTTPError, URLError, TimeoutError) as exc:
                print(f"Warning: failed to fetch {url}: {exc}", file=sys.stderr)
                break

            items = parse_items(html, base_url)
            if verbose:
                print(f"  found {len(items)} items", file=sys.stderr)

            if not items:
                break

            all_items.extend(items)
            if delay and page != max_pages:
                time.sleep(delay)

    unique = unique_by_link(all_items)
    unique.sort(key=lambda item: item.timestamp, reverse=True)
    return unique


def load_custom_update_hook():
    hook_path = Path(__file__).with_name("custom_update.py")
    if not hook_path.exists():
        return None

    spec = importlib.util.spec_from_file_location("custom_update", hook_path)
    if spec is None or spec.loader is None:
        return None

    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return getattr(module, "apply_custom_updates", None)


def write_feed(path: Path, items: list[FeedItem], limit: int) -> None:
    selected = items[:limit]
    payload = {
        "title": "Rumble videos",
        "generatedAt": format_datetime(datetime.now().astimezone()),
        "itemCount": len(selected),
        "items": [item.as_json() for item in selected],
    }
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Generate JSON from Rumble channel pages.")
    parser.add_argument("--input", help="Optional URL list file. If omitted, built-in Rumble URLs are used.")
    parser.add_argument("--output", default=DEFAULT_OUTPUT, help=f"JSON output file. Default: {DEFAULT_OUTPUT!r}")
    parser.add_argument("--limit", type=int, default=30, help="Number of feed items to write. Default: 30")
    parser.add_argument("--pages", type=int, default=2, help="Pages to fetch per Rumble URL. Default: 2")
    parser.add_argument("--delay", type=float, default=0.5, help="Delay between pages for the same URL. Default: 0.5")
    parser.add_argument("--verbose", action="store_true", help="Print fetch progress.")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    print(f"[{datetime.now().isoformat()}] Starting rumble feed generation")
    output_path = Path(args.output)

    if args.input:
        input_path = Path(args.input)
        if not input_path.exists():
            print(f"Input file not found: {input_path}", file=sys.stderr)
            return 2
        urls = read_urls(input_path)
    else:
        urls = DEFAULT_URLS

    if not urls:
        print("No Rumble URLs configured.", file=sys.stderr)
        return 2

    items = build_feed(urls, max_pages=max(1, args.pages), delay=max(0, args.delay), verbose=args.verbose)
    if not items:
        print("No Rumble items found. Rumble may have changed its page HTML.", file=sys.stderr)
        return 1

    custom_update = load_custom_update_hook()
    if custom_update:
        items = custom_update(items, parse_datetime)

    write_feed(output_path, items, limit=max(1, args.limit))
    print(f"Wrote {min(len(items), args.limit)} items to {output_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
