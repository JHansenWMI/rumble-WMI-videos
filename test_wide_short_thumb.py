#!/usr/bin/env python3
"""Wide Rumble short thumbs: 9:16 listing tile vs 16:9 OvCc sibling."""

from __future__ import annotations

import io
import unittest
from urllib.error import HTTPError

from PIL import Image

from generate_rumble_feed import (
    FeedItem,
    jpeg_is_landscape,
    jpeg_is_portrait_letterboxed,
    prefer_wide_short_thumbs,
    wide_short_thumb_url,
)


LISTING = (
    "https://hugh.cdn.rumble.cloud/video/fww1/de/s8/1/u/G/_/V/"
    "uG_VA.adyb-small-Baverton-and-Nelspruit-Sund..jpg"
)
WIDE = (
    "https://hugh.cdn.rumble.cloud/video/fww1/de/s8/1/u/G/_/V/"
    "uG_VA.OvCc-small-Baverton-and-Nelspruit-Sund..jpg"
)


def jpeg_bytes(width: int, height: int, paint) -> bytes:
    im = Image.new("RGB", (width, height), (0, 0, 0))
    paint(im)
    buf = io.BytesIO()
    im.save(buf, format="JPEG", quality=95)
    return buf.getvalue()


def letterboxed_9x16() -> bytes:
    # Matches Rumble fitting a wide custom thumb into the shorts tile.
    def paint(im: Image.Image) -> None:
        im.paste((210, 90, 40), (0, 110, 360, 530))

    return jpeg_bytes(360, 640, paint)


def full_bleed_9x16() -> bytes:
    def paint(im: Image.Image) -> None:
        im.paste((40, 90, 180), (0, 0, 360, 640))

    return jpeg_bytes(360, 640, paint)


def poster_9x16_black_bottom() -> bytes:
    # Gateway-style: content at the top, black lower third. Not curtains.
    def paint(im: Image.Image) -> None:
        im.paste((90, 70, 200), (0, 0, 360, 380))
        im.paste((0, 0, 0), (0, 380, 360, 640))

    return jpeg_bytes(360, 640, paint)


def landscape_16x9() -> bytes:
    def paint(im: Image.Image) -> None:
        im.paste((210, 90, 40), (0, 0, 640, 360))

    return jpeg_bytes(640, 360, paint)


def _item(**kwargs) -> FeedItem:
    base = dict(
        title="Baverton and Nelspruit Sunday Service in South Africa",
        link="https://rumble.com/shorts/v7f73f8",
        pub_date="Mon, 07 Sep 2026 14:48:18 +0000",
        thumb=LISTING,
        source_page="https://rumble.com/user/DrJonathanHansenWMI/shorts",
        video_id="445132574",
        timestamp=1.0,
        video_code="v7f73f8",
    )
    base.update(kwargs)
    return FeedItem(**base)


class WideShortThumbUrlTests(unittest.TestCase):
    def test_adyb_small(self):
        self.assertEqual(wide_short_thumb_url(LISTING), WIDE)

    def test_adyb_dot_one_keeps_suffix(self):
        listing = LISTING.replace(".adyb-small-", ".adyb.1-small-")
        self.assertEqual(
            wide_short_thumb_url(listing),
            WIDE.replace(".OvCc-small-", ".OvCc.1-small-"),
        )

    def test_aieb(self):
        listing = LISTING.replace(".adyb-small-", ".aiEB-small-")
        self.assertEqual(wide_short_thumb_url(listing), WIDE)

    def test_adyb_without_small(self):
        listing = "https://cdn.example/Y-iFA.adyb.jpg"
        self.assertEqual(wide_short_thumb_url(listing), "https://cdn.example/Y-iFA.OvCc.jpg")

    def test_already_ovcc(self):
        self.assertIsNone(wide_short_thumb_url(WIDE))

    def test_empty(self):
        self.assertIsNone(wide_short_thumb_url(""))


class LetterboxTests(unittest.TestCase):
    def test_curtains(self):
        self.assertTrue(jpeg_is_portrait_letterboxed(letterboxed_9x16()))

    def test_full_bleed_vertical(self):
        self.assertFalse(jpeg_is_portrait_letterboxed(full_bleed_9x16()))

    def test_poster_with_black_lower_third(self):
        self.assertFalse(jpeg_is_portrait_letterboxed(poster_9x16_black_bottom()))

    def test_landscape_is_not_letterboxed(self):
        self.assertFalse(jpeg_is_portrait_letterboxed(landscape_16x9()))
        self.assertTrue(jpeg_is_landscape(landscape_16x9()))


class PreferWideShortThumbsTests(unittest.TestCase):
    def test_swaps_letterboxed_short(self):
        blobs = {LISTING: letterboxed_9x16(), WIDE: landscape_16x9()}
        out = prefer_wide_short_thumbs([_item()], fetch=blobs.__getitem__)
        self.assertEqual(out[0].thumb, WIDE)

    def test_keeps_full_bleed_short(self):
        blobs = {LISTING: full_bleed_9x16(), WIDE: landscape_16x9()}
        out = prefer_wide_short_thumbs([_item()], fetch=blobs.__getitem__)
        self.assertEqual(out[0].thumb, LISTING)

    def test_keeps_gateway_style_poster(self):
        blobs = {LISTING: poster_9x16_black_bottom(), WIDE: landscape_16x9()}
        out = prefer_wide_short_thumbs([_item()], fetch=blobs.__getitem__)
        self.assertEqual(out[0].thumb, LISTING)

    def test_skips_non_short(self):
        item = _item(
            link="https://rumble.com/v7f73f8-sunday.html",
            source_page="https://rumble.com/user/DrJonathanHansenWMI/videos",
        )
        called = []

        def fetch(url):
            called.append(url)
            return b""

        out = prefer_wide_short_thumbs([item], fetch=fetch)
        self.assertEqual(out[0].thumb, LISTING)
        self.assertEqual(called, [])

    def test_ovcc_403_keeps_listing(self):
        def fetch(url):
            if "OvCc" in url:
                raise HTTPError(url, 403, "Forbidden", hdrs=None, fp=io.BytesIO())
            return letterboxed_9x16()

        out = prefer_wide_short_thumbs([_item()], fetch=fetch)
        self.assertEqual(out[0].thumb, LISTING)

    def test_ovcc_still_portrait_keeps_listing(self):
        blobs = {LISTING: letterboxed_9x16(), WIDE: full_bleed_9x16()}
        out = prefer_wide_short_thumbs([_item()], fetch=blobs.__getitem__)
        self.assertEqual(out[0].thumb, LISTING)


if __name__ == "__main__":
    unittest.main()
