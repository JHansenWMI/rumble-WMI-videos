#!/usr/bin/env python3
"""
Generate docs/shortwave-schedule.txt from Intra Support Files/radio_programs.csv.

Designed to run after radio_programs.csv is produced (standalone or via
update_radio_programs.py). Includes rows whose program_number ends with SW.

Usage:
    python update_shortwave_schedule.py

    python update_shortwave_schedule.py --csv "Intra Support Files/radio_programs.csv" \\
        --schedule docs/shortwave-schedule.txt

    # One-time: extract CMS static list for comparison
    python update_shortwave_schedule.py --extract-static
"""

from __future__ import annotations

import argparse
import html
import re
import sys
from datetime import datetime
from pathlib import Path

from update_radio_programs import (
    air_date_for_entry,
    format_schedule_line,
    load_radio_programs_csv,
    schedule_cutoff_date,
    write_schedule,
)

SW_PROG_RE = re.compile(r"SW$", re.IGNORECASE)
# Strip anywhere in the string (shortwave lines often combine two programs).
DATE_ANYWHERE_RE = re.compile(
    r"\s*\d{1,2}/\d{1,2}/\d{2,4}(?:\s*[ap]m)?",
    re.IGNORECASE,
)
PROG_ANYWHERE_RE = re.compile(r"\s*\d+(?:R[1-5]|SW|Sun)\b", re.IGNORECASE)
PAREN_RE = re.compile(r"\([^()]*\)")


def clean_shortwave_title_for_display(title: str) -> str:
    """Remove dates, program numbers, and parenthetical text from shortwave titles."""
    if not title:
        return ""
    t = html.unescape(title.strip())
    while True:
        prev = t
        t = DATE_ANYWHERE_RE.sub(" ", t)
        t = PROG_ANYWHERE_RE.sub(" ", t)
        if t == prev:
            break
    while True:
        prev = t
        t = PAREN_RE.sub(" ", t)
        if t == prev:
            break
    t = re.sub(r"\s+,", ",", t)
    t = re.sub(r"\s+", " ", t).strip()
    while True:
        prev = t
        t = re.sub(r"-\s+-", "-", t)
        if t == prev:
            break
    return t
CMS_HTML_DEFAULT = Path("WorkToDo/ShortWaveBroadcastSnippet-fromCMS.html")
STATIC_DEFAULT = Path("docs/shortwave-schedule-static.txt")


def is_shortwave_entry(entry: dict) -> bool:
    prog = (entry.get("program_number") or "").strip()
    return bool(SW_PROG_RE.search(prog))


def entries_to_shortwave_schedule_lines(
    entries: list[dict],
    max_future_days: int = 10,
) -> list[str]:
    """Build schedule lines from CSV rows (SW program numbers, newest first)."""
    cutoff = schedule_cutoff_date(max_future_days)
    candidates: list[tuple[datetime, str]] = []

    for entry in entries:
        if not is_shortwave_entry(entry):
            continue
        air_date = air_date_for_entry(entry)
        if not air_date:
            continue
        if air_date > cutoff:
            continue
        title = clean_shortwave_title_for_display(entry.get("title") or "")
        if not title:
            continue
        candidates.append((air_date, format_schedule_line(air_date, title)))

    candidates.sort(key=lambda x: x[0], reverse=True)
    return [line for _, line in candidates]


def generate_shortwave_schedule_from_csv(
    csv_path: Path,
    max_future_days: int = 10,
) -> list[str]:
    rows = load_radio_programs_csv(csv_path)
    return entries_to_shortwave_schedule_lines(rows, max_future_days=max_future_days)


def generate_and_write(
    csv_path: Path,
    schedule_path: Path,
    max_future_days: int = 10,
) -> list[str]:
    lines = generate_shortwave_schedule_from_csv(csv_path, max_future_days=max_future_days)
    write_schedule(schedule_path, lines)
    return lines


