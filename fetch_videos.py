import json
from datetime import datetime
import yt_dlp

# Correct channels requested by user
CHANNELS = [
    "https://rumble.com/c/WarningTVJonathanHansen/videos",
    "https://rumble.com/c/WarningTVJonathanHansen/shorts",
    "https://rumble.com/c/WarningTVJonathanHansen/livestreams",
]

print("🚀 Fetching videos from WMI WarningTV sections...")

all_videos = []

# Enhanced options to avoid 403 blocking
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
        'Connection': 'keep-alive',
        'Upgrade-Insecure-Requests': '1',
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
            # Skip entries without proper title or url
            if not entry.get('title') or not entry.get('url'):
                continue
            video = {
                'title': entry.get('title'),
                'url': entry.get('url') if entry.get('url', '').startswith('http') else f"https://rumble.com{entry.get('url')}",
                'id': entry.get('id'),
                'duration': entry.get('duration'),
                'upload_date': entry.get('upload_date'),
                'view_count': entry.get('view_count'),
                'type': url.split('/')[-1],
            }
            all_videos.append(video)
    except Exception as e:
        print(f"   ⚠️ Error on {url}: {e}")

# Sort newest first
all_videos.sort(key=lambda x: x.get('upload_date') or '19000101', reverse=True)

output = {
    "last_updated": datetime.now().isoformat(),
    "total_videos": len(all_videos),
    "sources_checked": len(CHANNELS),
    "videos": all_videos
}

with open('videos.json', 'w', encoding='utf-8') as f:
    json.dump(output, f, indent=2, ensure_ascii=False)

print(f"\n✅ Done! Total videos saved: {len(all_videos)}")
