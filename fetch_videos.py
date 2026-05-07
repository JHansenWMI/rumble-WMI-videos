import json
from datetime import datetime
import yt_dlp
import traceback

# Correct channels requested by user
CHANNELS = [
    "https://rumble.com/c/WarningTVJonathanHansen/videos",
    "https://rumble.com/c/WarningTVJonathanHansen/shorts",
    "https://rumble.com/c/WarningTVJonathanHansen/livestreams",
]

print("🚀 Fetching videos from WMI WarningTV sections...")

all_videos = []

# Try multiple header sets to bypass 403
header_sets = [
    # Set 1: Standard Chrome on Windows
    {
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36',
        'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,*/*;q=0.8',
        'Accept-Language': 'en-US,en;q=0.9',
        'Referer': 'https://rumble.com/',
        'DNT': '1',
    },
    # Set 2: Firefox on Windows
    {
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:125.0) Gecko/20100101 Firefox/125.0',
        'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,*/*;q=0.8',
        'Accept-Language': 'en-US,en;q=0.5',
        'Referer': 'https://rumble.com/',
    },
]

for url in CHANNELS:
    section = url.split('/')[-1].capitalize()
    print(f"   → Fetching {section}...")
    
    success = False
    for i, headers in enumerate(header_sets):
        ydl_opts = {
            'extract_flat': True,
            'quiet': True,
            'ignoreerrors': True,
            'playlistend': 500,
            'http_headers': headers,
            'extractor_args': {'rumble': {'force': True}},
            'sleep_interval': 2,
            'max_sleep_interval': 5,
        }
        
        try:
            with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                info = ydl.extract_info(url, download=False)

            entries = info.get('entries', []) if info else []
            print(f"     Found {len(entries)} items (using header set {i+1})")

            for entry in entries:
                if not entry:
                    continue
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
            success = True
            break  # If successful, move to next URL
        except Exception as e:
            print(f"   ⚠️ Error with header set {i+1} on {url}: {type(e).__name__}: {e}")
            if i == len(header_sets) - 1:  # Last header set failed
                print(f"   Full traceback for last attempt:")
                traceback.print_exc()

if not success:
    print("   ⚠️ All header sets failed for this section")

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
