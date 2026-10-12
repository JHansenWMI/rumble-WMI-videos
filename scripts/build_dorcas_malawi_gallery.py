#!/usr/bin/env python3
"""Rebuild the Malawi 2026 slides in the git-hosted Dorcas galleries.

The live CMS page only mounts this widget. Intro text, the older country
galleries, and these slides are docs/dorcas-fund-galleries.html on GitHub Pages.
Kenya, United States, Israel, and Philippines pictures stay on the CMS
Userfiles URLs already in that file. Malawi pictures are files in this repo.

Photo list (slide order), one filename per line:
  docs/dorcas-fund/malawi-2026.txt

  python3 scripts/build_dorcas_malawi_gallery.py
  python3 scripts/build_dorcas_malawi_gallery.py --from-folder

Photos are saved at most 600px wide, JPEG quality 70.

--seed recopies the intro and the four existing carousels from
wmi-web/the-dorcas-fund.html, then writes the Malawi block. Use that only
when the older galleries in the CMS copy changed. A normal photo update
does not need --seed.
"""

from __future__ import annotations

import argparse
import re
import sys
from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo

from PIL import Image, ImageOps

REPO = Path(__file__).resolve().parents[1]
DOCS = REPO / "docs"
FRAGMENT = DOCS / "dorcas-fund-galleries.html"
LIST_FILE = DOCS / "dorcas-fund" / "malawi-2026.txt"
OUT_DIR = DOCS / "dorcas-fund" / "malawi"
WIDGET_JS = DOCS / "widgets" / "Dorcas-Fund-Galleries.js"
CMS_SHELL = REPO / "Dorcas-Fund-Galleries-cms.html"
WMI_PAGE = Path.home() / "dev" / "wmi-web" / "the-dorcas-fund.html"

# Absolute, because the CMS injects this HTML into worldministries.org.
# A relative path would be requested from the CMS host and 404.
IMAGE_BASE = "https://jhansenwmi.github.io/rumble-WMI-videos/dorcas-fund/malawi"
MAX_WIDTH = 600
JPEG_QUALITY = 70
START = "<!-- DORCAS_MALAWI_START -->"
END = "<!-- DORCAS_MALAWI_END -->"
DEFAULT_SRC = Path.home() / "dev" / "facebook-media-archive" / "trips" / "joined"


def version_stamp() -> str:
    now = datetime.now(ZoneInfo("America/Los_Angeles"))
    return now.strftime("%Y%m%d") + "a"


def read_list(path: Path) -> list[str]:
    names = []
    for line in path.read_text(encoding="utf-8").splitlines():
        line = line.split("#", 1)[0].strip()
        if line:
            names.append(line)
    if not names:
        sys.exit(f"No photo names in {path}")
    return names


def folder_names(src: Path) -> list[str]:
    names = sorted(
        p.name for p in src.iterdir() if p.is_file() and p.suffix.lower() in {".jpg", ".jpeg"}
    )
    if not names:
        sys.exit(f"No JPGs in {src}")
    return names


def write_list(names: list[str]) -> None:
    header = (
        "# Slide order for the Malawi 2026 carousel.\n"
        "# One source filename per line. Lines starting with # are ignored.\n"
        "# Rebuild this list from every JPG in the source folder:\n"
        "#   python3 scripts/build_dorcas_malawi_gallery.py --from-folder\n"
    )
    LIST_FILE.write_text(header + "\n".join(names) + "\n", encoding="utf-8")


def sequence_name(index: int) -> str:
    """Web copy name. Sources are left unchanged. Slide 1 is malawi-2026-001.jpg."""
    return f"malawi-2026-{index:03d}.jpg"


def export_jpeg(src: Path, dest: Path) -> None:
    with Image.open(src) as im:
        im = ImageOps.exif_transpose(im)
        if im.mode != "RGB":
            im = im.convert("RGB")
        if im.width > MAX_WIDTH:
            height = round(im.height * MAX_WIDTH / im.width)
            im = im.resize((MAX_WIDTH, height), Image.Resampling.LANCZOS)
        im.save(dest, "JPEG", quality=JPEG_QUALITY, optimize=True)


# Extra slide after this photo number. The file sits next to the JPEGs.
VIDEO_AFTER = 18
VIDEO_NAME = "malawi-2026-020-video.mp4"


