#!/usr/bin/env python3
"""Purge a video from accumulated website feed JSON after it was deleted on Rumble.

This is not the same as REMOVE_GUIDS in custom_update.py:

  hide   (REMOVE_GUIDS)  video stays on Rumble; we keep it off the website.
                         Next scrape would bring it back without the hide list.

  delete (this script)   video is already gone on Rumble. Remove our stored
                         copy from rumble / overcoming / TV feed JSON (and
                         archives). Do not add it to REMOVE_GUIDS.

Usage:
  python delete_from_feed.py --dry-run 443372718
  python delete_from_feed.py 443372718
  python delete_from_feed.py 443372718 --publish
  python delete_from_feed.py https://rumble.com/v7e5jq2-sderot-....html
"""

from __future__ import annotations

import argparse
import json
import re
import subprocess
import sys
from pathlib import Path

from generate_rumble_feed import feed_timestamps, get_archive_path

SCRIPT_DIR = Path(__file__).resolve().parent

FEED_FILES = [
    "docs/rumble-feed.json",
    "docs/overcoming-feed.json",
    "docs/tv-feed.json",
]

SLUG_RE = re.compile(r"^v[a-z0-9]+$", re.I)
URL_SLUG_RE = re.compile(r"/(v[a-z0-9]+)-", re.I)


def parse_target(token: str) -> dict[str, str]:
    raw = token.strip()
    if not raw:
        raise ValueError("empty target")
    if raw.startswith("http://") or raw.startswith("https://"):
        parsed = {"link": raw.split("?", 1)[0].rstrip("/")}
        m = URL_SLUG_RE.search(parsed["link"])
        if m:
            parsed["slug"] = m.group(1).lower()
        return parsed
    if SLUG_RE.match(raw):
        return {"slug": raw.lower()}
    return {"guid": raw}


def item_target_values(item: dict) -> dict[str, str]:
    link = str(item.get("link") or "").split("?", 1)[0].rstrip("/")
    slug = ""
    m = URL_SLUG_RE.search(link)
    if m:
        slug = m.group(1).lower()
    embed = str(item.get("videoId") or "").strip().lower()
    return {
        "guid": str(item.get("guid") or "").strip(),
        "link": link,
        "slug": slug,
        "videoId": embed,
    }


def item_matches(item: dict, targets: list[dict[str, str]]) -> bool:
    values = item_target_values(item)
    for target in targets:
        if target.get("guid") and values["guid"] == target["guid"]:
            return True
        if target.get("link") and values["link"] == target["link"]:
            return True
        slug = target.get("slug")
        if slug and slug in {values["slug"], values["videoId"]}:
            return True
    return False


def load_feed(path: Path) -> dict:
    data = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(data, dict):
        raise ValueError(f"{path} is not a feed object")
    items = data.get("items")
    if not isinstance(items, list):
        data["items"] = []
    return data


def write_feed(path: Path, data: dict, items: list[dict]) -> None:
    payload = {
        "title": data.get("title") or "Rumble videos",
        **feed_timestamps(),
        "itemCount": len(items),
        "items": items,
    }
    path.write_text(json.dumps(payload, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")


def feed_paths() -> list[Path]:
    paths: list[Path] = []
    seen: set[Path] = set()
    for rel in FEED_FILES:
        primary = SCRIPT_DIR / rel
        candidates = [primary, SCRIPT_DIR / get_archive_path(Path(rel))]
        for path in candidates:
            resolved = path.resolve()
            if resolved in seen or not path.is_file():
                continue
            seen.add(resolved)
            paths.append(path)
    return paths


def purge_feeds(targets: list[dict[str, str]]) -> list[dict]:
    removed: list[dict] = []
    for path in feed_paths():
        data = load_feed(path)
        kept: list[dict] = []
        changed = False
        for item in data.get("items") or []:
            if isinstance(item, dict) and item_matches(item, targets):
                removed.append(
                    {
                        "file": str(path.relative_to(SCRIPT_DIR)),
                        "guid": item.get("guid"),
                        "title": item.get("title"),
                        "link": item.get("link"),
                    }
                )
                changed = True
                continue
            kept.append(item)
        if changed:
            write_feed(path, data, kept)
    return removed


def commit_changed_feeds(removed: list[dict]) -> None:
    files = sorted({row["file"] for row in removed})
    if not files:
        return
    titles = sorted({str(row.get("title") or row.get("guid") or "") for row in removed})
    label = titles[0] if len(titles) == 1 else f"{len(titles)} videos"
    subprocess.run(["git", "add", "--", *files], cwd=SCRIPT_DIR, check=True)
    subprocess.run(
        ["git", "commit", "-m", f"Delete {label} from rumble feed JSON"],
        cwd=SCRIPT_DIR,
        check=True,
    )


def run_publish() -> int:
    script = SCRIPT_DIR / "publish_rumble_feed.sh"
    result = subprocess.run([str(script)], cwd=SCRIPT_DIR)
    return result.returncode


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description=(
            "Delete a video from accumulated website feed JSON "
            "(after it was deleted on Rumble). "
            "Use REMOVE_GUIDS in custom_update.py to hide a video that is still on Rumble."
        )
    )
    parser.add_argument(
        "targets",
        nargs="+",
        help="Rumble guid, video slug (v7e5jq2), or full Rumble URL",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Print matches only; do not write files",
    )
    parser.add_argument(
        "--commit",
        action="store_true",
        help="git commit the feed JSON changes",
    )
    parser.add_argument(
        "--publish",
        action="store_true",
        help="Commit feed JSON (if needed) then run publish_rumble_feed.sh",
    )
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    try:
        targets = [parse_target(token) for token in args.targets]
    except ValueError as exc:
        print(exc, file=sys.stderr)
        return 2

    if args.dry_run:
        matches: list[dict] = []
        for path in feed_paths():
            data = load_feed(path)
            for item in data.get("items") or []:
                if isinstance(item, dict) and item_matches(item, targets):
                    matches.append(
                        {
                            "file": str(path.relative_to(SCRIPT_DIR)),
                            "guid": item.get("guid"),
                            "title": item.get("title"),
                            "link": item.get("link"),
                        }
                    )
        if not matches:
            print("No matching items in feed JSON.")
            return 1
        print(f"Would delete {len(matches)} item(s):")
        for row in matches:
            print(f"  {row['file']}: {row['guid']}  {row['title']}")
        return 0

    removed = purge_feeds(targets)
    if not removed:
        print("No matching items in feed JSON.")
        return 1

    print(f"Deleted {len(removed)} item(s):")
    for row in removed:
        print(f"  {row['file']}: {row['guid']}  {row['title']}")
    print(
        "This only updates our accumulated JSON. "
        "If the video is still on Rumble page 1, the next scrape will add it again "
        "(use REMOVE_GUIDS in custom_update.py to hide a still-live video)."
    )

    if args.publish or args.commit:
        commit_changed_feeds(removed)
    if args.publish:
        return run_publish()
    if not args.commit:
        print("Next: ./publish_rumble_feed.sh  (or re-run with --publish)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
