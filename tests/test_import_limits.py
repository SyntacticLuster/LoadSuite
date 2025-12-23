from __future__ import annotations

import json
from datetime import datetime, timezone
import csv
import io

import pytest
from fastapi.testclient import TestClient

from app.config import settings
from app.main import app


client = TestClient(app)


def _iso_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _make_valid_load(load_id: str = "L-1") -> dict:
    now = _iso_now()
    return {
        "id": load_id,
        "origin": {"city": "Chicago", "state": "IL"},
        "destination": {"city": "Dallas", "state": "TX"},
        "pickup_start": now,
        "pickup_end": now,
        "delivery_start": now,
        "delivery_end": now,
        "equipment": "Dry Van",
        "weight_lbs": 40000,
        "hazmat": False,
        "distance_miles": 900.0,
        "deadhead_miles": 50.0,
        "rate_total_usd": 2500.0,
        "rpm": 2.7,
        "broker": {"name": "TestBroker", "rating": 4.2},
        "detention": False,
        "multi_stop": False,
        "lane_history": False,
        "commodity": "General",
        "posted_at": now,
        "updated_at": now,
    }


@pytest.fixture()
def _restore_import_limits():
    old_bytes = settings.import_max_bytes
    old_records = settings.import_max_records
    yield
    settings.import_max_bytes = old_bytes
    settings.import_max_records = old_records


def test_import_accepts_valid_json_array(_restore_import_limits) -> None:
    settings.import_max_bytes = 1_000_000
    settings.import_max_records = 10

    payload = json.dumps([_make_valid_load("L-1")]).encode("utf-8")
    resp = client.post("/api/import", params={"filename": "loads.json"}, data=payload)
    assert resp.status_code == 200
    body = resp.json()
    assert body["ok"] is True
    assert body["source"] == "import:json"
    assert body["count"] == 1


def _make_csv_payload(rows: list[dict[str, str]]) -> bytes:
    buf = io.StringIO()
    writer = csv.DictWriter(buf, fieldnames=list(rows[0].keys()))
    writer.writeheader()
    for r in rows:
        writer.writerow(r)
    return buf.getvalue().encode("utf-8")


def test_import_accepts_valid_csv(_restore_import_limits) -> None:
    settings.import_max_bytes = 1_000_000
    settings.import_max_records = 10

    now = _iso_now()
    row = {
        "id": "C-1",
        "origin_city": "Chicago",
        "origin_state": "IL",
        "destination_city": "Dallas",
        "destination_state": "TX",
        "pickup_start": now,
        "pickup_end": now,
        "delivery_start": now,
        "delivery_end": now,
        "equipment": "Dry Van",
        "weight_lbs": "40000",
        "hazmat": "false",
        "distance_miles": "900",
        "deadhead_miles": "50",
        "rate_total_usd": "2500",
        "rpm": "2.7",
        "broker_name": "TestBroker",
        "broker_rating": "4.2",
        "detention": "false",
        "multi_stop": "false",
        "lane_history": "false",
        "commodity": "General",
        "posted_at": now,
        "updated_at": now,
    }
    payload = _make_csv_payload([row])

    resp = client.post("/api/import", params={"filename": "loads.csv"}, data=payload)
    assert resp.status_code == 200
    body = resp.json()
    assert body["ok"] is True
    assert body["source"] == "import:csv"
    assert body["count"] == 1


