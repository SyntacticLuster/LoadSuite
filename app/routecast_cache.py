from __future__ import annotations

import hashlib
import json
import time
from dataclasses import dataclass
from typing import Any, Callable


@dataclass
class _CacheEntry:
    expires_at: float
    value: Any
    negative: bool = False


class RouteCastCache:
    """In-memory TTL cache for RouteCast responses."""

    def __init__(self, ttl_seconds: int, negative_ttl_seconds: int, *, clock: Callable[[], float] | None = None):
        self._ttl_seconds = max(int(ttl_seconds), 1)
        self._negative_ttl_seconds = max(int(negative_ttl_seconds), 1)
        self._clock = clock or time.time
        self._store: dict[str, _CacheEntry] = {}

    def _now(self) -> float:
        return float(self._clock())

    def _stable_hash(self, payload: dict[str, Any]) -> str:
        encoded = json.dumps(payload, sort_keys=True, separators=(",", ":"))
        return hashlib.sha256(encoded.encode("utf-8")).hexdigest()

    def make_key(self, payload: dict[str, Any], provider: str) -> str:
        materialized = {
            "provider": provider,
            **payload,
        }
        return self._stable_hash(materialized)

    def get(self, key: str) -> Any | None:
        entry = self._store.get(key)
        if not entry:
            return None
        if entry.expires_at < self._now():
            self._store.pop(key, None)
            return None
        return entry.value

    def set(self, key: str, value: Any, *, negative: bool = False) -> None:
        ttl = self._negative_ttl_seconds if negative else self._ttl_seconds
        self._store[key] = _CacheEntry(expires_at=self._now() + ttl, value=value, negative=negative)

    def clear(self) -> None:
        self._store.clear()
