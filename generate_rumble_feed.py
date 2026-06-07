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
import os
import random
import re
import sys
import time
from dataclasses import dataclass
from dataclasses import replace
from datetime import datetime, timezone
from email.utils import format_datetime, parsedate_to_datetime
from html import unescape
from pathlib import Path
from typing import Iterable
from urllib.error import HTTPError, URLError
from urllib.parse import parse_qsl, urlencode, urljoin, urlparse, urlunparse
from urllib.request import Request, urlopen


RUMBLE_BASE = "https://rumble.com"
DEFAULT_OUTPUT = "docs/rumble-feed.json"
DEFAULT_URLS = [
    "https://rumble.com/user/DrJonathanHansenWMI/videos",
    "https://rumble.com/user/DrJonathanHansenWMI/shorts",
    "https://rumble.com/user/DrJonathanHansenWMI/livestreams",
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
    channel_name: str = ""
    channel_url: str = ""

    def as_json(self) -> dict[str, str]:
        item = {
            "title": self.title,
            "link": self.link,
            "pubDate": self.pub_date,
            "media:content": self.thumb,
            "guid": self.video_id,
            "sourcePage": self.source_page,
        }
        if self.channel_name:
            item["channelName"] = self.channel_name
        if self.channel_url:
            item["channelUrl"] = self.channel_url
        return item


@dataclass(frozen=True)
class ChannelInfo:
    name: str = ""
    url: str = ""


@dataclass(frozen=True)
class RumbleSource:
    url: str
    pages: int = 1


def parse_source_line(line: str, line_number: int) -> RumbleSource | None:
    content = line.split("#", 1)[0].strip()
    if not content:
        return None

    parts = content.split()
    url = parts[0]
    pages = 1

    for part in parts[1:]:
        key, separator, value = part.partition("=")
        if separator and key.lower() in {"page", "pages"}:
            try:
                pages = max(1, int(value))
            except ValueError:
                print(f"Warning: invalid pages value on line {line_number}: {part}", file=sys.stderr)

    return RumbleSource(url=url, pages=pages)


def read_urls(path: Path) -> list[RumbleSource]:
    urls: list[RumbleSource] = []
    for line_number, raw_line in enumerate(path.read_text(encoding="utf-8").splitlines(), start=1):
        source = parse_source_line(raw_line, line_number)
        if source:
            urls.append(source)
    return urls


def default_sources() -> list[RumbleSource]:
    return [RumbleSource(url=url) for url in DEFAULT_URLS]


def channel_cache_keys(link: str, video_id: str) -> list[str]:
    keys: list[str] = []
    if link:
        keys.append(f"link:{link}")
    if video_id:
        keys.append(f"guid:{video_id}")
    return keys


def load_channel_cache(path: Path) -> dict[str, ChannelInfo]:
    if not path.exists():
        return {}

    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        print(f"Warning: failed to read channel cache from {path}: {exc}", file=sys.stderr)
        return {}

    cache: dict[str, ChannelInfo] = {}
    for item in payload.get("items", []):
        if not isinstance(item, dict):
            continue

        raw_channel_url = str(item.get("channelUrl") or "")
        channel = ChannelInfo(
            name=clean_text(str(item.get("channelName") or "")),
            url=clean_link(raw_channel_url) if raw_channel_url else "",
        )
        if not channel.name and not channel.url:
            continue

        for key in channel_cache_keys(str(item.get("link") or ""), str(item.get("guid") or "")):
            cache[key] = channel

    return cache


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
    """Return RFC 2822 pubDate and epoch seconds, always normalized to UTC (+0000)."""
    if not value:
        return "", float("-inf")

    dt: datetime | None = None
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


def extract_first(pattern: str, text: str) -> str:
    match = re.search(pattern, text, re.DOTALL | re.IGNORECASE)
    return match.group(1) if match else ""


def polite_sleep(delay: float) -> None:
    if delay <= 0:
        return

    time.sleep(delay * random.uniform(0.75, 1.25))


def parse_embedded_listing_items(html: str, source_page: str) -> list[FeedItem]:
    """Parse video cards from Rumble's embedded listing JSON (replaces videostream HTML)."""
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

            channel_name = ""
            channel_url = ""
            by = entry.get("by")
            if isinstance(by, dict) and by.get("type") == "channel":
                channel_name = clean_text(str(by.get("name") or by.get("title") or ""))
                raw_channel_url = str(by.get("url") or by.get("relative_url") or "")
                channel_url = clean_link(raw_channel_url) if raw_channel_url else ""

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
                    channel_name=channel_name,
                    channel_url=channel_url,
                )
            )

        if items:
            return items

    return items


