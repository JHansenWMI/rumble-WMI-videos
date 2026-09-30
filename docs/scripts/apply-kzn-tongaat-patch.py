#!/usr/bin/env python3
"""Decode optional itinerary flyer .jpg.b64 sidecars. Never overwrite a valid JPEG (>=5000 bytes)."""
import base64
from pathlib import Path

root = Path(__file__).resolve().parents[2]
assets = root / "docs/itinerary-assets"

for f in sorted(assets.glob("*.jpg.b64")):
    out = assets / f.name[:-4]
    if out.exists() and out.stat().st_size >= 5000:
        raw_existing = out.read_bytes()[:3]
        if raw_existing.startswith(b"\xff\xd8"):
            print(f"Keeping existing {out.name} ({out.stat().st_size} bytes); removing sidecar {f.name}")
            f.unlink()
            continue
    text = f.read_text().strip()
    try:
        raw = base64.b64decode(text, validate=True)
    except Exception as e:
        print(f"Skipping invalid sidecar {f.name}: {e}")
        f.unlink()
        continue
    if (not raw.startswith(b"\xff\xd8\xff")) or len(raw) < 5000:
        print(f"Skipping corrupt sidecar {f.name} ({len(raw)} bytes)")
        f.unlink()
        continue
    out.write_bytes(raw)
    f.unlink()
    print(f"Decoded {out.name} ({out.stat().st_size} bytes)")

for f in sorted(assets.glob("*.jpg.b64.c*")):
    base = f.name.rsplit(".c", 1)[0]
    jpg_name = base[:-4] if base.endswith(".b64") else base
    out = assets / jpg_name
    if out.exists() and out.stat().st_size >= 5000 and out.read_bytes()[:2] == b"\xff\xd8":
        print(f"Keeping {out.name}; removing leftover chunk {f.name}")
        f.unlink()
    else:
        print(f"Leaving chunk {f.name} (no valid JPEG yet for {jpg_name})")

print("Done (no event-patch restore; valid posters are preserved)")
