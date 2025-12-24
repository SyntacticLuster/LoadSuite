from __future__ import annotations

import csv
import json
import random
import math
import uuid
import hashlib
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Iterable, List, Tuple

from .models import Broker, Load, Location


_CITIES: list[tuple[str, str, float, float]] = [
    ("Atlanta", "GA", 33.7490, -84.3880),
    ("Chicago", "IL", 41.8781, -87.6298),
    ("Dallas", "TX", 32.7767, -96.7970),
    ("Denver", "CO", 39.7392, -104.9903),
    ("Kansas City", "MO", 39.0997, -94.5786),
    ("Los Angeles", "CA", 34.0522, -118.2437),
    ("Miami", "FL", 25.7617, -80.1918),
    ("Nashville", "TN", 36.1627, -86.7816),
    ("New York", "NY", 40.7128, -74.0060),
    ("Phoenix", "AZ", 33.4484, -112.0740),
    ("Salt Lake City", "UT", 40.7608, -111.8910),
    ("Seattle", "WA", 47.6062, -122.3321),

    # Additional cities for broader geographic coverage
    ("Birmingham", "AL", 33.5186, -86.8104),
    ("Mobile", "AL", 30.6954, -88.0399),
    ("Anchorage", "AK", 61.2181, -149.9003),
    ("Tucson", "AZ", 32.2226, -110.9747),
    ("Little Rock", "AR", 34.7465, -92.2896),
    ("Fresno", "CA", 36.7378, -119.7871),
    ("Sacramento", "CA", 38.5816, -121.4944),
    ("San Diego", "CA", 32.7157, -117.1611),
    ("San Jose", "CA", 37.3382, -121.8863),
    ("San Francisco", "CA", 37.7749, -122.4194),
    ("Oakland", "CA", 37.8044, -122.2711),
    ("Long Beach", "CA", 33.7701, -118.1937),
    ("Riverside", "CA", 33.9806, -117.3755),
    ("Bakersfield", "CA", 35.3733, -119.0187),
    ("Stockton", "CA", 37.9577, -121.2908),
    ("Chula Vista", "CA", 32.6401, -117.0842),
    ("Colorado Springs", "CO", 38.8339, -104.8214),
    ("Aurora", "CO", 39.7294, -104.8319),
    ("Tampa", "FL", 27.9506, -82.4572),
    ("Orlando", "FL", 28.5383, -81.3792),
    ("St. Petersburg", "FL", 27.7676, -82.6403),
    ("Jacksonville", "FL", 30.3322, -81.6557),
    ("Tallahassee", "FL", 30.4383, -84.2807),
    ("Honolulu", "HI", 21.3069, -157.8583),
    ("Boise", "ID", 43.6150, -116.2023),
    ("Indianapolis", "IN", 39.7684, -86.1581),
    ("Fort Wayne", "IN", 41.0793, -85.1394),
    ("Des Moines", "IA", 41.5868, -93.6250),
    ("Wichita", "KS", 37.6872, -97.3301),
    ("Louisville", "KY", 38.2527, -85.7585),
    ("New Orleans", "LA", 29.9511, -90.0715),
    ("Shreveport", "LA", 32.5252, -93.7502),
    ("Portland", "ME", 43.6591, -70.2568),
    ("Baltimore", "MD", 39.2904, -76.6122),
    ("Boston", "MA", 42.3601, -71.0589),
    ("Detroit", "MI", 42.3314, -83.0458),
    ("Grand Rapids", "MI", 42.9634, -85.6681),
    ("Minneapolis", "MN", 44.9778, -93.2650),
    ("Saint Paul", "MN", 44.9537, -93.0900),
    ("Jackson", "MS", 32.2988, -90.1848),
    ("Omaha", "NE", 41.2565, -95.9345),
    ("Las Vegas", "NV", 36.1699, -115.1398),
    ("Reno", "NV", 39.5296, -119.8138),
    ("Albuquerque", "NM", 35.0844, -106.6504),
    ("Santa Fe", "NM", 35.6870, -105.9378),
    ("Rochester", "NY", 43.1566, -77.6088),
    ("Buffalo", "NY", 42.8864, -78.8784),
    ("Syracuse", "NY", 43.0481, -76.1474),
    ("Yonkers", "NY", 40.9312, -73.8988),
    ("Charlotte", "NC", 35.2271, -80.8431),
    ("Raleigh", "NC", 35.7796, -78.6382),
    ("Durham", "NC", 35.9940, -78.8986),
    ("Greensboro", "NC", 36.0726, -79.7920),
    ("Fargo", "ND", 46.8772, -96.7898),
    ("Akron", "OH", 41.0814, -81.5190),
    ("Cleveland", "OH", 41.4993, -81.6944),
    ("Columbus", "OH", 39.9612, -82.9988),
    ("Oklahoma City", "OK", 35.4676, -97.5164),
    ("Tulsa", "OK", 36.15398, -95.992775),
    ("Portland", "OR", 45.5152, -122.6784),
    ("Allentown", "PA", 40.6084, -75.4902),
    ("Philadelphia", "PA", 39.9526, -75.1652),
    ("Pittsburgh", "PA", 40.4406, -79.9959),
    ("Providence", "RI", 41.8236, -71.4222),
    ("Charleston", "SC", 32.7765, -79.9311),
    ("Columbia", "SC", 34.0007, -81.0348),
    ("Sioux Falls", "SD", 43.5446, -96.7311),
    ("Knoxville", "TN", 35.9606, -83.9207),
    ("Memphis", "TN", 35.1495, -90.0490),
    ("Austin", "TX", 30.2672, -97.7431),
    ("Houston", "TX", 29.7604, -95.3698),
    ("San Antonio", "TX", 29.4241, -98.4936),
    ("El Paso", "TX", 31.7619, -106.4850),
    ("Fort Worth", "TX", 32.7555, -97.3308),
    ("Lubbock", "TX", 33.5779, -101.8552),
    ("Corpus Christi", "TX", 27.8006, -97.3964),
    ("Burlington", "VT", 44.4759, -73.2121),
    ("Virginia Beach", "VA", 36.8529, -75.9780),
    ("Norfolk", "VA", 36.8508, -76.2859),
    ("Richmond", "VA", 37.5407, -77.4360),
    ("Spokane", "WA", 47.6588, -117.4260),
    ("Tacoma", "WA", 47.2529, -122.4443),
    ("Milwaukee", "WI", 43.0389, -87.9065),
    ("Madison", "WI", 43.0731, -89.4012),
    ("Green Bay", "WI", 44.5133, -88.0133),
    ("Cheyenne", "WY", 41.139981, -104.820246),
    ("Casper", "WY", 42.8501, -106.3252),
]

