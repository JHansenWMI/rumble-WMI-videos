# Site thumbs (Watch Warning / social grid)

JPEGs used as **`media:content` overrides** so the website card can differ from Rumble’s thumbnail.

Public URL after push to `main`:

```text
https://jhansenwmi.github.io/rumble-WMI-videos/site-thumbs/<filename>.jpg
```

Wire it in `custom_update.py` `OVERRIDES_BY_GUID` under the video’s `guid` (`thumb` key). The generator applies that after each scrape.
