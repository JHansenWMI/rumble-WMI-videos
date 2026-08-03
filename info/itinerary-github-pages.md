# Side note: Itinerary data on GitHub Pages

**Hub plan:** `~/dev/WMIMediaOperations/PLAN_Itinerary_Website_Update.md`  
**Status:** v1 files exist — seed JSON + widget + CMS shell (international).

## Role of this repo

Near-term consumers are **live CMS pages** (paste into `#content`).  
`wmi-web` is a longer-term full-host replacement and may consume the same files later.

Host **website-facing** itinerary data the same way as TV/radio widgets:

| Path | Purpose |
|------|---------|
| `docs/international-itinerary.json` | Event list + intro (seeded from live CMS scrape; events keep `body_html` for fidelity) |
| `docs/united-states-itinerary.json` | Same schema (later) |
| `docs/itinerary-assets/` | Posters (~600px wide) |
| `docs/widgets/International-Itinerary.js` + `.css` | Render for CMS / consumers |
| `docs/itinerary-preview-international.html` | Local/static preview harness |
| `International-Itinerary-cms.html` (repo root) | One-time CMS paste shell |

Live base URL pattern (existing):  
`https://jhansenwmi.github.io/rumble-WMI-videos/…`

## Rules (same as other docs/ data)

- Display logic in **widgets**, not buried in data files.
- CMS shell at repo root is **paste source**; push alone does not update CMS.
- `docs/*` is live after push to GitHub Pages.
- No GitHub Actions for this; local commit/push (see AGENTS.md).

## Writers

MediaSite (planned) writes JSON + assets. Humans may edit JSON carefully if needed. Seed from scrape of live `#content` / `table.events-list`.

## See also

- [feeds-and-schedules.md](./feeds-and-schedules.md) — established feed/widget pattern  
