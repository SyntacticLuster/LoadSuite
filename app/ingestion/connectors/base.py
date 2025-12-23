from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass
from datetime import datetime
from typing import AsyncIterator, Generic, Optional, TypeVar

T = TypeVar("T")


@dataclass
class ConnectorConfig:
    name: str
    enabled: bool = True
    poll_interval_seconds: int = 300
    timeout_seconds: int = 30
    retry_attempts: int = 3
    retry_backoff_seconds: int = 5


@dataclass
class FetchResult(Generic[T]):
    records: list[T]
    source: str
    fetched_at: datetime
    cursor: Optional[str] = None
    has_more: bool = False
    errors: Optional[list[str]] = None


class BaseConnector(ABC, Generic[T]):
    """Abstract connector interface.

    The repo uses FastAPI but avoids heavy frameworks; keep connector code simple.
    """

    def __init__(self, config: ConnectorConfig):
        self.config = config
        self._last_fetch: datetime | None = None

    @abstractmethod
    async def fetch(self, cursor: str | None = None) -> FetchResult[T]:
        ...

    @abstractmethod
    async def healthcheck(self) -> bool:
        ...

    async def fetch_all(self) -> AsyncIterator[FetchResult[T]]:
        cursor: str | None = None
        while True:
            result = await self.fetch(cursor)
            self._last_fetch = result.fetched_at
            yield result
            if not result.has_more:
                break
            cursor = result.cursor
