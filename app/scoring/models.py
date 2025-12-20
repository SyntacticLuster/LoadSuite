"""Scoring engine domain models.

Defines data structures for the GreenLight scoring system:
- UserPreferences: User-specific configuration affecting scoring
- MarketContext: External market data that influences scores
- FactorResult: Individual factor contribution with explanation
- CompositeScore: Final aggregated score with transparency
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from typing import Literal, Optional


FactorCategory = Literal["profitability", "feasibility", "risk", "preference"]
FactorDirection = Literal["positive", "negative", "neutral"]


@dataclass(frozen=True)
class UserPreferences:
    """User-specific preferences that influence scoring.
    
    Attributes:
        equipment_types: List of equipment the user can haul (e.g., ["Dry Van", "Reefer"])
        max_deadhead_miles: Maximum acceptable empty miles to pickup
        max_weight_lbs: Maximum weight the user's equipment can handle
        cost_per_mile: Operating cost estimate used for profit calculations
        preferred_lanes: List of "origin:destination" lane strings
        home_base: User's home location (city, state) for backhaul scoring
        hazmat_endorsed: Whether user has hazmat endorsement
        min_broker_rating: Minimum acceptable broker rating (0-5)
    """
    equipment_types: tuple[str, ...] = ("Dry Van",)
    max_deadhead_miles: float = 200.0
    max_weight_lbs: int = 45000
    cost_per_mile: float = 1.50
    preferred_lanes: tuple[str, ...] = ()
    home_base: Optional[str] = None
    hazmat_endorsed: bool = False
    min_broker_rating: float = 0.0


@dataclass(frozen=True)
class MarketContext:
    """External market data for context-aware scoring.
    
    Attributes:
        lane_rpm: Market average RPM for this lane (if known)
        lane_volume: Number of loads posted in lane recently
        market_pressure: Market condition ("shipper", "balanced", "carrier")
        backhaul_probability: Estimated chance of finding return load (0-1)
        origin_dwell_avg_minutes: Average dwell time at origin facility
        dest_dwell_avg_minutes: Average dwell time at destination facility
        detention_likelihood: Categorical risk of detention ("low", "medium", "high")
    """
    lane_rpm: Optional[float] = None
    lane_volume: Optional[int] = None
    market_pressure: Optional[Literal["shipper", "balanced", "carrier"]] = None
    backhaul_probability: Optional[float] = None
    origin_dwell_avg_minutes: Optional[float] = None
    dest_dwell_avg_minutes: Optional[float] = None
    detention_likelihood: Optional[Literal["low", "medium", "high"]] = None


@dataclass(frozen=True)
class FactorResult:
    """Result of a single scoring factor computation.
    
    Provides transparency into how each factor contributed to the final score.
    
    Attributes:
        name: Factor identifier (e.g., "rpm", "deadhead", "broker_rating")
        display_name: Human-readable name (e.g., "Rate Per Mile")
        category: Factor category for grouping
        raw_score: Normalized score from 0.0 to 1.0
        weight: Applied weight for this factor
        weighted_score: raw_score × weight
        contribution_pct: Percentage of final score this factor contributed
        direction: Whether this factor helped, hurt, or was neutral
        explanation: Human-readable explanation of the score
    """
    name: str
    display_name: str
    category: FactorCategory
    raw_score: float
    weight: float
    weighted_score: float
    contribution_pct: float
    direction: FactorDirection
    explanation: str


@dataclass(frozen=True)
class CompositeScore:
    """Complete scoring result with full explainability.
    
    The GreenLight score is a weighted combination of all factors,
    normalized to 0-100 for intuitive interpretation.
    
    Attributes:
        score: Final composite score (0-100)
        factors: All computed factor results
        top_reasons: Top 5 factors by absolute contribution (positive or negative)
        confidence: Data completeness indicator (0-1)
        scored_at: Timestamp when score was computed (for cache validation)
        deterministic_seed: If set, indicates deterministic mode was used
    """
    score: float
    factors: tuple[FactorResult, ...]
    top_reasons: tuple[FactorResult, ...]
    confidence: float
    scored_at: datetime
    deterministic_seed: Optional[int] = None
    
    def get_factor(self, name: str) -> Optional[FactorResult]:
        """Retrieve a specific factor by name."""
        for f in self.factors:
            if f.name == name:
                return f
        return None
    
    def factors_by_category(self, category: FactorCategory) -> tuple[FactorResult, ...]:
        """Get all factors in a specific category."""
        return tuple(f for f in self.factors if f.category == category)
    
    def positive_factors(self) -> tuple[FactorResult, ...]:
        """Get all factors that contributed positively."""
        return tuple(f for f in self.factors if f.direction == "positive")
    
    def negative_factors(self) -> tuple[FactorResult, ...]:
        """Get all factors that contributed negatively."""
        return tuple(f for f in self.factors if f.direction == "negative")