def parse_embedded_channel_info(html: str) -> ChannelInfo:
    decoder = json.JSONDecoder()

    for match in re.finditer(r'"by"\s*:\s*{', html):
        object_start = html.find("{", match.start())
        if object_start == -1:
            continue

        try:
            payload, _ = decoder.raw_decode(html[object_start:])
        except json.JSONDecodeError:
            continue

        if not isinstance(payload, dict) or payload.get("type") != "channel":
            continue

        name = clean_text(str(payload.get("name") or payload.get("title") or ""))
        raw_url = str(payload.get("url") or payload.get("relative_url") or "")
        url = clean_link(raw_url) if raw_url else ""
        if name or url:
            return ChannelInfo(name=name, url=url)

    return ChannelInfo()


def parse_channel_info(html: str) -> ChannelInfo:
    container = extract_first(
        r'(<div\b[^>]*\bdata-js="media_channel_container"[^>]*>.*?</a>\s*</div>)',
        html,
    )
    if not container:
        return parse_embedded_channel_info(html)

    link_tag = extract_first(r'(<a\b[^>]*\bclass="[^"]*\bmedia-by--a\b[^"]*"[^>]*>)', container)
    name = clean_text(
        extract_first(
            r'<div\b[^>]*\bclass="[^"]*\bmedia-heading-name\b[^"]*\btruncate\b[^"]*"[^>]*>(.*?)</div>',
            container,
        )
    )
    url = clean_link(attr_value(link_tag, "href"))
    return ChannelInfo(name=name, url=url)


def parse_items(html: str, source_page: str) -> list[FeedItem]:
    embedded = parse_embedded_listing_items(html, source_page)
    if embedded:
        return embedded

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


def cached_channel_info(cache: dict[str, ChannelInfo], item: FeedItem) -> ChannelInfo | None:
    for key in channel_cache_keys(item.link, item.video_id):
        channel = cache.get(key)
        if channel:
            return channel
    return None


def cache_channel_info(cache: dict[str, ChannelInfo], item: FeedItem, channel: ChannelInfo) -> None:
    for key in channel_cache_keys(item.link, item.video_id):
        cache[key] = channel


def enrich_channel_details(
    items: list[FeedItem],
    limit: int,
    delay: float,
    verbose: bool,
    channel_cache: dict[str, ChannelInfo] | None = None,
) -> list[FeedItem]:
    enriched: list[FeedItem] = []
    channel_cache = dict(channel_cache or {})
    selected_count = min(len(items), limit)

    for index, item in enumerate(items):
        if index >= selected_count:
            enriched.append(item)
            continue

        if item.channel_name or item.channel_url:
            channel = ChannelInfo(name=item.channel_name, url=item.channel_url)
            if verbose:
                print(f"Using listing channel details for {item.link}", file=sys.stderr)
        elif cached_channel := cached_channel_info(channel_cache, item):
            channel = cached_channel
            if verbose:
                print(f"Reusing channel details for {item.link}", file=sys.stderr)
        else:
            polite_sleep(delay)
            if verbose:
                print(f"Fetching channel details for {item.link}", file=sys.stderr)

            try:
                channel = parse_channel_info(fetch_html(item.link))
            except (HTTPError, URLError, TimeoutError) as exc:
                print(f"Warning: failed to fetch channel details for {item.link}: {exc}", file=sys.stderr)
                channel = ChannelInfo()

            cache_channel_info(channel_cache, item, channel)

        enriched.append(replace(item, channel_name=channel.name, channel_url=channel.url))

    return enriched


