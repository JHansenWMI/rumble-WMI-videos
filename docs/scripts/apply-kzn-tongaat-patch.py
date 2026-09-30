#!/usr/bin/env python3
import base64
import html
import json
from datetime import datetime, timezone
from pathlib import Path

root = Path(__file__).resolve().parents[2]
itinerary_path = root / "docs/international-itinerary.json"
patch_path = root / "docs/kzn-tongaat-events-patch.json"
assets = root / "docs/itinerary-assets"

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

for f in sorted(assets.glob("*.jpg.b64")):
    out = assets / f.name[:-4]
    out.write_bytes(base64.b64decode(f.read_text()))
    f.unlink()
    print(f"Decoded {out.name} ({out.stat().st_size} bytes)")

# Assemble patch parts if needed
parts = sorted(root.glob("docs/kzn-tongaat-events-patch.json.p*"))
if parts and not patch_path.exists():
    patch_path.write_text("".join(p.read_text() for p in parts))
    for p in parts:
        p.unlink()
    print("Assembled patch from parts")

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
