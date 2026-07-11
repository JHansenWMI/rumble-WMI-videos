#!/usr/bin/env python3
"""
Match radio-schedule.txt titles to Podbean RSS episodes for play-button links.

Usage:
  # Default: match using existing docs/radio-schedule.txt (no Office drive needed)
  python match_podbean_to_radio.py

  # Or build the title list from existing radio_programs.csv (no spreadsheet rebuild)
  python match_podbean_to_radio.py --from-csv

  python match_podbean_to_radio.py --dry-run

This script never rebuilds radio_programs.csv and never opens the Office spreadsheet.
Needs: Podbean RSS (network, unless --cache-only) + local schedule text and/or CSV.

Podbean episode catalog (accumulated, not website):
  - Intra Support Files/podbean_episodes.json
  Each fetch merges into this file by guid (add/update; never drops old episodes
  that aged out of the RSS window). Matching uses the full local catalog.

Writes website data only:
  - docs/podbean-radio-matches.json          (newest active matches, default max 100)
  - docs/podbean-radio-matches-archive.json  (older matches beyond the active cap)

Matching (summary):
  - Normalize titles (like other WMI tools).
  - Exact → containment → fuzzy (with thresholds).
  - Part N on radio may match a Podbean episode *without* Part N (full program
    on Podbean; radio split for airtime). Same Part N still matches. Different
    Part numbers do not.
  - Weak/ambiguous matches are omitted (no play button).
"""

from __future__ import annotations

import argparse
import html
import json
import re
import sys
import urllib.request
from collections import defaultdict
from difflib import SequenceMatcher
from pathlib import Path

DEFAULT_FEED = "https://feed.podbean.com/warningjonathanhansen/feed.xml"
DEFAULT_SCHEDULE = Path("docs/radio-schedule.txt")
DEFAULT_CSV = Path("Intra Support Files/radio_programs.csv")
DEFAULT_PODBEAN_CACHE = Path("Intra Support Files/podbean_episodes.json")
DEFAULT_OUTPUT = Path("docs/podbean-radio-matches.json")
DEFAULT_ARCHIVE = Path("docs/podbean-radio-matches-archive.json")
DEFAULT_ACTIVE_LIMIT = 100

LINE_RE = re.compile(
    r"^(?:[A-Za-z]+,\s+)?([A-Za-z]+)\s+(\d{1,2}),\s+(\d{4}):\s*(.*)$"
)
PART_RE = re.compile(r"\bpart\s*(\d+)\b", re.I)
TRAIL_DATE_RE = re.compile(r"\s+\d{1,2}/\d{1,2}/\d{2,4}\s*$")
PROG_RE = re.compile(r"\s+\d+(?:R[1-5]|SW|Sun)\s*$", re.I)
# Strip "Part N" (and optional dash before it) for base-title compares
PART_STRIP_RE = re.compile(r"\s*[-–—]?\s*part\s*\d+\b", re.I)


def normalize_title(value: str) -> str:
    value = (value or "").lower().replace("&", " and ")
    value = re.sub(r"[^a-z0-9]+", " ", value)
    value = re.sub(r"\b(the|a|an)\b", " ", value)
    return " ".join(value.split())


def clean_title(t: str) -> str:
    t = html.unescape(re.sub(r"\s+", " ", (t or "").strip()))
    t = re.sub(
        r"^(?:warning\s*!?\s*[-:]?\s*|dr\.?\s*hansen\s*[-:]\s*)",
        "",
        t,
        flags=re.I,
    ).strip()
    while True:
        prev = t
        t = TRAIL_DATE_RE.sub("", t)
        t = PROG_RE.sub("", t)
        if t == prev:
            break
    return t.strip(" -–—")


def part_num(t: str) -> int | None:
    m = PART_RE.search(t or "")
    return int(m.group(1)) if m else None


def base_title(t: str) -> str:
    """Title with Part N removed (for matching radio parts to full PB episodes)."""
    return PART_STRIP_RE.sub("", t or "").strip(" -–—")


