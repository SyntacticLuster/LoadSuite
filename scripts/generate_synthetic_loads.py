#!/usr/bin/env python3
"""Generate a deterministic synthetic loads JSON file.

Usage examples:
  poetry run python scripts/generate_synthetic_loads.py --count 6769 --seed 6769

This script will prefer to load `sample_data/cities_conus_100k_v2024.json` if
present; otherwise it falls back to the built-in in-memory `_CITIES` list. The
output file is written to `sample_data/synthetic_loads_<count>.json` by default.
"""
from __future__ import annotations

import argparse
import json
from datetime import datetime, timezone
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parent.parent
SAMPLE_DIR = ROOT / "sample_data"
SAMPLE_DIR.mkdir(parents=True, exist_ok=True)

DEFAULT_ANCHOR = datetime(2025, 1, 15, 12, 0, 0, tzinfo=timezone.utc)


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser()
    p.add_argument("--cities", default=str(SAMPLE_DIR / "cities_conus_100k_v2024.json"))
    p.add_argument("--count", type=int, default=6769)
    p.add_argument("--seed", type=int, default=6769)
    p.add_argument("--out", default=str(SAMPLE_DIR / f"synthetic_loads_6769.json"))
    args = p.parse_args(argv)

    # Delay import of app.data until args parsed so script is fast when used as a helper
    from app import data

    cities_path = Path(args.cities)
    if cities_path.exists():
        raw = json.loads(cities_path.read_text(encoding="utf-8"))
        # Build a simple list of (city, state, lat, lon)
        cities = []
        for item in raw:
            try:
                cities.append((item["city"], item["state"], float(item["lat"]), float(item["lng"])))
            except Exception:
                raise RuntimeError(f"Invalid city item in {cities_path}: {item}")
        if not cities:
            raise RuntimeError(f"No cities parsed from {cities_path}")
        # Temporarily override the module-level cities for generation
        data._CITIES = cities
    else:
        print(f"Cities file not found at {cities_path}; falling back to built-in city list", file=sys.stderr)

    rng = __import__("random").Random(args.seed)

    ds = data.generate_synthetic_loads(args.count, rng=rng, seed=args.seed, now_override=DEFAULT_ANCHOR)

    out_path = Path(args.out)
    out_path.write_text(json.dumps([l.model_dump(mode="json") for l in ds.loads], indent=2), encoding="utf-8")
    print(f"Wrote {len(ds.loads)} loads to {out_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())