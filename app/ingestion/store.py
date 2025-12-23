from __future__ import annotations

import json
import uuid
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from typing import Any, Callable, Literal, Optional

from ..models import Load
from .dedupe import generate_dedup_key
from .models import Classification, LicenseClass, Provenance, RightsFlags


def _now_utc() -> datetime:
    return datetime.now(timezone.utc)


@dataclass(frozen=True)
class StoredLoad:
    load: Load
    provenance: Provenance


class RawPayloadStore:
    """In-memory store for opaque raw payload blobs with TTL purge.

    This is intentionally simple: we store bytes and treat them as opaque.
    """

    def __init__(self, *, default_ttl_seconds: int = 86400, now_fn: Callable[[], datetime] = _now_utc):
        self._default_ttl_seconds = int(default_ttl_seconds)
        self._now_fn = now_fn
        self._blobs: dict[str, tuple[bytes, datetime]] = {}

    def put(self, payload: bytes | dict[str, Any] | list[Any], *, ttl_seconds: Optional[int] = None) -> str:
        ref = str(uuid.uuid4())
        expires_at = self._now_fn() + timedelta(seconds=int(ttl_seconds or self._default_ttl_seconds))

        if isinstance(payload, bytes):
            data = payload
        else:
            data = json.dumps(payload, separators=(",", ":"), ensure_ascii=False).encode("utf-8")

        self._blobs[ref] = (data, expires_at)
        return ref

    def get(self, ref: str) -> Optional[bytes]:
        item = self._blobs.get(ref)
        if not item:
            return None
        data, expires_at = item
        if expires_at <= self._now_fn():
            # Lazy purge
            self._blobs.pop(ref, None)
            return None
        return data

    def purge_expired(self, *, now: Optional[datetime] = None) -> int:
        now = now or self._now_fn()
        to_delete = [ref for ref, (_, exp) in self._blobs.items() if exp <= now]
        for ref in to_delete:
            self._blobs.pop(ref, None)
        return len(to_delete)

    def stats(self) -> dict[str, Any]:
        return {"count": len(self._blobs)}


