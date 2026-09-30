#!/usr/bin/env python3
import base64
import json
from datetime import datetime, timezone
from pathlib import Path

root = Path(__file__).resolve().parents[2]
itinerary_path = root / "docs/international-itinerary.json"
patch_path = root / "docs/kzn-tongaat-events-patch.json"
assets = root / "docs/itinerary-assets"

for f in sorted(assets.glob("*.jpg.b64")):
    out = assets / f.name[:-4]  # remove trailing .b64
    out.write_bytes(base64.b64decode(f.read_text()))
    f.unlink()
    print(f"Decoded {out.name} ({out.stat().st_size} bytes)")

data = json.loads(itinerary_path.read_text())
patch = json.loads(patch_path.read_text())
by_id = {e.get("id"): i for i, e in enumerate(data["events"])}
for ev in patch["events"]:
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
print("eventCount", data["eventCount"])
