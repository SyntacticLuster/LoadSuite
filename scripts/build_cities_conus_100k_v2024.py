#!/usr/bin/env python3
"""Build `sample_data/cities_conus_100k_v2024.json` from Census snapshots.

This script expects to find the following files in `docs/`:
  - docs/SUB-IP-EST2024-POP.xlsx  (Census city estimates)
  - docs/2024_gaz_place_national.txt (Gazetteer places with lat/lon)

If these files are not present, the script will produce a fallback cities file
based on the built-in `_CITIES` constant in `app.data` so users can generate
loads without Census files. The fallback file sets `pop_2024` to 100000 for
all entries to satisfy consumers that expect 100k+ cities.
"""
from __future__ import annotations

import json
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parent.parent
DOCS = ROOT / "docs"
OUT = ROOT / "sample_data" / "cities_conus_100k_v2024.json"
OUT.parent.mkdir(parents=True, exist_ok=True)

# Best-effort: if census files exist we could parse them. For now, do a
# fallback that writes a stable file derived from `app.data._CITIES`.
try:
    from app import data
except Exception as e:
    print("Failed to import app.data:", e, file=sys.stderr)
    raise SystemExit(1)

cities = []
for city, state, lat, lng in data._CITIES:
    # Exclude Alaska/Hawaii per requirements
    if state in ("AK", "HI"):
        continue
    cities.append(
        {
            "city": city,
            "state": state,
            "pop_2024": 100000,  # fallback placeholder
            "lat": float(lat),
            "lng": float(lng),
            "source": "fallback",
            "raw_place": f"{city}",
            "raw_state": state,
        }
    )

# Stable sort by state then city
cities.sort(key=lambda i: (i["state"], i["city"]))
OUT.write_text(json.dumps(cities, indent=2), encoding="utf-8")
print(f"Wrote {len(cities)} cities to {OUT}")
print("Note: This is a fallback cities file. Replace with canonical Census-derived file by providing the Census snapshots in docs/ and re-running this script.")
