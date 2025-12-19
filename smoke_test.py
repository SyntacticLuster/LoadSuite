from __future__ import annotations

import json
from pathlib import Path

from fastapi.testclient import TestClient

from app.main import app


def main() -> None:
    base_dir = Path(__file__).resolve().parent
    client = TestClient(app)

    meta = client.get("/api/meta").json()
    assert meta["count"] > 0

    res = client.get("/api/loads").json()
    assert res["total"] > 0
    first_id = res["loads"][0]["id"]

    detail = client.get(f"/api/loads/{first_id}").json()
    assert detail["id"] == first_id

    # Filtering sanity
    res2 = client.get("/api/loads", params={"hazmat": "true"}).json()
    assert "total" in res2
    for load in res2["loads"][:25]:
        assert load["hazmat"] is True

    # Import JSON sample
    sample_json = base_dir / "sample_data" / "sample_loads.json"
    if sample_json.exists():
        imported = client.post(
            "/api/import",
            params={"filename": "sample_loads.json"},
            content=sample_json.read_bytes(),
            headers={"content-type": "application/json"},
        ).json()
        assert imported["ok"] is True
        meta2 = client.get("/api/meta").json()
        assert str(meta2["source"]).startswith("import")

    print("smoke_test: OK")


if __name__ == "__main__":
    main()
