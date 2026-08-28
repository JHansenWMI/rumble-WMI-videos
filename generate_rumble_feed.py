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
import subprocess
import sys
import time
from dataclasses import dataclass
from dataclasses import replace
from datetime import datetime, timezone
from email.utils import format_datetime, parsedate_to_datetime
from zoneinfo import ZoneInfo
from html import unescape
from pathlib import Path
from typing import Iterable
from urllib.error import HTTPError, URLError
from urllib.parse import parse_qsl, quote, urlencode, urljoin, urlparse, urlunparse
from urllib.request import Request, urlopen


RUMBLE_BASE = "https://rumble.com"
PACIFIC = ZoneInfo("America/Los_Angeles")
DEFAULT_OUTPUT = "docs/rumble-feed.json"
DEFAULT_URLS = [
    "https://rumble.com/user/DrJonathanHansenWMI/videos",
    "https://rumble.com/user/DrJonathanHansenWMI/shorts",
    "https://rumble.com/user/DrJonathanHansenWMI/livestreams",
]

PRIMARY_FEED_FILES = [
    "docs/rumble-feed.json",
    "docs/overcoming-feed.json",
]

OVERCOMING_CHANNEL_NAME = "The Overcoming Women"
OVERCOMING_CHANNEL_SLUG = "c-7899090"
RUMBLE_CHANNEL_HINT_FILES = [
    "docs/rumble-feed.json",
    "docs/rumble-feed-archive.json",
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
    video_code: str = ""  # slug from list page (e.g. v7bokoc in URL)
    video_embed_id: str = ""  # embed player id (e.g. v79hwo4) from detail page only
    scheduled_time: str = ""  # premiere/livestream start (Rumble live_datetime)

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
        if self.video_embed_id:
            item["videoId"] = self.video_embed_id
        elif self.video_code and "/shorts/" not in (self.link or ""):
            # List-page slug is not a valid embed id for shorts (embed/v… returns 410).
            item["videoId"] = self.video_code  # fallback during transition
        if self.scheduled_time:
            item["scheduledTime"] = self.scheduled_time
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


def load_existing_items(path: Path) -> list[dict]:
    """Load items from prior feed JSON.

    Used for:
    - Carrying video_embed_id (and similar) into freshly scraped items.
    - Accumulating historical items so past data is not discarded on periodic runs.
    """
    if not path.exists():
        return []
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
        items = payload.get("items", []) if isinstance(payload, dict) else []
        return [i for i in items if isinstance(i, dict)]
    except Exception as exc:
        print(f"Warning: failed to read existing feed from {path}: {exc}", file=sys.stderr)
        return []


def merge_scraped_with_existing(scraped: list[FeedItem], existing: list[dict]) -> list[FeedItem]:
    """Carry forward embed ids etc from prior run into the current fresh scrape results.
    (Used as part of the accumulation flow for periodic scrapers.)
    """
    prev_by_link: dict[str, dict] = {}
    for e in existing:
        lnk = e.get("link")
        if lnk:
            prev_by_link[lnk] = e
    result: list[FeedItem] = []
    for s in scraped:
        e = prev_by_link.get(s.link)
        embed_id = s.video_embed_id
        slug = s.video_code
        if e:
            # carry prior embed id if current scrape didn't provide one
            if not embed_id:
                embed_id = e.get("videoId") or ""
            # bootstrap fix: if carried value == the list slug, it was the old non-embed id; clear to force detail fetch
            if embed_id and slug and embed_id == slug:
                embed_id = ""
        result.append(
            replace(s, video_embed_id=embed_id) if embed_id else s
        )
    return result


def _dict_to_feeditem(d: dict) -> FeedItem | None:
    """Reconstruct a minimal FeedItem from a previously written JSON item dict.
    Used when accumulating older history items that are no longer on the current page 1.
    """
    try:
        link = clean_link(str(d.get("link") or ""))
        pub_date = str(d.get("pubDate") or "")
        _, timestamp = parse_datetime(pub_date)
        if timestamp == float("-inf"):
            timestamp = 0.0

        video_code = ""
        if link:
            m = re.search(r"/(v[a-z0-9]+)-", link)
            if m:
                video_code = m.group(1)

        channel_url = ""
        raw_ch_url = d.get("channelUrl")
        if raw_ch_url:
            channel_url = clean_link(str(raw_ch_url))

        scheduled_time = str(d.get("scheduledTime") or "")
        if scheduled_time:
            scheduled_time, _ = parse_datetime(scheduled_time)

        return FeedItem(
            title=clean_text(str(d.get("title") or "")),
            link=link,
            pub_date=pub_date,
            thumb=str(d.get("media:content") or ""),
            source_page=str(d.get("sourcePage") or ""),
            video_id=str(d.get("guid") or ""),
            timestamp=timestamp,
            channel_name=clean_text(str(d.get("channelName") or "")),
            channel_url=channel_url,
            video_code=video_code,
            video_embed_id=str(d.get("videoId") or ""),
            scheduled_time=scheduled_time,
        )
    except Exception as exc:
        print(f"Warning: failed to reconstruct item from previous JSON: {exc}", file=sys.stderr)
        return None


def merge_fresh_into_accumulated(fresh: list[FeedItem], previous: list[dict]) -> list[FeedItem]:
    """Accumulate history for the feed JSONs.

    - Keep all previous items (history).
    - Add any newly discovered items from the current scrape.
    - Prefer data from the fresh scrape for any overlapping items.
    - Re-sort by timestamp desc (newest first).
    This is used by periodic runs so we don't discard older videos.
    """
    prev_by_link: dict[str, dict] = {}
    for e in previous:
        lnk = e.get("link")
        if lnk:
            prev_by_link[lnk] = e

    seen: set[str] = set()
    result: list[FeedItem] = []

    # Fresh items first (these are the current newest from page 1)
    for item in fresh:
        if item.link and item.link not in seen:
            seen.add(item.link)
            result.append(item)

    # Add older history items that are no longer present in the latest scrape
    for e in previous:
        link = e.get("link")
        if link and link not in seen:
            seen.add(link)
            reconstructed = _dict_to_feeditem(e)
            if reconstructed:
                result.append(reconstructed)

    result.sort(key=lambda x: x.timestamp, reverse=True)
    return result


def is_overcoming_feed_path(path: Path) -> bool:
    return Path(path).name == "overcoming-feed.json"


def is_overcoming_channel(name: str = "", url: str = "") -> bool:
    if str(name or "").strip().casefold() == OVERCOMING_CHANNEL_NAME.casefold():
        return True
    return OVERCOMING_CHANNEL_SLUG in str(url or "").casefold()


def load_rumble_channel_hints() -> dict[str, ChannelInfo]:
    """Channel names from the main rumble feed (generated earlier in the same publish run)."""
    hints: dict[str, ChannelInfo] = {}
    for raw in RUMBLE_CHANNEL_HINT_FILES:
        path = Path(raw)
        if path.exists():
            hints.update(load_channel_cache(path))
    return hints


def prune_recategorized_overcoming_items(
    items: list[FeedItem],
    fresh_links: set[str],
    *,
    channel_hints: dict[str, ChannelInfo] | None = None,
    fetch_missing: bool = True,
    delay: float = 2.0,
) -> list[FeedItem]:
    """Drop Overcoming history that now belongs to another Rumble channel.

    Items still on this run's Overcoming listing pages stay. History-only
    items are checked against rumble-feed channel fields, then the video
    page if needed. A failed fetch keeps the item. Recategorized videos
    are not archived.
    """
    hints = dict(channel_hints or {})
    kept: list[FeedItem] = []
    for item in items:
        if item.link in fresh_links:
            kept.append(item)
            continue

        channel = cached_channel_info(hints, item)
        if channel is None and fetch_missing and item.link:
            try:
                polite_sleep(delay)
                channel = parse_channel_info(fetch_html(item.link))
            except (HTTPError, URLError, TimeoutError, OSError) as exc:
                print(f"Warning: could not recheck channel for {item.link}: {exc}", file=sys.stderr)
                kept.append(item)
                continue
            if channel and (channel.name or channel.url):
                cache_channel_info(hints, item, channel)

        if channel and (channel.name or channel.url) and not is_overcoming_channel(
            channel.name, channel.url
        ):
            print(
                f"Pruned recategorized video from overcoming feed: {item.title} "
                f"(now {channel.name or channel.url})",
                file=sys.stderr,
            )
            continue

        kept.append(item)
    return kept


def get_archive_path(path: Path) -> Path:
    if path.stem.endswith("-archive"):
        return path
    return path.with_name(f"{path.stem}-archive{path.suffix}")


def load_archive(path: Path) -> list[dict]:
    if not path.exists():
        return []
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
        return data.get("items", []) if isinstance(data, dict) else []
    except Exception as exc:
        print(f"Warning: failed to load archive {path}: {exc}", file=sys.stderr)
        return []


def save_archive(path: Path, items: list[dict]) -> None:
    payload = {
        "title": "Rumble videos (archive)",
        **feed_timestamps(),
        "itemCount": len(items),
        "items": items,
    }
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")


def archive_excess(items: list[FeedItem], output_path: Path, limit: int) -> list[FeedItem]:
    """If the accumulated list exceeds the active limit, move the excess older items
    (the tail) into the corresponding archive JSON. Returns the capped active list.
    This is the archive feature to prevent the main feed JSONs from growing unbounded.
    """
    if len(items) <= limit:
        return items

    main_items = items[:limit]
    excess = items[limit:]

    arch_path = get_archive_path(output_path)
    existing = load_archive(arch_path)
    seen = {it.get("link") for it in existing if it.get("link")}

    previous_by_link = previous_items_by_link(output_path)
    now_utc = datetime.now(timezone.utc)

    to_add: list[dict] = []
    for it in excess:
        d = stamp_item_json(it, previous_by_link.get(it.link), now_utc)
        lnk = d.get("link")
        if lnk and lnk not in seen:
            to_add.append(d)
            seen.add(lnk)

    if to_add:
        combined = existing + to_add
        combined.sort(key=lambda x: x.get("pubDate", ""), reverse=True)
        save_archive(arch_path, combined)
        print(f"Archived {len(to_add)} older items to {arch_path.name} (archive now {len(combined)})")

    return main_items


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


def format_pacific_updated(dt: datetime | None = None) -> str:
    """Human-readable Pacific time with PDT or PST."""
    if dt is None:
        dt = datetime.now(timezone.utc)
    elif dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    return dt.astimezone(PACIFIC).strftime("%Y-%m-%d %H:%M:%S %Z")


def parse_pacific_updated(s: str) -> datetime:
    """Parse strings produced by format_pacific_updated, e.g. '2026-07-02 08:56:36 PDT'."""
    if not s:
        raise ValueError("empty pacific updated string")
    s = s.strip()
    if s.endswith(" PDT") or s.endswith(" PST"):
        core = s[:-4].strip()
    else:
        core = s
    dt_naive = datetime.strptime(core, "%Y-%m-%d %H:%M:%S")
    return dt_naive.replace(tzinfo=PACIFIC)


def item_identity_keys(items: list) -> set[tuple[str, str]]:
    """Stable item identities for add/remove detection (guid and/or link)."""
    keys: set[tuple[str, str]] = set()
    for it in items:
        if not isinstance(it, dict):
            continue
        guid = str(it.get("guid") or "").strip()
        if guid:
            keys.add(("guid", guid))
        link = str(it.get("link") or "").strip()
        if link:
            keys.add(("link", link))
    return keys


def committed_feed_items(path: Path) -> list[dict] | None:
    """Items array from HEAD for this feed file, or None if it cannot be read."""
    try:
        rel = path.as_posix()
        if path.is_absolute():
            root = subprocess.check_output(
                ["git", "rev-parse", "--show-toplevel"],
                text=True,
                stderr=subprocess.DEVNULL,
            ).strip()
            rel = Path(path).resolve().relative_to(Path(root)).as_posix()
        out = subprocess.check_output(
            ["git", "show", f"HEAD:{rel}"],
            text=True,
            stderr=subprocess.DEVNULL,
        )
        data = json.loads(out)
        return data.get("items", []) if isinstance(data, dict) else []
    except Exception:
        return None


def feed_has_meaningful_change(path: str | Path) -> bool:
    """True if generated feed content warrants a commit + push.

    Detects:
    - items added or removed (guid/link set vs HEAD)
    - any per-item 'updated' newer than the file's last git commit

    Used by publish_rumble_feed.sh. Top-level generatedAt/updated alone is not enough.
    """
    p = Path(path)
    if not p.exists():
        return False

    # Last commit time for this specific path (committer date, ISO).
    try:
        out = subprocess.check_output(
            ["git", "log", "-1", "--format=%cI", "--", str(p)],
            text=True,
            stderr=subprocess.DEVNULL,
        ).strip()
        if out:
            last_commit = datetime.fromisoformat(out.replace("Z", "+00:00"))
        else:
            last_commit = datetime.min.replace(tzinfo=timezone.utc)
    except Exception:
        return True  # untracked / git error → treat as worth committing

    try:
        data = json.loads(p.read_text(encoding="utf-8"))
    except Exception:
        return True

    items = data.get("items", []) if isinstance(data, dict) else []
    committed = committed_feed_items(p)
    if committed is None:
        return True
    if item_identity_keys(items) != item_identity_keys(committed):
        return True

    for it in items:
        if not isinstance(it, dict):
            continue
        u = it.get("updated")
        if not u:
            continue
        try:
            item_dt = parse_pacific_updated(u)
            if item_dt.timestamp() > last_commit.timestamp():
                return True
        except Exception:
            # Unparseable updated on an item → conservative
            return True

    return False


def feed_timestamps() -> dict[str, str]:
    now_utc = datetime.now(timezone.utc)
    return {
        "generatedAt": format_datetime(now_utc),
        "updated": format_pacific_updated(now_utc),
    }


def previous_items_by_link(path: Path) -> dict[str, dict]:
    return {
        link: item
        for item in load_existing_items(path)
        if (link := item.get("link"))
    }


def stamp_item_json(item: FeedItem, previous: dict | None, now_utc: datetime) -> dict[str, str]:
    """Attach per-item updated timestamp in Pacific time.

    New items and changed items get the current time; unchanged items keep their prior value.
    """
    current = item.as_json()
    if previous is None:
        current["updated"] = format_pacific_updated(now_utc)
        return current

    previous_body = {key: value for key, value in previous.items() if key != "updated"}
    if previous_body == current:
        if previous.get("updated"):
            current["updated"] = previous["updated"]
        return current

    current["updated"] = format_pacific_updated(now_utc)
    return current


def listing_scheduled_time(entry: dict) -> str:
    """Premiere/livestream start from Rumble listing JSON, if present.

    Upcoming premieres set live_datetime (ISO UTC) and often livestream_status=1
    with live_placeholder=true. Finished livestreams typically have live_datetime
    null. Browser HTML uses the same instant as scheduled-time= on the card.
    """
    raw = entry.get("live_datetime") or entry.get("scheduled_time") or ""
    if raw is None:
        return ""
    formatted, ts = parse_datetime(str(raw))
    if ts == float("-inf") or not formatted:
        return ""
    return formatted


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


def iter_embedded_listing_arrays(html: str) -> list[list[dict]]:
    """Every embedded ``{"items":[...]}`` video array on a Rumble listing page.

    The user All page has more than one (a short top shelf, then a longer grid).
    Full-feed parse still uses the first non-empty array; the tripwire fingerprints all of them.
    """
    arrays: list[list[dict]] = []
    decoder = json.JSONDecoder()
    for match in re.finditer(r'\{"items":\[', html):
        try:
            payload, _ = decoder.raw_decode(html[match.start():])
        except json.JSONDecodeError:
            continue
        if not isinstance(payload, dict):
            continue
        raw_items = payload.get("items")
        if not isinstance(raw_items, list):
            continue
        videos = [
            entry
            for entry in raw_items
            if isinstance(entry, dict)
            and (not entry.get("object_type") or entry.get("object_type") == "video")
        ]
        if videos:
            arrays.append(videos)
    return arrays


def feeditems_from_listing_entries(entries: list[dict], source_page: str) -> list[FeedItem]:
    items: list[FeedItem] = []
    for entry in entries:
        title = clean_text(str(entry.get("title") or ""))
        raw_url = str(entry.get("url") or entry.get("relative_url") or "")
        link = clean_link(raw_url) if raw_url else ""
        thumb = str(entry.get("thumb") or "")
        video_id = str(entry.get("id") or "")
        video_code = str(entry.get("permalink_id") or "")
        if not video_code and link:
            m = re.search(r"/(v[a-z0-9]+)-", link)
            if m:
                video_code = m.group(1)
        video_embed_id = ""
        pub_date, timestamp = parse_datetime(str(entry.get("upload_date") or ""))
        scheduled_time = listing_scheduled_time(entry)

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
                video_code=video_code,
                video_embed_id=video_embed_id,
                scheduled_time=scheduled_time,
            )
        )
    return items


