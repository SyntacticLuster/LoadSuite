from routecast_core.models import Coordinate
from routecast_sources import fetch_alerts_for_corridor, fetch_events, fetch_restrictions


def test_fetch_alerts_returns_list():
    result = fetch_alerts_for_corridor([Coordinate(lat=0, lon=0)])
    assert isinstance(result, list)


def test_fetch_restrictions_returns_list():
    result = fetch_restrictions([Coordinate(lat=0, lon=0)])
    assert result == []


def test_fetch_events_returns_list():
    result = fetch_events([Coordinate(lat=0, lon=0)])
    assert result == []
