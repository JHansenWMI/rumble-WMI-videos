#!/usr/bin/env python3
from __future__ import annotations

import unittest

from custom_update import apply_custom_updates
from generate_rumble_feed import FeedItem, parse_datetime


def _item(**kwargs) -> FeedItem:
    base = dict(
        title="Original",
        link="https://rumble.com/shorts/v7esa7o",
        pub_date="Fri, 28 Aug 2026 21:36:37 +0000",
        thumb="https://rumble.example/default.jpg",
        source_page="https://rumble.com/user/DrJonathanHansenWMI/shorts",
        video_id="444441534",
        timestamp=1.0,
        channel_name="WARNING TV - Jonathan Hansen",
        channel_url="https://rumble.com/c/WarningTVJonathanHansen",
        video_code="v7esa7o",
    )
    base.update(kwargs)
    return FeedItem(**base)


class CustomUpdateTests(unittest.TestCase):
    def test_site_thumb_override_keeps_channel_fields(self):
        out = apply_custom_updates([_item()], parse_datetime)
        self.assertEqual(len(out), 1)
        item = out[0]
        self.assertTrue(item.thumb.endswith("site-thumbs/take-the-territory-16x9.jpg"))
        self.assertEqual(item.channel_name, "WARNING TV - Jonathan Hansen")
        self.assertEqual(item.video_code, "v7esa7o")
        self.assertEqual(item.title, "Original")


if __name__ == "__main__":
    unittest.main()
