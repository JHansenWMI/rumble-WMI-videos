REMOVE_GUIDS = {
    "434910718",  # Duplicate part listing
    "434910604",  # Duplicate part listing
}

OVERRIDES_BY_GUID = {
    "435104480": {
        "pub_date": "Thu, 29 Apr 2026 22:07:53 -0400",
    },
    "434910266": {
        "title": "Reverends Dr. Jonathan Hansen & Dr Adalia Hansen - Deliverance Church Kitengala Kenya",
    },
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

        pub_date = overrides.get("pub_date", item.pub_date)
        timestamp = item.timestamp
        if "pub_date" in overrides:
            pub_date, parsed_timestamp = parse_datetime(pub_date)
            if parsed_timestamp != float("-inf"):
                timestamp = parsed_timestamp

        fixed.append(
            type(item)(
                title=overrides.get("title", item.title),
                link=overrides.get("link", item.link),
                pub_date=pub_date,
                thumb=overrides.get("thumb", item.thumb),
                source_page=overrides.get("source_page", item.source_page),
                video_id=item.video_id,
                timestamp=timestamp,
            )
        )

    fixed.sort(key=lambda item: item.timestamp, reverse=True)
    return fixed