def build_feed(urls: list[RumbleSource], max_pages: int, delay: float, verbose: bool) -> list[FeedItem]:
    all_items: list[FeedItem] = []
    request_count = 0

    for source in urls:
        source_pages = min(max_pages, source.pages)
        for page in range(1, source_pages + 1):
            if request_count:
                polite_sleep(delay)

            url = page_url(source.url, page)
            if verbose:
                print(f"Fetching {url}", file=sys.stderr)

            try:
                html = fetch_html(url)
            except (HTTPError, URLError, TimeoutError) as exc:
                print(f"Warning: failed to fetch {url}: {exc}", file=sys.stderr)
                break
            request_count += 1

            items = parse_items(html, source.url)
            if verbose:
                print(f"  found {len(items)} items", file=sys.stderr)

            if not items:
                break

            all_items.extend(items)

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
        "generatedAt": format_datetime(datetime.now(timezone.utc)),
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
    parser.add_argument(
        "--pages",
        type=int,
        default=100,
        help="Safety cap for pages per Rumble URL. URL list lines opt in with pages=N. Default: 100",
    )
    parser.add_argument(
        "--delay",
        type=float,
        default=2.0,
        help="Base delay between Rumble requests, with small jitter. Default: 2.0",
    )
    parser.add_argument(
        "--no-channel-details",
        action="store_true",
        help="Skip fetching each selected video page for channelName and channelUrl.",
    )
    parser.add_argument("--verbose", action="store_true", help="Print fetch progress.")
    parser.add_argument(
        "--test-html",
        metavar="PATH",
        help="Debug mode: load and parse this local HTML file (from a capture sample) instead of network fetches. Prints parsed count and first few items.",
    )
    parser.add_argument(
        "--test-source",
        default="https://rumble.com/user/DrJonathanHansenWMI/videos",
        help="source_page value to associate when using --test-html. Default matches main channel.",
    )
    parser.add_argument(
        "--compare-to-items",
        metavar="JSONPATH",
        help="With --test-html, also load this .items.json (from sample) and report how many of the expected items were successfully parsed.",
    )
    parser.add_argument(
        "--production",
        action="store_true",
        help="Force safe/production mode (default when RUMBLE_FEED_MODE is unset or 'production'). "
             "On parser failure, emit only a short message (no long dev/Grok instructions). "
             "Intended for scheduled runs on the production machine.",
    )
    return parser.parse_args()


