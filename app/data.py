from __future__ import annotations

import csv
import json
import random
import uuid
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Iterable, List, Tuple

from .models import Broker, Load, Location


_CITIES: list[tuple[str, str]] = [
    ("Atlanta", "GA"),
    ("Chicago", "IL"),
    ("Dallas", "TX"),
    ("Denver", "CO"),
    ("Kansas City", "MO"),
    ("Los Angeles", "CA"),
    ("Miami", "FL"),
    ("Nashville", "TN"),
    ("New York", "NY"),
    ("Phoenix", "AZ"),
    ("Salt Lake City", "UT"),
    ("Seattle", "WA"),
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


def _rand_city(excluding: tuple[str, str] | None = None) -> tuple[str, str]:
    options = [c for c in _CITIES if c != excluding]
    return random.choice(options)


def generate_synthetic_loads(count: int) -> Dataset:
    now = _now_utc()
    loads: list[Load] = []
    for _ in range(count):
        origin_city = _rand_city()
        dest_city = _rand_city(excluding=origin_city)

        pickup_start = now + timedelta(hours=random.randint(1, 72))
        pickup_end = pickup_start + timedelta(hours=random.randint(2, 10))
        transit_hours = random.randint(8, 60)
        delivery_start = pickup_end + timedelta(hours=transit_hours)
        delivery_end = delivery_start + timedelta(hours=random.randint(2, 10))

        distance = float(random.randint(150, 2200))
        deadhead = float(random.randint(0, 250))
        equipment = random.choice(_EQUIPMENT)
        weight = random.randint(5000, 46000)
        hazmat = random.random() < 0.08
        detention = random.random() < 0.35
        multi_stop = random.random() < 0.12
        lane_history = random.random() < 0.25
        commodity = random.choice(_COMMODITIES)

        base_rpm = random.uniform(1.6, 3.4)
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

        broker = Broker(name=random.choice(_BROKERS), rating=round(random.uniform(2.5, 5.0), 1))
        posted_at = now - timedelta(hours=random.randint(1, 48))
        updated_at = now - timedelta(minutes=random.randint(0, 180))

        loads.append(
            Load(
                id=str(uuid.uuid4()),
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
