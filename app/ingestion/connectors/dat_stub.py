from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any, Optional

from .base import BaseConnector, ConnectorConfig, FetchResult


@dataclass
class DatStubConnectorConfig(ConnectorConfig):
    api_key: Optional[str] = None
    client_id: Optional[str] = None
    client_secret: Optional[str] = None


class DatStubConnector(BaseConnector[dict[str, Any]]):
    """DAT stub connector.

    Intentionally performs no external calls. Exists so the ingestion pipeline can
    treat DAT as a drop-in source later.
    """

    def __init__(self, config: DatStubConnectorConfig):
        super().__init__(config)
        self.dat_config = config
        self.status_text: str = "not_checked"

    async def fetch(self, cursor: Optional[str] = None) -> FetchResult[dict[str, Any]]:
        self.status_text = "not_implemented"
        return FetchResult(
            records=[],
            source="dat_stub",
            fetched_at=datetime.now(timezone.utc),
            cursor=None,
            has_more=False,
            errors=["Not implemented: provide DAT API spec"],
        )

    async def healthcheck(self) -> bool:
        # We can say "configured" if any auth material is present.
        configured = bool(self.dat_config.api_key or (self.dat_config.client_id and self.dat_config.client_secret))
        if configured:
            self.status_text = "configured_but_not_implemented"
            return True
        self.status_text = "missing_auth_config"
        return False