class LoadStore:
    """In-memory store of normalized loads plus provenance, with TTL purge and dedupe/merge."""

    def __init__(
        self,
        *,
        default_ttl_seconds: int = 86400,
        quarantine_mode: bool = True,
        now_fn: Callable[[], datetime] = _now_utc,
    ):
        self._default_ttl_seconds = int(default_ttl_seconds)
        self._quarantine_mode = bool(quarantine_mode)
        self._now_fn = now_fn

        self._by_id: dict[str, StoredLoad] = {}
        self._dedup_to_id: dict[str, str] = {}

    def list(self) -> list[StoredLoad]:
        return list(self._by_id.values())

    def get(self, load_id: str) -> Optional[StoredLoad]:
        return self._by_id.get(load_id)

    def upsert(
        self,
        *,
        load: Load,
        source_system: str,
        source_record_id: Optional[str] = None,
        source_updated_at: Optional[datetime] = None,
        ttl_expires_at: Optional[datetime] = None,
        raw_payload_ref: Optional[str] = None,
        license_class: LicenseClass = LicenseClass.UNKNOWN,
        rights_flags: Optional[RightsFlags] = None,
        classification: Optional[Classification] = None,
        acquired_at: Optional[datetime] = None,
    ) -> StoredLoad:
        stored, _ = self.upsert_with_outcome(
            load=load,
            source_system=source_system,
            source_record_id=source_record_id,
            source_updated_at=source_updated_at,
            ttl_expires_at=ttl_expires_at,
            raw_payload_ref=raw_payload_ref,
            license_class=license_class,
            rights_flags=rights_flags,
            classification=classification,
            acquired_at=acquired_at,
        )
        return stored

    def upsert_with_outcome(
        self,
        *,
        load: Load,
        source_system: str,
        source_record_id: Optional[str] = None,
        source_updated_at: Optional[datetime] = None,
        ttl_expires_at: Optional[datetime] = None,
        raw_payload_ref: Optional[str] = None,
        license_class: LicenseClass = LicenseClass.UNKNOWN,
        rights_flags: Optional[RightsFlags] = None,
        classification: Optional[Classification] = None,
        acquired_at: Optional[datetime] = None,
    ) -> tuple[StoredLoad, Literal["inserted", "updated", "ignored"]]:
        now = self._now_fn()

        dedup_key = generate_dedup_key(source_system=source_system, source_record_id=source_record_id, load=load)

        if classification is None:
            classification = Classification.QUARANTINED if self._quarantine_mode else Classification.COMPLIANT

        if rights_flags is None:
            # Conservative defaults; callers can loosen for compliant sources.
            rights_flags = RightsFlags(
                store_raw=False,
                store_derived=True,
                display=not self._quarantine_mode,
                display_aggregated=False,
                export=False,
                redistribute=False,
                commingle=False,
                train_models=False,
            )

        # Apply default TTL if needed.
        if ttl_expires_at is None and (classification == Classification.QUARANTINED):
            ttl_expires_at = now + timedelta(seconds=self._default_ttl_seconds)

        if acquired_at is None:
            acquired_at = now

        existing_id = self._dedup_to_id.get(dedup_key)
        if existing_id is None:
            stored = StoredLoad(
                load=load,
                provenance=Provenance(
                    source_system=source_system,
                    source_record_id=source_record_id,
                    acquired_at=acquired_at,
                    source_updated_at=source_updated_at,
                    dedup_key=dedup_key,
                    version=1,
                    license_class=license_class,
                    rights_flags=rights_flags,
                    classification=classification,
                    ttl_expires_at=ttl_expires_at,
                    raw_payload_ref=raw_payload_ref,
                ),
            )
            self._by_id[load.id] = stored
            self._dedup_to_id[dedup_key] = load.id
            return stored, "inserted"

        # Merge into existing.
        existing = self._by_id[existing_id]

        existing_ts = existing.provenance.source_updated_at or existing.load.updated_at
        new_ts = source_updated_at or load.updated_at

        if new_ts > existing_ts:
            merged_load = load.model_copy(update={"id": existing.load.id})
            merged_prov = existing.provenance.model_copy(
                update={
                    "source_system": source_system,
                    "source_record_id": source_record_id or existing.provenance.source_record_id,
                    "source_updated_at": source_updated_at or existing.provenance.source_updated_at,
                    "dedup_key": dedup_key,
                    "version": existing.provenance.version + 1,
                    "license_class": license_class,
                    "rights_flags": rights_flags,
                    "classification": classification,
                    "ttl_expires_at": ttl_expires_at or existing.provenance.ttl_expires_at,
                    "raw_payload_ref": raw_payload_ref or existing.provenance.raw_payload_ref,
                    # Preserve first acquired_at
                    "acquired_at": existing.provenance.acquired_at,
                }
            )
            stored = StoredLoad(load=merged_load, provenance=merged_prov)
            self._by_id[existing_id] = stored
            return stored, "updated"

        # Not newer: keep existing (preserve acquired_at/version).
        return existing, "ignored"

    def purge_expired(self, *, now: Optional[datetime] = None) -> int:
        now = now or self._now_fn()
        expired_ids: list[str] = []
        for load_id, stored in self._by_id.items():
            exp = stored.provenance.ttl_expires_at
            if exp is not None and exp <= now:
                expired_ids.append(load_id)

        for load_id in expired_ids:
            stored = self._by_id.pop(load_id, None)
            if stored is not None:
                self._dedup_to_id.pop(stored.provenance.dedup_key, None)

        return len(expired_ids)

    def stats(self) -> dict[str, Any]:
        return {
            "count": len(self._by_id),
            "dedup_index": len(self._dedup_to_id),
            "quarantine_mode": self._quarantine_mode,
            "default_ttl_seconds": self._default_ttl_seconds,
        }
