from __future__ import annotations

import asyncio
import json
import os
from pathlib import Path

from app.ingestion.manager import IngestionManager


def _load_payload(load_id: str) -> dict:
    # Minimal canonical Load payload (matches app.models.Load).
    return {
        "id": load_id,
        "origin": {"city": "Atlanta", "state": "GA"},
        "destination": {"city": "Chicago", "state": "IL"},
        "pickup_start": "2024-12-19T20:00:00+00:00",
        "pickup_end": "2024-12-19T22:00:00+00:00",
        "delivery_start": "2024-12-20T12:00:00+00:00",
        "delivery_end": "2024-12-20T16:00:00+00:00",
        "equipment": "Dry Van",
        "weight_lbs": 38000,
        "hazmat": False,
        "distance_miles": 720.0,
        "deadhead_miles": 25.0,
        "rate_total_usd": 2520.0,
        "rpm": 3.5,
        "broker": {"name": "Premium Logistics", "rating": 4.8},
        "detention": False,
        "multi_stop": False,
        "lane_history": True,
        "commodity": "General Freight",
        "posted_at": "2024-12-19T10:00:00+00:00",
        "updated_at": "2024-12-19T11:00:00+00:00",
    }


def _write_json(path: Path, payload: object) -> None:
    path.write_text(json.dumps(payload), encoding="utf-8")


def test_json_dir_tail_cursor_persists_across_manager_restart(tmp_path: Path) -> None:
    drop = tmp_path / "drop"
    drop.mkdir()

    f1 = drop / "a.json"
    f2 = drop / "b.json"

    _write_json(f1, _load_payload("L-1"))
    _write_json(f2, _load_payload("L-2"))

    # Force deterministic mtimes.
    os.utime(f1, (1000, 1000))
    os.utime(f2, (2000, 2000))

    cursor_file = tmp_path / "cursors.json"

    old_env = os.environ.get("INGESTION_CURSOR_STORE_PATH")
    os.environ["INGESTION_CURSOR_STORE_PATH"] = str(cursor_file)
    try:
        manager1 = IngestionManager.from_settings(
            connector_specs=f"json_dir_tail:{drop}",
            quarantine_mode=True,
            default_ttl_seconds=60,
            raw_payload_ttl_seconds=60,
        )
        counts1 = asyncio.run(manager1.run_once())
        assert counts1["fetched_records"] == 2
        assert cursor_file.exists()

        # Add a new file with a newer timestamp.
        f3 = drop / "c.json"
        _write_json(f3, _load_payload("L-3"))
        os.utime(f3, (3000, 3000))

        # New manager instance simulates a process restart.
        manager2 = IngestionManager.from_settings(
            connector_specs=f"json_dir_tail:{drop}",
            quarantine_mode=True,
            default_ttl_seconds=60,
            raw_payload_ttl_seconds=60,
        )
        counts2 = asyncio.run(manager2.run_once())
        assert counts2["fetched_records"] == 1
    finally:
        if old_env is None:
            os.environ.pop("INGESTION_CURSOR_STORE_PATH", None)
        else:
            os.environ["INGESTION_CURSOR_STORE_PATH"] = old_env