def parse_embedded_listing_items(html: str, source_page: str) -> list[FeedItem]:
    """Parse video cards from Rumble's embedded listing JSON (replaces videostream HTML)."""
    for entries in iter_embedded_listing_arrays(html):
        items = feeditems_from_listing_entries(entries, source_page)
        if items:
            return items
    return []


def tripwire_fingerprint(html: str) -> str:
    """Stable identity+schedule fingerprint of every listing video on the page.

    Fields: id, title, live_datetime. Ignores views/comments so the cheap check
    does not fire on watch-count churn.

    The user All page SSR payload is regular videos only. Shorts on that page
    live in ``<rum-shorts-row>`` and are fetched by the browser from ``/shorts``.
    Callers that need shorts in the fingerprint must GET that listing too.
    """
    seen: set[tuple[str, str, str]] = set()
    lines: list[str] = []
    for entries in iter_embedded_listing_arrays(html):
        for entry in entries:
            vid = str(entry.get("id") or "").strip()
            title = clean_text(str(entry.get("title") or ""))
            live_dt = entry.get("live_datetime")
            live_s = "" if live_dt in (None, "", "null", "None") else str(live_dt)
            key = (vid, title, live_s)
            if not vid and not title:
                continue
            if key in seen:
                continue
            seen.add(key)
            lines.append(f"{vid}\t{title}\t{live_s}")
    lines.sort()
    return "\n".join(lines) + ("\n" if lines else "")


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