def part_compatible(radio_title: str, ep_part: int | None) -> bool:
    """
    Radio Part N may match:
      - Podbean same Part N
      - Podbean with no Part (full program; radio was split for time)
    Radio Part N must NOT match a different Part M.
    """
    rp = part_num(radio_title)
    if rp is None:
        return True
    if ep_part is None:
        return True  # allow full-episode on Podbean
    return rp == ep_part


def fetch_feed(url: str) -> str:
    req = urllib.request.Request(
        url,
        headers={"User-Agent": "WMI-radio-podbean-match/1.0"},
    )
    with urllib.request.urlopen(req, timeout=120) as resp:
        return resp.read().decode("utf-8", errors="replace")


def _episode_key(ep: dict) -> str:
    """Stable id for merge: guid preferred, else link, else enclosure."""
    return (
        (ep.get("guid") or "").strip()
        or (ep.get("link") or "").strip()
        or (ep.get("enclosure") or "").strip()
    )


def enrich_episode_fields(ep: dict) -> dict:
    """Ensure derived clean/norm/part fields exist (for cache reload)."""
    title = ep.get("title") or ""
    cleaned = clean_title(title)
    ep["clean"] = cleaned
    ep["norm"] = normalize_title(cleaned)
    ep["base_norm"] = normalize_title(base_title(cleaned))
    ep["part"] = part_num(cleaned)
    return ep


def parse_podbean_rss(xml_text: str) -> list[dict]:
    """
    Parse one RSS document.

    Note: A typical Podbean RSS response is a *rolling window* (here ~999 items),
    not guaranteed full lifetime history. There is usually no separate "latest only"
    endpoint that is smaller — you download the whole feed XML each time.
    """
    raw_items = re.findall(r"<item>(.*?)</item>", xml_text, re.S | re.I)

    def grab(tag: str, blob: str) -> str:
        m = re.search(rf"<{tag}(?:\s[^>]*)?>(.*?)</{tag}>", blob, re.S | re.I)
        return re.sub(r"<[^>]+>", "", m.group(1)).strip() if m else ""

    episodes: list[dict] = []
    for it in raw_items:
        title = html.unescape(grab("title", it))
        link = grab("link", it)
        guid = grab("guid", it)
        pub = grab("pubDate", it)
        m = re.search(r'<enclosure[^>]+url=["\']([^"\']+)["\']', it, re.I)
        enc = m.group(1) if m else ""
        if not title:
            continue
        ep = {
            "guid": guid,
            "title": title,
            "link": link,
            "enclosure": enc,
            "pubDate": pub,
        }
        episodes.append(enrich_episode_fields(ep))
    return episodes


def load_podbean_cache(path: Path) -> list[dict]:
    if not path.is_file():
        return []
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        print(f"Warning: could not read Podbean cache {path}: {exc}", file=sys.stderr)
        return []
    raw = data.get("episodes") if isinstance(data, dict) else data
    if not isinstance(raw, list):
        return []
    return [enrich_episode_fields(dict(ep)) for ep in raw if ep.get("title")]


def merge_podbean_episodes(existing: list[dict], fresh: list[dict]) -> tuple[list[dict], int, int]:
    """
    Merge fresh RSS items into the accumulated catalog by guid/link.
    Returns (merged_list, added_count, updated_count).
    Never removes episodes that disappeared from the feed.
    """
    from datetime import datetime, timezone

    now = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    by_key: dict[str, dict] = {}
    order: list[str] = []

    for ep in existing:
        key = _episode_key(ep)
        if not key:
            continue
        if key not in by_key:
            order.append(key)
        by_key[key] = enrich_episode_fields(dict(ep))

    added = 0
    updated = 0
    for ep in fresh:
        key = _episode_key(ep)
        if not key:
            continue
        ep = enrich_episode_fields(dict(ep))
        if key not in by_key:
            ep.setdefault("firstSeen", now)
            ep["lastSeen"] = now
            by_key[key] = ep
            order.append(key)
            added += 1
        else:
            prev = by_key[key]
            # Update mutable fields from feed; keep firstSeen
            first = prev.get("firstSeen") or now
            changed = any(
                prev.get(f) != ep.get(f)
                for f in ("title", "link", "enclosure", "pubDate")
            )
            if changed:
                updated += 1
            prev.update(
                {
                    "guid": ep.get("guid") or prev.get("guid"),
                    "title": ep.get("title") or prev.get("title"),
                    "link": ep.get("link") or prev.get("link"),
                    "enclosure": ep.get("enclosure") or prev.get("enclosure"),
                    "pubDate": ep.get("pubDate") or prev.get("pubDate"),
                    "firstSeen": first,
                    "lastSeen": now,
                }
            )
            by_key[key] = enrich_episode_fields(prev)

    # Prefer newest pubDate first for matching shortlists (stable enough)
    merged = [by_key[k] for k in order if k in by_key]
    return merged, added, updated


