from __future__ import annotations

import json
import urllib.error
import urllib.request
from typing import Any
from typing import cast


_ZIPPO_BASE = "https://api.zippopotam.us/us/"
_NWS_BASE = "https://api.weather.gov"

# NWS requires a User-Agent identifying the client.
# Keep it simple for local dev; override via env if needed later.
_NWS_HEADERS = {
    "User-Agent": "LoadSuite FreightLens MVP (local dev)",
    "Accept": "application/geo+json",
}


_NWS_ALERTS_TIMEOUT_S = 4.0


_CITY_COORDS_FALLBACK: dict[tuple[str, str], tuple[float, float]] = {
    # Keep a small fallback map to avoid hard failures if the synthetic list changes
    # or is unavailable for any reason.
    ("Atlanta", "GA"): (33.7490, -84.3880),
    ("Chicago", "IL"): (41.8781, -87.6298),
    ("Dallas", "TX"): (32.7767, -96.7970),
    ("Denver", "CO"): (39.7392, -104.9903),
    ("Kansas City", "MO"): (39.0997, -94.5786),
    ("Los Angeles", "CA"): (34.0522, -118.2437),
    ("Miami", "FL"): (25.7617, -80.1918),
    ("Nashville", "TN"): (36.1627, -86.7816),
    ("New York", "NY"): (40.7128, -74.0060),
    ("Phoenix", "AZ"): (33.4484, -112.0740),
    ("Salt Lake City", "UT"): (40.7608, -111.8910),
    ("Seattle", "WA"): (47.6062, -122.3321),
}


_CITY_COORDS_CACHE: dict[tuple[str, str], tuple[float, float]] | None = None


def _city_coords() -> dict[tuple[str, str], tuple[float, float]]:
    """Return city->(lat,lon) map used by RouteCast.

    Primary source is the synthetic city list in `app.data._CITIES` so RouteCast
    works for every synthetic load.
    """

    global _CITY_COORDS_CACHE
    if _CITY_COORDS_CACHE is not None:
        return _CITY_COORDS_CACHE

    coords: dict[tuple[str, str], tuple[float, float]] = {}
    try:
        # Import lazily to avoid import-order surprises.
        from .data import _CITIES  # type: ignore

        for city, state, lat, lon in _CITIES:
            key = (str(city).strip(), str(state).strip())
            if key[0] and key[1]:
                coords[key] = (float(lat), float(lon))
    except Exception:
        coords = {}

    if not coords:
        coords = dict(_CITY_COORDS_FALLBACK)
    else:
        # Ensure fallback coverage for legacy cities.
        for k, v in _CITY_COORDS_FALLBACK.items():
            coords.setdefault(k, v)

    _CITY_COORDS_CACHE = coords
    return coords


def _get_json(url: str, *, headers: dict[str, str] | None = None, timeout_s: float = 8.0) -> Any:
    req = urllib.request.Request(url, headers=headers or {})
    with urllib.request.urlopen(req, timeout=timeout_s) as resp:
        payload = resp.read()
    return json.loads(payload)


def geocode_us_zip(zip_code: str) -> dict[str, Any]:
    zip_code = (zip_code or "").strip()
    if len(zip_code) >= 5:
        zip_code = zip_code[:5]

    if len(zip_code) != 5 or not zip_code.isdigit():
        raise ValueError("zip must be a 5-digit US ZIP code")

    try:
        data = _get_json(f"{_ZIPPO_BASE}{zip_code}")
    except urllib.error.HTTPError as e:
        if e.code == 404:
            raise LookupError("zip not found") from e
        raise

    data_obj = cast(dict[str, Any], data)
    places = cast(list[dict[str, Any]], data_obj.get("places") or [])
    if not places:
        raise LookupError("zip not found")

    place = places[0]
    try:
        lat = float(place["latitude"])
        lon = float(place["longitude"])
    except Exception as e:  # pragma: no cover
        raise LookupError("zip geocoding unavailable") from e

    return {
        "zip": zip_code,
        "city": place.get("place name"),
        "state": place.get("state abbreviation") or place.get("state"),
        "lat": lat,
        "lon": lon,
    }


def nws_forecast_by_point(lat: float, lon: float) -> dict[str, Any]:
    points = cast(dict[str, Any], _get_json(f"{_NWS_BASE}/points/{lat:.4f},{lon:.4f}", headers=_NWS_HEADERS))
    props = cast(dict[str, Any], points.get("properties") or {})
    forecast_url = props.get("forecast")
    if not forecast_url:
        raise LookupError("forecast unavailable")

    forecast = cast(dict[str, Any], _get_json(str(forecast_url), headers=_NWS_HEADERS))
    fprops = cast(dict[str, Any], forecast.get("properties") or {})
    periods = cast(list[dict[str, Any]], fprops.get("periods") or [])

    simplified_periods: list[dict[str, Any]] = []
    for p in periods[:8]:
        simplified_periods.append(
            {
                "name": p.get("name"),
                "startTime": p.get("startTime"),
                "isDaytime": p.get("isDaytime"),
                "temperature": p.get("temperature"),
                "temperatureUnit": p.get("temperatureUnit"),
                "windSpeed": p.get("windSpeed"),
                "windDirection": p.get("windDirection"),
                "shortForecast": p.get("shortForecast"),
                "detailedForecast": p.get("detailedForecast"),
                "icon": p.get("icon"),
            }
        )

    rel_root = cast(dict[str, Any], props.get("relativeLocation") or {})
    rel = cast(dict[str, Any], rel_root.get("properties") or {})
    location_label: str | None = None
    city = cast(str | None, rel.get("city"))
    state = cast(str | None, rel.get("state"))
    if city and state:
        location_label = f"{city}, {state}"

    return {
        "location": location_label,
        "periods": simplified_periods,
        "units": fprops.get("units"),
        "updated": fprops.get("updated"),
    }


