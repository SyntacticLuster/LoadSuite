from __future__ import annotations

import hashlib
from datetime import datetime
from typing import Optional

from ..models import Load


def _hour_bucket(dt: datetime) -> str:
    # Normalize to YYYY-MM-DDTHH (no minutes/seconds) in the dt's timezone.
    return dt.replace(minute=0, second=0, microsecond=0).isoformat(timespec="hours")


def _weight_bucket_lbs(weight_lbs: int) -> int:
    # Deterministic, coarse bucket to avoid tiny diffs causing key churn.
    # 1k-lb bucket is a reasonable default for MVP.
    return int(max(weight_lbs, 0) // 1000) * 1000


def generate_dedup_key(
    *,
    source_system: str,
    source_record_id: Optional[str],
    load: Load,
) -> str:
    """Generate a deterministic dedupe key.

    Priority:
    1) source_system + source_record_id (if present)
    2) composite hash of identifying load fields
    """

    if source_record_id:
        return f"src:{source_system}|id:{source_record_id}"

    parts = [
        load.origin.city.strip().lower(),
        load.origin.state.strip().upper(),
        load.destination.city.strip().lower(),
        load.destination.state.strip().upper(),
        _hour_bucket(load.pickup_start),
        load.equipment.strip().lower(),
        str(_weight_bucket_lbs(load.weight_lbs)),
    ]
    payload = "|".join(parts)
    digest = hashlib.sha256(payload.encode("utf-8")).hexdigest()[:20]
    return f"cmp:{digest}"
