#!/usr/bin/env python3
"""Rebuild the Malawi 2026 slides in the git-hosted Dorcas galleries.

The live CMS page only mounts this widget. Intro text, the older country
galleries, and these slides are docs/dorcas-fund-galleries.html on GitHub Pages.
Kenya, United States, Israel, and Philippines pictures stay on the CMS
Userfiles URLs already in that file. Malawi pictures are files in this repo.

Photo list (slide order), one filename per line:
  docs/dorcas-fund/malawi-2026.txt

  python3 scripts/build_dorcas_malawi_gallery.py
  python3 scripts/build_dorcas_malawi_gallery.py --src ~/dev/facebook-media-archive/trips/joined

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

# Relative to docs/dorcas-fund-galleries.html so the same file works
# on GitHub Pages and on the local preview server.
IMAGE_BASE = "dorcas-fund/malawi"
MAX_EDGE = 1400
JPEG_QUALITY = 82
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


def export_jpeg(src: Path, dest: Path) -> None:
    with Image.open(src) as im:
        im = ImageOps.exif_transpose(im)
        if im.mode != "RGB":
            im = im.convert("RGB")
        im.thumbnail((MAX_EDGE, MAX_EDGE), Image.Resampling.LANCZOS)
        im.save(dest, "JPEG", quality=JPEG_QUALITY, optimize=True)


def malawi_block(count: int) -> str:
    slides = []
    for n in range(1, count + 1):
        name = f"malawi{n:03d}.jpg"
        slides.append(
            '<div class="swiper-slide">'
            f'<img src="{IMAGE_BASE}/{name}" loading="lazy" '
            f'alt="Dorcas Fund Malawi 2026 picture {n}" />'
            "</div>"
        )
    inner = "\n".join(slides)
    return (
        f"{START}\n"
        "<p>&nbsp;</p>\n"
        '<div class="carousel">\n'
        '<div class="cgroup">Malawi 2026</div>\n'
        f'<div class="swiper" id="carousel-5" data-count="{count}">\n'
        '<div class="swiper-wrapper">\n'
        f"{inner}\n"
        "</div>\n"
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
    for old in OUT_DIR.glob("malawi*.jpg"):
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
        "--seed",
        action="store_true",
        help="Recopy intro and the four older carousels from wmi-web/the-dorcas-fund.html",
    )
    args = parser.parse_args()

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
        dest = OUT_DIR / f"malawi{index:03d}.jpg"
        export_jpeg(args.src / name, dest)
        print(f"{name} -> {dest.name}")

    html = replace_block(html, malawi_block(len(names)))
    FRAGMENT.write_text(html, encoding="utf-8")

    version = version_stamp()
    for path in (WIDGET_JS, CMS_SHELL):
        if path.exists():
            path.write_text(bump_version(path.read_text(encoding="utf-8"), version), encoding="utf-8")
    print(f"Wrote {len(names)} slides, version {version}")


if __name__ == "__main__":
    main()
