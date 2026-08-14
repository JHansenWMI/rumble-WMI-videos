#!/usr/bin/env python3
import unittest

from delete_from_feed import item_matches, parse_target
from generate_rumble_feed import item_identity_keys


class ParseTargetTests(unittest.TestCase):
    def test_guid(self):
        self.assertEqual(parse_target("443372718"), {"guid": "443372718"})

    def test_slug(self):
        self.assertEqual(parse_target("v7e5jq2"), {"slug": "v7e5jq2"})

    def test_url(self):
        self.assertEqual(
            parse_target("https://rumble.com/v7e5jq2-sderot-israel-trip-march-2012-part-3.html"),
            {
                "link": "https://rumble.com/v7e5jq2-sderot-israel-trip-march-2012-part-3.html",
                "slug": "v7e5jq2",
            },
        )


class MatchTests(unittest.TestCase):
    item = {
        "title": "Sderot Israel Trip March 2012 Part 3",
        "link": "https://rumble.com/v7e5jq2-sderot-israel-trip-march-2012-part-3.html",
        "guid": "443372718",
        "videoId": "v7bz0ku",
    }

    def test_guid_match(self):
        self.assertTrue(item_matches(self.item, [parse_target("443372718")]))

    def test_url_match(self):
        self.assertTrue(
            item_matches(
                self.item,
                [parse_target("https://rumble.com/v7e5jq2-sderot-israel-trip-march-2012-part-3.html")],
            )
        )

    def test_embed_slug_match(self):
        self.assertTrue(item_matches(self.item, [parse_target("v7bz0ku")]))

    def test_other_guid_no_match(self):
        self.assertFalse(item_matches(self.item, [parse_target("443285196")]))


class IdentityKeyTests(unittest.TestCase):
    def test_add_or_remove_changes_set(self):
        before = [{"guid": "1", "link": "https://rumble.com/a.html"}]
        after = [{"guid": "2", "link": "https://rumble.com/b.html"}]
        self.assertNotEqual(item_identity_keys(before), item_identity_keys(after))

    def test_field_edit_keeps_set(self):
        before = [{"guid": "1", "link": "https://rumble.com/a.html", "title": "Old"}]
        after = [{"guid": "1", "link": "https://rumble.com/a.html", "title": "New"}]
        self.assertEqual(item_identity_keys(before), item_identity_keys(after))


if __name__ == "__main__":
    unittest.main()
