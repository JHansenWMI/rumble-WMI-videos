__version__ = "2026.05.07-v2"

import json
from datetime import datetime
import yt_dlp

# Correct channels requested by user
CHANNELS = [
    "https://rumble.com/c/WarningTVJonathanHansen/videos",
    "https://rumble.com/c/WarningTVJonathanHansen/shorts",
    "https://rumble.com/c/WarningTVJonathanHansen/livestreams",
]

print(f"v{__version__} - Fetching videos from WMI WarningTV sections...")

all_videos = []

# Headers that work well
ydl_opts = {
    'extract_flat': True,
    'quiet': True,
    'ignoreerrors': True,
    'playlistend': 500,
    'http_headers': {
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36',
        'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,*/*;q=0.8',
        'Accept-Language': 'en-US,en;q=0.9',
        'Referer': 'https://rumble.com/',
        'DNT': '1',
    },
    'extractor_args': {'rumble': {'force': True}},
    'sleep_interval': 1,
    'max_sleep_interval': 3,
}

for url in CHANNELS:
    section = url.split('/')[-1].capitalize()
    print(f"   → Fetching {section}...")
    try:
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            info = ydl.extract_info(url, download=False)

        entries = info.get('entries', []) if info else []
        print(f"     Found {len(entries)} items")

        for entry in entries:
            if not entry:
                continue
            raw_url = entry.get('url', '')
            if not raw_url:
                continue
            
            # Generate a readable title from the URL slug
            slug = raw_url.split('/')[-1].split('?')[0].replace('.html', '')
            title = slug.replace('-', ' ').replace('_', ' ').title()
            
            video = {
                'title': title,
                'url': raw_url if raw_url.startswith('http') else f"https://rumble.com{raw_url}",
                'id': entry.get('id'),
                'type': url.split('/')[-1],
            }
            all_videos.append(video)
    except Exception as e:
        print(f"   ⚠️ Error on {url}: {type(e).__name__}: {e}")

# Sort newest first (by position since we don't have dates from flat extraction)
all_videos = all_videos[:300]  # Reasonable limit

output = {
    "last_updated": datetime.now().isoformat(),
    "total_videos": len(all_videos),
    "sources_checked": len(CHANNELS),
    "videos": all_videos
}

with open('videos.json', 'w', encoding='utf-8') as f:
    json.dump(output, f, indent=2, ensure_ascii=False)

print(f"\n✅ Done! Total videos saved: {len(all_videos)}")
