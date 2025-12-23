from __future__ import annotations

import csv
import json
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Optional

from .base import BaseConnector, ConnectorConfig, FetchResult


@dataclass
class JsonFileConnectorConfig(ConnectorConfig):
    file_path: Path = Path(".")


class JsonFileConnector(BaseConnector[dict[str, Any]]):
    def __init__(self, config: JsonFileConnectorConfig):
        super().__init__(config)
        self.file_config = config

    async def fetch(self, cursor: Optional[str] = None) -> FetchResult[dict[str, Any]]:
        path = self.file_config.file_path
        raw = path.read_bytes()
        data = json.loads(raw.decode("utf-8"))

        records: list[dict[str, Any]]
        if isinstance(data, list):
            if not all(isinstance(item, dict) for item in data):
                raise ValueError("JSON array must contain objects")
            records = [item for item in data if isinstance(item, dict)]
        elif isinstance(data, dict):
            records = [data]
        else:
            raise ValueError("JSON must be an object or an array of objects")

        return FetchResult(
            records=records,
            source=f"file:{path}",
            fetched_at=datetime.now(timezone.utc),
            cursor=None,
            has_more=False,
        )

    async def healthcheck(self) -> bool:
        return self.file_config.file_path.exists() and self.file_config.file_path.is_file()


@dataclass
class CsvFileConnectorConfig(ConnectorConfig):
    file_path: Path = Path(".")
    delimiter: str = ","
    encoding: str = "utf-8"


class CsvFileConnector(BaseConnector[dict[str, Any]]):
    def __init__(self, config: CsvFileConnectorConfig):
        super().__init__(config)
        self.csv_config = config

    async def fetch(self, cursor: Optional[str] = None) -> FetchResult[dict[str, Any]]:
        path = self.csv_config.file_path
        text = path.read_text(encoding=self.csv_config.encoding)
        reader = csv.DictReader(text.splitlines(), delimiter=self.csv_config.delimiter)
        records = list(reader)
        return FetchResult(
            records=records,
            source=f"csv:{path}",
            fetched_at=datetime.now(timezone.utc),
            cursor=None,
            has_more=False,
        )

    async def healthcheck(self) -> bool:
        return self.csv_config.file_path.exists() and self.csv_config.file_path.is_file()
