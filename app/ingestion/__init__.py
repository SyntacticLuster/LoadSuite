"""Ingestion package (connectors → normalization → dedupe/merge → provenance → retention).

This package is intentionally in-memory and vendor-agnostic for MVP speed.
"""

from .models import Classification, LicenseClass, Provenance, RightsFlags
from .dedupe import generate_dedup_key
from .manager import IngestionManager
from .normalization import CanonicalLoadNormalizer, Normalizer, NormalizedLoad
from .store import LoadStore, RawPayloadStore, StoredLoad

__all__ = [
    "Classification",
    "LicenseClass",
    "RightsFlags",
    "Provenance",
    "generate_dedup_key",
    "IngestionManager",
    "Normalizer",
    "NormalizedLoad",
    "CanonicalLoadNormalizer",
    "RawPayloadStore",
    "StoredLoad",
    "LoadStore",
]
