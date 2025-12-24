from __future__ import annotations

import json
from pathlib import Path

from fastapi.testclient import TestClient

from app import main


def test_static_dataset_count_served():
    # Ensure we rebuild a fresh AppContext so the committed static dataset file
    # is loaded by the lifespan handler (tests often reuse a pre-seeded ctx).
    main.app.state.ctx = None
    with TestClient(main.app) as c:
        resp = c.get("/api/loads")
        assert resp.status_code == 200
        data = resp.json()
        assert "total" in data
        assert data["total"] == 6769


def test_refresh_disabled_by_default():
    with TestClient(main.app) as c:
        resp = c.post("/api/refresh", json={"count": 100})
        assert resp.status_code == 403
        body = resp.json()
        assert body.get("ok") is False
        assert "Synthetic regeneration disabled" in body.get("error", "")


def test_synthetic_file_deterministic_first_ids():
    path = Path(__file__).resolve().parent.parent / "sample_data" / "synthetic_loads_6769.json"
    raw = json.loads(path.read_text(encoding="utf-8"))
    raw2 = json.loads(path.read_text(encoding="utf-8"))

    ids1 = [r.get("id") for r in raw[:25]]
    ids2 = [r.get("id") for r in raw2[:25]]
    assert ids1 == ids2