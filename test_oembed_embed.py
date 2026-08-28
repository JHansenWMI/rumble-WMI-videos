#!/usr/bin/env python3
from __future__ import annotations

import unittest

from generate_rumble_feed import FeedItem, parse_oembed_embed_id, parse_video_embed_id


OEMBED = {
    "html": '<iframe src="https://rumble.com/embed/v7clxa6/" width="1080" height="1920"></iframe>'
}

SHORTS_DETAIL_HTML = """
<html><body>
<script>{"permalink_id":"v7esa7o","is_short":true,"id":444441534}</script>
</body></html>
"""


class OembedEmbedTests(unittest.TestCase):
    def test_oembed_iframe_id(self):
        self.assertEqual(parse_oembed_embed_id(OEMBED), "v7clxa6")

    def test_oembed_json_string(self):
        import json

        self.assertEqual(parse_oembed_embed_id(json.dumps(OEMBED)), "v7clxa6")

    def test_shorts_detail_html_has_no_play_embed(self):
        self.assertEqual(parse_video_embed_id(SHORTS_DETAIL_HTML), "")

    def test_shorts_without_embed_id_omits_videoId(self):
        item = FeedItem(
            title="Take the Territory",
            link="https://rumble.com/shorts/v7esa7o",
            pub_date="Fri, 28 Aug 2026 21:36:37 +0000",
            thumb="https://example.com/t.jpg",
            source_page="https://rumble.com/user/DrJonathanHansenWMI/shorts",
            video_id="444441534",
            timestamp=1.0,
            video_code="v7esa7o",
        )
        self.assertNotIn("videoId", item.as_json())

    def test_shorts_with_oembed_id_uses_it(self):
        item = FeedItem(
            title="Take the Territory",
            link="https://rumble.com/shorts/v7esa7o",
            pub_date="Fri, 28 Aug 2026 21:36:37 +0000",
            thumb="https://example.com/t.jpg",
            source_page="https://rumble.com/user/DrJonathanHansenWMI/shorts",
            video_id="444441534",
            timestamp=1.0,
            video_code="v7esa7o",
            video_embed_id="v7clxa6",
        )
        self.assertEqual(item.as_json()["videoId"], "v7clxa6")


if __name__ == "__main__":
    unittest.main()
