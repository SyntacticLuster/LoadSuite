from fastapi.testclient import TestClient

import app.main as main
from app.weather import geocode_city_state


def test_geocode_city_state_supports_expanded_synthetic_city_list():
    # Pick a city that exists in app.data._CITIES but not in the original 12-city map.
    r = geocode_city_state("Birmingham", "AL")
    assert r["city"] == "Birmingham"
    assert r["state"] == "AL"
    assert abs(r["lat"] - 33.5186) < 0.001
    assert abs(r["lon"] - (-86.8104)) < 0.001


def test_load_routecast_endpoint_works_for_synthetic_load(monkeypatch):
    # Avoid network calls in tests.
    monkeypatch.setattr(
        main,
        "nws_current_by_point",
        lambda lat, lon: {"timestamp": None, "text": "Clear", "temperature_f": 70.0},
    )
    monkeypatch.setattr(
        main,
        "merge_alerts_for_points",
        lambda points: {"count": 0, "alerts": [], "partial": False, "failures": 0},
    )

    client = TestClient(main.app)
    loads_resp = client.get("/api/loads")
    assert loads_resp.status_code == 200
    loads = loads_resp.json()["loads"]
    assert loads

    load_id = loads[0]["id"]
    rc_resp = client.get(f"/api/loads/{load_id}/routecast")
    assert rc_resp.status_code == 200
    payload = rc_resp.json()

    assert payload["load_id"] == load_id
    assert "origin" in payload and "destination" in payload
    assert "lat" in payload["origin"] and "lon" in payload["origin"]
    assert "lat" in payload["destination"] and "lon" in payload["destination"]
