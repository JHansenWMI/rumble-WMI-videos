#!/usr/bin/env python3
"""Cheap listing change detector for the Rumble feed tick.

The All page HTML includes a ``<rum-shorts-row feed-path="…/shorts">`` shelf
that the browser hydrates after load. SSR JSON on All is videos-only, so a
new short never changes that payload. The tripwire therefore also GETs the
shorts listing (same path the web component uses) and unions fingerprints.

Fingerprints id + title + live_datetime across every listing JSON array.

Exit codes:
  0  UNCHANGED (state file updated to the same fingerprint)
  1  CHANGED or first run (state not written — caller saves after a successful full scrape)
  2  fetch/parse error (do not run a full scrape)
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path
from urllib.error import HTTPError, URLError

from generate_rumble_feed import fetch_html, tripwire_fingerprint

DEFAULT_URLS = [
    "https://rumble.com/user/DrJonathanHansenWMI",
    "https://rumble.com/user/DrJonathanHansenWMI/shorts",
]
DEFAULT_URL = DEFAULT_URLS[0]
DEFAULT_STATE = Path(__file__).resolve().parent / ".rumble-tripwire-state"


def load_state(path: Path) -> str:
    if not path.is_file():
        return ""
    return path.read_text(encoding="utf-8")


def save_state(path: Path, fingerprint: str) -> None:
    path.write_text(fingerprint, encoding="utf-8")


def merge_fingerprints(parts: list[str]) -> str:
    """Union fingerprint lines from several listing pages, sorted stably."""
    seen: set[str] = set()
    lines: list[str] = []
    for part in parts:
        for line in part.splitlines():
            if not line or line in seen:
                continue
            seen.add(line)
            lines.append(line)
    lines.sort()
    return "\n".join(lines) + ("\n" if lines else "")


def fetch_one_fingerprint(url: str, *, required: bool) -> str:
    html = fetch_html(url)
    fp = tripwire_fingerprint(html)
    if fp.strip():
        return fp
    if required:
        raise RuntimeError(f"Tripwire parsed zero listing videos from {url}")
    return ""


def fetch_fingerprint(urls: list[str] | str) -> str:
    if isinstance(urls, str):
        urls = [urls]
    if not urls:
        raise RuntimeError("Tripwire needs at least one listing URL")
    parts: list[str] = []
    for i, url in enumerate(urls):
        part = fetch_one_fingerprint(url, required=(i == 0))
        if part:
            parts.append(part)
    merged = merge_fingerprints(parts)
    if not merged.strip():
        raise RuntimeError("Tripwire parsed zero listing videos")
    return merged


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Rumble All+shorts tripwire")
    parser.add_argument(
        "--url",
        action="append",
        dest="urls",
        help="Listing URL (repeatable). Default: All page + shorts listing.",
    )
    parser.add_argument("--state", type=Path, default=DEFAULT_STATE)
    parser.add_argument(
        "--save",
        action="store_true",
        help="Fetch and write state (use after a successful full scrape)",
    )
    args = parser.parse_args(argv)
    urls = args.urls or list(DEFAULT_URLS)

    try:
        fingerprint = fetch_fingerprint(urls)
    except HTTPError as exc:
        print(f"ERROR HTTP {exc.code} fetching listing", file=sys.stderr)
        return 2
    except (URLError, OSError, RuntimeError) as exc:
        print(f"ERROR {exc}", file=sys.stderr)
        return 2

    n = fingerprint.count("\n")
    if args.save:
        save_state(args.state, fingerprint)
        print(f"SAVED {n} listing videos -> {args.state}")
        return 0

    previous = load_state(args.state)
    if not previous:
        print(f"CHANGED first-run ({n} listing videos)")
        return 1
    if previous == fingerprint:
        save_state(args.state, fingerprint)
        print(f"UNCHANGED ({n} listing videos)")
        return 0
    print(f"CHANGED ({n} listing videos)")
    return 1


if __name__ == "__main__":
    sys.exit(main())