def parse_embed_id_from_iframe(html: str) -> str:
    """Pull v… id from a rumble.com/embed/ iframe src (oEmbed html)."""
    if not html:
        return ""
    m = re.search(r"rumble\.com/embed/(v[0-9a-z]+)/?", html, re.I)
    return m.group(1) if m else ""


def parse_oembed_embed_id(payload: str | dict) -> str:
    """Embed id from a Rumble oEmbed JSON body or its html field."""
    if isinstance(payload, str):
        try:
            payload = json.loads(payload)
        except json.JSONDecodeError:
            return parse_embed_id_from_iframe(payload)
    if not isinstance(payload, dict):
        return ""
    return parse_embed_id_from_iframe(str(payload.get("html") or ""))


def fetch_oembed_embed_id(page_url: str) -> str:
    """Shorts pages have no Rumble('play') snippet; oEmbed has the real embed id."""
    if not page_url:
        return ""
    oembed_url = (
        "https://rumble.com/api/Media/oembed.json?url=" + quote(page_url, safe="")
    )
    try:
        raw = fetch_html(oembed_url)
    except (HTTPError, URLError, TimeoutError, OSError):
        return ""
    return parse_oembed_embed_id(raw)


def parse_video_embed_id(html: str) -> str:
    """Extract the Rumble JS embed 'video' id (e.g. 'v79hwo4') from a *video detail page*.

    This is often different from the list-page slug (v... in the URL).
    Looks in common locations on the detail page.
    Shorts pages typically have none of these; use fetch_oembed_embed_id.
    """
    if not html:
        return ""
    # 1. Rumble("play", {"video": "v79hwo4", ...})
    m = re.search(r'Rumble\s*\(\s*["\']play["\']\s*,\s*\{\s*["\']video["\']\s*:\s*["\'](v[0-9a-z]+)["\']', html, re.I)
    if m:
        return m.group(1)
    # 2. data or json "video": "v79hwo4"
    m = re.search(r'["\']video["\']\s*:\s*["\'](v[0-9a-z]+)["\']', html, re.I)
    if m:
        return m.group(1)
    # 3. rumble_XXXXX div id used by embed
    m = re.search(r'id=["\']rumble_(v[0-9a-z]+)["\']', html, re.I)
    if m:
        return m.group(1)
    # 4. embedJS/... .v79hwo4
    m = re.search(r'embedJS/[^"\']*\.(v[0-9a-z]+)', html, re.I)
    if m:
        return m.group(1)
    return ""


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
        scheduled_attr = attr_value(body, "scheduled-time")
        scheduled_time, _ = parse_datetime(scheduled_attr) if scheduled_attr else ("", float("-inf"))

        video_code = ""
        if link:
            m = re.search(r'/(v[a-z0-9]+)-', link)
            if m:
                video_code = m.group(1)
        video_embed_id = ""  # only from detail page

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
                video_code=video_code,
                video_embed_id=video_embed_id,
                scheduled_time=scheduled_time,
            )
        )

    footer_items = parse_thumbnail_footer_items(html, source_page)
    return items or footer_items


