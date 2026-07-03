#!/usr/bin/env python3
"""
Parse the WATV Radio NOTES sheet from the radio spreadsheet and generate a clean CSV.

First step toward producing a text document similar to docs/tv-schedule.txt.

Usage:
    python update_radio_programs.py \
        --xlsx "/Volumes/Office/Public/01 TV-Radio Spreadsheets/Warning! Radio - Air Date Record.xlsx" \
        --csv "Intra Support Files/radio_programs.csv"

    # Preview:
    python update_radio_programs.py --xlsx ... --csv ... --dry-run

Output CSV columns (one row per program entry):
    week_start,week_end,day,slot,program_number,title,recorded_date,week_str,source_row

- week_start/end: ISO dates parsed from the week header (e.g. 2026-06-22)
- day: Monday..Friday
- slot: "1", "2", or "filler"
- program_number: e.g. 1147R1 , 1147SW , 1147Sun (as stored)
- title: original title from sheet (stripped)
- recorded_date: extracted trailing date from title if present (YYYY-MM-DD) or empty
- week_str: original week header
- source_row: excel row for debugging

The parser focuses on the "live" mini-table section starting ~row 9039.
It automatically stops when it hits the first week header beginning with "2020/"
(the repeated template section described in WorkToDo/Radio Program Parsing.MD).
This ensures new data appended at the end of the live section is included
without any code changes to row limits. Older template data is ignored.
"""

import argparse
import csv
import re
from datetime import datetime
from pathlib import Path

try:
    from openpyxl import load_workbook
except ImportError:
    print("ERROR: openpyxl not installed. Run: pip install openpyxl", file=sys.stderr)
    raise

import sys

MONTHS = ["Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"]


def parse_week_range(week_str: str):
    """Parse '2026/06/22 - 2026/06/26' -> (start_date, end_date) as datetime."""
    if not week_str or " - " not in week_str:
        return None, None
    try:
        left, right = week_str.split(" - ", 1)
        def to_dt(s):
            y, m, d = map(int, s.strip().split("/"))
            return datetime(y, m, d)
        return to_dt(left), to_dt(right)
    except Exception:
        return None, None


def extract_recorded_date(title: str):
    """Look for trailing date like 06/10/2026 or 6/10/26 at end of title. Return YYYY-MM-DD or ''."""
    if not title:
        return ""
    m = re.search(r"(\d{1,2})/(\d{1,2})/(\d{2,4})\s*$", title)
    if not m:
        return ""
    mm, dd, yycap = m.groups()
    yyi = int(yycap)
    if len(yycap) == 4:
        year = yyi
    else:
        year = 2000 + yyi if yyi < 50 else 1900 + yyi
    try:
        dt = datetime(year, int(mm), int(dd))
        return dt.strftime("%Y-%m-%d")
    except Exception:
        return ""


def clean_title_for_display(title: str) -> str:
    """Remove trailing recorded date and any rerun program number suffix for display use."""
    if not title:
        return ""
    t = title.strip()
    # remove trailing date
    t = re.sub(r"\s+\d{1,2}/\d{1,2}/\d{2,4}\s*$", "", t)
    # remove trailing rerun prog num like " 1145R1" or " 1145SW" if it appears at very end after cleaning
    t = re.sub(r"\s+\d+[A-Z]+\s*$", "", t)
    return t.strip()


