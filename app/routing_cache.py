from __future__ import annotations

import hashlib
import json
import time
from collections import OrderedDict
from dataclasses import dataclass
from typing import Any, Callable


@dataclass
class _CacheEntry:
    expires_at: float
    value: Any
    negative: bool = False


class RoutingCache:
    """Bounded in-memory TTL cache for routed geometry responses."""

    def __init__(
        self,
        ttl_seconds: int,
        negative_ttl_seconds: int,
        max_entries: int,
        *,
        clock: Callable[[], float] | None = None,
    ) -> None:
        self._ttl_seconds = max(int(ttl_seconds), 1)
        self._negative_ttl_seconds = max(int(negative_ttl_seconds), 1)
        self._max_entries = max(int(max_entries), 1)
        self._clock = clock or time.time
        self._store: OrderedDict[str, _CacheEntry] = OrderedDict()

    def _now(self) -> float:
        return float(self._clock())

    def _stable_hash(self, payload: dict[str, Any]) -> str:
        encoded = json.dumps(payload, sort_keys=True, separators=(",", ":"))
        return hashlib.sha256(encoded.encode("utf-8")).hexdigest()

    def make_key(self, payload: dict[str, Any], provider: str, profile: str) -> str:
        materialized = {
            "provider": provider,
            "profile": profile,
            **payload,
        }
        return self._stable_hash(materialized)

    def _evict_expired(self) -> None:
        now = self._now()
        expired = [key for key, entry in self._store.items() if entry.expires_at < now]
        for key in expired:
            self._store.pop(key, None)

    def get(self, key: str) -> Any | None:
        entry = self._store.get(key)
        if not entry:
            return None
        if entry.expires_at < self._now():
            self._store.pop(key, None)
            return None
        self._store.move_to_end(key)
        return entry.value

    def set(self, key: str, value: Any, *, negative: bool = False) -> None:
        self._evict_expired()
        ttl = self._negative_ttl_seconds if negative else self._ttl_seconds
        self._store[key] = _CacheEntry(expires_at=self._now() + ttl, value=value, negative=negative)
        self._store.move_to_end(key)
        while len(self._store) > self._max_entries:
            self._store.popitem(last=False)

    def clear(self) -> None:
        self._store.clear()
