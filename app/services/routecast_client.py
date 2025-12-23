from __future__ import annotations

import json
import logging
import urllib.error
import urllib.request
from datetime import datetime, timezone
from typing import Any

from ..api_models import RouteCastScoreRequest, RouteCastScoreResponse
from ..routecast_cache import RouteCastCache

logger = logging.getLogger(__name__)


class RouteCastClient:
    """Thin HTTP client with caching and degraded fallbacks."""

    def __init__(
        self,
        *,
        base_url: str,
        timeout_seconds: float,
        provider: str,
        cache: RouteCastCache | None,
        api_key: str | None = None,
    ) -> None:
        self.base_url = base_url.rstrip("/")
        self.timeout_seconds = float(timeout_seconds)
        self.provider = provider
        self.cache = cache
        self.api_key = api_key

    def _degraded(self, reason: str) -> RouteCastScoreResponse:
        logger.warning("routecast degraded", extra={"reason": reason, "provider": self.provider})
        return RouteCastScoreResponse(
            overlays=[],
            risk_score=None,
            summary="Route risk unavailable",
            reasons=[reason],
            provider=self.provider,
            confidence="degraded",
        )

    def _departure_bucket(self, departure_time: datetime | None) -> str:
        if departure_time is None:
            return "none"
        dt = departure_time
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=timezone.utc)
        truncated = dt.replace(minute=0, second=0, microsecond=0)
        return truncated.isoformat()

    def _cache_key(self, request: RouteCastScoreRequest) -> str | None:
        if self.cache is None:
            return None
        payload = {
            "origin": request.origin.model_dump(mode="json"),
            "destination": request.destination.model_dump(mode="json"),
            "via": [pt.model_dump(mode="json") for pt in (request.via or [])],
            "equipment_type": request.equipment_type,
            "departure_time_bucket": self._departure_bucket(request.departure_time),
        }
        return self.cache.make_key(payload, self.provider)

    def _send(self, payload: dict[str, Any]) -> tuple[int, dict[str, Any] | None]:
        url = f"{self.base_url}/route/score"
        headers = {"Content-Type": "application/json"}
        if self.api_key:
            headers["Authorization"] = f"Bearer {self.api_key}"
        req = urllib.request.Request(url, data=json.dumps(payload).encode("utf-8"), headers=headers)
        with urllib.request.urlopen(req, timeout=self.timeout_seconds) as resp:
            status = int(resp.status)
            body = resp.read() or b"{}"
            return status, json.loads(body.decode("utf-8"))

    def _to_response(self, data: dict[str, Any] | None) -> RouteCastScoreResponse:
        data = data or {}
        return RouteCastScoreResponse(
            overlays=data.get("overlays") or [],
            risk_score=data.get("overall") or data.get("risk_score"),
            summary=str(data.get("summary") or "Route risk available"),
            reasons=[str(r) for r in data.get("reasons") or []],
            provider=str(data.get("provider") or self.provider),
            confidence=str(data.get("confidence") or "normal"),
        )

    def score_route(self, request: RouteCastScoreRequest) -> RouteCastScoreResponse:
        key = self._cache_key(request)
        if key and self.cache:
            cached = self.cache.get(key)
            if cached is not None:
                logger.info("routecast cache hit", extra={"provider": self.provider})
                return cached

        payload = request.model_dump(mode="json", exclude_none=True)
        payload["departure_time_bucket"] = self._departure_bucket(request.departure_time)

        try:
            status, data = self._send(payload)
        except urllib.error.HTTPError as e:
            if 500 <= e.code <= 599:
                resp = self._degraded(f"upstream_{e.code}")
                if key and self.cache:
                    self.cache.set(key, resp, negative=True)
                return resp
            try:
                raw = e.read() if hasattr(e, "read") else b"{}"
                parsed = json.loads(raw or b"{}") if raw else {}
            except Exception:
                parsed = {}
            resp = self._to_response(parsed)
            if key and self.cache:
                self.cache.set(key, resp, negative=False)
            return resp
        except Exception as e:  # pragma: no cover - defensive
            logger.exception("routecast request failed", extra={"provider": self.provider})
            resp = self._degraded("routecast_unavailable")
            if key and self.cache:
                self.cache.set(key, resp, negative=True)
            return resp

        if status >= 500:
            resp = self._degraded(f"upstream_{status}")
            if key and self.cache:
                self.cache.set(key, resp, negative=True)
            return resp

        resp = self._to_response(data)
        if key and self.cache:
            self.cache.set(key, resp, negative=False)
        return resp
