from fastapi.testclient import TestClient

import app.deps as deps
import app.main as main
from app.api_models import RouteGeometryResponse, RouteLineString


class _StubRoutingClient:
    provider = "osrm"

    def __init__(self, response: RouteGeometryResponse) -> None:
        self._response = response

    def route(self, *_args, **_kwargs) -> RouteGeometryResponse:
        return self._response


def test_routes_endpoint_returns_geometry() -> None:
    response = RouteGeometryResponse(
        geometry=RouteLineString(type="LineString", coordinates=[[-87.6, 41.9], [-74.0, 40.7]]),
        distance_m=1234.5,
        duration_s=987.6,
        provider="osrm",
        provider_error=None,
    )
    main.app.dependency_overrides[deps.get_routing_client] = lambda: _StubRoutingClient(response)
    client = TestClient(main.app)
    try:
        resp = client.get("/api/routes?origin_lat=41.9&origin_lng=-87.6&dest_lat=40.7&dest_lng=-74.0")
        assert resp.status_code == 200
        payload = resp.json()
        assert payload["geometry"]["type"] == "LineString"
        assert payload["geometry"]["coordinates"]
        assert payload["provider"] == "osrm"
    finally:
        main.app.dependency_overrides = {}


def test_routes_endpoint_returns_provider_error() -> None:
    response = RouteGeometryResponse(
        geometry=None,
        distance_m=None,
        duration_s=None,
        provider="osrm",
        provider_error="routing_unavailable",
    )
    main.app.dependency_overrides[deps.get_routing_client] = lambda: _StubRoutingClient(response)
    client = TestClient(main.app)
    try:
        resp = client.get("/api/routes?origin_lat=41.9&origin_lng=-87.6&dest_lat=40.7&dest_lng=-74.0")
        assert resp.status_code == 200
        payload = resp.json()
        assert payload["geometry"] is None
        assert payload["provider_error"] == "routing_unavailable"
    finally:
        main.app.dependency_overrides = {}
