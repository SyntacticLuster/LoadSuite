from __future__ import annotations

import json
import logging
from typing import List

from fastapi import FastAPI

from routecast_core import buffer_polyline, score_route
from routecast_core.models import (
    Coordinate,
    Overlay,
    OverlayCollection,
    RouteRequest,
    RouteResponse,
    ScoreBreakdown,
)
from routecast_routing.osrm import OsrmRoutingProvider
from routecast_sources import fetch_alerts_for_corridor, fetch_events, fetch_restrictions

logger = logging.getLogger("routecast")


def _configure_logging() -> None:
    handler = logging.StreamHandler()
    fmt = json.dumps({
        "ts": "%(asctime)s",
        "level": "%(levelname)s",
        "msg": "%(message)s",
        "logger": "%(name)s",
    })
    formatter = logging.Formatter(fmt)
    handler.setFormatter(formatter)

    root = logging.getLogger()
    root.handlers.clear()
    root.addHandler(handler)
    root.setLevel(logging.INFO)


_configure_logging()

app = FastAPI(title="RouteCast API", version="0.1.0")


@app.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok", "service": "routecast-api"}


@app.post("/route", response_model=RouteResponse)
def compute_route(req: RouteRequest) -> RouteResponse:
    """Return a stub route between origin and destination."""

    provider = OsrmRoutingProvider()
    route = provider.route(req)
    logger.info("computed route", extra={"provider": route.provider})
    return route


@app.post("/route/overlays", response_model=OverlayCollection)
def route_overlays(req: RouteRequest) -> OverlayCollection:
    """Return overlays along the route corridor (stub empty)."""

    polyline = [req.origin, *(req.via or []), req.destination]
    corridor = buffer_polyline(polyline, buffer_meters=500)

    overlays: List = []
    overlays.extend(fetch_alerts_for_corridor(corridor))
    overlays.extend(fetch_restrictions(polyline))
    overlays.extend(fetch_events(corridor))

    logger.info("fetched overlays", extra={"count": len(overlays)})
    return OverlayCollection(overlays=overlays)


class RouteScoreResponse(ScoreBreakdown):
    polyline: List[Coordinate]
    distance_miles: float
    duration_minutes: float
    duration_seconds: float
    overlays: List[Overlay]
    provider: str
    route_provider: str | None = None


@app.post("/route/score", response_model=RouteScoreResponse)
def score_endpoint(req: RouteRequest) -> RouteScoreResponse:
    """Return a stub score for the route."""

    route = OsrmRoutingProvider().route(req)
    overlays = route_overlays(req).overlays
    breakdown = score_route(route, overlays=overlays)
    logger.info("scored route", extra={"score": breakdown.overall})
    payload = breakdown.model_dump()
    payload.update(
        {
            "polyline": route.polyline,
            "distance_miles": route.distance_miles,
            "duration_minutes": route.duration_minutes,
            "duration_seconds": route.duration_seconds,
            "overlays": overlays,
            "provider": route.provider,
            "route_provider": route.provider,
        }
    )
    return RouteScoreResponse(**payload)
