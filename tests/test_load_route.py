from datetime import datetime, timezone

from fastapi.testclient import TestClient

import app.main as main
from app.data import Dataset
from app.models import Broker, Load, Location


def _build_load(load_id: str, origin: Location, destination: Location) -> Load:
    now = datetime(2024, 1, 1, 12, 0, 0, tzinfo=timezone.utc)
    return Load(
        id=load_id,
        origin=origin,
        destination=destination,
        pickup_start=now,
        pickup_end=now,
        delivery_start=now,
        delivery_end=now,
        equipment="Dry Van",
        weight_lbs=10000,
        hazmat=False,
        distance_miles=250.0,
        deadhead_miles=10.0,
        rate_total_usd=750.0,
        rpm=3.0,
        broker=Broker(name="Test Broker", rating=4.0),
        detention=False,
        multi_stop=False,
        lane_history=False,
        commodity="General Freight",
        posted_at=now,
        updated_at=now,
    )


def test_load_route_endpoint_returns_coords():
    client = TestClient(main.app)
    loads_resp = client.get("/api/loads")
    assert loads_resp.status_code == 200
    loads = loads_resp.json()["loads"]
    assert loads

    load_id = loads[0]["id"]
    resp = client.get(f"/api/loads/{load_id}/route")
    assert resp.status_code == 200
    payload = resp.json()

    assert payload["load_id"] == load_id
    assert "origin" in payload and "destination" in payload
    assert isinstance(payload["origin"]["lat"], (int, float))
    assert isinstance(payload["origin"]["lon"], (int, float))
    assert isinstance(payload["destination"]["lat"], (int, float))
    assert isinstance(payload["destination"]["lon"], (int, float))
    assert isinstance(payload["stops"], list)


def test_load_route_endpoint_missing_coords_returns_400(monkeypatch):
    bad_origin = Location(city="Nowhere", state="ZZ")
    bad_destination = Location(city="Gotham", state="ZZ")
    bad_load = _build_load("BAD-ROUTE-1", bad_origin, bad_destination)
    dataset = Dataset(loads=[bad_load], source="test")
    monkeypatch.setattr(main.app.state.ctx, "dataset", dataset)

    client = TestClient(main.app)
    resp = client.get("/api/loads/BAD-ROUTE-1/route")
    assert resp.status_code == 400
    assert "city/state not supported" in resp.json()["detail"]
