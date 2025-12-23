from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any, Optional

from .base import BaseConnector, ConnectorConfig, FetchResult


@dataclass
class TruckstopStubConnectorConfig(ConnectorConfig):
    api_key: Optional[str] = None
    username: Optional[str] = None
    password: Optional[str] = None


class TruckstopStubConnector(BaseConnector[dict[str, Any]]):
    """Truckstop stub connector.

    Intentionally performs no external calls. Exists so the ingestion pipeline can
    treat Truckstop as a drop-in source later.
    """

    def __init__(self, config: TruckstopStubConnectorConfig):
        super().__init__(config)
        self.truckstop_config = config
        self.status_text: str = "not_checked"

    async def fetch(self, cursor: Optional[str] = None) -> FetchResult[dict[str, Any]]:
        self.status_text = "not_implemented"
        return FetchResult(
            records=[],
            source="truckstop_stub",
            fetched_at=datetime.now(timezone.utc),
            cursor=None,
            has_more=False,
            errors=["Not implemented: provide Truckstop API spec"],
        )

    async def healthcheck(self) -> bool:
        configured = bool(self.truckstop_config.api_key or (self.truckstop_config.username and self.truckstop_config.password))
        if configured:
            self.status_text = "configured_but_not_implemented"
            return True
        self.status_text = "missing_auth_config"
        return False
