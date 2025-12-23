from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Protocol


class CursorStore(Protocol):
    """Persistence for per-connector cursors.

    Cursor values are opaque strings owned by the connector.
    """

    def get(self, connector_id: str) -> str | None:  # pragma: no cover
        ...

    def set(self, connector_id: str, cursor: str | None) -> None:  # pragma: no cover
        ...


class NullCursorStore:
    """Default: no persistence (behavior identical to prior implementation)."""

    def get(self, connector_id: str) -> str | None:
        return None

    def set(self, connector_id: str, cursor: str | None) -> None:
        return


class FileCursorStore:
    """Simple JSON file-backed cursor store.

    Enabled when INGESTION_CURSOR_STORE_PATH is set.
    """

    def __init__(self, path: Path):
        self._path = path
        self._cursors: dict[str, str] = {}
        self._load()

    def get(self, connector_id: str) -> str | None:
        return self._cursors.get(connector_id)

    def set(self, connector_id: str, cursor: str | None) -> None:
        if not connector_id:
            return

        if cursor is None or cursor == "":
            if connector_id in self._cursors:
                self._cursors.pop(connector_id, None)
                self._persist()
            return

        if self._cursors.get(connector_id) == cursor:
            return

        self._cursors[connector_id] = cursor
        self._persist()

    def _load(self) -> None:
        try:
            data = json.loads(self._path.read_text(encoding="utf-8"))
        except FileNotFoundError:
            return
        except Exception:
            return

        if isinstance(data, dict):
            for k, v in data.items():
                if isinstance(k, str) and isinstance(v, str):
                    self._cursors[k] = v

    def _persist(self) -> None:
        self._path.parent.mkdir(parents=True, exist_ok=True)

        tmp = Path(f"{self._path}.tmp")
        payload = json.dumps(self._cursors, ensure_ascii=False, separators=(",", ":"))
        # Ensure the cursor file is not accidentally world-readable; cursors should
        # be treated as operational state.
        fd = os.open(str(tmp), os.O_WRONLY | os.O_CREAT | os.O_TRUNC, 0o600)
        try:
            with os.fdopen(fd, "w", encoding="utf-8", closefd=True) as f:
                f.write(payload)
        except Exception:
            # If os.fdopen fails, close the raw fd.
            try:
                os.close(fd)
            except OSError:
                pass
            raise
        os.replace(tmp, self._path)
