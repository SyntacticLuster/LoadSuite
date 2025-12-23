from __future__ import annotations

import asyncio
import json
import os
from pathlib import Path

from app.ingestion.connectors.json_dir_tail import JsonDirTailConnector, JsonDirTailConnectorConfig


def _write_json(path: Path, payload: object) -> None:
    path.write_text(json.dumps(payload), encoding="utf-8")


def test_json_dir_tail_fetch_uses_cursor(tmp_path: Path) -> None:
    drop = tmp_path / "drop"
    drop.mkdir()

    f1 = drop / "a.json"
    f2 = drop / "b.json"

    _write_json(f1, {"id": "1"})
    _write_json(f2, [{"id": "2"}, {"id": "3"}])

    # Force deterministic mtimes.
    os.utime(f1, (1000, 1000))
    os.utime(f2, (2000, 2000))

    connector = JsonDirTailConnector(
        JsonDirTailConnectorConfig(
            name="json_dir_tail:test",
            enabled=True,
            dir_path=drop,
        )
    )

    first = asyncio.run(connector.fetch(cursor=None))
    assert [r["id"] for r in first.records] == ["1", "2", "3"]
    assert first.cursor is not None

    # Add an older file (should be ignored) and a newer file (should be read).
    f_old = drop / "old.json"
    _write_json(f_old, {"id": "old"})
    os.utime(f_old, (1500, 1500))

    f_new = drop / "c.json"
    _write_json(f_new, {"id": "new"})
    os.utime(f_new, (3000, 3000))

    second = asyncio.run(connector.fetch(cursor=first.cursor))
    assert [r["id"] for r in second.records] == ["new"]
