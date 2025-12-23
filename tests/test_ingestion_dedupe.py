from __future__ import annotations

from datetime import timedelta

from app.ingestion.dedupe import generate_dedup_key
from app.ingestion.store import LoadStore
from app.ingestion.models import Classification


def test_dedup_key_stability(ideal_load):
    key1 = generate_dedup_key(source_system="upload:json", source_record_id=None, load=ideal_load)
    key2 = generate_dedup_key(source_system="upload:json", source_record_id=None, load=ideal_load)
    assert key1 == key2


def test_merge_version_increment_preserves_acquired_at(ideal_load, fixed_now):
    store = LoadStore(default_ttl_seconds=86400, quarantine_mode=False, now_fn=lambda: fixed_now)

    first = ideal_load.model_copy(update={"id": "L-1", "updated_at": fixed_now - timedelta(hours=2)})
    store.upsert(
        load=first,
        source_system="partner:acme",
        source_record_id=None,
        source_updated_at=fixed_now - timedelta(hours=2),
        classification=Classification.COMPLIANT,
    )

    newer_same_identity = ideal_load.model_copy(update={"id": "L-2", "updated_at": fixed_now - timedelta(hours=1)})
    stored2 = store.upsert(
        load=newer_same_identity,
        source_system="partner:acme",
        source_record_id=None,
        source_updated_at=fixed_now - timedelta(hours=1),
        classification=Classification.COMPLIANT,
    )

    assert len(store.list()) == 1
    assert stored2.load.id == "L-1"  # canonical id remains stable
    assert stored2.provenance.version == 2
    assert stored2.provenance.acquired_at == fixed_now