def save_podbean_cache(
    path: Path,
    episodes: list[dict],
    feed_url: str,
) -> None:
    from datetime import datetime, timezone

    path.parent.mkdir(parents=True, exist_ok=True)
    # Persist a lean record (drop pure derived fields that can be recomputed)
    lean = []
    for ep in episodes:
        lean.append(
            {
                "guid": ep.get("guid") or "",
                "title": ep.get("title") or "",
                "link": ep.get("link") or "",
                "enclosure": ep.get("enclosure") or "",
                "pubDate": ep.get("pubDate") or "",
                "firstSeen": ep.get("firstSeen") or "",
                "lastSeen": ep.get("lastSeen") or "",
            }
        )
    payload = {
        "sourceFeed": feed_url,
        "lastFetched": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "episodeCount": len(lean),
        "note": (
            "Accumulated Podbean catalog. Daily RSS is a rolling window (~1000 items); "
            "merge by guid so older episodes are retained after they leave the feed."
        ),
        "episodes": lean,
    }
    path.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")


def load_schedule(path: Path) -> list[dict]:
    """Load title list from docs/radio-schedule.txt (website schedule)."""
    rows: list[dict] = []
    for ln in path.read_text(encoding="utf-8").splitlines():
        ln = ln.strip()
        if not ln:
            continue
        m = LINE_RE.match(ln)
        if not m:
            continue
        title = m.group(4).strip()
        rows.append(
            {
                "date": f"{m.group(1)} {m.group(2)}, {m.group(3)}",
                "title": title,
                "clean": clean_title(title),
            }
        )
    return rows


def load_schedule_from_csv(
    csv_path: Path,
    max_future_days: int = 10,
) -> list[dict]:
    """
    Build the same title list the website schedule uses, from an existing
    radio_programs.csv — without opening the Office spreadsheet or rewriting
    the CSV. Reuses update_radio_programs mapping (slot 1, title clean, cutoff).
    """
    # Local import so this file can still run if radio updater is absent.
    from update_radio_programs import (
        MONTHS,
        air_date_for_entry,
        clean_title_for_display,
        load_radio_programs_csv,
        schedule_cutoff_date,
    )

    if not csv_path.is_file():
        raise FileNotFoundError(f"CSV not found: {csv_path}")

    entries = load_radio_programs_csv(csv_path)
    cutoff = schedule_cutoff_date(max_future_days)
    rows: list[dict] = []

    for entry in entries:
        if entry.get("slot") != "1":
            continue
        air_date = air_date_for_entry(entry)
        if not air_date or air_date > cutoff:
            continue
        title = clean_title_for_display(entry.get("title") or "")
        if not title:
            continue
        date_str = f"{MONTHS[air_date.month - 1]} {air_date.day}, {air_date.year}"
        rows.append(
            {
                "date": date_str,
                "title": title,
                "clean": clean_title(title),
            }
        )

    # Newest first (same as radio-schedule.txt)
    def sort_key(r: dict):
        # date like "Jul 17, 2026"
        try:
            from datetime import datetime

            return datetime.strptime(r["date"], "%b %d, %Y")
        except Exception:
            return r["date"]

    rows.sort(key=sort_key, reverse=True)
    return rows


