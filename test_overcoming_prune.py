#!/usr/bin/env python3
import unittest
from pathlib import Path
from unittest.mock import patch

from generate_rumble_feed import (
    ChannelInfo,
    FeedItem,
    is_overcoming_channel,
    is_overcoming_feed_path,
    prune_recategorized_overcoming_items,
)


def _item(title, link, guid, channel_name, channel_url=""):
    return FeedItem(
        title=title,
        link=link,
        pub_date="",
        thumb="",
        source_page="",
        video_id=guid,
        timestamp=1.0,
        channel_name=channel_name,
        channel_url=channel_url,
    )


SDEROT = _item(
    "Sderot Israel Trip March 2012 Part 3",
    "https://rumble.com/v7el060-sderot-israel-trip-march-2012-part-3.html",
    "444101922",
    "The Overcoming Women",
    "https://rumble.com/c/c-7899090",
)
STILL_OW = _item(
    "Igniting the Fire",
    "https://rumble.com/v7dxge8-church-on-fire-conference-rev.-dr.-adalia-hansen.html",
    "442995156",
    "The Overcoming Women",
    "https://rumble.com/c/c-7899090",
)


class ChannelMatchTests(unittest.TestCase):
    def test_name(self):
        self.assertTrue(is_overcoming_channel("The Overcoming Women", ""))
        self.assertTrue(is_overcoming_channel("the overcoming women", ""))
        self.assertFalse(is_overcoming_channel("WARNING TV - Jonathan Hansen", ""))

    def test_url_slug(self):
        self.assertTrue(is_overcoming_channel("", "https://rumble.com/c/c-7899090"))
        self.assertFalse(is_overcoming_channel("", "https://rumble.com/c/WarningTVJonathanHansen"))

    def test_feed_path(self):
        self.assertTrue(is_overcoming_feed_path(Path("docs/overcoming-feed.json")))
        self.assertFalse(is_overcoming_feed_path(Path("docs/rumble-feed.json")))


class PruneTests(unittest.TestCase):
    def test_keeps_fresh_listing_even_if_hint_says_other_channel(self):
        hints = {
            "guid:444101922": ChannelInfo(
                name="WARNING TV - Jonathan Hansen",
                url="https://rumble.com/c/WarningTVJonathanHansen",
            )
        }
        kept = prune_recategorized_overcoming_items(
            [SDEROT],
            {SDEROT.link},
            channel_hints=hints,
            fetch_missing=False,
        )
        self.assertEqual([SDEROT.link], [item.link for item in kept])

    def test_drops_history_when_rumble_feed_says_recategorized(self):
        hints = {
            "guid:444101922": ChannelInfo(
                name="WARNING TV - Jonathan Hansen",
                url="https://rumble.com/c/WarningTVJonathanHansen",
            )
        }
        kept = prune_recategorized_overcoming_items(
            [SDEROT, STILL_OW],
            {STILL_OW.link},
            channel_hints=hints,
            fetch_missing=False,
        )
        self.assertEqual([STILL_OW.link], [item.link for item in kept])

    def test_keeps_history_when_still_overcoming(self):
        hints = {
            "guid:442995156": ChannelInfo(
                name="The Overcoming Women",
                url="https://rumble.com/c/c-7899090",
            )
        }
        kept = prune_recategorized_overcoming_items(
            [STILL_OW],
            set(),
            channel_hints=hints,
            fetch_missing=False,
        )
        self.assertEqual([STILL_OW.link], [item.link for item in kept])

    def test_keeps_history_when_no_hint_and_no_fetch(self):
        kept = prune_recategorized_overcoming_items(
            [SDEROT],
            set(),
            channel_hints={},
            fetch_missing=False,
        )
        self.assertEqual([SDEROT.link], [item.link for item in kept])

    def test_drops_history_after_video_page_fetch(self):
        with patch(
            "generate_rumble_feed.fetch_html", return_value="<html></html>"
        ), patch(
            "generate_rumble_feed.parse_channel_info",
            return_value=ChannelInfo(
                name="WARNING TV - Jonathan Hansen",
                url="https://rumble.com/c/WarningTVJonathanHansen",
            ),
        ), patch("generate_rumble_feed.polite_sleep"):
            kept = prune_recategorized_overcoming_items(
                [SDEROT],
                set(),
                channel_hints={},
                fetch_missing=True,
                delay=0,
            )
        self.assertEqual([], kept)

    def test_keeps_history_when_fetch_fails(self):
        with patch(
            "generate_rumble_feed.fetch_html", side_effect=TimeoutError("boom")
        ), patch("generate_rumble_feed.polite_sleep"):
            kept = prune_recategorized_overcoming_items(
                [SDEROT],
                set(),
                channel_hints={},
                fetch_missing=True,
                delay=0,
            )
        self.assertEqual([SDEROT.link], [item.link for item in kept])


if __name__ == "__main__":
    unittest.main()
