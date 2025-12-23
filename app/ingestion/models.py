from __future__ import annotations

from datetime import datetime
from enum import Enum
from typing import Optional

from pydantic import BaseModel, Field


class LicenseClass(str, Enum):
    OPEN = "OPEN"
    LICENSED = "LICENSED"
    USER_PROVIDED = "USER_PROVIDED"
    USER_CONNECTED = "USER_CONNECTED"
    UNKNOWN = "UNKNOWN"


class Classification(str, Enum):
    COMPLIANT = "COMPLIANT"
    RESTRICTED = "RESTRICTED"
    QUARANTINED = "QUARANTINED"
    BLOCKED = "BLOCKED"


class RightsFlags(BaseModel):
    """Granular rights permissions for a record.

    Mirrors docs/DATA_RIGHTS_AND_SOURCING.md. Defaults are conservative.
    """

    store_raw: bool = False
    store_derived: bool = True
    display: bool = False
    display_aggregated: bool = False
    export: bool = False
    redistribute: bool = False
    commingle: bool = False
    train_models: bool = False


class Provenance(BaseModel):
    """Minimal provenance metadata required by rights policy."""

    source_system: str = Field(..., description="Source identifier (e.g. upload:csv, partner:acme, dat)")
    source_record_id: Optional[str] = Field(default=None, description="Original ID from the source system")

    acquired_at: datetime = Field(..., description="When we first received this record (UTC)")
    source_updated_at: Optional[datetime] = Field(default=None, description="When source last updated this record (UTC)")

    dedup_key: str = Field(..., description="Deterministic key used for deduplication")
    version: int = Field(default=1, ge=1, description="Incremented when a newer duplicate replaces prior")

    license_class: LicenseClass = Field(default=LicenseClass.UNKNOWN)
    rights_flags: RightsFlags = Field(default_factory=RightsFlags)
    classification: Classification = Field(default=Classification.QUARANTINED)

    ttl_expires_at: Optional[datetime] = Field(
        default=None, description="When record must be deleted (UTC), if retention applies"
    )
    raw_payload_ref: Optional[str] = Field(
        default=None, description="Reference to stored raw payload blob (opaque)"
    )
