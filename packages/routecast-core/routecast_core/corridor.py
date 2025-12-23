from __future__ import annotations

from typing import List

from .models import Coordinate


def buffer_polyline(polyline: List[Coordinate], buffer_meters: float) -> List[Coordinate]:
    """Return a stubbed corridor polygon around the input polyline.

    Deterministic placeholder: simply returns the input polyline duplicated as a
    closed ring (first point repeated) to mimic a corridor outline without
    geospatial math. Caller should treat this as a stand-in until a real buffer
    implementation lands.
    """

    if not polyline:
        return []
    ring = list(polyline)
    if polyline[0] != polyline[-1]:
        ring.append(polyline[0])
    return ring
