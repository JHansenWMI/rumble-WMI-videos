# Radio Program Parsing
Goal: To parse the radio program data from the source spreadsheet and create a text document
that can be used by the website to display them, similar to how the TV parsing works (see update_tv_schedule.py + docs/tv-schedule.txt).

## Current Status (as of 2026-07)
- CSV generation implemented and run (see below).
- Output is clean: 1283 meaningful rows (only entries with program_number or title).
- Script: `update_radio_programs.py` (modeled on TV updater).
- Intermediate file: `Intra Support Files/radio_programs.csv`
- Seed list fetched from public site (see below).
- `docs/radio-schedule.txt` generated from CSV (slot 1 primary programs + title cleaning) and usable like `tv-schedule.txt`.
- RadioBroadcastSnippet.html implemented (dynamic fetch of radio-schedule.txt + full paging logic in the snippet only).
- Paging: 50 items at a time, buttons auto-hide when no data in direction, special last-page handling (natural/short height, buttons directly under content).
- Scroll stabilization on full pages (rect capture + compensation); minimal correction on last page.
- Initial load always at top (page 0, no auto-scroll).
- Design principle: all display/paging logic lives in the snippet; source data files remain pure (no display concepts).

## Design Details for CSV Generation
- **Source**: Sheet "WATV Radio NOTES" in the Warning! Radio xlsx.
- **Parsing range**: Starts at ~row 9030 (first 2023/01 week; beginning row is not expected to change). Collects *all* weeks whose header year >= 2023 (skipping any 2020 or earlier blocks, which appear interspersed or as the final repeated templates). This automatically includes any new data added to the end (newer weeks will have high years). No hardcoded end row. (In current data this reaches the 2026/07/06 week at source row ~12882-12902.)
- **Structure recognized**:
  - Week header row: `YYYY/MM/DD - YYYY/MM/DD`
  - For each of Monday–Friday: header row, then up to Program 1 / Program 2 / Filler rows.
- **CSV columns** (one row per slot entry):
  - `week_start`, `week_end`: ISO (YYYY-MM-DD) parsed from week header
  - `day`: Monday..Friday
  - `slot`: "1" | "2" | "filler"
  - `program_number`: e.g. `1147R1`, `1147SW`, `1147Sun` (raw, as in sheet)
  - `title`: original title from sheet (stripped; may be empty for some slots)
  - `recorded_date`: extracted trailing date from title (e.g. 06/26/2026 → 2026-06-26) or empty. Handles 2-digit and 4-digit years.
  - `week_str`, `source_row`: original header + excel row (for traceability/debug)
- **Cleaning**:
  - Skips completely empty (no prog_num and no title) slot rows for a compact CSV.
  - No aggressive title stripping in the CSV `title` field (raw data preserved). `clean_title_for_display()` helper exists in the script for future text output.
  - Program numbers kept verbatim (structure: seq + R[1-5]/SW/Sun documented in spec).
- **Run command** (similar to TV):
  ```
  python update_radio_programs.py \
      --xlsx "/Volumes/Office/Public/01 TV-Radio Spreadsheets/Warning! Radio - Air Date Record.xlsx" \
      --csv "Intra Support Files/radio_programs.csv"
  ```
  Supports `--dry-run`.
- **Output location**: `Intra Support Files/` (per project convention for generated intermediates; see its README).
- **Stats on clean run**: 1283 rows; ~621 have extracted `recorded_date`.

## Seed List from Website
- **Source**: https://www.worldministries.org/radio-broadcasts.aspx ("Warning Radio Broadcast" section).
- Fetched directly with curl + HTML parse (full list served in initial page HTML; no need for saved source).
- Files:
  - `Intra Support Files/radio_broadcasts_seed.txt` — lines in `* Day, Mon DD, YYYY: Title` format (newest first). Header notes fetch time + total count.
  - `Intra Support Files/radio_broadcasts_seed.csv` — structured columns: `air_date, day, title, program_numbers, formatted`.
- A few entries on the site include the original program number(s) appended to the title (e.g. `... 1095R5 1096R5 1097R2`). These are captured in both files (currently 2 known).
- Purpose: the public aired titles/dates as published on the site. Combined later with `radio_programs.csv` (schedule with program_numbers) to produce final output text.
- Refresh by re-fetching the URL (scriptable; modeled after how other intermediates are produced).

## Generating radio-schedule from CSV + comparison to seed (Jul 2026 experiment)
- Generated `docs/radio-schedule.txt` (and Intra `radio-schedule-with-prog.txt`) from `radio_programs.csv` using:
  - Only `slot == "1"` (primary Mon-Fri program per day).
  - Compute exact air date = week_start + day offset.
  - Clean title: strip trailing recorded date (e.g. ` 06/19/2026`) + trailing program number suffix.
  - Format: `Jul 03, 2026: Title` (exact same style as tv-schedule.txt), newest first.
