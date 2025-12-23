from __future__ import annotations

import json
from datetime import datetime, timezone

import pytest
from fastapi.testclient import TestClient

from app.config import settings
from app.main import app


client = TestClient(app)


def _iso_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _valid_load(load_id: str = "L-1") -> dict:
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
def _restore_auth_settings():
    old_enabled = settings.auth_enabled
    old_key = settings.admin_api_key
    yield
    settings.auth_enabled = old_enabled
    settings.admin_api_key = old_key


def test_auth_disabled_allows_sensitive_endpoints(_restore_auth_settings) -> None:
    settings.auth_enabled = False
    settings.admin_api_key = "test-key"

    # Connector metadata endpoint
    resp = client.get("/api/ingestion/sources")
    assert resp.status_code == 200

    # Ingestion run endpoint (will be 409 if ingestion disabled, but must not be 401)
    resp = client.post("/api/ingestion/run")
    assert resp.status_code in (200, 409)

    # Import endpoint (valid JSON)
    payload = json.dumps([_valid_load("L-1")]).encode("utf-8")
    resp = client.post("/api/import", params={"filename": "loads.json"}, data=payload)
    assert resp.status_code == 200


def test_auth_enabled_requires_key(_restore_auth_settings) -> None:
    settings.auth_enabled = True
    settings.admin_api_key = "secret"

    resp = client.get("/api/ingestion/sources")
    assert resp.status_code == 401

    resp = client.post("/api/ingestion/run")
    assert resp.status_code == 401

    payload = json.dumps([_valid_load("L-1")]).encode("utf-8")
    resp = client.post("/api/import", params={"filename": "loads.json"}, data=payload)
    assert resp.status_code == 401


def test_auth_enabled_accepts_bearer_and_x_api_key(_restore_auth_settings) -> None:
    settings.auth_enabled = True
    settings.admin_api_key = "secret"

    payload = json.dumps([_valid_load("L-1")]).encode("utf-8")

    # Bearer
    resp = client.post(
        "/api/import",
        params={"filename": "loads.json"},
        data=payload,
        headers={"Authorization": "Bearer secret"},
    )
    assert resp.status_code == 200

    # X-API-Key
    resp = client.get(
        "/api/ingestion/sources",
        headers={"X-API-Key": "secret"},
    )
    assert resp.status_code == 200
