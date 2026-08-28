# `docs/` — website data

Generated and supporting files **served or fetched by the public site** (GitHub Pages). Longer project notes: [`info/feeds-and-schedules.md`](../info/feeds-and-schedules.md).

- **Feeds / schedules:** `rumble-feed.json`, `overcoming-feed.json`, `tv-feed.json`, `*-schedule.txt`, archives, URL lists, Podbean match maps.
- **TV thumbs (no Rumble video yet):** `tv-thumbs/YYYYMMDD.jpg` — see `tv-thumbs/README.md`. Widget also falls back to CMS `Userfiles/video-thumbs/`.
- **Site thumbs (Watch Warning card ≠ Rumble thumb):** `site-thumbs/` — see `site-thumbs/README.md`. Point `OVERRIDES_BY_GUID[guid].thumb` at the GitHub Pages URL.
- **Widgets:** `widgets/*.css` and `widgets/*.js` — loaded by thin CMS shells at repo root (`*-cms.html`). Edits here go live after push; CMS paste only when the shell itself changes.
