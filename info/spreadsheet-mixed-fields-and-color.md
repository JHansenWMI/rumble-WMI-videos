# Spreadsheet mixed-use fields & colored text

Notes for redesign discussions with Vance (primary spreadsheet maintainer).  
Parsers in this project read **cell values only**; they do not use font color.

**Date:** 2026-07-17  
**Related code:** `update_tv_schedule.py`, `update_radio_programs.py`, `update_shortwave_schedule.py`

---

## Can the parsers recognize colored text?

**No — not today.**

- Excel is loaded with **openpyxl** (`load_workbook(..., data_only=False)`).
- Parsers read only `cell.value` (plain text / numbers).
- Font color, fill, bold, and partial (in-cell) rich-text coloring are **ignored**.

Color is useful **human** annotation in the sheets. Machine logic depends on **text patterns and column layout**.

### Could we add color support later?

| Approach | openpyxl | Fit for current sheets |
|---|---|---|
| Whole-cell font color | `cell.font.color` | Only if the entire cell is one color |
| Partial red inside a title | Rich-text / shared-string runs (harder, uneven support) | What Vance actually does (date or prog # red, title black) |
| Cell background fill | `cell.fill` | Different signal; not used as the title convention |

Even if color reading were added, it should be an **optional hint** with **regex/column fallback**. Red is overloaded (see below), so color alone is a weak contract.

---

## Mixed-use Title fields (intentional)

Fields are reused for more than one kind of data. The parsers already accommodate that via text rules.

### KAZQ (TV) — title + trailing record date

Example title cell:

```text
The Sacrifice God Desires 06/24/26
```

- Black: program title  
- Red (human only): trailing record/source date  

**Parser behavior** (`update_tv_schedule.py`):

- Air date comes from the air-code column (adjusted to Friday), not from the red date.
- Trailing `MM/DD/YY` / `MM/DD/YYYY` is **stripped** for the public `tv-schedule.txt` title.
- Regex: `TRAILING_DATE_RE` (end of string only).

### Radio WATV NOTES — Program 1 title + recorded date

Example:

```text
How is Your Altar? 07/03/2026
```

**Parser behavior** (`update_radio_programs.py`):

- Raw title kept in CSV `title`.
- Trailing date extracted to `recorded_date` when present.
- Display cleaning strips trailing date (and trailing prog-number suffixes when present).

### Radio shortwave (Program 2 / `*SW`) — two titles + embedded program refs

Example Title cell for `1151SW`:

```text
The Power of the Holy Spirit in You 1151R3 / The Functions of the Holy Spirit 1151R4R5
```

- Black: two program titles joined with ` / `
- Red (human only): cross-refs to the Mon–Fri (or related) program numbers those pieces came from  
- Program Number column still holds the canonical id: `1151SW`

This is **one shortwave hour composed of two programs**, not a single title with a recorded date.

**Parser behavior** (`update_shortwave_schedule.py`):

- Selects CSV rows whose `program_number` ends with `SW`.
- Stricter cleaning than radio: dates and program-number tokens removed **anywhere** in the string; parentheticals removed; whitespace / `- -` collapsed.
- Public schedule keeps the combined titles and the ` / ` separator, e.g.:

  ```text
  Fri, Jul 24, 2026: The Power of the Holy Spirit in You / The Functions of the Holy Spirit
  ```

---

## Red text is overloaded

| Context | Typical black text | Typical red text | Machine meaning today |
|---|---|---|---|
| KAZQ / radio Program 1 Title | Program name | Trailing recorded date | Date via **trailing text** regex |
| Radio SW Title | `Title A / Title B` | Embedded prog refs (`1151R3`, …) | Refs via **prog-number** regex; dual title via ` / ` |
| Day header cells, etc. | — | (fills / labels) | Layout / day markers; not title color |

Implication: **“red = date” is false for shortwave.** Color cannot be the sole signal for either “strip this” or “this is a date.”

---

## What the parsers rely on instead

1. **Columns** — e.g. air/sent codes (KAZQ), Program Number, week headers, day blocks (radio).
2. **Stable text patterns**
   - Trailing dates: `MM/DD/YY` or `MM/DD/YYYY`
   - Program tokens: `####R[1-5]`, `####SW`, `####Sun` (and related)
   - SW multi-title: ` / ` between titles
3. **Slot / program_number** — e.g. `*SW` rows get shortwave cleaning; slot 1 drives radio schedule.

---

## Known text edge case

Compound program refs such as `1151R4R5` (two R-slots glued) do not always match the current “single suffix” style regex cleanly. Cleaning may leave a stray fragment (e.g. residual `1151R`) instead of removing the whole token. Normal single refs like `1151R3` strip fine.

Options if that form stays in the sheets:

- Document allowed token shapes and extend the cleaner, or  
- Prefer clearer writing (`1151R4 1151R5`), or  
- Move sources into a dedicated column.

---

## Redesign talking points (with Vance)

- Mixed-use Title is **already supported** for:
  - title + trailing date  
  - dual title + embedded prog refs (SW)
- Red can remain as **operator UX**; it is not required for parsing.
- Prefer for new / cleaner sheets:
  - **Title** — display text only  
  - **Recorded date** — real date column  
  - **Source / composed-of program numbers** — especially for SW dual hours  
- Keep color if it helps workflow; **do not make color a required machine contract**.
- If color-aware parsing is ever added: rich-text support + always keep text/column fallback.

---

## Code map

| Spreadsheet | Updater | Public / intermediate output |
|---|---|---|
| KAZQ.xlsx | `update_tv_schedule.py` | `docs/tv-schedule.txt` |
| Warning! Radio – Air Date Record.xlsx (WATV Radio NOTES) | `update_radio_programs.py` | `Intra Support Files/radio_programs.csv`, `docs/radio-schedule.txt` |
| Same radio CSV, `*SW` rows | `update_shortwave_schedule.py` | `docs/shortwave-schedule.txt` |

See also: `WorkToDo/Radio Program Parsing.MD`, `info/feeds-and-schedules.md`, root `README.md`.
