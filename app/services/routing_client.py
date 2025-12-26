from __future__ import annotations

import json
import logging
import urllib.error
import urllib.parse
import urllib.request
from dataclasses import dataclass
from typing import Any

from ..api_models import CoordinateModel, RouteGeometryResponse, RouteLineString
from ..routing_cache import RoutingCache

logger = logging.getLogger(__name__)


@dataclass
class _RoutePayload:
    origin: CoordinateModel
    destination: CoordinateModel
    stops: list[CoordinateModel]

    def cache_payload(self) -> dict[str, Any]:
        return {
            "origin": self.origin.model_dump(mode="json"),
            "destination": self.destination.model_dump(mode="json"),
            "stops": [stop.model_dump(mode="json") for stop in self.stops],
        }


class RoutingClient:
    """Thin HTTP client for routing geometry with caching and graceful degradation."""

    def __init__(
        self,
        *,
        base_url: str,
        timeout_seconds: float,
        provider: str,
        profile: str,
        cache: RoutingCache | None,
        max_retries: int = 1,
    ) -> None:
        self.base_url = base_url.rstrip("/")
        self.timeout_seconds = float(timeout_seconds)
        self.provider = provider
        self.profile = profile
        self.cache = cache
        self.max_retries = max(int(max_retries), 0)

    def _cache_key(self, payload: _RoutePayload) -> str | None:
        if self.cache is None:
            return None
        return self.cache.make_key(payload.cache_payload(), self.provider, self.profile)

    def _coords_str(self, payload: _RoutePayload) -> str:
        points = [payload.origin, *payload.stops, payload.destination]
        return ";".join(f"{pt.lon},{pt.lat}" for pt in points)

    def _send(self, payload: _RoutePayload) -> tuple[int, dict[str, Any] | None]:
        coords = self._coords_str(payload)
        params = urllib.parse.urlencode(
            {
                "overview": "full",
                "geometries": "geojson",
                "steps": "false",
            }
        )
        url = f"{self.base_url}/route/v1/{self.profile}/{coords}?{params}"
        req = urllib.request.Request(url)
        with urllib.request.urlopen(req, timeout=self.timeout_seconds) as resp:
            status = int(resp.status)
            body = resp.read() or b"{}"
            return status, json.loads(body.decode("utf-8"))

    def _to_response(self, data: dict[str, Any] | None) -> RouteGeometryResponse:
        data = data or {}
        routes = data.get("routes") or []
        if not routes:
            return RouteGeometryResponse(
                geometry=None,
                distance_m=None,
                duration_s=None,
                provider=self.provider,
                provider_error="no_routes",
            )
        route = routes[0] or {}
        geometry = route.get("geometry")
        if not geometry or geometry.get("type") != "LineString":
            return RouteGeometryResponse(
                geometry=None,
                distance_m=route.get("distance"),
                duration_s=route.get("duration"),
                provider=self.provider,
                provider_error="invalid_geometry",
            )
        return RouteGeometryResponse(
            geometry=RouteLineString(type="LineString", coordinates=geometry.get("coordinates") or []),
            distance_m=route.get("distance"),
            duration_s=route.get("duration"),
            provider=self.provider,
            provider_error=None,
        )

    def route(
        self,
        origin: CoordinateModel,
        destination: CoordinateModel,
        stops: list[CoordinateModel] | None = None,
    ) -> RouteGeometryResponse:
        payload = _RoutePayload(origin=origin, destination=destination, stops=stops or [])
        key = self._cache_key(payload)
        if key and self.cache:
            cached = self.cache.get(key)
            if cached is not None:
                logger.info("routing cache hit", extra={"provider": self.provider})
                return cached

        last_error: str | None = None
        for attempt in range(self.max_retries + 1):
            try:
                status, data = self._send(payload)
            except urllib.error.HTTPError as e:
                last_error = f"upstream_{e.code}"
                if 500 <= e.code <= 599 and attempt < self.max_retries:
                    continue
                response = RouteGeometryResponse(
                    geometry=None,
                    distance_m=None,
                    duration_s=None,
                    provider=self.provider,
                    provider_error=last_error,
                )
                if key and self.cache:
                    self.cache.set(key, response, negative=True)
                return response
            except Exception:
                logger.exception("routing request failed", extra={"provider": self.provider})
                last_error = "routing_unavailable"
                if attempt < self.max_retries:
                    continue
                response = RouteGeometryResponse(
                    geometry=None,
                    distance_m=None,
                    duration_s=None,
                    provider=self.provider,
                    provider_error=last_error,
                )
                if key and self.cache:
                    self.cache.set(key, response, negative=True)
                return response

            if status >= 500:
                last_error = f"upstream_{status}"
                if attempt < self.max_retries:
                    continue
                response = RouteGeometryResponse(
                    geometry=None,
                    distance_m=None,
                    duration_s=None,
                    provider=self.provider,
                    provider_error=last_error,
                )
                if key and self.cache:
                    self.cache.set(key, response, negative=True)
                return response

            response = self._to_response(data)
            if key and self.cache:
                self.cache.set(key, response, negative=response.provider_error is not None)
            return response

        return RouteGeometryResponse(
            geometry=None,
            distance_m=None,
            duration_s=None,
            provider=self.provider,
            provider_error=last_error or "routing_unavailable",
        )