- Comparison vs `radio_broadcasts_seed.csv` (247 overlapping dates):
  - Exact title matches: 156 (63.2%).
  - Recent (Jun–Jul 2026 block): virtually 100% match after cleaning. Example week 2026-06-29/07-03 lines up entry-for-entry with the seed titles.
  - Mismatches (~91): clustered in mid-2025 and earlier. These are real differences (XLSX scheduled a different program for the calendar slot than what the website actually published/listed for that air date). Not a cleaning bug.
- One trivial data issue found and visible in mismatch: "The Bilding Blocks..." (typo in sheet) vs correct "Building".
- Bonus from CSV: every entry carries its `program_number` (R1/R5/SW etc.). Debug file exposes them.
- Future dates (e.g. Nov 2026) appear because the XLSX already contains planned weeks.
- Conclusion: Strong rules-based mapping exists from the CSV for recent/current data. 100% historical identity to the site-published seed list is not possible without also incorporating seed titles (the two sources track planned/recorded vs actually-published in some periods). The CSV version is richer for program numbers.

The `docs/radio-schedule.txt` can now be treated like `tv-schedule.txt` as the derived list for snippets.

## Snippet Implementation
- `RadioBroadcastSnippet.html` (at project root) is the live CMS snippet.
- Dynamically fetches `https://jhansenwmi.github.io/rumble-WMI-videos/radio-schedule.txt` (modeled on TVShowsSnippetNew.html).
- **All paging/display logic is in the snippet only** (50 items/page, "Newer 50"/"Older 50" buttons, auto-hide when no data that direction).
- Last page special case: drops min-height so pager sits directly under actual (short) content; minimal scroll correction only if needed to bring buttons into view.
- Scroll stabilization on full pages keeps buttons at ~same viewport position when list height changes.
- Initial load always starts at page 0 (top); no auto-scroll to "best" page.
- Uses site's `jQ()` / `jQuery()` (from asp/site.js) for pager controls.
- Pure data principle: `radio-schedule.txt` contains only flat "Day, Mon DD, YYYY: Title" lines. No page markers or display info.

See also: RadioBroadcastSnippet.html, docs/radio-schedule.txt, and the scroll/paging logic in the script.

Future steps (per original spec):
- Read the CSV (or re-parse) to produce a text document analogous to `docs/tv-schedule.txt` (likely date-based lines, possibly per-program or weekly summary).
- Integrate into website snippets (similar to TVShowsSnippet*) — basic dynamic snippet + paging complete (see Snippet Implementation section above).

See also: `update_tv_schedule.py` for the TV equivalent and merge/update logic.

# info 

Excel doc located here
/Volumes/Office/Public/01 TV-Radio Spreadsheets/Warning! Radio - Air Date Record.xlsx

Sheet: WATV Radio NOTES

Write a python that can parse that sheet and generate a .csv
I created a folder 'Intra Support Files/' See the README.md inside.

Future steps will be to read the csv and make a text document similar to tv-schedule.txt

# How to parse WATV Radio NOTES
Starting at about row 9039
Column 1: 2023/01/02 - 2023/01/06

Until after row 12840
When the date starts to become '2020/07/27 - 2020/07/31'
From there and after there are 'mini' table templates for future data

Between those two rows is the live data which consists of what I will call 'mini tables'
That look like the following.
Single row with a one week date range
Followed by groups of rows for days of the week: Monday, Tuesday, Wednesday, Thursday, Friday
The Duration column isn't maintained and can be ignored. 
The Program Number column is maintained
The Title is maintained
The title usually ends with a date recorded, and sometimes also a Program number. 
The Program number is put there to indicate a rerun. It is the original program number.

The program numbers have some structure
Sequence number, Letters indicating type: R = Broadcast Radio; SW = Shortwave; Sun = Audio played on Sunday but not broadcast station
If the letter is an R, then the following number is the day of the week: 1 = Monday, 2, 3, 4, 5 = Tue, Wed, Thu, Fri

Example data for one week.
2026/06/08 - 2026/06/12			
Monday	Duration	Program Number	Title
Program 1	14:00	1145R1	Pursue Your Life Purpose - Bishop Dr. Geoffrey Njuguna 05/28/2026
Program 2	14:00		
Filler	0:00		
Tuesday	Duration	Program Number	Title
Program 1	14:00	1145R2	Warning - 25 Prophetic Dreams 05/29/2026
Program 2	14:00		
Filler	0:00		
Wednesday	Duration	Program Number	Title
Program 1	14:00	1145R3	His Divine Nature Part 1 - Apostle Joe Mwaniki 05/30/2026
Program 2	14:00		
Filler	0:00		
Thursday	Duration	Program Number	Title
Program 1	14:00	1145R4	His Divine Nature Part 2 - Apostle Joe Mwaniki 05/30/2026
Program 2	14:00		
Filler	0:00		
Friday	Duration	Program Number	Title
Program 1	14:00	1145R5	His Divine Nature Part 3 - Apostle Joe Mwaniki 05/30/2026
Program 2	14:00	1145SW	His Divine Nature - Apostle Joe Mwaniki 05/30/2026
Filler	0:00	1145Sun	
