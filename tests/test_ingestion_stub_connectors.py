from __future__ import annotations

import asyncio

from app.ingestion.manager import IngestionManager


def test_stub_connectors_parse_and_show_sources() -> None:
    manager = IngestionManager.from_settings(
        connector_specs="dat_stub,truckstop_stub",
        quarantine_mode=True,
        default_ttl_seconds=60,
        raw_payload_ttl_seconds=60,
    )

    sources = asyncio.run(manager.sources())
    names = {s.name for s in sources}
    assert "dat_stub" in names
    assert "truckstop_stub" in names
