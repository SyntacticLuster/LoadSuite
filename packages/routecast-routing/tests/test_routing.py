from routecast_core.models import Coordinate, RouteRequest
from routecast_routing.osrm import OsrmRoutingProvider
from routecast_routing.valhalla import ValhallaRoutingProvider


def test_osrm_stub_route():
    req = RouteRequest(origin=Coordinate(lat=0, lon=0), destination=Coordinate(lat=1, lon=1))
    res = OsrmRoutingProvider().route(req)
    assert res.provider == "osrm-stub"
    assert res.legs
    assert res.duration_seconds > 0
    assert res.polyline


def test_valhalla_stub_route():
    req = RouteRequest(origin=Coordinate(lat=0, lon=0), destination=Coordinate(lat=1, lon=1))
    res = ValhallaRoutingProvider().route(req)
    assert res.provider == "valhalla-stub"
    assert res.legs
    assert res.duration_seconds > 0
    assert res.polyline