def extract_lines_from_cms_html(html_path: Path) -> list[str]:
    """Pull list lines from the saved CMS snippet HTML (<ul> only, schedule-shaped rows)."""
    content = html_path.read_text(encoding="utf-8")
    ul_match = re.search(r"<ul[^>]*>(.*)</ul>", content, re.DOTALL | re.IGNORECASE)
    if not ul_match:
        return []
    ul_body = ul_match.group(1)
    date_re = re.compile(r"^[A-Za-z]{3},\s")
    lines: list[str] = []
    for match in re.finditer(r"<li[^>]*>(.*?)</li>", ul_body, re.DOTALL | re.IGNORECASE):
        raw = match.group(1)
        text = re.sub(r"<[^>]+>", "", raw)
        text = html.unescape(text).replace("\xa0", " ")
        text = re.sub(r"\s+", " ", text).strip()
        if text and date_re.match(text):
            lines.append(text)
    return lines


def write_static_from_cms(
    html_path: Path,
    static_path: Path,
) -> list[str]:
    lines = extract_lines_from_cms_html(html_path)
    write_schedule(static_path, lines)
    return lines


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Generate shortwave schedule text from radio_programs.csv (SW rows).",
    )
    parser.add_argument(
        "--csv",
        default="Intra Support Files/radio_programs.csv",
        help="Input CSV path (from update_radio_programs.py)",
    )
    parser.add_argument(
        "--schedule",
        default="docs/shortwave-schedule.txt",
        help="Output schedule text path",
    )
    parser.add_argument(
        "--max-future-days",
        type=int,
        default=10,
        help="Include entries at most this many days beyond today (Pacific)",
    )
    parser.add_argument("--dry-run", action="store_true", help="Preview only, do not write")
    parser.add_argument(
        "--extract-static",
        action="store_true",
        help="Extract WorkToDo CMS HTML to docs/shortwave-schedule-static.txt",
    )
    parser.add_argument(
        "--cms-html",
        default=str(CMS_HTML_DEFAULT),
        help="CMS HTML source for --extract-static",
    )
    parser.add_argument(
        "--static-out",
        default=str(STATIC_DEFAULT),
        help="Output path for --extract-static",
    )
    args = parser.parse_args()

    project_root = Path(__file__).parent
    csv_path = Path(args.csv)
    schedule_path = Path(args.schedule)
    if not csv_path.is_absolute():
        csv_path = project_root / csv_path
    if not schedule_path.is_absolute():
        schedule_path = project_root / schedule_path

    if args.extract_static:
        html_path = Path(args.cms_html)
        static_path = Path(args.static_out)
        if not html_path.is_absolute():
            html_path = project_root / html_path
        if not static_path.is_absolute():
            static_path = project_root / static_path
        if not html_path.exists():
            print(f"ERROR: CMS HTML not found: {html_path}", file=sys.stderr)
            sys.exit(1)
        lines = write_static_from_cms(html_path, static_path)
        print(f"Wrote {len(lines)} lines to {static_path}")
        return

    if not csv_path.exists():
        print(f"ERROR: CSV not found: {csv_path}", file=sys.stderr)
        sys.exit(1)

    cutoff = schedule_cutoff_date(args.max_future_days)
    print(f"CSV path: {csv_path}")
    print(f"Schedule target: {schedule_path}")
    print(f"Schedule air-date cutoff: {cutoff.strftime('%Y-%m-%d')} (today PT + {args.max_future_days} days)")

    lines = generate_shortwave_schedule_from_csv(csv_path, max_future_days=args.max_future_days)
    print(f"Generated {len(lines)} shortwave schedule lines (program_number ends with SW).")

    if args.dry_run:
        print("\nNewest 8:")
        for line in lines[:8]:
            print(" ", line)
        print("\nOldest 3:")
        for line in lines[-3:]:
            print(" ", line)
        return

    write_schedule(schedule_path, lines)
    print(f"Wrote {len(lines)} lines to {schedule_path}")
    print("\nNewest entries:")
    for line in lines[:5]:
        print(" ", line)


if __name__ == "__main__":
    main()