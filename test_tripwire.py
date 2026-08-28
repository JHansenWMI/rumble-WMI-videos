#!/usr/bin/env python3
from __future__ import annotations

import unittest
from pathlib import Path
from tempfile import TemporaryDirectory

from generate_rumble_feed import parse_embedded_listing_items, tripwire_fingerprint
from rumble_tripwire import load_state, merge_fingerprints, save_state

TWO_ARRAYS_HTML = """
<html><body>
<script>
{"items":[{"object_type":"video","id":1,"title":"Top Shelf Upcoming","url":"https://rumble.com/v1-a.html","upload_date":"2026-08-27T02:41:21+00:00","live_datetime":"2026-08-27T15:00:00+00:00"}]}
</script>
<script>
{"items":[{"object_type":"video","id":2,"title":"Overcoming Talk","url":"https://rumble.com/v2-b.html","upload_date":"2026-08-20T01:00:00+00:00","live_datetime":null},{"object_type":"video","id":3,"title":"Warning TV Show","url":"https://rumble.com/v3-c.html","upload_date":"2026-08-21T01:00:00+00:00","live_datetime":null}]}
</script>
</body></html>
"""


class TripwireFingerprintTests(unittest.TestCase):
    def test_unions_all_listing_arrays(self):
        fp = tripwire_fingerprint(TWO_ARRAYS_HTML)
        self.assertIn("1\tTop Shelf Upcoming\t2026-08-27T15:00:00+00:00", fp)
        self.assertIn("2\tOvercoming Talk\t", fp)
        self.assertIn("3\tWarning TV Show\t", fp)
        self.assertEqual(fp.count("\n"), 3)

    def test_full_parser_still_uses_first_array_only(self):
        items = parse_embedded_listing_items(TWO_ARRAYS_HTML, "https://rumble.com/user/DrJonathanHansenWMI")
        self.assertEqual(len(items), 1)
        self.assertEqual(items[0].title, "Top Shelf Upcoming")

    def test_live_datetime_change_alters_fingerprint(self):
        after = TWO_ARRAYS_HTML.replace(
            "2026-08-27T15:00:00+00:00",
            "null",
        )
        self.assertNotEqual(tripwire_fingerprint(TWO_ARRAYS_HTML), tripwire_fingerprint(after))

    def test_view_churn_fields_are_ignored(self):
        extra = TWO_ARRAYS_HTML.replace(
            '"live_datetime":null}',
            '"live_datetime":null,"views":99,"watching_now":3}',
        )
        self.assertEqual(tripwire_fingerprint(TWO_ARRAYS_HTML), tripwire_fingerprint(extra))

    def test_state_roundtrip(self):
        fp = tripwire_fingerprint(TWO_ARRAYS_HTML)
        with TemporaryDirectory() as tmp:
            path = Path(tmp) / "state"
            save_state(path, fp)
            self.assertEqual(load_state(path), fp)

    def test_merge_includes_shorts_not_in_all_ssr(self):
        all_fp = tripwire_fingerprint(TWO_ARRAYS_HTML)
        shorts_html = """
        <html><body><script>
        {"items":[{"object_type":"video","id":444441534,"title":"Pastor Hansen prays for the Jesso's to take the territory","url":"https://rumble.com/shorts/v7esa7o","upload_date":"2026-08-28T21:36:00+00:00","live_datetime":null,"is_short":true}]}
        </script></body></html>
        """
        shorts_fp = tripwire_fingerprint(shorts_html)
        merged = merge_fingerprints([all_fp, shorts_fp])
        self.assertIn("1\tTop Shelf Upcoming\t2026-08-27T15:00:00+00:00", merged)
        self.assertIn("444441534\tPastor Hansen prays for the Jesso's to take the territory\t", merged)
        self.assertNotIn("444441534", all_fp)

    def test_merge_dedupes_overlap(self):
        fp = tripwire_fingerprint(TWO_ARRAYS_HTML)
        merged = merge_fingerprints([fp, fp])
        self.assertEqual(merged, fp)


if __name__ == "__main__":
    unittest.main()