def match_one(radio_title: str, episodes: list[dict], by_norm: dict, by_base: dict):
    cleaned = clean_title(radio_title)
    n = normalize_title(cleaned)
    n_base = normalize_title(base_title(cleaned))
    if not n:
        return "no_match", 0.0, None

    def ok(ep: dict) -> bool:
        return part_compatible(radio_title, ep["part"])

    # 1) Exact full title
    exact = [ep for ep in by_norm.get(n, []) if ok(ep)]
    if exact:
        return "exact_norm", 1.0, exact[0]

    # 2) Radio "… Part N" → Podbean base title (no part) or same base
    if part_num(radio_title) is not None and n_base:
        base_hits = [ep for ep in by_base.get(n_base, []) if ok(ep)]
        # Prefer episode with no part (full program), then same part exact already handled
        no_part = [ep for ep in base_hits if ep["part"] is None]
        if no_part:
            return "part_to_full", 0.95, no_part[0]
        same_part = [ep for ep in base_hits if ep["part"] == part_num(radio_title)]
        if same_part:
            return "exact_norm", 1.0, same_part[0]

    # 3) Containment
    hits: list[tuple[float, dict]] = []
    for ep in episodes:
        if not ep["norm"] or not ok(ep):
            continue
        pn = ep["norm"]
        # Also try base forms when radio has a part
        candidates = [(n, pn)]
        if n_base and n_base != n:
            candidates.append((n_base, pn))
            candidates.append((n_base, ep["base_norm"]))
        for a, b in candidates:
            if not a or not b:
                continue
            if len(a) >= 10 and a in b:
                hits.append((0.92, ep))
            elif len(b) >= 10 and b in a:
                hits.append((0.88, ep))
    if hits:
        hits.sort(key=lambda x: (-x[0], -len(x[1]["norm"])))
        top_score = hits[0][0]
        top = [h for h in hits if h[0] >= top_score - 0.02]
        norms = {h[1]["norm"] for h in top}
        if len(norms) == 1:
            return "containment", top[0][0], top[0][1]
        scored = [
            (SequenceMatcher(None, n_base or n, h[1]["base_norm"] or h[1]["norm"]).ratio(), h[1])
            for h in top
        ]
        scored.sort(key=lambda x: -x[0])
        if scored[0][0] >= 0.90 and (
            len(scored) == 1 or scored[0][0] - scored[1][0] >= 0.02
        ):
            return "fuzzy_from_ambig", scored[0][0], scored[0][1]
        return "containment_ambiguous", top[0][0], top[0][1]

    # 4) Fuzzy on token shortlist
    tokens = set((n_base or n).split())
    pool_scored: list[tuple[float, dict]] = []
    for ep in episodes:
        if not ok(ep) or not ep["norm"]:
            continue
        pt = set((ep["base_norm"] or ep["norm"]).split())
        inter = len(tokens & pt)
        if inter == 0:
            continue
        jacc = inter / len(tokens | pt)
        if jacc >= 0.35 or inter >= 3:
            pool_scored.append((jacc, ep))
    pool_scored.sort(key=lambda x: -x[0])
    pool = [ep for _, ep in pool_scored[:50]]
    if not pool:
        pool = [ep for ep in episodes if ok(ep)]

    compare = n_base or n
    scores = [
        (
            SequenceMatcher(None, compare, ep["base_norm"] or ep["norm"]).ratio(),
            ep,
        )
        for ep in pool
        if (ep["base_norm"] or ep["norm"])
    ]
    scores.sort(key=lambda x: -x[0])
    if not scores:
        return "no_match", 0.0, None
    best_r, best = scores[0]
    second = scores[1][0] if len(scores) > 1 else 0.0
    gap = best_r - second
    if best_r >= 0.92 or (best_r >= 0.88 and gap >= 0.04):
        return "fuzzy", best_r, best
    if best_r >= 0.80:
        return "weak_fuzzy", best_r, best
    return "no_match", best_r, best


