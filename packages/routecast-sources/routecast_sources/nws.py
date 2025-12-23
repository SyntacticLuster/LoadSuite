from __future__ import annotations

from typing import List

from routecast_core.models import Coordinate, Overlay


def fetch_alerts_for_corridor(corridor: List[Coordinate]) -> List[Overlay]:
    """Stub NWS alert fetcher.

    Deterministic behavior: returns an empty list to keep downstream tests and
    callers predictable until a real integration is wired.
    """

    return []
