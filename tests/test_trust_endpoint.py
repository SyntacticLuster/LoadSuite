from __future__ import annotations

from datetime import datetime, timezone, timedelta

from fastapi.testclient import TestClient

from app.main import app
from app.ingestion.store import StoredLoad
from app.ingestion.models import Provenance, LicenseClass, Classification


client = TestClient(app)


def _mutate_first_load(**updates):
    ctx = app.state.ctx
    original = ctx.dataset.loads[0]
    mutated = original.model_copy(update=updates)
    ctx.dataset.loads[0] = mutated
    return original


def _restore_first_load(original):
    app.state.ctx.dataset.loads[0] = original


def test_trust_reasons_present_when_degraded():
    load = app.state.ctx.dataset.loads[0]
    base = client.get(f"/api/loads/{load.id}/trust").json()
    base_score = base["confidence_score"]

    original = _mutate_first_load(distance_miles=0.0, rpm=0.0)
    degraded = client.get(f"/api/loads/{load.id}/trust").json()
    _restore_first_load(original)

    assert degraded["confidence_score"] < base_score
    factors = {r["factor"] for r in degraded["confidence_reasons"]}
    assert {"rpm_derived", "distance_clamped"} & factors
    assert all(r.get("details") for r in degraded["confidence_reasons"])


def test_trust_includes_missing_provenance_reason():
    load = app.state.ctx.dataset.loads[0]
    resp = client.get(f"/api/loads/{load.id}/trust").json()
    factors = {r["factor"] for r in resp["confidence_reasons"]}
    assert "provenance_missing_record_id" in factors
    assert "provenance_missing_updated_at" in factors


def test_trust_response_excludes_sensitive_fields():
    load = app.state.ctx.dataset.loads[0]
    resp = client.get(f"/api/loads/{load.id}/trust").json()

    assert set(resp.keys()) == {"load_id", "confidence_score", "confidence_bucket", "confidence_reasons"}

    for reason in resp["confidence_reasons"]:
        assert "factor" in reason and "contribution" in reason and "details" in reason


def test_trust_penalizes_stale_provenance():
    ctx = app.state.ctx
    load = ctx.dataset.loads[0]
    class _StubStore:
        def __init__(self, stored):
            self._stored = stored

        def get(self, load_id: str):
            return self._stored if self._stored.load.id == load_id else None

    def _make_prov(updated_at: datetime) -> StoredLoad:
        prov = Provenance(
            source_system="import:csv",
            source_record_id="ext-1",
            acquired_at=updated_at,
            source_updated_at=updated_at,
            dedup_key="dedup-1",
            version=1,
            license_class=LicenseClass.UNKNOWN,
            classification=Classification.COMPLIANT,
        )
        return StoredLoad(load=load, provenance=prov)

    original_manager = ctx.ingestion_manager

    fresh_time = datetime.now(timezone.utc).replace(microsecond=0)
    ctx.ingestion_manager = type("_StubManager", (), {"_load_store": _StubStore(_make_prov(fresh_time))})()
    base = client.get(f"/api/loads/{load.id}/trust").json()

    stale_time = fresh_time - timedelta(hours=15)
    ctx.ingestion_manager = type("_StubManager", (), {"_load_store": _StubStore(_make_prov(stale_time))})()
    degraded = client.get(f"/api/loads/{load.id}/trust").json()

    ctx.ingestion_manager = original_manager

    assert degraded["confidence_score"] < base["confidence_score"]
    factors = {r["factor"] for r in degraded["confidence_reasons"]}
    assert "data_expired" in factors


def test_trust_penalizes_recently_stale_provenance():
    ctx = app.state.ctx
    load = ctx.dataset.loads[0]

    class _StubStore:
        def __init__(self, stored):
            self._stored = stored

        def get(self, load_id: str):
            return self._stored if self._stored.load.id == load_id else None

    def _make_prov(updated_at: datetime) -> StoredLoad:
        prov = Provenance(
            source_system="import:csv",
            source_record_id="ext-2",
            acquired_at=updated_at,
            source_updated_at=updated_at,
            dedup_key="dedup-2",
            version=1,
            license_class=LicenseClass.UNKNOWN,
            classification=Classification.COMPLIANT,
        )
        return StoredLoad(load=load, provenance=prov)

    original_manager = ctx.ingestion_manager

    fresh_time = datetime.now(timezone.utc).replace(microsecond=0)
    ctx.ingestion_manager = type("_StubManager", (), {"_load_store": _StubStore(_make_prov(fresh_time))})()
    fresh = client.get(f"/api/loads/{load.id}/trust").json()

    stale_time = fresh_time - timedelta(hours=6)
    ctx.ingestion_manager = type("_StubManager", (), {"_load_store": _StubStore(_make_prov(stale_time))})()
    stale = client.get(f"/api/loads/{load.id}/trust").json()

    ctx.ingestion_manager = original_manager

    assert stale["confidence_score"] < fresh["confidence_score"]
    factors = {r["factor"] for r in stale["confidence_reasons"]}
    assert "data_stale" in factors


def test_trust_unknown_load_returns_404():
    resp = client.get("/api/loads/unknown-id/trust")
    assert resp.status_code == 404
