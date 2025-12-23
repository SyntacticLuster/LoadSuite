from __future__ import annotations

from typing import List

from routecast_core.models import Coordinate, Overlay


def fetch_restrictions(polyline: List[Coordinate]) -> List[Overlay]:
    """Stub OSM restriction query.

    Returns an empty list; real implementation would query OSM/Overpass for
    truck restrictions along the path.
    """

    return []
