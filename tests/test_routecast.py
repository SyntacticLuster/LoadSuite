from __future__ import annotations

import urllib.error

from fastapi.testclient import TestClient

from app.config import settings
from app.main import app
from app.services.routecast_client import RouteCastClient
from app.routecast_cache import RouteCastCache


client = TestClient(app)


ROUTECAST_PAYLOAD = {
    "origin": {"lat": 33.7490, "lon": -84.3880},
    "destination": {"lat": 41.8781, "lon": -87.6298},
    "via": [],
    "equipment_type": "Dry Van",
    "weight_lbs": 40000,
}


def _reset_routecast_state() -> None:
    app.state.ctx.routecast_client = None
    app.state.ctx.routecast_cache = RouteCastCache(
        ttl_seconds=settings.routecast_cache_ttl_seconds,
        negative_ttl_seconds=settings.routecast_negative_cache_ttl_seconds,
    )


def test_routecast_disabled_returns_501(monkeypatch):
    monkeypatch.setattr(settings, "routecast_enabled", False)
    _reset_routecast_state()

    resp = client.post("/api/routecast/score", json=ROUTECAST_PAYLOAD)
    assert resp.status_code == 501
    assert "disabled" in resp.json()["detail"].lower()


def test_routecast_success(monkeypatch):
    monkeypatch.setattr(settings, "routecast_enabled", True)
    _reset_routecast_state()

    def fake_send(self, payload):
        return 200, {
            "overlays": [{"id": "o1"}],
            "overall": 82.0,
            "summary": "ok",
            "reasons": ["clear_path"],
            "provider": settings.routecast_provider,
            "confidence": "high",
        }

    monkeypatch.setattr(RouteCastClient, "_send", fake_send)

    resp = client.post("/api/routecast/score", json=ROUTECAST_PAYLOAD)
    assert resp.status_code == 200
    data = resp.json()
    assert data["risk_score"] == 82.0
    assert data["summary"] == "ok"
    assert data["provider"] == settings.routecast_provider
    assert data["overlays"]
    assert data["reasons"] == ["clear_path"]


def test_routecast_failure_degraded(monkeypatch):
    monkeypatch.setattr(settings, "routecast_enabled", True)
    _reset_routecast_state()

    def fake_send(_self, _payload):
        raise urllib.error.URLError("boom")

    monkeypatch.setattr(RouteCastClient, "_send", fake_send)

    resp = client.post("/api/routecast/score", json=ROUTECAST_PAYLOAD)
    assert resp.status_code == 200
    data = resp.json()
    assert data["risk_score"] is None
    assert data["summary"] == "Route risk unavailable"
    assert data["confidence"] == "degraded"
    assert "routecast" in data["reasons"][0]


def test_routecast_cache_hits(monkeypatch):
    monkeypatch.setattr(settings, "routecast_enabled", True)
    _reset_routecast_state()
    calls = {"count": 0}

    def fake_send(self, payload):
        calls["count"] += 1
        return 200, {
            "overlays": [],
            "overall": 50.0,
            "summary": "cached",
            "reasons": ["first"],
            "provider": settings.routecast_provider,
            "confidence": "ok",
        }

    monkeypatch.setattr(RouteCastClient, "_send", fake_send)

    resp1 = client.post("/api/routecast/score", json=ROUTECAST_PAYLOAD)
    resp2 = client.post("/api/routecast/score", json=ROUTECAST_PAYLOAD)

    assert resp1.status_code == 200
    assert resp2.status_code == 200
    assert calls["count"] == 1
    assert resp2.json()["summary"] == "cached"
