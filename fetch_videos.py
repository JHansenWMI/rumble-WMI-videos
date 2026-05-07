import json
from datetime import datetime
import yt_dlp

# List of Rumble pages to fetch from
CHANNELS = [
    {
        "url": "https://rumble.com/user/DrJonathanHansenWMI/videos",
        "type": "videos"
    },
    {
        "url": "https://rumble.com/user/DrJonathanHansenWMI/shorts",
        "type": "shorts"
    },
    {
        "url": "https://rumble.com/user/DrJonathanHansenWMI/livestreams",
        "type": "livestreams"
    }
]

print("🚀 Fetching videos from 3 WMI Rumble sections...")

all_videos = []

ydl_opts = {
    'extract_flat': True,
    'quiet': True,
    'ignoreerrors': True,
    'playlistend': 500,   # Increase if you need more videos per section
}

for channel in CHANNELS:
    print(f"   → Fetching {channel['type'].upper()}...")
    try:
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            info = ydl.extract_info(channel['url'], download=False)

        for entry in info.get('entries', []):
            if not entry:
                continue
            video = {
                'title': entry.get('title'),
                'url': entry.get('url') if entry.get('url', '').startswith('http') else f"https://rumble.com{entry.get('url')}",
                'id': entry.get('id'),
                'duration': entry.get('duration'),
                'upload_date': entry.get('upload_date'),  # Format: YYYYMMDD
                'view_count': entry.get('view_count'),
                'source': channel['type'],
            }
            all_videos.append(video)
    except Exception as e:
        print(f"   ⚠️ Error fetching {channel['type']}: {e}")

# Sort by upload_date (newest first)
all_videos.sort(key=lambda x: x.get('upload_date') or '19000101', reverse=True)

# Create final JSON with metadata
output = {
    "last_updated": datetime.now().isoformat(),
    "total_videos": len(all_videos),
    "sources": ["videos", "shorts", "livestreams"],
    "videos": all_videos
}

with open('videos.json', 'w', encoding='utf-8') as f:
    json.dump(output, f, indent=2, ensure_ascii=False)

print(f"\n✅ Success! Fetched {len(all_videos)} videos total")
print("   → videos.json created")