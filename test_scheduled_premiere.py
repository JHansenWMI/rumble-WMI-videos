#!/usr/bin/env python3
"""Parse upcoming premiere start time from listing JSON and HTML footer."""

from __future__ import annotations

import unittest

from generate_rumble_feed import parse_items

LISTING_HTML = """
<html><body>
<script>
{"items":[{"object_type":"video","title":"The Power of Persistence in Prayer","url":"https://rumble.com/v7epi68-the-power-of-persistence-in-prayer.html","thumb":"https://example.com/thumb.jpg","id":444311882,"permalink_id":"v7epi68","upload_date":"2026-08-27T02:41:21+00:00","live":false,"live_placeholder":true,"live_datetime":"2026-08-27T15:00:00+00:00","livestream_status":1,"by":{"type":"channel","name":"WARNING TV - Jonathan Hansen","url":"https://rumble.com/c/WarningTVJonathanHansen"}}]}
</script>
</body></html>
"""

FOOTER_HTML = """
<section>
<img class="rum-video-thumbnail__image" src="https://example.com/thumb.jpg" alt="The Power of Persistence in Prayer">
<rum-video-thumbnail-footer url="https://rumble.com/v7epi68-the-power-of-persistence-in-prayer.html" video-title="The Power of Persistence in Prayer" time="2026-08-27T02:41:21+00:00" scheduled-time="2026-08-27T15:00:00+00:00" views="0" video-id="444311882" creator-url="https://rumble.com/c/WarningTVJonathanHansen" creator-name="WARNING TV - Jonathan Hansen">
<time datetime="2026-08-27T15:00:00+00:00">Starts Aug 27, 8:00 AM</time>
</rum-video-thumbnail-footer>
</section>
"""


class ScheduledPremiereTests(unittest.TestCase):
    def test_listing_json_live_datetime(self):
        items = parse_items(LISTING_HTML, "https://rumble.com/user/DrJonathanHansenWMI/livestreams")
        self.assertEqual(len(items), 1)
        item = items[0]
        self.assertEqual(item.title, "The Power of Persistence in Prayer")
        self.assertIn("02:41:21", item.pub_date)
        self.assertIn("15:00:00", item.scheduled_time)
        self.assertIn("scheduledTime", item.as_json())

    def test_regular_listing_omits_scheduled_time(self):
        html = LISTING_HTML.replace(
            '"live_datetime":"2026-08-27T15:00:00+00:00"',
            '"live_datetime":null',
        )
        items = parse_items(html, "https://rumble.com/user/DrJonathanHansenWMI/videos")
        self.assertEqual(len(items), 1)
        self.assertEqual(items[0].scheduled_time, "")
        self.assertNotIn("scheduledTime", items[0].as_json())

    def test_html_footer_scheduled_time(self):
        items = parse_items(FOOTER_HTML, "https://rumble.com/user/DrJonathanHansenWMI/livestreams")
        self.assertEqual(len(items), 1)
        item = items[0]
        self.assertEqual(item.title, "The Power of Persistence in Prayer")
        self.assertIn("15:00:00", item.scheduled_time)
        self.assertTrue(item.thumb.endswith("thumb.jpg"))


if __name__ == "__main__":
    unittest.main()
