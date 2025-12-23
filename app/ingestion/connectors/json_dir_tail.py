from __future__ import annotations

import json
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Optional

from .base import BaseConnector, ConnectorConfig, FetchResult


@dataclass
class JsonDirTailConnectorConfig(ConnectorConfig):
    dir_path: Path = Path(".")
    glob_pattern: str = "*.json"


def _parse_cursor(cursor: str | None) -> tuple[int, str]:
    if not cursor:
        return 0, ""
    if ":" not in cursor:
        return 0, cursor
    left, right = cursor.split(":", 1)
    try:
        return int(left), right
    except ValueError:
        return 0, cursor


def _format_cursor(mtime_ns: int, filename: str) -> str:
    return f"{mtime_ns}:{filename}"


class JsonDirTailConnector(BaseConnector[dict[str, Any]]):
    """Tail a directory of JSON files like a fake live feed.

    Intended for local dev: drop new *.json files into a folder and the connector
    will only read files newer than the provided cursor.

    Cursor format: "{mtime_ns}:{filename}".
    """

    def __init__(self, config: JsonDirTailConnectorConfig):
        super().__init__(config)
        self.dir_config = config

    async def fetch(self, cursor: Optional[str] = None) -> FetchResult[dict[str, Any]]:
        base_dir = self.dir_config.dir_path
        fetched_at = datetime.now(timezone.utc)

        if not base_dir.exists() or not base_dir.is_dir():
            return FetchResult(
                records=[],
                source=f"json_dir_tail:{base_dir}",
                fetched_at=fetched_at,
                cursor=cursor,
                has_more=False,
                errors=[f"directory_not_found: {base_dir}"],
            )

        cursor_key = _parse_cursor(cursor)

        candidates: list[tuple[int, str, Path]] = []
        for path in base_dir.glob(self.dir_config.glob_pattern):
            if not path.is_file():
                continue
            try:
                stat = path.stat()
            except OSError:
                continue
            mtime_ns = int(getattr(stat, "st_mtime_ns", int(stat.st_mtime * 1_000_000_000)))
            candidates.append((mtime_ns, path.name, path))

        candidates.sort(key=lambda t: (t[0], t[1]))
        to_read = [t for t in candidates if (t[0], t[1]) > cursor_key]

        records: list[dict[str, Any]] = []
        errors: list[str] = []

        last_cursor = cursor
        for mtime_ns, filename, path in to_read:
            try:
                raw = path.read_bytes()
                data = json.loads(raw.decode("utf-8"))

                if isinstance(data, dict):
                    records.append(data)
                elif isinstance(data, list):
                    if not all(isinstance(item, dict) for item in data):
                        raise ValueError("JSON array must contain objects")
                    records.extend([item for item in data if isinstance(item, dict)])
                else:
                    raise ValueError("JSON must be an object or an array of objects")

                last_cursor = _format_cursor(mtime_ns, filename)
            except Exception as e:
                errors.append(f"{filename}: {e}")

        return FetchResult(
            records=records,
            source=f"json_dir_tail:{base_dir}",
            fetched_at=fetched_at,
            cursor=last_cursor,
            has_more=False,
            errors=errors or None,
        )

    async def healthcheck(self) -> bool:
        base_dir = self.dir_config.dir_path
        return base_dir.exists() and base_dir.is_dir()
