from __future__ import annotations

import asyncio
import os
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Optional

from ..models import Load
from .connectors import (
    BaseConnector,
    ConnectorConfig,
    DatStubConnector,
    DatStubConnectorConfig,
    CsvFileConnector,
    CsvFileConnectorConfig,
    JsonFileConnector,
    JsonFileConnectorConfig,
    JsonDirTailConnector,
    JsonDirTailConnectorConfig,
    TruckstopStubConnector,
    TruckstopStubConnectorConfig,
)
from .normalization import CanonicalLoadNormalizer, Normalizer
from .store import LoadStore, RawPayloadStore
from .stores import CursorStore, FileCursorStore, NullCursorStore


def _now_utc() -> datetime:
    return datetime.now(timezone.utc)


@dataclass(frozen=True)
class SourceStatus:
    name: str
    enabled: bool
    kind: str
    spec: str
    healthy: bool
    last_error: Optional[str] = None


class IngestionManager:
    """In-memory ingestion orchestrator.

    Keeps API stability by exposing loads as plain app.models.Load (no provenance in API for now).
    """

    def __init__(
        self,
        *,
        connectors: list[BaseConnector[dict[str, Any]]],
        normalizer: Normalizer,
        load_store: LoadStore,
        raw_payload_store: RawPayloadStore,
        cursor_store: CursorStore | None = None,
    ):
        self._connectors = connectors
        self._normalizer = normalizer
        self._load_store = load_store
        self._raw_payload_store = raw_payload_store
        self._cursor_store: CursorStore = cursor_store or NullCursorStore()

        self._last_run_at: datetime | None = None
        self._last_error: str | None = None
        self._errors: list[str] = []

        self._last_counts: dict[str, int] = {
            "sources_enabled": 0,
            "sources_healthy": 0,
            "fetched_records": 0,
            "normalized_records": 0,
            "inserted": 0,
            "updated": 0,
            "ignored": 0,
            "purged_raw": 0,
            "purged_loads": 0,
        }

        # Guard concurrent run_once() calls (e.g. background poller + manual trigger)
        self._lock = asyncio.Lock()

    @classmethod
    def from_settings(
        cls,
        *,
        connector_specs: str,
        quarantine_mode: bool,
        default_ttl_seconds: int,
        raw_payload_ttl_seconds: int,
    ) -> "IngestionManager":
        connectors = cls._parse_connectors(connector_specs)

        cursor_store: CursorStore | None = None
        cursor_path = (os.environ.get("INGESTION_CURSOR_STORE_PATH") or "").strip()
        if cursor_path:
            cursor_store = FileCursorStore(Path(cursor_path).expanduser())

        return cls(
            connectors=connectors,
            normalizer=CanonicalLoadNormalizer(),
            load_store=LoadStore(
                default_ttl_seconds=default_ttl_seconds,
                quarantine_mode=quarantine_mode,
            ),
            raw_payload_store=RawPayloadStore(default_ttl_seconds=raw_payload_ttl_seconds),
            cursor_store=cursor_store,
        )

    @staticmethod
    def _parse_connectors(specs: str) -> list[BaseConnector[dict[str, Any]]]:
        """Parse settings.ingestion_connectors.

        Supported MVP specs (comma-separated):
        - json:/abs/or/rel/path.json
        - csv:/abs/or/rel/path.csv
        - json_dir_tail:/abs/path/to/dropfolder
        - dat_stub
        - truckstop_stub

        Optional params for stubs:
        - dat_stub:api_key=...&client_id=...&client_secret=...
        - truckstop_stub:api_key=...&username=...&password=...
        """

        connectors: list[BaseConnector[dict[str, Any]]] = []
        for raw in (specs or "").split(","):
            spec = raw.strip()
            if not spec:
                continue

            kind, params = _split_spec(spec)

            if kind == "json" and params.get("path"):
                path = Path(params["path"]).expanduser()
                cfg = JsonFileConnectorConfig(
                    name=f"json:{path.name}",
                    enabled=True,
                    file_path=path,
                )
                connectors.append(JsonFileConnector(cfg))
                continue

            if kind == "csv" and params.get("path"):
                path = Path(params["path"]).expanduser()
                cfg = CsvFileConnectorConfig(
                    name=f"csv:{path.name}",
                    enabled=True,
                    file_path=path,
                )
                connectors.append(CsvFileConnector(cfg))
                continue

            if kind == "json_dir_tail" and params.get("path"):
                path = Path(params["path"]).expanduser()
                cfg = JsonDirTailConnectorConfig(
                    name=f"json_dir_tail:{path.name}",
                    enabled=True,
                    dir_path=path,
                )
                connectors.append(JsonDirTailConnector(cfg))
                continue

            if kind == "dat_stub":
                cfg = DatStubConnectorConfig(
                    name="dat_stub",
                    enabled=True,
                    api_key=params.get("api_key"),
                    client_id=params.get("client_id"),
                    client_secret=params.get("client_secret"),
                )
                connectors.append(DatStubConnector(cfg))
                continue

            if kind == "truckstop_stub":
                cfg = TruckstopStubConnectorConfig(
                    name="truckstop_stub",
                    enabled=True,
                    api_key=params.get("api_key"),
                    username=params.get("username"),
                    password=params.get("password"),
                )
                connectors.append(TruckstopStubConnector(cfg))
                continue

            # Unknown spec: ignore (manager will report via sources endpoint)
            cfg = ConnectorConfig(name=f"unknown:{spec}", enabled=False)
            connectors.append(_DisabledConnector(cfg, spec=spec))

        return connectors

    async def run_once(self) -> dict[str, int]:
        """Fetch from all enabled connectors, normalize, dedupe/merge, store."""

        async with self._lock:
            self._errors = []
            self._last_error = None

            counts: dict[str, int] = {
                "sources_enabled": 0,
                "sources_healthy": 0,
                "fetched_records": 0,
                "normalized_records": 0,
                "inserted": 0,
                "updated": 0,
                "ignored": 0,
                "purged_raw": 0,
                "purged_loads": 0,
            }

            # Hygiene: purge expired blobs/loads on every run (cheap in-memory walk)
            try:
                counts["purged_raw"] = self._raw_payload_store.purge_expired(now=_now_utc())
            except Exception as e:
                self._errors.append(f"raw_payload_purge_failed: {e}")

            try:
                counts["purged_loads"] = self._load_store.purge_expired(now=_now_utc())
            except Exception as e:
                self._errors.append(f"load_purge_failed: {e}")

            for connector in self._connectors:
                if not getattr(connector.config, "enabled", True):
                    continue
                counts["sources_enabled"] += 1

                healthy = False
                try:
                    healthy = await connector.healthcheck()
                except Exception as e:
                    self._errors.append(f"{connector.config.name}: healthcheck_failed: {e}")

                if not healthy:
                    self._errors.append(f"{connector.config.name}: unhealthy")
                    continue
                counts["sources_healthy"] += 1

                try:
                    connector_id = str(getattr(connector.config, "name", ""))
                    cursor = self._cursor_store.get(connector_id) if connector_id else None

                    while True:
                        batch = await connector.fetch(cursor=cursor)
                        counts["fetched_records"] += len(batch.records)

                        if connector_id and batch.cursor is not None and batch.cursor != cursor:
                            self._cursor_store.set(connector_id, batch.cursor)
                            cursor = batch.cursor

                        for raw_record in batch.records:
                            normalized = self._normalizer.normalize(raw_record)
                            if normalized is None:
                                continue
                            counts["normalized_records"] += 1

                            # For now we don't store raw payload by default; callers can add later.
                            _stored, outcome = self._load_store.upsert_with_outcome(
                                load=normalized.load,
                                source_system=batch.source,
                                source_record_id=normalized.source_record_id,
                                source_updated_at=normalized.source_updated_at,
                            )
                            counts[outcome] += 1

                        if not bool(batch.has_more):
                            break
                except Exception as e:
                    self._errors.append(f"{connector.config.name}: fetch_failed: {e}")

            self._last_run_at = _now_utc()
            if self._errors:
                self._last_error = self._errors[-1]

            self._last_counts = counts
            return counts

    def get_loads(self) -> list[Load]:
        """Return canonical loads with provenance stripped (API stability)."""

        return [stored.load for stored in self._load_store.list()]

    async def sources(self) -> list[SourceStatus]:
        result: list[SourceStatus] = []
        for connector in self._connectors:
            enabled = bool(getattr(connector.config, "enabled", True))
            kind = type(connector).__name__
            spec = getattr(connector, "_spec", connector.config.name)
            healthy = False
            last_error: Optional[str] = None
            if enabled:
                try:
                    healthy = await connector.healthcheck()
                except Exception as e:
                    healthy = False
                    last_error = str(e)
                if last_error is None:
                    # Many connectors (stubs) keep explicit status text.
                    last_error = getattr(connector, "status_text", None)
            result.append(
                SourceStatus(
                    name=connector.config.name,
                    enabled=enabled,
                    kind=kind,
                    spec=str(spec),
                    healthy=healthy,
                    last_error=last_error,
                )
            )
        return result

    def stats(self) -> dict[str, Any]:
        return {
            "last_run_at": self._last_run_at.isoformat() if self._last_run_at else None,
            "counts": dict(self._last_counts),
            "errors": list(self._errors),
            "last_error": self._last_error,
            "store": {
                "loads": self._load_store.stats(),
                "raw_payloads": self._raw_payload_store.stats(),
            },
        }