def test_import_rejects_csv_missing_required_columns(_restore_import_limits) -> None:
    settings.import_max_bytes = 1_000_000

    now = _iso_now()
    # Missing pickup_end
    header = [
        "id",
        "origin_city",
        "origin_state",
        "destination_city",
        "destination_state",
        "pickup_start",
        "delivery_start",
        "delivery_end",
        "equipment",
        "weight_lbs",
        "distance_miles",
        "deadhead_miles",
        "rate_total_usd",
        "rpm",
        "posted_at",
        "updated_at",
    ]
    buf = io.StringIO()
    w = csv.writer(buf)
    w.writerow(header)
    w.writerow(
        [
            "C-1",
            "Chicago",
            "IL",
            "Dallas",
            "TX",
            now,
            now,
            now,
            "Dry Van",
            "40000",
            "900",
            "50",
            "2500",
            "2.7",
            now,
            now,
        ]
    )
    payload = buf.getvalue().encode("utf-8")

    resp = client.post("/api/import", params={"filename": "loads.csv"}, data=payload)
    assert resp.status_code == 400


def test_import_rejects_csv_too_many_records(_restore_import_limits) -> None:
    settings.import_max_bytes = 1_000_000
    settings.import_max_records = 1

    now = _iso_now()
    base = {
        "origin_city": "Chicago",
        "origin_state": "IL",
        "destination_city": "Dallas",
        "destination_state": "TX",
        "pickup_start": now,
        "pickup_end": now,
        "delivery_start": now,
        "delivery_end": now,
        "equipment": "Dry Van",
        "weight_lbs": "40000",
        "hazmat": "false",
        "distance_miles": "900",
        "deadhead_miles": "50",
        "rate_total_usd": "2500",
        "rpm": "2.7",
        "posted_at": now,
        "updated_at": now,
    }
    rows = [
        {"id": "C-1", **base},
        {"id": "C-2", **base},
    ]
    payload = _make_csv_payload(rows)

    resp = client.post("/api/import", params={"filename": "loads.csv"}, data=payload)
    assert resp.status_code == 400


def test_import_rejects_csv_oversized_payload_413(_restore_import_limits) -> None:
    settings.import_max_bytes = 50

    payload = b"a" * 200
    resp = client.post("/api/import", params={"filename": "loads.csv"}, data=payload)
    assert resp.status_code == 413


def test_import_rejects_non_json_array(_restore_import_limits) -> None:
    settings.import_max_bytes = 1_000_000
    payload = json.dumps({"not": "an array"}).encode("utf-8")
    resp = client.post("/api/import", params={"filename": "loads.json"}, data=payload)
    assert resp.status_code == 400


def test_import_rejects_item_not_object(_restore_import_limits) -> None:
    settings.import_max_bytes = 1_000_000
    payload = json.dumps([123]).encode("utf-8")
    resp = client.post("/api/import", params={"filename": "loads.json"}, data=payload)
    assert resp.status_code == 400


def test_import_rejects_missing_required_fields(_restore_import_limits) -> None:
    settings.import_max_bytes = 1_000_000
    payload = json.dumps(
        [
            {
                "id": "L-1",
                "origin": {"city": "A", "state": "AA"},
                "destination": {"city": "B", "state": "BB"},
            }
        ]
    ).encode("utf-8")

    resp = client.post("/api/import", params={"filename": "loads.json"}, data=payload)
    assert resp.status_code == 400


def test_import_rejects_too_many_records(_restore_import_limits) -> None:
    settings.import_max_bytes = 1_000_000
    settings.import_max_records = 1

    payload = json.dumps([_make_valid_load("L-1"), _make_valid_load("L-2")]).encode("utf-8")
    resp = client.post("/api/import", params={"filename": "loads.json"}, data=payload)
    assert resp.status_code == 400


def test_import_rejects_oversized_payload_413(_restore_import_limits) -> None:
    settings.import_max_bytes = 50

    payload = b"x" * 200
    resp = client.post("/api/import", params={"filename": "loads.json"}, data=payload)
    assert resp.status_code == 413


def test_import_rejects_unsupported_extension(_restore_import_limits) -> None:
    settings.import_max_bytes = 1_000_000

    payload = json.dumps([_make_valid_load("L-1")]).encode("utf-8")
    resp = client.post("/api/import", params={"filename": "loads.txt"}, data=payload)
    assert resp.status_code == 400