FOOTER_RE = re.compile(
    r"<rum-video-thumbnail-footer\b(?P<attrs>[^>]*)>",
    re.IGNORECASE,
)


def parse_thumbnail_footer_items(html: str, source_page: str) -> list[FeedItem]:
    """Fallback for logged-in / Lit HTML cards (scheduled-time on the footer)."""
    items: list[FeedItem] = []
    for match in FOOTER_RE.finditer(html):
        attrs = match.group("attrs")
        title = clean_text(attr_value(attrs, "video-title"))
        link = clean_link(attr_value(attrs, "url"))
        pub_date, timestamp = parse_datetime(attr_value(attrs, "time"))
        scheduled_time, sched_ts = parse_datetime(attr_value(attrs, "scheduled-time"))
        if not pub_date and scheduled_time:
            pub_date, timestamp = scheduled_time, sched_ts
        video_id = attr_value(attrs, "video-id")
        channel_name = clean_text(attr_value(attrs, "creator-name"))
        channel_url = clean_link(attr_value(attrs, "creator-url"))
        video_code = ""
        if link:
            m = re.search(r"/(v[a-z0-9]+)-", link)
            if m:
                video_code = m.group(1)
        start = max(0, match.start() - 3000)
        chunk = html[start:match.start()]
        img_tag = extract_first(
            r'(<img\b[^>]*\brum-video-thumbnail__image\b[^>]*>)',
            chunk,
        )
        thumb = attr_value(img_tag, "src")
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
                video_code=video_code,
                scheduled_time=scheduled_time,
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

        need_channel = not (item.channel_name or item.channel_url)
        need_embed = not item.video_embed_id
        do_fetch = need_channel or need_embed

        channel = None
        embed_id = item.video_embed_id

        if not do_fetch:
            if item.channel_name or item.channel_url:
                channel = ChannelInfo(name=item.channel_name, url=item.channel_url)
            else:
                channel = ChannelInfo()
            if verbose:
                print(f"Reusing cached details for {item.link}", file=sys.stderr)
        else:
            # need more info (channel or embed). Use channel cache only if we don't need embed (no html)
            if need_channel and not need_embed and (cached_channel := cached_channel_info(channel_cache, item)):
                channel = cached_channel
                if verbose:
                    print(f"Reusing channel details for {item.link}", file=sys.stderr)
            else:
                polite_sleep(delay)
                if verbose:
                    print(f"Fetching details for {item.link} (need channel={need_channel}, embed={need_embed})", file=sys.stderr)

                try:
                    detail_html = fetch_html(item.link)
                    channel = parse_channel_info(detail_html)
                    if need_embed:
                        parsed_embed = parse_video_embed_id(detail_html)
                        if not parsed_embed:
                            parsed_embed = fetch_oembed_embed_id(item.link)
                        if parsed_embed:
                            embed_id = parsed_embed
                except (HTTPError, URLError, TimeoutError) as exc:
                    print(f"Warning: failed to fetch details for {item.link}: {exc}", file=sys.stderr)
                    channel = ChannelInfo()

                if channel and need_channel:
                    cache_channel_info(channel_cache, item, channel)

        if not channel:
            channel = ChannelInfo(name=item.channel_name, url=item.channel_url)

        enriched.append(
            replace(item, channel_name=channel.name, channel_url=channel.url, video_embed_id=embed_id)
        )

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
    previous_by_link = previous_items_by_link(path)
    now_utc = datetime.now(timezone.utc)
    selected = items[:limit]
    payload = {
        "title": "Rumble videos",
        **feed_timestamps(),
        "itemCount": len(selected),
        "items": [
            stamp_item_json(item, previous_by_link.get(item.link), now_utc)
            for item in selected
        ],
    }
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Generate JSON from Rumble channel pages.")
    parser.add_argument("--input", help="Optional URL list file. If omitted, built-in Rumble URLs are used.")
    parser.add_argument("--output", default=DEFAULT_OUTPUT, help=f"JSON output file. Default: {DEFAULT_OUTPUT!r}")
    parser.add_argument("--limit", type=int, default=90, help="Number of feed items to write for the active feed. Default: 90 (main feeds accumulate up to ~90 before archiving)")
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
             "On parser failure, emit only a short message. "
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

    scraped = build_feed(urls, max_pages=max(1, args.pages), delay=max(0, args.delay), verbose=args.verbose)

    # Accumulation (change for TV channel rules reorg):
    # Scrape only the first page (periodic behavior). Merge any new items into
    # the history from the previous JSON. Do not discard past data.
    # Fresh data is preferred for overlapping recent items.
    existing = load_existing_items(output_path)
    if not scraped:
        items = []
    elif existing:
        scraped = merge_scraped_with_existing(scraped, existing)
        items = merge_fresh_into_accumulated(scraped, existing)
    else:
        items = scraped

    if not items:
        print("No Rumble items found. Rumble may have changed its page HTML.", file=sys.stderr)

        is_prod = args.production or (os.environ.get("RUMBLE_FEED_MODE") or "production").lower() == "production"
        if is_prod:
            print(
                "Running in production/safe mode. Auto-capture and Grok are disabled. "
                "Fix on the dev MacBook (RUMBLE_FEED_MODE=development). "
                "See samples/rumble-channel-pages/README.md.",
                file=sys.stderr,
            )
        else:
            print(
                "Parser returned zero items. publish_rumble_feed.sh may capture a sample "
                "and try a bounded Grok fix; do not push parser edits until you review. "
                "See samples/rumble-channel-pages/README.md.",
                file=sys.stderr,
            )
        return 1

    custom_update = load_custom_update_hook()
    if custom_update:
        items = custom_update(items, parse_datetime)

    if is_overcoming_feed_path(output_path):
        items = prune_recategorized_overcoming_items(
            items,
            {item.link for item in scraped if item.link},
            channel_hints=load_rumble_channel_hints(),
            fetch_missing=not args.no_channel_details,
            delay=max(0, args.delay),
        )

    limit = max(1, args.limit)

    # Scrape + accumulation + enrichment have no limit.
    # We just scrape the configured first page(s), accumulate via merge,
    # and enrich what needs it from the full current set.
    if not args.no_channel_details:
        channel_cache = load_channel_cache(output_path)
        items = enrich_channel_details(
            items,
            limit=100000,  # effectively no limit on enrichment for the current set
            delay=max(0, args.delay),
            verbose=args.verbose,
            channel_cache=channel_cache,
        )

    # Final step after all scraping and enrichment: archive excess older
    # videos so the main feed stays at the target size (default 90).
    items = archive_excess(items, output_path, limit)

    write_feed(output_path, items, limit=limit)
    print(f"Wrote {min(len(items), args.limit)} items to {output_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
