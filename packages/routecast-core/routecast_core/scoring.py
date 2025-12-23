from __future__ import annotations

from typing import List

from .models import Overlay, RouteResponse, ScoreBreakdown


def score_route(route: RouteResponse, overlays: List[Overlay] | None = None) -> ScoreBreakdown:
    """Deterministic stub score.

    - Base score is 80 minus one point per leg.
    - If overlays are provided, subtract 5 per overlay marked as "major".
    - Clamp to [0, 100].
    """

    overlays = overlays or []
    score = 80 - len(route.legs)
    deductions = sum(5 for o in overlays if o.severity == "major")
    score = max(0.0, min(100.0, score - deductions))

    factors = [f"legs:{len(route.legs)}"]
    if deductions:
        factors.append(f"major_overlays:{deductions/5}")

    summary = "Stub score based on leg count and major overlays"
    reasons: List[str] = []
    if deductions:
        reasons.append("major overlays present")
    if len(route.legs) > 1:
        reasons.append("multiple legs")

    return ScoreBreakdown(
        overall=score,
        risk_score=score,
        summary=summary,
        reasons=reasons,
        factors=factors,
        rationale=summary,
        confidence=0.5,
    )
