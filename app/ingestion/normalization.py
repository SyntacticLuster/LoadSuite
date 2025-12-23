from __future__ import annotations

import uuid
from dataclasses import dataclass
from datetime import datetime
from typing import Any, Optional, Protocol

from ..models import Load


@dataclass(frozen=True)
class NormalizedLoad:
    load: Load
    source_record_id: Optional[str] = None
    source_updated_at: Optional[datetime] = None


class Normalizer(Protocol):
    def normalize(self, raw_record: Any) -> NormalizedLoad | None:
        ...


class CanonicalLoadNormalizer:
    """Normalizer for raw dicts already matching app.models.Load schema."""

    def normalize(self, raw_record: Any) -> NormalizedLoad | None:
        if not isinstance(raw_record, dict):
            return None

        record: dict[str, Any] = raw_record

        # Allow callers to provide a separate source record id.
        source_record_id_raw = record.get("source_record_id") or record.get("external_id")
        source_record_id = str(source_record_id_raw) if source_record_id_raw is not None else None

        source_updated_at = record.get("source_updated_at")
        if isinstance(source_updated_at, str):
            try:
                source_updated_at = datetime.fromisoformat(source_updated_at)
            except Exception:
                source_updated_at = None

        # Ensure we have an internal canonical ID.
        if not record.get("id"):
            record = {**record, "id": str(uuid.uuid4())}

        load = Load.model_validate(record)
        return NormalizedLoad(load=load, source_record_id=source_record_id, source_updated_at=source_updated_at)
