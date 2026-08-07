# Side note: Itinerary data on GitHub Pages

**Hub plan:** `~/dev/WMIMediaOperations/PLAN_Itinerary_Website_Update.md`  
**Status:** International + United States seed JSON, widgets, CMS shells, and MediaSite editors.

## Role of this repo

Near-term consumers are **live CMS pages** (paste into `#content`).  
`wmi-web` is a longer-term full-host replacement and may consume the same files later.

Host **website-facing** itinerary data the same way as TV/radio widgets:

| Path | Purpose |
|------|---------|
| `docs/international-itinerary.json` | International events + intro |
| `docs/united-states-itinerary.json` | US events + intro (same schema, `region: "us"`) |
| `docs/itinerary-assets/` | Event posters (~600px wide) |
| `docs/itinerary-assets/country-flags/` | Country flag GIFs (international) |
| `docs/itinerary-assets/state-flags/` | US state / DC flag GIFs |
| `docs/widgets/International-Itinerary.js` + `.css` | Live international widget |
| `docs/widgets/United-States-Itinerary.js` + `.css` | Live US widget |
| `docs/itinerary-preview-international.html` | Offline/GH preview harness |
| `docs/itinerary-preview-united-states.html` | Offline/GH preview harness |
| `International-Itinerary-cms.html` | Paste into live CMS `#content` |
| `United-States-Itinerary-cms.html` | Paste into live CMS `#content` |

## Flags

- International → `country-flags/`
- United States → **one flag per state** in `state-flags/` (default new-event flag: **Washington**)
- Prefer GH Pages assets over permanent hotlinks to CMS `Userfiles/Flags/`

## MediaSite

| Path | Page |
|------|------|
| `/website/itinerary/international` | International page-preview editor |
| `/website/itinerary/united-states` | United States page-preview editor |

Publish stages both itinerary JSON trees, widgets, flags, and CMS shells via git push to this repo.
