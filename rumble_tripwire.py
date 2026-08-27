#!/usr/bin/env python3
"""Cheap All-page change detector for the Rumble feed tick.

Fetches https://rumble.com/user/DrJonathanHansenWMI (no git).
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

DEFAULT_URL = "https://rumble.com/user/DrJonathanHansenWMI"
DEFAULT_STATE = Path(__file__).resolve().parent / ".rumble-tripwire-state"


def load_state(path: Path) -> str:
    if not path.is_file():
        return ""
    return path.read_text(encoding="utf-8")


def save_state(path: Path, fingerprint: str) -> None:
    path.write_text(fingerprint, encoding="utf-8")


def fetch_fingerprint(url: str) -> str:
    html = fetch_html(url)
    fp = tripwire_fingerprint(html)
    if not fp.strip():
        raise RuntimeError("Tripwire parsed zero listing videos from the All page")
    return fp


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Rumble All-page tripwire")
    parser.add_argument("--url", default=DEFAULT_URL)
    parser.add_argument("--state", type=Path, default=DEFAULT_STATE)
    parser.add_argument(
        "--save",
        action="store_true",
        help="Fetch and write state (use after a successful full scrape)",
    )
    args = parser.parse_args(argv)

    try:
        fingerprint = fetch_fingerprint(args.url)
    except HTTPError as exc:
        print(f"ERROR HTTP {exc.code} fetching {args.url}", file=sys.stderr)
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