_EQUIPMENT: list[str] = [
    "Dry Van",
    "Reefer",
    "Flatbed",
    "Power Only",
]

_COMMODITIES: list[str] = [
    "General Freight",
    "Food",
    "Paper",
    "Building Materials",
    "Automotive",
    "Chemicals",
]

_BROKERS: list[str] = [
    "Acme Logistics",
    "Bluebird Brokerage",
    "Canyon Freight",
    "Delta Carrier Services",
    "Evergreen Transport",
]


@dataclass
class Dataset:
    loads: list[Load]
    source: str  # "synthetic" | "import"


def _now_utc() -> datetime:
    return datetime.now(timezone.utc)


def _rand_city(excluding: tuple[str, str] | None = None) -> tuple[str, str, float, float]:
    """Pick a random city tuple (city, state, lat, lon).

    `excluding` may be a (city, state) pair or a full (city, state, lat, lon) tuple.
    Comparison is done by city/state to preserve previous semantics.
    """
    def _matches(c: tuple[str, str, float, float]) -> bool:
        if excluding is None:
            return False
        # Support callers passing either (city, state) or the full 4-tuple
        try:
            return (c[0], c[1]) == (excluding[0], excluding[1])
        except Exception:
            return False

    options = [c for c in _CITIES if not _matches(c)]
    return random.choice(options)


