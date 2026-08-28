# Hide from the website while the video is still on Rumble (or may come back
# on the next scrape). The generator accumulates history, so a live Rumble
# video will reappear unless it stays in this set.
#
# If you already deleted the video on Rumble, do not add it here.
# Purge our accumulated copy instead:
#   python delete_from_feed.py GUID
#   ./publish_rumble_feed.sh
from dataclasses import replace

REMOVE_GUIDS = {
    "434910718",  # Duplicate part listing
    "434910604",  # Duplicate part listing
}

SITE_THUMB_BASE = "https://jhansenwmi.github.io/rumble-WMI-videos/site-thumbs/"

OVERRIDES_BY_GUID = {
    "435104480": {
        "pub_date": "Thu, 29 Apr 2026 22:07:53 -0400",
    },
    "434910266": {
        "title": "Reverends Dr. Jonathan Hansen & Dr Adalia Hansen - Deliverance Church Kitengala Kenya",
    },
    # Watch Warning card only; Rumble keeps its own thumb.
    "444441534": {
        "thumb": SITE_THUMB_BASE + "take-the-territory-16x9.jpg",
    },
}

_FEEDITEM_FIELDS = {
    "title",
    "link",
    "pub_date",
    "thumb",
    "source_page",
    "video_code",
    "video_embed_id",
    "channel_name",
    "channel_url",
    "scheduled_time",
}


def apply_custom_updates(items, parse_datetime):
    fixed = []

    for item in items:
        if item.video_id in REMOVE_GUIDS:
            continue

        overrides = OVERRIDES_BY_GUID.get(item.video_id)
        if not overrides:
            fixed.append(item)
            continue

        fields = {key: overrides[key] for key in _FEEDITEM_FIELDS if key in overrides}
        if "pub_date" in overrides:
            pub_date, parsed_timestamp = parse_datetime(overrides["pub_date"])
            fields["pub_date"] = pub_date
            if parsed_timestamp != float("-inf"):
                fields["timestamp"] = parsed_timestamp

        fixed.append(replace(item, **fields) if fields else item)

    fixed.sort(key=lambda item: item.timestamp, reverse=True)
    return fixed
