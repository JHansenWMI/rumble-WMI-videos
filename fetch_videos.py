import json
from datetime import datetime
import requests
import re

# Correct channels requested by user
CHANNELS = [
    "https://rumble.com/c/WarningTVJonathanHansen/videos",
    "https://rumble.com/c/WarningTVJonathanHansen/shorts",
    "https://rumble.com/c/WarningTVJonathanHansen/livestreams",
]

print("🚀 Fetching videos from WMI WarningTV sections (using direct HTML parsing)...")

all_videos = []

headers = {
    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36',
    'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8',
    'Accept-Language': 'en-US,en;q=0.9',
    'Referer': 'https://rumble.com/',
}

for url in CHANNELS:
    section = url.split('/')[-1].capitalize()
    print(f"   → Fetching {section}...")
    try:
        resp = requests.get(url, headers=headers, timeout=30)
        if resp.status_code != 200:
            print(f"     HTTP {resp.status_code} - skipping")
            continue
        
        html = resp.text
        
        # Rumble often puts video data in a JSON blob in a script tag
        # Look for common patterns like window.__INITIAL_STATE__ or video list JSON
        videos_found = []
        
        # Try to find video entries in the HTML (common patterns)
        # Pattern 1: data-video-id or rumble video links
        video_links = re.findall(r'href="(/v/[^"]+)"', html)
        titles = re.findall(r'<h3[^>]*class="[^"]*video-item--title[^"]*"[^>]*>([^<]+)</h3>', html, re.IGNORECASE)
        
        print(f"     Found {len(video_links)} video links in HTML")
        
        for i, link in enumerate(video_links[:50]):  # Limit to first 50
            video_url = f"https://rumble.com{link}"
            title = titles[i] if i < len(titles) else f"Video {i+1}"
            videos_found.append({
                'title': title.strip(),
                'url': video_url,
                'id': link.split('/')[-1].split('-')[0] if '-' in link else link,
                'type': url.split('/')[-1],
            })
        
        print(f"     Extracted {len(videos_found)} videos")
        all_videos.extend(videos_found)
        
    except Exception as e:
        print(f"   ⚠️ Error on {url}: {type(e).__name__}: {e}")

# Sort newest first (by position for now, since we don't have dates)
all_videos = all_videos[:200]  # Limit total

output = {
    "last_updated": datetime.now().isoformat(),
    "total_videos": len(all_videos),
    "sources_checked": len(CHANNELS),
    "videos": all_videos
}

with open('videos.json', 'w', encoding='utf-8') as f:
    json.dump(output, f, indent=2, ensure_ascii=False)

print(f"\n✅ Done! Total videos saved: {len(all_videos)}")
