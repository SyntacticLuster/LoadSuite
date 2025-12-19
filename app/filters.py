from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from typing import Iterable, List, Optional

from .models import Load, LoadsQuery


def _contains(haystack: str, needle: str) -> bool:
    return needle.lower() in haystack.lower()


def apply_filters(loads: Iterable[Load], query: LoadsQuery) -> list[Load]:
    result: list[Load] = []
    for load in loads:
        if query.q:
            q = query.q.strip()
            if q:
                if not (
                    _contains(load.origin.city, q)
                    or _contains(load.origin.state, q)
                    or _contains(load.destination.city, q)
                    or _contains(load.destination.state, q)
                    or _contains(load.commodity, q)
                ):
                    continue

        if query.equipment and load.equipment != query.equipment:
            continue

        if query.weight_min is not None and load.weight_lbs < query.weight_min:
            continue
        if query.weight_max is not None and load.weight_lbs > query.weight_max:
            continue
        if query.hazmat is not None and load.hazmat != query.hazmat:
            continue

        if query.pickup_start is not None and load.pickup_end < query.pickup_start:
            continue
        if query.pickup_end is not None and load.pickup_start > query.pickup_end:
            continue
        if query.delivery_start is not None and load.delivery_end < query.delivery_start:
            continue
        if query.delivery_end is not None and load.delivery_start > query.delivery_end:
            continue

        if query.deadhead_max is not None and load.deadhead_miles > query.deadhead_max:
            continue
        if query.rpm_min is not None and load.rpm < query.rpm_min:
            continue
        if query.broker_rating_min is not None and load.broker.rating < query.broker_rating_min:
            continue

        if query.detention is not None and load.detention != query.detention:
            continue
        if query.multi_stop is not None and load.multi_stop != query.multi_stop:
            continue
        if query.lane_history is not None and load.lane_history != query.lane_history:
            continue

        result.append(load)
    return result


def _composite_score(load: Load, now: datetime) -> float:
    # Higher is better.
    # Keep it simple and deterministic:
    # - rpm (primary)
    # - deadhead penalty
    # - broker rating bonus
    # - pickup urgency bonus (sooner pickup => higher)
    hours_to_pickup = max((load.pickup_start - now).total_seconds() / 3600.0, 0.0)
    pickup_bonus = max(0.0, 48.0 - min(hours_to_pickup, 48.0)) / 48.0  # 0..1
    deadhead_penalty = min(load.deadhead_miles, 300.0) / 300.0  # 0..1
    broker_bonus = load.broker.rating / 5.0  # 0..1
    accessorial_bonus = (0.05 if load.detention else 0.0) + (0.03 if load.multi_stop else 0.0) + (0.02 if load.lane_history else 0.0)

    return (load.rpm * 2.0) + (broker_bonus * 0.75) + (pickup_bonus * 0.5) + accessorial_bonus - (deadhead_penalty * 0.85)


def apply_sort(loads: list[Load], query: LoadsQuery, now: datetime) -> list[Load]:
    if query.sort == "rpm_desc":
        return sorted(loads, key=lambda l: (l.rpm, l.rate_total_usd), reverse=True)
    if query.sort == "pickup_soonest":
        return sorted(loads, key=lambda l: (l.pickup_start, -l.rpm))
    if query.sort == "deadhead_asc":
        return sorted(loads, key=lambda l: (l.deadhead_miles, -l.rpm))
    if query.sort == "broker_desc":
        return sorted(loads, key=lambda l: (l.broker.rating, l.rpm), reverse=True)

    # composite
    return sorted(loads, key=lambda l: _composite_score(l, now), reverse=True)