def geocode_city_state(city: str, state: str) -> dict[str, Any]:
    key = (str(city or "").strip(), str(state or "").strip())
    if not key[0] or not key[1]:
        raise ValueError("city/state required")
    coords = _city_coords().get(key)
    if not coords:
        raise LookupError(f"city/state not supported: {key[0]}, {key[1]}")
    return {"city": key[0], "state": key[1], "lat": coords[0], "lon": coords[1]}


def _c_to_f(c: float) -> float:
    return (c * 9.0 / 5.0) + 32.0


def nws_current_by_point(lat: float, lon: float) -> dict[str, Any]:
    """Fetch latest NWS observation near a point.

    Uses:
    - /points/{lat,lon} to find stations
    - /stations/{id}/observations/latest for current conditions
    """
    points = cast(dict[str, Any], _get_json(f"{_NWS_BASE}/points/{lat:.4f},{lon:.4f}", headers=_NWS_HEADERS))
    props = cast(dict[str, Any], points.get("properties") or {})
    stations_url = props.get("observationStations")
    if not stations_url:
        raise LookupError("stations unavailable")

    stations = cast(dict[str, Any], _get_json(str(stations_url), headers=_NWS_HEADERS))
    features = cast(list[dict[str, Any]], stations.get("features") or [])
    if not features:
        raise LookupError("no stations found")

    station_props = cast(dict[str, Any], features[0].get("properties") or {})
    station_id = station_props.get("stationIdentifier") or station_props.get("id")
    if not station_id:
        # Fall back to parsing the station URL from feature.id
        station_id = features[0].get("id")
    if not station_id:
        raise LookupError("station id unavailable")

    obs = cast(dict[str, Any], _get_json(f"{_NWS_BASE}/stations/{station_id}/observations/latest", headers=_NWS_HEADERS))
    oprops = cast(dict[str, Any], obs.get("properties") or {})

    temp = cast(dict[str, Any], oprops.get("temperature") or {})
    temp_c = temp.get("value")
    temp_f = _c_to_f(float(temp_c)) if isinstance(temp_c, (int, float)) else None

    wind_speed = cast(dict[str, Any], oprops.get("windSpeed") or {})
    wind_mps = wind_speed.get("value")

    return {
        "timestamp": oprops.get("timestamp"),
        "text": oprops.get("textDescription"),
        "temperature_c": float(temp_c) if isinstance(temp_c, (int, float)) else None,
        "temperature_f": float(temp_f) if isinstance(temp_f, (int, float)) else None,
        "wind_mps": float(wind_mps) if isinstance(wind_mps, (int, float)) else None,
    }


def merge_alerts_for_points(points: list[tuple[float, float]]) -> dict[str, Any]:
    seen: set[str] = set()
    merged: list[dict[str, Any]] = []
    failures = 0
    for lat, lon in points:
        try:
            payload = nws_alerts_by_point(lat, lon)
        except Exception:
            failures += 1
            continue
        for a in cast(list[dict[str, Any]], payload.get("alerts") or []):
            aid = str(a.get("id") or "")
            if not aid or aid in seen:
                continue
            seen.add(aid)
            merged.append(a)
    return {
        "count": len(merged),
        "alerts": merged,
        "partial": failures > 0,
        "failures": failures,
    }


def nws_alerts_by_point(lat: float, lon: float, *, timeout_s: float = _NWS_ALERTS_TIMEOUT_S) -> dict[str, Any]:
    data = cast(
        dict[str, Any],
        _get_json(
            f"{_NWS_BASE}/alerts/active?point={lat:.4f},{lon:.4f}",
            headers=_NWS_HEADERS,
            timeout_s=timeout_s,
        ),
    )
    features = cast(list[dict[str, Any]], data.get("features") or [])

    alerts: list[dict[str, Any]] = []
    for feat in features[:10]:
        props = cast(dict[str, Any], feat.get("properties") or {})
        alerts.append(
            {
                "id": props.get("id") or feat.get("id"),
                "event": props.get("event"),
                "severity": props.get("severity"),
                "urgency": props.get("urgency"),
                "certainty": props.get("certainty"),
                "headline": props.get("headline"),
                "description": props.get("description"),
                "instruction": props.get("instruction"),
                "sent": props.get("sent"),
                "effective": props.get("effective"),
                "ends": props.get("ends"),
                "expires": props.get("expires"),
                "web": props.get("web"),
            }
        )

    return {
        "count": len(features),
        "alerts": alerts,
        "updated": data.get("updated"),
    }


def forecast_for_zip(zip_code: str) -> dict[str, Any]:
    loc = geocode_us_zip(zip_code)
    forecast = nws_forecast_by_point(loc["lat"], loc["lon"])
    return {
        "zip": loc["zip"],
        "location": forecast.get("location") or (f"{loc.get('city')}, {loc.get('state')}" if loc.get("city") and loc.get("state") else None),
        "lat": loc["lat"],
        "lon": loc["lon"],
        "forecast": forecast,
    }


def alerts_for_zip(zip_code: str) -> dict[str, Any]:
    loc = geocode_us_zip(zip_code)
    try:
        alerts = nws_alerts_by_point(loc["lat"], loc["lon"])
    except Exception:
        alerts = {"count": 0, "alerts": [], "updated": None, "unavailable": True}
    return {
        "zip": loc["zip"],
        "location": f"{loc.get('city')}, {loc.get('state')}" if loc.get("city") and loc.get("state") else None,
        "lat": loc["lat"],
        "lon": loc["lon"],
        "alerts": alerts,
    }
