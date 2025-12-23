from __future__ import annotations

import json
from datetime import datetime, timezone
import csv
import io

import pytest
from fastapi.testclient import TestClient

from app.config import settings
from app.data import loads_from_csv_bytes
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


def test_import_allows_blank_distance_when_rpm_present(_restore_import_limits) -> None:
    settings.import_max_bytes = 1_000_000
    settings.import_max_records = 10

    now = _iso_now()
    row = {
        "id": "C-blank-distance",
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
        "distance_miles": "",  # blank distance is allowed when rpm is provided
        "deadhead_miles": "50",
        "rate_total_usd": "2500",
        "rpm": "2.5",
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
    assert resp.json()["count"] == 1


def test_import_rejects_blank_distance_when_rpm_missing(_restore_import_limits) -> None:
    settings.import_max_bytes = 1_000_000
    settings.import_max_records = 10

    now = _iso_now()
    row = {
        "id": "C-missing-rpm",
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
        "distance_miles": "",  # missing distance
        "deadhead_miles": "50",
        "rate_total_usd": "2500",
        "rpm": "",  # missing rpm so synthesis should fail cleanly
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

    assert resp.status_code == 400
    assert "distance_miles" in resp.json().get("detail", "")


def test_import_allows_numeric_strings_with_whitespace(_restore_import_limits) -> None:
    settings.import_max_bytes = 1_000_000
    settings.import_max_records = 10

    now = _iso_now()
    row = {
        "id": "C-trimmed",
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
        "distance_miles": " 1000 ",
        "deadhead_miles": "50",
        "rate_total_usd": " 2500 ",
        "rpm": "",  # triggers synthesis using trimmed numbers
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
    assert resp.json()["count"] == 1


def test_import_rejects_non_numeric_distance_or_rate(_restore_import_limits) -> None:
    settings.import_max_bytes = 1_000_000
    settings.import_max_records = 10

    now = _iso_now()
    rows = [
        {
            "id": "C-non-numeric-distance",
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
            "distance_miles": "N/A",
            "deadhead_miles": "50",
            "rate_total_usd": "2500",
            "rpm": "",
            "broker_name": "TestBroker",
            "broker_rating": "4.2",
            "detention": "false",
            "multi_stop": "false",
            "lane_history": "false",
            "commodity": "General",
            "posted_at": now,
            "updated_at": now,
        },
        {
            "id": "C-non-numeric-rate",
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
            "rate_total_usd": "N/A",
            "rpm": "",
            "broker_name": "TestBroker",
            "broker_rating": "4.2",
            "detention": "false",
            "multi_stop": "false",
            "lane_history": "false",
            "commodity": "General",
            "posted_at": now,
            "updated_at": now,
        },
    ]

    payload = _make_csv_payload(rows)
    resp = client.post("/api/import", params={"filename": "loads.csv"}, data=payload)

    assert resp.status_code == 400
    assert any(field in resp.json().get("detail", "") for field in ["distance_miles", "rate_total_usd"])


def test_csv_rpm_zero_is_synthesized() -> None:
    now = _iso_now()
    row = {
        "id": "C-zero-rpm",
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
        "distance_miles": "1000",
        "deadhead_miles": "50",
        "rate_total_usd": "2500",
        "rpm": "0",  # should synthesize
        "broker_name": "TestBroker",
        "broker_rating": "4.2",
        "detention": "false",
        "multi_stop": "false",
        "lane_history": "false",
        "commodity": "General",
        "posted_at": now,
        "updated_at": now,
    }

    loads = loads_from_csv_bytes(_make_csv_payload([row]))
    assert len(loads) == 1
    assert loads[0].rpm == 2.5


def test_csv_non_numeric_rpm_synthesizes_from_rate_and_distance() -> None:
    now = _iso_now()
    row = {
        "id": "C-nonnumeric-rpm",
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
        "rate_total_usd": "2700",
        "rpm": "not-a-number",  # synthesize instead of failing
        "broker_name": "TestBroker",
        "broker_rating": "4.2",
        "detention": "false",
        "multi_stop": "false",
        "lane_history": "false",
        "commodity": "General",
        "posted_at": now,
        "updated_at": now,
    }

    loads = loads_from_csv_bytes(_make_csv_payload([row]))
    assert loads[0].rpm == round(2700 / 900, 3)


def test_csv_rpm_synthesis_requires_rate_and_distance() -> None:
    now = _iso_now()
    row = {
        "id": "C-missing-rate",
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
        "rate_total_usd": "",  # missing for synthesis
        "rpm": "",  # missing triggers synthesis
        "broker_name": "TestBroker",
        "broker_rating": "4.2",
        "detention": "false",
        "multi_stop": "false",
        "lane_history": "false",
        "commodity": "General",
        "posted_at": now,
        "updated_at": now,
    }

    with pytest.raises(ValueError) as excinfo:
        loads_from_csv_bytes(_make_csv_payload([row]))

    assert "rate_total_usd" in str(excinfo.value)
    assert "Row 1" in str(excinfo.value)


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
