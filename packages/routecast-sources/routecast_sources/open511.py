from __future__ import annotations

from typing import List

from routecast_core.models import Coordinate, Overlay


def fetch_events(corridor: List[Coordinate]) -> List[Overlay]:
    """Stub Open511 event fetcher.

    Deterministic placeholder returning no events.
    """

    return []
