from routecast_core import buffer_polyline, score_route
from routecast_core.models import Coordinate, RouteLeg, RouteResponse


def test_buffer_polyline_closes_ring():
    pts = [Coordinate(lat=0, lon=0), Coordinate(lat=1, lon=1)]
    corridor = buffer_polyline(pts, buffer_meters=10)
    assert corridor[0] == corridor[-1]


def test_score_route_stub_shape():
    leg = RouteLeg(
        start=Coordinate(lat=0, lon=0),
        end=Coordinate(lat=1, lon=1),
        distance_miles=1.0,
        duration_minutes=2.0,
        polyline=[Coordinate(lat=0, lon=0), Coordinate(lat=1, lon=1)],
    )
    route = RouteResponse(
        origin=leg.start,
        destination=leg.end,
        legs=[leg],
        polyline=leg.polyline,
        distance_miles=1.0,
        duration_minutes=2.0,
        duration_seconds=120.0,
        provider="stub",
    )
    score = score_route(route, overlays=[])
    assert 0 <= score.overall <= 100
    assert score.risk_score == score.overall
    assert score.factors
    assert isinstance(score.reasons, list)
    assert 0.0 <= score.confidence <= 1.0
