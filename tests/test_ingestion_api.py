from __future__ import annotations

from fastapi.testclient import TestClient

from app.main import app


def test_ingestion_endpoints_exist_when_disabled() -> None:
    client = TestClient(app)

    status = client.get("/api/ingestion/status")
    assert status.status_code == 200
    payload = status.json()
    assert payload["enabled"] in (False, True)

    sources = client.get("/api/ingestion/sources")
    assert sources.status_code == 200
    payload2 = sources.json()
    assert "enabled" in payload2
    assert "sources" in payload2

    run = client.post("/api/ingestion/run")
    # Default settings have ingestion disabled.
    assert run.status_code in (409, 200)
    if run.status_code == 409:
        assert "detail" in run.json()
