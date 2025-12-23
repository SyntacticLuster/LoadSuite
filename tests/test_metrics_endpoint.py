from __future__ import annotations

from fastapi.testclient import TestClient

from app.main import app
from app.metrics import CONTENT_TYPE_LATEST, http_requests_total


client = TestClient(app)


def test_metrics_endpoint_returns_prometheus_text() -> None:
    resp = client.get("/metrics")
    assert resp.status_code == 200
    assert resp.headers.get("content-type") == CONTENT_TYPE_LATEST
    # Basic guard that Prometheus exposition is present
    assert "http_requests_total" in resp.text


def test_metrics_uses_route_template_label() -> None:
    load_id = app.state.ctx.dataset.loads[0].id
    before = http_requests_total.labels("GET", "/api/loads/{load_id}", "200")._value.get()

    resp = client.get(f"/api/loads/{load_id}")
    assert resp.status_code == 200

    after = http_requests_total.labels("GET", "/api/loads/{load_id}", "200")._value.get()
    assert after >= before + 1


def test_metrics_falls_back_to_unknown_route() -> None:
    before = http_requests_total.labels("GET", "unknown_route", "404")._value.get()

    resp = client.get("/does-not-exist")
    assert resp.status_code == 404

    after = http_requests_total.labels("GET", "unknown_route", "404")._value.get()
    assert after >= before + 1
