from __future__ import annotations

from routecast_core.models import Coordinate, RouteLeg, RouteRequest, RouteResponse
from .provider import RoutingProvider


class ValhallaRoutingProvider(RoutingProvider):
    """Valhalla stub provider."""

    def route(self, request: RouteRequest) -> RouteResponse:
        polyline = [request.origin, request.destination]
        leg = RouteLeg(
            start=request.origin,
            end=request.destination,
            distance_miles=1.0,
            duration_minutes=2.0,
            polyline=polyline,
        )
        return RouteResponse(
            origin=request.origin,
            destination=request.destination,
            legs=[leg],
            polyline=polyline,
            distance_miles=1.0,
            duration_minutes=2.0,
            duration_seconds=120.0,
            provider="valhalla-stub",
        )