def _split_spec(spec: str) -> tuple[str, dict[str, str]]:
    """Split a connector spec into kind + params.

    Formats supported:
    - json:/path/file.json  -> ("json", {"path": "/path/file.json"})
    - csv:/path/file.csv    -> ("csv", {"path": "/path/file.csv"})
    - dat_stub              -> ("dat_stub", {})
    - dat_stub:api_key=...&client_id=... -> ("dat_stub", {...})
    """

    if spec.startswith("json:"):
        return "json", {"path": spec[len("json:") :].strip()}
    if spec.startswith("csv:"):
        return "csv", {"path": spec[len("csv:") :].strip()}
    if spec.startswith("json_dir_tail:"):
        return "json_dir_tail", {"path": spec[len("json_dir_tail:") :].strip()}

    if ":" not in spec:
        return spec, {}

    kind, rest = spec.split(":", 1)
    kind = kind.strip()
    rest = rest.strip()
    if not rest:
        return kind, {}

    params: dict[str, str] = {}
    # allow & or ; separators
    for pair in rest.replace(";", "&").split("&"):
        pair = pair.strip()
        if not pair:
            continue
        if "=" not in pair:
            continue
        k, v = pair.split("=", 1)
        k = k.strip()
        v = v.strip()
        if k and v:
            params[k] = v
    return kind, params


class _DisabledConnector(BaseConnector[dict[str, Any]]):
    """Placeholder connector for unknown specs.

    Kept enabled=False so it never runs, but shows up in /api/ingestion/sources.
    """

    def __init__(self, config: ConnectorConfig, *, spec: str):
        super().__init__(config)
        self._spec = spec

    async def fetch(self, cursor: str | None = None):
        raise RuntimeError("disabled")

    async def healthcheck(self) -> bool:
        return False
