from fastapi.testclient import TestClient

from routecast_api.main import app
from routecast_core.models import Coordinate

client = TestClient(app)


def test_health_ok():
    resp = client.get("/health")
    assert resp.status_code == 200
    assert resp.json()["status"] == "ok"


def test_route_stub():
    payload = {
        "origin": {"lat": 0, "lon": 0},
        "destination": {"lat": 1, "lon": 1},
    }
    resp = client.post("/route", json=payload)
    assert resp.status_code == 200
    body = resp.json()
    assert body["provider"]
    assert body["polyline"]
    assert body["duration_seconds"] > 0


def test_route_score_stub():
    payload = {
        "origin": {"lat": 0, "lon": 0},
        "destination": {"lat": 1, "lon": 1},
    }
    resp = client.post("/route/score", json=payload)
    assert resp.status_code == 200
    body = resp.json()
    assert "overall" in body
    assert "risk_score" in body
    assert "reasons" in body
    assert "confidence" in body
    assert "polyline" in body and body["polyline"]
    assert "provider" in body
