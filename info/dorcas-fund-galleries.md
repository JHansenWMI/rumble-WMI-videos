# Side note: Dorcas Fund galleries on GitHub Pages

**Live page:** https://www.worldministries.org/compassion-in-action.aspx  
**CMS paste (already done):** `Dorcas-Fund-Galleries-cms.html`  
**Status:** One paste. Later photo changes are a git push, not another CMS edit.

## How it is split

The CMS page holds three lines: a mount div, the stylesheet, and the script.  
The page body (vision text, older galleries, Malawi) is `docs/dorcas-fund-galleries.html`.

| Path | Purpose |
|------|---------|
| `docs/dorcas-fund-galleries.html` | Intro, Kenya / US / Israel / Philippines slides, Malawi mount |
| `docs/dorcas-fund/malawi/` | Web JPEGs `malawi-2026-001.jpg` … and the video |
| `docs/dorcas-fund/malawi-2026.txt` | Source filenames, in slide order |
| `docs/widgets/Dorcas-Fund-Galleries.js` | Builds Malawi slides from the count. Inserts the video. |
| `docs/widgets/Dorcas-Fund-Galleries.css` | Wide slides stay 653×490. Narrower windows shrink. |
| `scripts/build_dorcas_malawi_gallery.py` | Resize and rename from the joined folder |
| `docs/dorcas-fund/to-review/` | Local look folder only. Not published. |

Kenya, the United States, Israel, and the Philippines still use pictures already on the CMS (`Userfiles/Dorcas-Fund/`). Only their slide list lives in git. Malawi pictures and the video are files in this repo.

Image addresses must be absolute `jhansenwmi.github.io` URLs. A relative path is requested from worldministries.org and shows a black slide.

## Photo change

Source folder (do not rename those files):  
`~/dev/facebook-media-archive/trips/joined`

Order is filename order in that folder. To move a photo, rename it so it sorts where it belongs.

Web copies are at most 600px wide, JPEG quality 70, named `malawi-2026-001.jpg` upward. The script does not keep a list of those names. It uses `data-count`, and the widget builds `001`, `002`, …

Before publishing, the same resize can be written to `docs/dorcas-fund/to-review/` for a Finder look. That folder is not part of the site and is not committed.

Publish (replaces `docs/dorcas-fund/malawi/*.jpg` and the Malawi block):

```bash
python3 scripts/build_dorcas_malawi_gallery.py --from-folder
```

Then commit and push this repo. Reload the live page. GitHub Pages can take about a minute. The CMS paste does not change.

## Video

`VIDEO_AFTER` in the build script is the photo number the video follows. It is **18** (`malawi-2026-018.jpg`). The file is `malawi-2026-018video.mp4` next to the JPEGs. Arriving on that slide starts playback. When it ends, the gallery moves to the next photo.

Changing only `VIDEO_AFTER` still requires a publish run so the HTML `data-video-after` updates. That run also rewrites the JPEGs.

## Another pack

Add another carousel in `docs/dorcas-fund-galleries.html` with its own `data-sequence` prefix and `data-count`. The widget already fills any element that has those attributes. That does not need a new CMS paste.

Use a new prefix per pack (`malawi-2027-`, not a reuse of `malawi-2026-`). Keep one video insert per carousel (`data-video-after` + `data-video`). Wide size stays the shared CSS cap.
