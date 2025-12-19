from __future__ import annotations

import argparse
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from app.data import detect_and_parse_import
from app.filters import apply_filters, apply_sort
from app.models import LoadsQuery


def _load_dataset(path: Path) -> list[dict[str, Any]]:
    content = path.read_bytes()
    loads, _kind = detect_and_parse_import(path.name, content)
    return [l.model_dump(mode="json") for l in loads]


def _loads_query_from_args(args: argparse.Namespace) -> LoadsQuery:
    # Only map CLI flags we support; keep it small.
    return LoadsQuery(
        q=args.q,
        equipment=args.equipment,
        weight_min=args.weight_min,
        weight_max=args.weight_max,
        hazmat=args.hazmat,
        deadhead_max=args.deadhead_max,
        rpm_min=args.rpm_min,
        broker_rating_min=args.broker_rating_min,
        detention=args.detention,
        multi_stop=args.multi_stop,
        lane_history=args.lane_history,
        sort=args.sort,
    )


def _print_load_row(load: dict[str, Any]) -> None:
    origin = load["origin"]
    dest = load["destination"]
    print(
        f"{load['id']} | {origin['city']}, {origin['state']} -> {dest['city']}, {dest['state']}"
        f" | ${load['rate_total_usd']:.0f} | ${load['rpm']:.2f}/mi"
        f" | dh {load['deadhead_miles']:.0f} | {load['equipment']} | {load['weight_lbs']} lbs"
    )


def cmd_list(args: argparse.Namespace) -> int:
    path = Path(args.data)
    content = path.read_bytes()
    loads, _kind = detect_and_parse_import(path.name, content)
    query = _loads_query_from_args(args)
    now = datetime.now(timezone.utc)

    filtered = apply_filters(loads, query)
    ranked = apply_sort(filtered, query, now)

    limit = max(1, int(args.limit))
    print(f"source={path.name} total={len(ranked)} showing={min(limit, len(ranked))} sort={args.sort}")
    for load in ranked[:limit]:
        _print_load_row(load.model_dump(mode="json"))
    return 0


def cmd_detail(args: argparse.Namespace) -> int:
    path = Path(args.data)
    content = path.read_bytes()
    loads, _kind = detect_and_parse_import(path.name, content)

    for load in loads:
        if load.id == args.id:
            print(json.dumps(load.model_dump(mode="json"), indent=2))
            return 0
    print("not found")
    return 2


def main() -> int:
    parser = argparse.ArgumentParser(description="Loadboard MVP CLI (output bundle)")
    parser.add_argument(
        "--data",
        default=str(Path(__file__).resolve().parent / "sample_data" / "user_lane_rate_sample.json"),
        help="Path to JSON/CSV dataset",
    )

    sub = parser.add_subparsers(dest="cmd", required=True)

    p_list = sub.add_parser("list", help="List loads with filters/sort")
    p_list.add_argument("--q", default=None)
    p_list.add_argument("--equipment", default=None)
    p_list.add_argument("--weight-min", dest="weight_min", type=int, default=None)
    p_list.add_argument("--weight-max", dest="weight_max", type=int, default=None)
    p_list.add_argument("--hazmat", type=lambda s: s.lower() == "true", default=None)
    p_list.add_argument("--deadhead-max", dest="deadhead_max", type=float, default=None)
    p_list.add_argument("--rpm-min", dest="rpm_min", type=float, default=None)
    p_list.add_argument("--broker-rating-min", dest="broker_rating_min", type=float, default=None)
    p_list.add_argument("--detention", type=lambda s: s.lower() == "true", default=None)
    p_list.add_argument("--multi-stop", dest="multi_stop", type=lambda s: s.lower() == "true", default=None)
    p_list.add_argument("--lane-history", dest="lane_history", type=lambda s: s.lower() == "true", default=None)
    p_list.add_argument(
        "--sort",
        choices=["composite", "rpm_desc", "pickup_soonest", "deadhead_asc", "broker_desc"],
        default="composite",
    )
    p_list.add_argument("--limit", type=int, default=20)
    p_list.set_defaults(func=cmd_list)

    p_detail = sub.add_parser("detail", help="Print one load JSON")
    p_detail.add_argument("id")
    p_detail.set_defaults(func=cmd_detail)

    args = parser.parse_args()
    return int(args.func(args))


if __name__ == "__main__":
    raise SystemExit(main())