def _payload_base(feed_url: str, schedule_label: str) -> dict:
    return {
        "sourceFeed": feed_url,
        "podbeanSite": "https://warningjonathanhansen.podbean.com/",
        "schedule": schedule_label,
        "rules": {
            "partN": (
                "Radio 'Part N' may link to Podbean episode without Part "
                "(full program). Different Part numbers never match."
            ),
            "reject": "weak_fuzzy / ambiguous / no_match omitted",
            "activeLimit": (
                "Active file keeps the newest N matches (by schedule order); "
                "older matches go to the archive file for lazy load on Older."
            ),
        },
    }


def run(
    feed_url: str,
    schedule_path: Path,
    output_path: Path,
    archive_path: Path,
    active_limit: int,
    dry_run: bool,
    from_csv: bool = False,
    csv_path: Path | None = None,
    max_future_days: int = 10,
    cache_path: Path | None = None,
    cache_only: bool = False,
    no_cache: bool = False,
) -> int:
    project_root = Path(__file__).parent
    cache_path = cache_path or DEFAULT_PODBEAN_CACHE
    if not cache_path.is_absolute():
        cache_path = project_root / cache_path

    existing = [] if no_cache else load_podbean_cache(cache_path)
    if existing:
        print(f"Loaded Podbean cache: {cache_path} ({len(existing)} episodes)")

    if cache_only:
        if not existing:
            print(f"ERROR: --cache-only but no cache at {cache_path}", file=sys.stderr)
            return 1
        episodes = existing
        print(f"Using cache only ({len(episodes)} episodes); no RSS fetch")
    else:
        print(f"Fetching {feed_url} …")
        xml_text = fetch_feed(feed_url)
        fresh = parse_podbean_rss(xml_text)
        print(f"Feed returned {len(fresh)} items (rolling window, full RSS document)")
        episodes, added, updated = merge_podbean_episodes(existing, fresh)
        print(
            f"Catalog after merge: {len(episodes)} "
            f"(+{added} new, ~{updated} updated fields)"
        )
        if not dry_run and not no_cache:
            save_podbean_cache(cache_path, episodes, feed_url)
            print(f"Wrote Podbean cache: {cache_path}")
        elif dry_run:
            print(f"--dry-run: would write cache {cache_path} ({len(episodes)} episodes)")

    if from_csv:
        csv_path = csv_path or DEFAULT_CSV
        if not csv_path.is_absolute():
            csv_path = Path(__file__).parent / csv_path
        print(f"Building title list from existing CSV (no rebuild): {csv_path}")
        schedule = load_schedule_from_csv(csv_path, max_future_days=max_future_days)
        schedule_label = str(csv_path).replace("\\", "/")
    else:
        if not schedule_path.is_absolute():
            schedule_path = Path(__file__).parent / schedule_path
        print(f"Loading schedule text: {schedule_path}")
        schedule = load_schedule(schedule_path)
        schedule_label = str(schedule_path).replace("\\", "/")

    print(f"Radio titles to match: {len(schedule)}")

    by_norm: dict[str, list] = defaultdict(list)
    by_base: dict[str, list] = defaultdict(list)
    for ep in episodes:
        if ep["norm"]:
            by_norm[ep["norm"]].append(ep)
        if ep["base_norm"]:
            by_base[ep["base_norm"]].append(ep)

    strong = {"exact_norm", "part_to_full", "containment", "fuzzy", "fuzzy_from_ambig"}
    matches = []
    tiers: dict[str, int] = defaultdict(int)

    # Schedule is newest-first; preserve that order so active = newest matches.
    for row in schedule:
        tier, conf, ep = match_one(row["title"], episodes, by_norm, by_base)
        tiers[tier] += 1
        if tier not in strong or not ep:
            continue
        matches.append(
            {
                "radioTitle": row["title"],
                "airDate": row["date"],
                "podbeanTitle": ep["title"],
                "episodeUrl": ep["link"],
                "audioUrl": ep["enclosure"],
                "match": tier,
                "confidence": round(conf, 3),
            }
        )

    print("Tiers:")
    for k, v in sorted(tiers.items(), key=lambda kv: -kv[1]):
        print(f"  {k}: {v}")
    print(f"Strong matches: {len(matches)}/{len(schedule)}")

    limit = max(0, int(active_limit))
    active = matches[:limit]
    archive = matches[limit:]

    base = _payload_base(feed_url, schedule_label)
    active_payload = {
        **base,
        "matchCount": len(active),
        "totalMatchCount": len(matches),
        "activeLimit": limit,
        "hasArchive": len(archive) > 0,
        "archiveFile": archive_path.name if archive else None,
        "matches": active,
    }
    archive_payload = {
        **base,
        "matchCount": len(archive),
        "totalMatchCount": len(matches),
        "activeLimit": limit,
        "isArchive": True,
        "matches": archive,
    }

    print(f"Active (newest): {len(active)}  archive (older): {len(archive)}")

    if dry_run:
        print("--dry-run: not writing", output_path, archive_path)
        return 0

    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(json.dumps(active_payload, indent=2) + "\n", encoding="utf-8")
    print(f"Wrote {output_path} ({len(active)} matches)")

    if archive:
        archive_path.write_text(
            json.dumps(archive_payload, indent=2) + "\n", encoding="utf-8"
        )
        print(f"Wrote {archive_path} ({len(archive)} matches)")
    elif archive_path.exists():
        archive_path.unlink()
        print(f"Removed empty archive {archive_path}")

    return 0


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(
        description=(
            "Match radio titles to Podbean RSS for play buttons. "
            "Does not open Office spreadsheets or rebuild radio_programs.csv."
        )
    )
    ap.add_argument("--feed", default=DEFAULT_FEED, help="Podbean RSS URL")
    ap.add_argument(
        "--schedule",
        type=Path,
        default=DEFAULT_SCHEDULE,
        help="Schedule text (default: docs/radio-schedule.txt)",
    )
    ap.add_argument(
        "--from-csv",
        action="store_true",
        help=(
            "Build title list from existing radio_programs.csv instead of "
            "radio-schedule.txt (no spreadsheet, no CSV rewrite)"
        ),
    )
    ap.add_argument(
        "--csv",
        type=Path,
        default=DEFAULT_CSV,
        help="CSV path when using --from-csv",
    )
    ap.add_argument(
        "--max-future-days",
        type=int,
        default=10,
        help="With --from-csv: same air-date cutoff as update_radio_programs (default 10)",
    )
    ap.add_argument(
        "--podbean-cache",
        type=Path,
        default=DEFAULT_PODBEAN_CACHE,
        help="Accumulated episode catalog (default: Intra Support Files/podbean_episodes.json)",
    )
    ap.add_argument(
        "--cache-only",
        action="store_true",
        help="Do not fetch RSS; match using existing Podbean cache only",
    )
    ap.add_argument(
        "--no-cache",
        action="store_true",
        help="Do not read/write the Podbean cache (feed-only, old behavior)",
    )
    ap.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    ap.add_argument("--archive", type=Path, default=DEFAULT_ARCHIVE)
    ap.add_argument(
        "--active-limit",
        type=int,
        default=DEFAULT_ACTIVE_LIMIT,
        help="Max matches in the active JSON (rest go to archive). Default: 100",
    )
    ap.add_argument("--dry-run", action="store_true")
    args = ap.parse_args(argv)
    if args.cache_only and args.no_cache:
        print("ERROR: use only one of --cache-only / --no-cache", file=sys.stderr)
        return 2
    try:
        return run(
            args.feed,
            args.schedule,
            args.output,
            args.archive,
            args.active_limit,
            args.dry_run,
            from_csv=args.from_csv,
            csv_path=args.csv,
            max_future_days=args.max_future_days,
            cache_path=args.podbean_cache,
            cache_only=args.cache_only,
            no_cache=args.no_cache,
        )
    except Exception as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