def main() -> int:
    args = parse_args()

    if args.test_html:
        test_path = Path(args.test_html)
        if not test_path.exists():
            print(f"Test HTML not found: {test_path}", file=sys.stderr)
            return 2
        html = test_path.read_text(encoding="utf-8")
        source = args.test_source
        print(f"Testing parse on {test_path} (source={source})")
        items = parse_items(html, source)
        print(f"Parsed {len(items)} items")
        for i, item in enumerate(items[:5]):
            print(f"  {i+1}. {item.title[:60]}... | {item.pub_date} | {item.link[:50]}")
        if args.compare_to_items:
            cmp_path = Path(args.compare_to_items)
            try:
                expected = json.loads(cmp_path.read_text(encoding="utf-8"))
                exp_items = expected.get("items", []) if isinstance(expected, dict) else expected
                print(f"Sample lists {len(exp_items)} items in JSON")
                parsed_links = {it.link for it in items}
                matched = 0
                sample_titles = []
                for e in exp_items:
                    if not isinstance(e, dict):
                        continue
                    raw = str(e.get("url") or e.get("relative_url") or "")
                    elink = clean_link(raw) if raw else ""
                    etitle = clean_text(str(e.get("title") or ""))
                    sample_titles.append(etitle)
                    if elink and elink in parsed_links:
                        matched += 1
                    elif etitle and any(etitle[:30] in it.title or it.title[:30] in etitle for it in items):
                        matched += 1
                print(f"Matched ~{matched} / {len(exp_items)} expected items by link/title heuristic")
                if matched == 0 and len(items) > 0:
                    print("Note: parser found items but no overlap with sample json keys? Check structure.")
            except Exception as exc:
                print(f"Could not compare to {cmp_path}: {exc}", file=sys.stderr)
        return 0

    print(f"[{datetime.now().isoformat()}] Starting rumble feed generation")
    output_path = Path(args.output)

    if args.input:
        input_path = Path(args.input)
        if not input_path.exists():
            print(f"Input file not found: {input_path}", file=sys.stderr)
            return 2
        urls = read_urls(input_path)
    else:
        urls = default_sources()

    if not urls:
        print("No Rumble URLs configured.", file=sys.stderr)
        return 2

    items = build_feed(urls, max_pages=max(1, args.pages), delay=max(0, args.delay), verbose=args.verbose)
    if not items:
        print("No Rumble items found. Rumble may have changed its page HTML.", file=sys.stderr)

        is_prod = args.production or (os.environ.get("RUMBLE_FEED_MODE") or "production").lower() == "production"
        if is_prod:
            print(
                "Running in production/safe mode (default when RUMBLE_FEED_MODE is unset or 'production'). "
                "Auto-capture and full dev/Grok instructions are disabled. "
                "Perform sample capture + parser fix on your dev MacBook (set RUMBLE_FEED_MODE=development there). "
                "See samples/rumble-channel-pages/README.md.",
                file=sys.stderr,
            )
        else:
            print(
                """
ACTION REQUIRED: Rumble channel listing HTML appears to have changed.
The parser in generate_rumble_feed.py (parse_embedded_listing_items + fallback CARD_RE) returned zero items.

To gather evidence + fix:

1. A sample may have been auto-captured (check for new dirs in samples/rumble-channel-pages/auto-*-rumble-html-change/ committed by scheduled run or GH workflow).

   If not present, manually capture for the affected source URLs:
   python samples/capture_rumble_channel_page.py --iteration "$(date +%Y-%m-%d)-html-change" \
     --url https://rumble.com/user/DrJonathanHansenWMI/videos
   (Repeat for /shorts and /livestreams; also for overcoming c-*/videos etc if those feeds are affected.)

2. The new sample dir contains:
   - *.html (full page response)
   - capture-meta.json (marker counts e.g. videostream:0, embeddedItemsJson:true/false, item counts)
   - *.items.json (extracted listing data block, if the {"items": pattern still present)

3. Use the debug CLI (works offline) to confirm current parser behavior against the sample:
   python generate_rumble_feed.py --test-html samples/rumble-channel-pages/NEW-DIR/DrJonathanHansenWMI-videos.html \
     --test-source https://rumble.com/user/DrJonathanHansenWMI/videos \
     --compare-to-items samples/rumble-channel-pages/NEW-DIR/DrJonathanHansenWMI-videos.items.json
   (Expect low/zero match count until fixed. Also test against the previous good sample at 2026-06-04-... to ensure no regression.)

4. Trigger Grok to diagnose/fix/test + prepare for review:
   Run this tool in the /Users/fredchristian/dev/rumble-WMI-videos workspace (or equivalent) and provide:
   "Rumble parser error triggered again in generate_rumble_feed.py (the 'No Rumble items found. Rumble may have changed...' message).
   New sample captured at samples/rumble-channel-pages/auto-...-rumble-html-change/ (or your dated dir).
   Please:
   - Analyze the new .html (via grep with path= to the html file, or read_file + open_page_with_find) to locate the current video listing data (titles, dates, urls, ids, channel 'by' info).
   - Update parse_embedded_listing_items (primary path) and helpers like parse_embedded_channel_info / parse_items as needed to handle the new Rumble HTML/JSON shape.
   - Keep the old embedded JSON logic and CARD_RE fallback working for the 2026-06-04 sample (and any older).
   - Use the --test-html + --compare-to-items commands (for BOTH the new broken sample and the prior good sample) repeatedly to verify during editing that the fix extracts correct items from new format and still works on old.
   - Optionally improve robustness (e.g. more finditer patterns for json data).
   - After changes, run the test commands showing success on new sample, run `git diff -- generate_rumble_feed.py samples/capture_rumble_channel_page.py` if touched, and output a clear summary for the user.
   - End by telling the user the changes are ready for their review (do not auto-push code changes to main; let user decide on commit/PR)."

5. After Grok completes the edits and local verification, you (the user) review the diff and test output. If good, commit the parser fix (typically via PR or direct if small). Once the fixed generate_rumble_feed.py is on main, future scheduled runs (local launchd + GH) will succeed and feeds will update again.

Full context and prior change history is in samples/rumble-channel-pages/README.md and git log.
""",
                file=sys.stderr,
            )
        return 1

    custom_update = load_custom_update_hook()
    if custom_update:
        items = custom_update(items, parse_datetime)

    limit = max(1, args.limit)
    if not args.no_channel_details:
        channel_cache = load_channel_cache(output_path)
        items = enrich_channel_details(
            items,
            limit=limit,
            delay=max(0, args.delay),
            verbose=args.verbose,
            channel_cache=channel_cache,
        )

    write_feed(output_path, items, limit=limit)
    print(f"Wrote {min(len(items), args.limit)} items to {output_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