def parse_radio_sheet(xlsx_path: Path, start_row: int = 9030, end_row: int = None):
    """Yield dicts for each program entry in the live mini-table region.

    Includes weeks from 2023 onward (per the spec in WorkToDo/Radio Program Parsing.MD).
    Skips any week headers with year < 2023 (older history or the repeated 2020
    template blocks at the end). This automatically includes any new data
    added at the end as long as it uses a 2023+ year in the week header.
    The start_row is stable; we do not rely on a hardcoded end row.
    """
    wb = load_workbook(xlsx_path, data_only=False)
    ws = wb["WATV Radio NOTES"]

    days_order = ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday"]

    current_week = None
    current_week_dates = (None, None)
    row = start_row
    max_row = end_row or ws.max_row

    def week_year(week_header):
        try:
            return int(week_header.split("/")[0])
        except:
            return 0

    while row <= max_row:
        col1 = ws.cell(row=row, column=1).value
        if col1 and isinstance(col1, str):
            col1 = col1.strip()

            # Detect week header
            if " - " in col1 and re.match(r"\d{4}/\d{2}/\d{2}", col1):
                if week_year(col1) < 2023:
                    # Older data or 2020 template blocks - skip this week entirely
                    row += 1
                    continue
                current_week = col1
                current_week_dates = parse_week_range(col1)
                row += 1
                continue

            # Detect day header
            if col1 in days_order and current_week:
                day = col1
                row += 1
                # Next 1-3 rows are usually Program 1, Program 2, Filler
                for _ in range(5):  # safety
                    if row > ws.max_row or (end_row and row > end_row):
                        break
                    slot_name = ws.cell(row=row, column=1).value
                    if slot_name and isinstance(slot_name, str):
                        slot_name = slot_name.strip()
                    prog_num = ws.cell(row=row, column=3).value
                    title = ws.cell(row=row, column=4).value

                    if slot_name in ("Program 1", "Program 2", "Filler"):
                        prog_str = str(prog_num).strip() if prog_num else ""
                        title_str = str(title).strip() if title else ""
                        if not (prog_str or title_str):
                            row += 1
                            continue  # skip completely empty slots for a cleaner CSV
                        recorded = extract_recorded_date(title_str)

                        yield {
                            "week_str": current_week,
                            "week_start": current_week_dates[0].strftime("%Y-%m-%d") if current_week_dates[0] else "",
                            "week_end": current_week_dates[1].strftime("%Y-%m-%d") if current_week_dates[1] else "",
                            "day": day,
                            "slot": "1" if slot_name == "Program 1" else ("2" if slot_name == "Program 2" else "filler"),
                            "program_number": prog_str,
                            "title": title_str,
                            "recorded_date": recorded,
                            "source_row": row,
                        }
                        row += 1
                    else:
                        # next day or week header
                        break
                continue

        row += 1


def main():
    parser = argparse.ArgumentParser(description="Parse WATV Radio NOTES sheet to clean CSV.")
    parser.add_argument(
        "--xlsx",
        default="/Volumes/Office/Public/01 TV-Radio Spreadsheets/Warning! Radio - Air Date Record.xlsx",
        help="Path to the radio spreadsheet",
    )
    parser.add_argument(
        "--csv",
        default="Intra Support Files/radio_programs.csv",
        help="Output CSV path (relative to project or absolute)",
    )
    parser.add_argument("--dry-run", action="store_true", help="Parse and print sample rows only, no file written.")
    parser.add_argument("--start-row", type=int, default=9030, help="Approx start row for live data (stable per spec)")
    parser.add_argument("--end-row", type=int, default=None, help="Optional hard max row (for debugging); normally we stop dynamically on first 2020/ week header")
    args = parser.parse_args()

    xlsx_path = Path(args.xlsx)
    csv_path = Path(args.csv)
    if not csv_path.is_absolute():
        # assume relative to script dir (project root)
        csv_path = Path(__file__).parent / csv_path

    print(f"Parsing {xlsx_path}")
    print(f"Output target: {csv_path}")

    entries = list(parse_radio_sheet(xlsx_path, args.start_row, args.end_row))
    print(f"Parsed {len(entries)} program entries.")

    if args.dry_run:
        print("\nSample (first 5):")
        for e in entries[:5]:
            print(e)
        print("\nSample (last 3):")
        for e in entries[-3:]:
            print(e)
        return

    csv_path.parent.mkdir(parents=True, exist_ok=True)
    with open(csv_path, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(
            f,
            fieldnames=["week_start", "week_end", "day", "slot", "program_number", "title", "recorded_date", "week_str", "source_row"],
        )
        writer.writeheader()
        writer.writerows(entries)

    print(f"Wrote {len(entries)} rows to {csv_path}")
    print("First few lines:")
    with open(csv_path, encoding="utf-8") as f:
        for i, line in enumerate(f):
            print(line.rstrip())
            if i >= 6:
                break


if __name__ == "__main__":
    main()