def _haversine_miles(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    """Great-circle distance in miles between two lat/lon points using Haversine."""
    R = 3958.8  # Earth radius in miles
    dlat = math.radians(lat2 - lat1)
    dlon = math.radians(lon2 - lon1)
    lat1r = math.radians(lat1)
    lat2r = math.radians(lat2)
    a = math.sin(dlat / 2) ** 2 + math.cos(lat1r) * math.cos(lat2r) * math.sin(dlon / 2) ** 2
    c = 2 * math.asin(min(1.0, math.sqrt(a)))
    return R * c


def _route_distance_miles(origin: tuple[str, str, float, float], dest: tuple[str, str, float, float]) -> float:
    """Estimate route distance by applying a small routing factor to straight-line distance."""
    base = _haversine_miles(origin[2], origin[3], dest[2], dest[3])
    factor = random.uniform(1.07, 1.18)
    return base * factor


@dataclass
class BrokerProfile:
    base_rating: float
    rating_display: float
    has_lane_history: bool
    detention_risk_flag: bool


# Broker profiles keyed by seed (int or None) then broker name. Profiles are
# intended to be stable per-broker within a process and deterministic when a
# seed is provided.
_BROKER_PROFILES: dict[int | None, dict[str, BrokerProfile]] = {}


def _lerp(a: float, b: float, t: float) -> float:
    return a + (b - a) * t


def _clamp(v: float, lo: float, hi: float) -> float:
    return max(lo, min(hi, v))


def _deterministic_hash_bytes(seed_key: int | None, name: str) -> bytes:
    key = f"{seed_key}:{name}".encode("utf-8")
    return hashlib.sha256(key).digest()


def _get_or_create_broker_profile(name: str, rng: random.Random, seed_key: int | None = None) -> BrokerProfile:
    profiles = _BROKER_PROFILES.setdefault(seed_key, {})
    if name in profiles:
        return profiles[name]

    # base_rating: 2.5 - 5.0, one decimal
    base_rating = round(rng.uniform(2.5, 5.0), 1)

    # Stable per-broker noise in {-0.1, 0.0, +0.1}
    if seed_key is not None:
        h = _deterministic_hash_bytes(seed_key, name)
        noise_idx = int.from_bytes(h[0:4], "big") % 3
        noise = (-0.1, 0.0, 0.1)[noise_idx]
    else:
        noise = (-0.1, 0.0, 0.1)[int(rng.random() * 3) % 3]

    rating_display = round(_clamp(base_rating + noise, 1.0, 5.0), 1)

    # Probabilities shaped by rating_display
    t = (rating_display - 1.0) / 4.0
    lane_p = _clamp(_lerp(0.10, 0.85, t), 0.0, 1.0)
    detention_p = _clamp(_lerp(0.60, 0.05, t), 0.0, 1.0)

    # Determine booleans deterministically when seed provided
    if seed_key is not None:
        h = _deterministic_hash_bytes(seed_key, name)
        lane_rand = int.from_bytes(h[4:8], "big") / 2**32
        det_rand = int.from_bytes(h[8:12], "big") / 2**32
        has_lane_history = lane_rand < lane_p
        detention_risk_flag = det_rand < detention_p
    else:
        has_lane_history = rng.random() < lane_p
        detention_risk_flag = rng.random() < detention_p

    profile = BrokerProfile(
        base_rating=base_rating,
        rating_display=rating_display,
        has_lane_history=has_lane_history,
        detention_risk_flag=detention_risk_flag,
    )
    profiles[name] = profile
    return profile


def generate_synthetic_loads(
    count: int,
    rng: random.Random | None = None,
    seed: int | None = None,
    now_override: datetime | None = None,
) -> Dataset:
    """Generate `count` synthetic loads using the provided RNG.

    If `rng` is None, uses the module-level `random` for compatibility.
    If `seed` is provided, broker profiles and any seeded behavior will be stored
    under that seed key so cached datasets with the same seed are consistent.
    The `now_override` parameter allows callers (scripts/tests) to supply a fixed
    anchor time so generated timestamps are deterministic across runs.
    """
    rng = rng or random
    now = now_override or _now_utc()
    loads: list[Load] = []

    # Round-robin coverage pass to ensure every city appears as origin and
    # destination at least once when possible. This helps give good lane coverage
    # when the number of loads is larger than the number of cities.
    cities = list(_CITIES)
    cities_len = len(cities)

    i = 0
    for _ in range(count):
        # For the first 2 * cities_len loads, cycle deterministically through
        # origins and destinations to ensure coverage. After that, sample with RNG.
        if i < 2 * cities_len:
            origin_city = cities[i % cities_len]
            dest_city = cities[(i + 1) % cities_len]
        else:
            origin_city = _rand_city()
            dest_city = _rand_city(excluding=(origin_city[0], origin_city[1]))
        i += 1

        pickup_start = now + timedelta(hours=rng.randint(1, 72))
        pickup_end = pickup_start + timedelta(hours=rng.randint(2, 10))
        transit_hours = rng.randint(8, 60)
        delivery_start = pickup_end + timedelta(hours=transit_hours)
        delivery_end = delivery_start + timedelta(hours=rng.randint(2, 10))

        distance = round(_route_distance_miles(origin_city, dest_city), 1)
        deadhead = round(distance * rng.uniform(0.0, 0.12), 1)
        equipment = rng.choice(_EQUIPMENT)
        weight = rng.randint(5000, 46000)
        hazmat = rng.random() < 0.08
        multi_stop = rng.random() < 0.12

        # Broker profiles provide per-broker consistent ratings and flags.
        broker_name = rng.choice(_BROKERS)
        profile = _get_or_create_broker_profile(broker_name, rng, seed_key=seed)
        detention = profile.detention_risk_flag
        lane_history = profile.has_lane_history
        commodity = rng.choice(_COMMODITIES)

        base_rpm = rng.uniform(1.6, 3.4)
        if equipment == "Reefer":
            base_rpm += 0.2
        if hazmat:
            base_rpm += 0.15
        if multi_stop:
            base_rpm += 0.1
        if detention:
            base_rpm += 0.05

        rate_total = round(base_rpm * distance, 2)
        rpm = round(rate_total / max(distance, 1.0), 3)

        # Use rating_display for API-facing rating (includes stable noise)
        broker = Broker(name=broker_name, rating=profile.rating_display)
        posted_at = now - timedelta(hours=rng.randint(1, 48))
        updated_at = now - timedelta(minutes=rng.randint(0, 180))

        # Use RNG-derived UUID so seeds produce deterministic IDs across restarts
        id_val = str(uuid.UUID(int=rng.getrandbits(128)))
        loads.append(
            Load(
                id=id_val,
                origin=Location(city=origin_city[0], state=origin_city[1]),
                destination=Location(city=dest_city[0], state=dest_city[1]),
                pickup_start=pickup_start,
                pickup_end=pickup_end,
                delivery_start=delivery_start,
                delivery_end=delivery_end,
                equipment=equipment,
                weight_lbs=weight,
                hazmat=hazmat,
                distance_miles=distance,
                deadhead_miles=deadhead,
                rate_total_usd=rate_total,
                rpm=rpm,
                broker=broker,
                detention=detention,
                multi_stop=multi_stop,
                lane_history=lane_history,
                commodity=commodity,
                posted_at=posted_at,
                updated_at=updated_at,
            )
        )
    return Dataset(loads=loads, source="synthetic")


def load_dataset_from_file(path: str | Path) -> Dataset:
    """Load a dataset JSON file (array of loads) and return a Dataset.

    Uses existing validation to ensure the JSON matches the Load model. The
    returned Dataset.source will be set to 'file:<name>' to indicate provenance.
    """
    p = Path(path)
    if not p.exists():
        raise FileNotFoundError(f"Dataset file not found: {p}")
    raw = p.read_bytes()
    loads = loads_from_json_bytes(raw)
    ds = Dataset(loads=loads, source=f"file:{p.name}")
    return ds


# In-process process-local cache for synthetic datasets keyed by (count, seed).
# Note: This cache is per-Python process (multi-worker deployments will have
# one cache per worker process).
_SYNTH_CACHE: dict[tuple[int, int | None], Dataset] = {}


def get_synthetic_dataset(count: int, seed: int | None = None) -> Dataset:
    key = (int(count), int(seed) if seed is not None else None)
    if key in _SYNTH_CACHE:
        return _SYNTH_CACHE[key]

    rng = random.Random(seed) if seed is not None else random.Random()
    # If a seed is provided, clear any existing broker profiles for that seed so
    # generation consumes RNG in a consistent order and remains reproducible
    # across separate runs (pre-populated profiles would otherwise change RNG
    # consumption and break determinism).
    if seed is not None:
        _BROKER_PROFILES[int(seed)] = {}

    ds = generate_synthetic_loads(count, rng=rng, seed=int(seed) if seed is not None else None)
    _SYNTH_CACHE[key] = ds
    return ds


def _parse_bool(value: str | None) -> bool | None:
    if value is None:
        return None
    v = value.strip().lower()
    if v in {"true", "1", "yes", "y"}:
        return True
    if v in {"false", "0", "no", "n"}:
        return False
    return None


def loads_from_json_bytes(data: bytes) -> list[Load]:
    raw = json.loads(data.decode("utf-8"))
    if not isinstance(raw, list):
        raise ValueError("JSON must be an array of load objects")
    return [Load.model_validate(item) for item in raw]


def loads_from_csv_bytes(
    data: bytes,
    *,
    max_records: int | None = None,
    max_line_length: int | None = None,
    max_field_length: int | None = None,
) -> list[Load]:
    text = data.decode("utf-8")
    lines = text.splitlines()

    if max_line_length is not None:
        limit = int(max_line_length)
        for i, line in enumerate(lines):
            if len(line) > limit:
                raise ValueError(f"CSV line {i + 1} too long")

    reader = csv.DictReader(lines)
    required_columns = {
        "origin_city",
        "origin_state",
        "destination_city",
        "destination_state",
        "pickup_start",
        "pickup_end",
        "delivery_start",
        "delivery_end",
        "equipment",
        "weight_lbs",
        "distance_miles",
        "deadhead_miles",
        "rate_total_usd",
        "rpm",
        "posted_at",
        "updated_at",
    }

    headers = set(reader.fieldnames or [])
    missing = sorted(required_columns.difference(headers))
    if missing:
        raise ValueError(f"Missing required CSV columns: {', '.join(missing)}")

    loads: list[Load] = []
    limit_records = int(max_records) if max_records is not None else None
    limit_field = int(max_field_length) if max_field_length is not None else None

    for idx, row in enumerate(reader):
        if limit_records is not None and idx >= limit_records:
            raise ValueError(f"Too many records (max {limit_records})")

        if limit_field is not None:
            for k, v in row.items():
                if v is not None and len(v) > limit_field:
                    raise ValueError(f"CSV field too long: {k}")

        row_number = idx + 1

        def _coerce_float(value, field: str, *, allow_blank: bool = False, none_on_non_numeric: bool = False) -> float | None:
            if value is None:
                if allow_blank:
                    return None
                raise ValueError(f"Row {row_number}: missing {field}")

            if isinstance(value, str):
                value = value.strip()
                if value == "":
                    if allow_blank:
                        return None
                    raise ValueError(f"Row {row_number}: missing {field}")

            try:
                return float(value)
            except (TypeError, ValueError):
                if none_on_non_numeric:
                    return None
                raise ValueError(f"Row {row_number}: invalid {field}") from None

        distance_miles = _coerce_float(row.get("distance_miles"), "distance_miles", allow_blank=True)
        rate_total_usd = _coerce_float(row.get("rate_total_usd"), "rate_total_usd", allow_blank=True)
        rpm = _coerce_float(row.get("rpm"), "rpm", allow_blank=True, none_on_non_numeric=True)

        if rpm is None or rpm <= 0:
            if distance_miles is None:
                raise ValueError(f"Row {row_number}: missing distance_miles for rpm synthesis")
            if rate_total_usd is None:
                raise ValueError(f"Row {row_number}: missing rate_total_usd for rpm synthesis")

            rpm = round(rate_total_usd / max(distance_miles, 1.0), 3)
        else:
            rpm = round(rpm, 3)

        deadhead_miles = _coerce_float(row.get("deadhead_miles"), "deadhead_miles") or 0.0
        broker_rating = _coerce_float(
            row.get("broker_rating"), "broker_rating", allow_blank=True, none_on_non_numeric=True
        )

        loads.append(
            Load(
                id=row.get("id") or str(uuid.uuid4()),
                origin=Location(city=row["origin_city"], state=row["origin_state"]),
                destination=Location(city=row["destination_city"], state=row["destination_state"]),
                pickup_start=datetime.fromisoformat(row["pickup_start"]),
                pickup_end=datetime.fromisoformat(row["pickup_end"]),
                delivery_start=datetime.fromisoformat(row["delivery_start"]),
                delivery_end=datetime.fromisoformat(row["delivery_end"]),
                equipment=row["equipment"],
                weight_lbs=int(row["weight_lbs"]),
                hazmat=bool(_parse_bool(row.get("hazmat")) or False),
                distance_miles=distance_miles if distance_miles is not None else 0.0,
                deadhead_miles=deadhead_miles,
                rate_total_usd=rate_total_usd if rate_total_usd is not None else 0.0,
                rpm=rpm,
                broker=Broker(
                    name=row.get("broker_name") or "Unknown",
                    rating=broker_rating if broker_rating is not None else 0.0,
                ),
                detention=bool(_parse_bool(row.get("detention")) or False),
                multi_stop=bool(_parse_bool(row.get("multi_stop")) or False),
                lane_history=bool(_parse_bool(row.get("lane_history")) or False),
                commodity=row.get("commodity") or "",
                posted_at=datetime.fromisoformat(row["posted_at"]),
                updated_at=datetime.fromisoformat(row["updated_at"]),
            )
        )

    return loads


def detect_and_parse_import(filename: str, content: bytes) -> tuple[list[Load], str]:
    lower = filename.lower()
    if lower.endswith(".json"):
        return loads_from_json_bytes(content), "json"
    if lower.endswith(".csv"):
        return loads_from_csv_bytes(content), "csv"
    # best-effort: try JSON then CSV
    try:
        return loads_from_json_bytes(content), "json"
    except Exception:
        return loads_from_csv_bytes(content), "csv"


def write_sample_files(base_dir: Path, *, overwrite: bool = False) -> None:
    sample_dir = base_dir / "sample_data"
    sample_dir.mkdir(parents=True, exist_ok=True)

    json_path = sample_dir / "sample_loads.json"
    csv_path = sample_dir / "sample_loads.csv"

    # These files are committed in-repo as static examples. Regenerating them on
    # every server start causes noisy diffs and accidental deploy commits.
    if not overwrite and json_path.exists() and csv_path.exists():
        return

    dataset = generate_synthetic_loads(25)
    json_path.write_text(
        json.dumps([l.model_dump(mode="json") for l in dataset.loads], indent=2),
        encoding="utf-8",
    )

    with csv_path.open("w", newline="", encoding="utf-8") as f:
        writer = csv.writer(f)
        writer.writerow(
            [
                "id",
                "origin_city",
                "origin_state",
                "destination_city",
                "destination_state",
                "pickup_start",
                "pickup_end",
                "delivery_start",
                "delivery_end",
                "equipment",
                "weight_lbs",
                "hazmat",
                "distance_miles",
                "deadhead_miles",
                "rate_total_usd",
                "rpm",
                "broker_name",
                "broker_rating",
                "detention",
                "multi_stop",
                "lane_history",
                "commodity",
                "posted_at",
                "updated_at",
            ]
        )
        for load in dataset.loads:
            writer.writerow(
                [
                    load.id,
                    load.origin.city,
                    load.origin.state,
                    load.destination.city,
                    load.destination.state,
                    load.pickup_start.isoformat(),
                    load.pickup_end.isoformat(),
                    load.delivery_start.isoformat(),
                    load.delivery_end.isoformat(),
                    load.equipment,
                    load.weight_lbs,
                    str(load.hazmat).lower(),
                    load.distance_miles,
                    load.deadhead_miles,
                    load.rate_total_usd,
                    load.rpm,
                    load.broker.name,
                    load.broker.rating,
                    str(load.detention).lower(),
                    str(load.multi_stop).lower(),
                    str(load.lane_history).lower(),
                    load.commodity,
                    load.posted_at.isoformat(),
                    load.updated_at.isoformat(),
                ]
            )
