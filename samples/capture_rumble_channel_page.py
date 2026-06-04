#!/usr/bin/env python3
"""Download a Rumble channel listing page into samples/rumble-channel-pages/."""

from __future__ import annotations

import argparse
import json
import re
import sys
from datetime import datetime, timezone
from pathlib import Path
from urllib.request import Request, urlopen

SAMPLES_ROOT = Path(__file__).resolve().parent / "rumble-channel-pages"
USER_AGENT = (
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
    "AppleWebKit/537.36 (KHTML, like Gecko) "
    "Chrome/124.0 Safari/537.36"
)


def fetch_html(url: str, timeout: int = 30) -> str:
    req = Request(
        url,
        headers={
            "User-Agent": USER_AGENT,
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
        },
    )
    with urlopen(req, timeout=timeout) as response:
        charset = response.headers.get_content_charset() or "utf-8"
        return response.read().decode(charset, errors="replace")


def extract_items_payload(html: str) -> dict | None:
    decoder = json.JSONDecoder()
    for match in re.finditer(r'\{"items":\[', html):
        try:
            payload, _ = decoder.raw_decode(html[match.start():])
        except json.JSONDecodeError:
            continue
        if isinstance(payload, dict) and payload.get("items"):
            return payload
    return None


def default_slug(url: str) -> str:
    parts = [segment for segment in url.rstrip("/").split("/") if segment]
    if len(parts) >= 2:
        return f"{parts[-2]}-{parts[-1]}"
    return parts[-1] if parts else "page"


def capture(url: str, iteration: str, slug: str | None) -> Path:
    out_dir = SAMPLES_ROOT / iteration
    out_dir.mkdir(parents=True, exist_ok=True)

    html = fetch_html(url)
    basename = slug or default_slug(url)

    html_path = out_dir / f"{basename}.html"
    html_path.write_text(html, encoding="utf-8")

    items_payload = extract_items_payload(html)
    meta = {
        "capturedAt": datetime.now(timezone.utc).isoformat(),
        "sourceUrl": url,
        "iteration": iteration,
        "htmlBytes": len(html.encode("utf-8")),
        "markers": {
            "videostream": html.count("videostream"),
            "data-video-id": html.count("data-video-id"),
            "thumbnail__title": html.count("thumbnail__title"),
            "embeddedItemsJson": bool(items_payload),
            "embeddedItemCount": len(items_payload.get("items", [])) if items_payload else 0,
        },
    }
    (out_dir / "capture-meta.json").write_text(json.dumps(meta, indent=2) + "\n", encoding="utf-8")

    if items_payload:
        items_path = out_dir / f"{basename}.items.json"
        items_path.write_text(json.dumps(items_payload, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")

    return out_dir


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--iteration",
        required=True,
        help="Dated folder name, e.g. 2026-06-04-embedded-json-listing",
    )
    parser.add_argument(
        "--url",
        default="https://rumble.com/user/DrJonathanHansenWMI/videos",
        help="Channel listing URL to download",
    )
    parser.add_argument("--slug", help="Output file basename (default: last URL segment)")
    args = parser.parse_args()

    try:
        out_dir = capture(args.url, args.iteration, args.slug)
    except OSError as exc:
        print(f"Failed to write sample: {exc}", file=sys.stderr)
        return 1

    print(f"Wrote sample to {out_dir}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())