def malawi_block(count: int) -> str:
    # Slides are not listed here. The widget builds malawi-2026-001.jpg
    # through malawi-2026-NNN.jpg from data-count, and inserts the video
    # after VIDEO_AFTER when that file is present.
    sequence = f"{IMAGE_BASE}/malawi-2026-"
    video_attr = ""
    if (OUT_DIR / VIDEO_NAME).is_file():
        video_attr = (
            f' data-video-after="{VIDEO_AFTER}" '
            f'data-video="{IMAGE_BASE}/{VIDEO_NAME}"'
        )
    return (
        f"{START}\n"
        "<p>&nbsp;</p>\n"
        '<div class="carousel">\n'
        '<div class="cgroup">Malawi 2026</div>\n'
        f'<div class="swiper" id="carousel-5" data-count="{count}" '
        f'data-sequence="{sequence}"{video_attr}>\n'
        '<div class="swiper-wrapper"></div>\n'
        '<div class="swiper-button-next"></div>\n'
        '<div class="swiper-button-prev"></div>\n'
        "</div>\n"
        "</div>\n"
        f"{END}\n"
    )


def replace_block(html: str, block: str) -> str:
    pattern = re.compile(re.escape(START) + r".*?" + re.escape(END) + r"\n?", re.S)
    if not pattern.search(html):
        sys.exit(f"{FRAGMENT} is missing the Malawi markers. Run with --seed.")
    return pattern.sub(block, html, count=1)


def bump_version(text: str, version: str) -> str:
    text = re.sub(
        r'var GALLERIES_VERSION = "[^"]*"',
        f'var GALLERIES_VERSION = "{version}"',
        text,
        count=1,
    )
    text = re.sub(r"\?v=\d{8}[a-z]", f"?v={version}", text)
    return text


def seed_fragment() -> str:
    page = WMI_PAGE.read_text(encoding="utf-8")
    intro_start = page.find('<div style="display: flex;')
    galleries_h = page.find("<h3>Galleries:")
    carousel_start = page.find('<div class="carousel">')
    script_start = page.find("<script", carousel_start)
    if min(intro_start, galleries_h, carousel_start, script_start) < 0:
        sys.exit(f"Could not find the Dorcas galleries in {WMI_PAGE}")
    intro = page[intro_start:galleries_h]
    carousels = page[carousel_start:script_start].strip()
    heading = "<h3>Galleries:&nbsp; Kenya, United States, Israel, Philippines, and Malawi</h3>\n"
    return intro + heading + "\n" + carousels + "\n" + malawi_block(0)


def clear_old_jpegs() -> None:
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    for old in OUT_DIR.glob("*.jpg"):
        old.unlink()


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--src",
        type=Path,
        default=DEFAULT_SRC,
        help="Folder of source JPGs named in the photo list",
    )
    parser.add_argument(
        "--from-folder",
        action="store_true",
        help="Use every JPG in --src, sorted by filename, and rewrite the photo list",
    )
    parser.add_argument(
        "--seed",
        action="store_true",
        help="Recopy intro and the four older carousels from wmi-web/the-dorcas-fund.html",
    )
    args = parser.parse_args()

    if args.from_folder:
        names = folder_names(args.src)
        write_list(names)
    else:
        names = read_list(LIST_FILE)
    missing = [name for name in names if not (args.src / name).is_file()]
    if missing:
        sys.exit("Missing source photos:\n" + "\n".join(missing))

    if args.seed or not FRAGMENT.exists():
        html = seed_fragment()
    else:
        html = FRAGMENT.read_text(encoding="utf-8")

    clear_old_jpegs()
    for index, name in enumerate(names, start=1):
        dest_name = sequence_name(index)
        export_jpeg(args.src / name, OUT_DIR / dest_name)
        print(f"{name} -> {dest_name}")

    html = replace_block(html, malawi_block(len(names)))
    FRAGMENT.write_text(html, encoding="utf-8")

    version = version_stamp()
    for path in (WIDGET_JS, CMS_SHELL):
        if path.exists():
            path.write_text(bump_version(path.read_text(encoding="utf-8"), version), encoding="utf-8")
    print(f"Wrote {len(names)} slides, version {version}")


if __name__ == "__main__":
    main()
