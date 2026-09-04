#!/usr/bin/env python3
import json
import tempfile
import unittest
from io import BytesIO
from pathlib import Path
from unittest.mock import patch
from urllib.error import HTTPError, URLError

from generate_rumble_feed import (
    FeedItem,
    prune_deleted_rumble_items,
    purge_gone_from_json_file,
    rumble_video_page_is_gone,
)


def _item(title, link, guid, timestamp, source_page=""):
    return FeedItem(
        title=title,
        link=link,
        pub_date="",
        thumb="",
        source_page=source_page,
        video_id=guid,
        timestamp=timestamp,
    )


LIVE_VOD = _item(
    "The Silence of the Church & the 9 Faces of the Holy Spirit to Save America and the Nations",
    "https://rumble.com/v7f0m9s-the-silence-of-the-church-and-the-9-faces-of-the-holy-spirit-to-save-americ.html",
    "444830410",
    100.0,
    "https://rumble.com/user/DrJonathanHansenWMI/videos",
)
GONE_LIVESTREAM = _item(
    "The Silence of the Church & the 9 Faces of the Holy Spirit to Save America and the Nations",
    "https://rumble.com/v7f0jv0-the-silence-of-the-church-and-the-9-faces-of-the-holy-spirit-to-save-americ.html",
    "444827286",
    90.0,
    "https://rumble.com/user/DrJonathanHansenWMI/livestreams",
)
SCROLLED_OFF = _item(
    "Older video still on Rumble",
    "https://rumble.com/v7old-older-video.html",
    "440000000",
    10.0,
    "https://rumble.com/user/DrJonathanHansenWMI/videos",
)
PAGE1_OLD = _item(
    "Oldest still on page 1",
    "https://rumble.com/v7page1-oldest.html",
    "441000000",
    50.0,
    "https://rumble.com/user/DrJonathanHansenWMI/videos",
)


def _http_error(code, url="https://rumble.com/gone"):
    return HTTPError(url, code, "Gone", None, BytesIO())


class GoneStatusTests(unittest.TestCase):
    def test_410_is_gone(self):
        with patch("generate_rumble_feed.fetch_html", side_effect=_http_error(410)):
            self.assertTrue(rumble_video_page_is_gone("https://rumble.com/gone"))

    def test_404_is_gone(self):
        with patch("generate_rumble_feed.fetch_html", side_effect=_http_error(404)):
            self.assertTrue(rumble_video_page_is_gone("https://rumble.com/gone"))

    def test_200_is_present(self):
        with patch("generate_rumble_feed.fetch_html", return_value="<html></html>"):
            self.assertFalse(rumble_video_page_is_gone("https://rumble.com/still-there"))

    def test_403_is_unknown(self):
        with patch("generate_rumble_feed.fetch_html", side_effect=_http_error(403)):
            self.assertIsNone(rumble_video_page_is_gone("https://rumble.com/blocked"))

    def test_network_error_is_unknown(self):
        with patch("generate_rumble_feed.fetch_html", side_effect=URLError("timeout")):
            self.assertIsNone(rumble_video_page_is_gone("https://rumble.com/flaky"))


class PruneDeletedTests(unittest.TestCase):
    def test_drops_recent_history_item_when_page_is_410(self):
        with patch("generate_rumble_feed.fetch_html", side_effect=_http_error(410)):
            kept, gone = prune_deleted_rumble_items(
                [LIVE_VOD, GONE_LIVESTREAM, SCROLLED_OFF],
                [LIVE_VOD, PAGE1_OLD],
                delay=0,
            )
        self.assertEqual([GONE_LIVESTREAM.link], [item.link for item in gone])
        self.assertEqual(
            [LIVE_VOD.link, SCROLLED_OFF.link],
            [item.link for item in kept],
        )

    def test_keeps_scrolled_off_item_without_fetching(self):
        with patch("generate_rumble_feed.fetch_html") as fetch:
            kept, gone = prune_deleted_rumble_items(
                [SCROLLED_OFF],
                [PAGE1_OLD],
                delay=0,
            )
            fetch.assert_not_called()
        self.assertEqual([], gone)
        self.assertEqual([SCROLLED_OFF.link], [item.link for item in kept])

    def test_keeps_fresh_listing_without_fetching(self):
        with patch("generate_rumble_feed.fetch_html") as fetch:
            kept, gone = prune_deleted_rumble_items(
                [LIVE_VOD],
                [LIVE_VOD],
                delay=0,
            )
            fetch.assert_not_called()
        self.assertEqual([], gone)
        self.assertEqual([LIVE_VOD.link], [item.link for item in kept])

    def test_timeout_keeps_item(self):
        with patch("generate_rumble_feed.fetch_html", side_effect=TimeoutError("boom")):
            kept, gone = prune_deleted_rumble_items(
                [GONE_LIVESTREAM],
                [PAGE1_OLD],
                delay=0,
            )
        self.assertEqual([], gone)
        self.assertEqual([GONE_LIVESTREAM.link], [item.link for item in kept])

    def test_no_fetch_when_disabled(self):
        with patch("generate_rumble_feed.fetch_html") as fetch:
            kept, gone = prune_deleted_rumble_items(
                [GONE_LIVESTREAM],
                [PAGE1_OLD],
                fetch_missing=False,
                delay=0,
            )
            fetch.assert_not_called()
        self.assertEqual([], gone)
        self.assertEqual([GONE_LIVESTREAM.link], [item.link for item in kept])

    def test_empty_fresh_does_not_prune(self):
        with patch("generate_rumble_feed.fetch_html") as fetch:
            kept, gone = prune_deleted_rumble_items([GONE_LIVESTREAM], [], delay=0)
            fetch.assert_not_called()
        self.assertEqual([], gone)
        self.assertEqual([GONE_LIVESTREAM.link], [item.link for item in kept])


class PurgeJsonTests(unittest.TestCase):
    def test_removes_by_guid_and_link(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "feed.json"
            path.write_text(
                json.dumps(
                    {
                        "title": "Rumble videos",
                        "items": [
                            {"guid": "444827286", "link": GONE_LIVESTREAM.link, "title": "gone"},
                            {"guid": "444830410", "link": LIVE_VOD.link, "title": "keep"},
                        ],
                    }
                ),
                encoding="utf-8",
            )
            n = purge_gone_from_json_file(path, {GONE_LIVESTREAM.link}, {"444827286"})
            self.assertEqual(1, n)
            data = json.loads(path.read_text(encoding="utf-8"))
            self.assertEqual(1, data["itemCount"])
            self.assertEqual(["444830410"], [it["guid"] for it in data["items"]])


if __name__ == "__main__":
    unittest.main()
