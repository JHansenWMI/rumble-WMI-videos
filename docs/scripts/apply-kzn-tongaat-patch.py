#!/usr/bin/env python3
import base64
import html
import json
import urllib.request
from collections import defaultdict
from datetime import datetime, timezone
from pathlib import Path

root = Path(__file__).resolve().parents[2]
itinerary_path = root / "docs/international-itinerary.json"
patch_path = root / "docs/kzn-tongaat-events-patch.json"
assets = root / "docs/itinerary-assets"

# Assemble base64 chunks: name.jpg.b64.c00 + c01 + ... -> name.jpg.b64
chunk_map = defaultdict(list)
for f in sorted(assets.glob("*.jpg.b64.c*")):
    base = f.name.rsplit(".c", 1)[0]
    chunk_map[base].append(f)
for base, files in chunk_map.items():
    out = assets / base
    out.write_text("".join(p.read_text() for p in files))
    for p in files:
        p.unlink()
    print(f"Assembled {out.name} from {len(files)} chunks")

for f in sorted(assets.glob("*.jpg.b64")):
    text = f.read_text().strip()
    try:
        raw = base64.b64decode(text, validate=True)
    except Exception as e:
        print(f"Skipping invalid sidecar {f.name} ({len(text)} chars): {e}")
        f.unlink()
        continue
    if (not raw.startswith(b"\xff\xd8\xff")) or len(raw) < 5000:
        print(f"Skipping corrupt sidecar {f.name} ({len(raw)} bytes)")
        f.unlink()
        continue
    out = assets / f.name[:-4]
    out.write_bytes(raw)
    f.unlink()
    print(f"Decoded {out.name} ({out.stat().st_size} bytes)")

# If Oct4 was corrupted by a truncated staging upload, restore last known-good binary
# Only when missing or under 5000 bytes — a freshly decoded valid JPEG (>=5000) must win.
GOOD_OCT4_URL = (
    "https://raw.githubusercontent.com/JHansenWMI/rumble-WMI-videos/"
    "3a2d9cd9c257c53d2686e05d7b28735621a68042/"
    "docs/itinerary-assets/2026-10-04-tongaat-jonathan-hansen.jpg"
)
oct4 = assets / "2026-10-04-tongaat-jonathan-hansen.jpg"
if (not oct4.exists()) or oct4.stat().st_size < 5000:
    with urllib.request.urlopen(GOOD_OCT4_URL) as resp:
        data = resp.read()
    if not data.startswith(b"\xff\xd8\xff") or len(data) < 5000:
        raise SystemExit(f"Good Oct4 restore fetch failed ({len(data)} bytes)")
    oct4.write_bytes(data)
    print(f"Restored {oct4.name} from known-good commit ({len(data)} bytes)")
else:
    print(f"Keeping existing {oct4.name} ({oct4.stat().st_size} bytes)")

# Assemble patch parts if needed
parts = sorted(root.glob("docs/kzn-tongaat-events-patch.json.p*"))
if parts and not patch_path.exists():
    patch_path.write_text("".join(p.read_text() for p in parts))
    for p in parts:
        p.unlink()
    print("Assembled patch from parts")

if not patch_path.exists():
    print("No event patch present; flyer decode / restore only")
    raise SystemExit(0)

def rebuild_body_html(ev):
    flyer = ev.get("flyer") or ""
    flyer_alt = ev.get("flyer_alt") or ""
    place = ev.get("place") or ""
    date_text = ev.get("date_text") or ""
    time_text = ev.get("time_text") or ""
    dt = f"{html.escape(date_text)} — {html.escape(time_text)}" if time_text else html.escape(date_text)
    lines = []
    if ev.get("event_name"):
        lines.append(html.escape(ev["event_name"]))
    speakers = ev.get("speakers") or []
    verb = ev.get("speaker_verb") or "speaking"
    if speakers:
        sp = html.escape(speakers[0])
        lines.append(f"{sp} - Speaking" if verb == "speaking" else f"{sp} {html.escape(verb)}")
    hosts = ev.get("hosts") or []
    if hosts:
        lines.append(f"Host: {html.escape(hosts[0])}")
    if ev.get("venue"):
        lines.append(html.escape(ev["venue"]))
    for a in ev.get("address_lines") or []:
        lines.append(html.escape(a))
    for b in ev.get("body_lines") or []:
        lines.append(html.escape(b))
    img = f'<img src="{flyer}" style="width: 200px; height: auto;" alt="{html.escape(flyer_alt)}" /><br />' if flyer else ""
    return "<p><strong>" + img + f"{html.escape(place)}<br /></strong>{dt}<br />" + "".join(l + "<br />" for l in lines) + "</p>"

data = json.loads(itinerary_path.read_text())
patch = json.loads(patch_path.read_text())
by_id = {e.get("id"): i for i, e in enumerate(data["events"])}
for ev in patch["events"]:
    if not ev.get("body_html"):
        ev["body_html"] = rebuild_body_html(ev)
    eid = ev["id"]
    if eid in by_id:
        data["events"][by_id[eid]] = ev
        print("updated", eid)
    else:
        data["events"].append(ev)
        print("added", eid)
data["events"].sort(key=lambda e: (e.get("sort_date") or "", e.get("id") or ""), reverse=True)
data["eventCount"] = len(data["events"])
now = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
data["generatedAt"] = now
data["lastManualUpdate"] = {"at": now, "note": patch.get("note") or "KZN Tongaat upsert"}
itinerary_path.write_text(json.dumps(data, indent=2, ensure_ascii=False) + "\n")
patch_path.unlink(missing_ok=True)
for p in root.glob("docs/kzn-tongaat-events-patch.json.p*"):
    p.unlink(missing_ok=True)
print("eventCount", data["eventCount"])
