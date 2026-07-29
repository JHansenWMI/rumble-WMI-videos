# TV schedule thumbs (GitHub Pages)

Place **JPEG** files named by **TV air date**:

```text
YYYYMMDD.jpg
```

Example: air date Aug 07, 2026 → `20260807.jpg`

Public URL after push to `main`:

```text
https://jhansenwmi.github.io/rumble-WMI-videos/tv-thumbs/YYYYMMDD.jpg
```

Used by **Warning TV Broadcasts** when there is a schedule line but no matching Rumble video in `tv-feed.json`. The widget also still probes the legacy CMS path:

```text
https://www.worldministries.org/Userfiles/video-thumbs/YYYYMMDD.jpg
```

GitHub path is tried first; CMS is fallback. When a Rumble VOD appears for that air date, the playable card replaces the thumb-only card.

Source stills: prefer title-matched program `.jpg`/`.jpeg` from VideoMedia (operator confirms). Convert/rename to `YYYYMMDD.jpg` here, then commit + push.
