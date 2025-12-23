from __future__ import annotations

from datetime import timedelta

from app.ingestion.store import LoadStore
from app.ingestion.models import Classification


def test_purge_expired_removes_records(ideal_load, fixed_now):
    store = LoadStore(default_ttl_seconds=86400, quarantine_mode=True, now_fn=lambda: fixed_now)

    expired = ideal_load.model_copy(update={"id": "EXP-1"})
    store.upsert(
        load=expired,
        source_system="upload:json",
        ttl_expires_at=fixed_now - timedelta(seconds=1),
        classification=Classification.QUARANTINED,
    )

    assert len(store.list()) == 1
    purged = store.purge_expired(now=fixed_now)
    assert purged == 1
    assert len(store.list()) == 0
