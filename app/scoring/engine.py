"""GreenLight Scoring Engine - Pure, Explainable Load Scoring.

This module implements the core scoring algorithm following the GreenLight spec:
- Input: Load + UserPreferences + optional MarketContext
- Output: CompositeScore (0-100) with factor breakdown and explanations

Design principles:
- Pure functions: no side effects, no I/O
- Deterministic: same inputs always produce same outputs
- Explainable: every factor includes human-readable reasoning
- Configurable: weights are driven by ScoringConfig
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Callable, List, Optional

from ..models import Load
from .config import DEFAULT_CONFIG, ScoringConfig
from .models import (
    CompositeScore,
    FactorCategory,
    FactorDirection,
    FactorResult,
    MarketContext,
    UserPreferences,
)


@dataclass
class _FactorComputation:
    """Internal structure for factor computation pipeline."""
    name: str
    display_name: str
    category: FactorCategory
    compute: Callable[[], tuple[float, str]]  # Returns (raw_score, explanation)


class ScoringEngine:
    """Pure, deterministic scoring engine for freight loads.
    
    The engine computes a composite GreenLight score (0-100) by:
    1. Computing individual factor scores (normalized 0-1)
    2. Applying configurable weights to each factor
    3. Aggregating into a weighted sum
    4. Providing transparency through FactorResult explanations
    
    Example:
        >>> engine = ScoringEngine()
        >>> score = engine.score(load, preferences, market_context)
        >>> print(f"Score: {score.score:.1f}")
        >>> for reason in score.top_reasons:
        ...     print(f"  {reason.explanation}")
    """
    
    def __init__(
        self,
        config: ScoringConfig | None = None,
        deterministic_seed: int | None = None,
    ):
        """Initialize the scoring engine.
        
        Args:
            config: Scoring configuration with factor weights. Uses DEFAULT_CONFIG if None.
            deterministic_seed: If set, enables deterministic mode for testing.
                               The seed itself is not used (no randomness in scoring),
                               but its presence is recorded in the output.
        """
        self.config = config or DEFAULT_CONFIG
        self.deterministic_seed = deterministic_seed
    
    def score(
        self,
        load: Load,
        preferences: UserPreferences | None = None,
        market: MarketContext | None = None,
        now: datetime | None = None,
    ) -> CompositeScore:
        """Compute the GreenLight composite score for a load.
        
        Args:
            load: The freight load to score
            preferences: User preferences affecting scoring (uses defaults if None)
            market: Market context for relative scoring (optional)
            now: Current timestamp (uses UTC now if None, for deterministic testing)
        
        Returns:
            CompositeScore with score 0-100, factor breakdown, and top reasons
        """
        prefs = preferences or UserPreferences()
        ctx = market or MarketContext()
        current_time = now or datetime.now(timezone.utc)
        
        # Build factor computations
        factor_specs = self._build_factor_specs(load, prefs, ctx, current_time)
        
        # Compute all factors
        factors: List[FactorResult] = []
        total_weighted = 0.0
        total_weight = 0.0
        
        for spec in factor_specs:
            weight = self.config.get_factor_weight(spec.name)
            if weight <= 0:
                continue  # Skip disabled factors
            
            raw_score, explanation = spec.compute()
            raw_score = max(0.0, min(1.0, raw_score))  # Clamp to [0, 1]
            weighted_score = raw_score * weight
            
            total_weighted += weighted_score
            total_weight += weight
            
            # Determine direction based on raw score
            if raw_score >= 0.7:
                direction: FactorDirection = "positive"
            elif raw_score <= 0.3:
                direction = "negative"
            else:
                direction = "neutral"
            
            factors.append(FactorResult(
                name=spec.name,
                display_name=spec.display_name,
                category=spec.category,
                raw_score=raw_score,
                weight=weight,
                weighted_score=weighted_score,
                contribution_pct=0.0,  # Will update after totals known
                direction=direction,
                explanation=explanation,
            ))
        
        # Calculate final score and contribution percentages
        if total_weight > 0:
            final_score = (total_weighted / total_weight) * 100
        else:
            final_score = 50.0  # Neutral if no factors enabled
        
        # Update contribution percentages
        factors_with_contrib = []
        for f in factors:
            contrib_pct = (f.weighted_score / total_weighted * 100) if total_weighted > 0 else 0.0
            factors_with_contrib.append(FactorResult(
                name=f.name,
                display_name=f.display_name,
                category=f.category,
                raw_score=f.raw_score,
                weight=f.weight,
                weighted_score=f.weighted_score,
                contribution_pct=contrib_pct,
                direction=f.direction,
                explanation=f.explanation,
            ))
        
        # Get top 5 reasons by absolute contribution (both positive and negative matter)
        sorted_by_impact = sorted(
            factors_with_contrib,
            key=lambda f: abs(f.weighted_score - (f.weight * 0.5)),  # Distance from neutral
            reverse=True,
        )
        top_reasons = tuple(sorted_by_impact[:5])
        
        # Calculate confidence based on data completeness
        confidence = self._calculate_confidence(load, ctx)
        
        return CompositeScore(
            score=round(final_score, 2),
            factors=tuple(factors_with_contrib),
            top_reasons=top_reasons,
            confidence=confidence,
            scored_at=current_time,
            deterministic_seed=self.deterministic_seed,
        )
    
    def _build_factor_specs(
        self,
        load: Load,
        prefs: UserPreferences,
        market: MarketContext,
        now: datetime,
    ) -> List[_FactorComputation]:
        """Build the list of factor computations."""
        return [
            # Profitability factors
            _FactorComputation(
                name="rpm",
                display_name="Rate Per Mile",
                category="profitability",
                compute=lambda: self._score_rpm(load, market),
            ),
            _FactorComputation(
                name="net_profit",
                display_name="Net Profit Estimate",
                category="profitability",
                compute=lambda: self._score_net_profit(load, prefs),
            ),
            _FactorComputation(
                name="revenue_per_hour",
                display_name="Revenue Per Hour",
                category="profitability",
                compute=lambda: self._score_revenue_per_hour(load, market),
            ),
            
            # Feasibility factors
            _FactorComputation(
                name="deadhead",
                display_name="Deadhead Distance",
                category="feasibility",
                compute=lambda: self._score_deadhead(load, prefs),
            ),
            _FactorComputation(
                name="pickup_urgency",
                display_name="Pickup Timing",
                category="feasibility",
                compute=lambda: self._score_pickup_urgency(load, now),
            ),
            _FactorComputation(
                name="equipment_match",
                display_name="Equipment Match",
                category="feasibility",
                compute=lambda: self._score_equipment_match(load, prefs),
            ),
            _FactorComputation(
                name="weight_constraint",
                display_name="Weight",
                category="feasibility",
                compute=lambda: self._score_weight_constraint(load, prefs),
            ),
            
            # Risk factors
            _FactorComputation(
                name="broker_rating",
                display_name="Broker Rating",
                category="risk",
                compute=lambda: self._score_broker_rating(load),
            ),
            _FactorComputation(
                name="dwell_risk",
                display_name="Dwell/Detention Risk",
                category="risk",
                compute=lambda: self._score_dwell_risk(load, market),
            ),
            
            # Preference factors
            _FactorComputation(
                name="preferred_lane",
                display_name="Lane Preference",
                category="preference",
                compute=lambda: self._score_preferred_lane(load, prefs),
            ),
            _FactorComputation(
                name="backhaul_probability",
                display_name="Backhaul Likelihood",
                category="preference",
                compute=lambda: self._score_backhaul_probability(market),
            ),
            _FactorComputation(
                name="hazmat_compatibility",
                display_name="Hazmat Compatibility",
                category="feasibility",
                compute=lambda: self._score_hazmat_compatibility(load, prefs),
            ),
        ]
    
    # -------------------------------------------------------------------------
    # Factor Scoring Functions (Pure)
    # -------------------------------------------------------------------------
    
    def _score_rpm(
        self,
        load: Load,
        market: MarketContext,
    ) -> tuple[float, str]:
        """Score rate per mile relative to market or absolute thresholds."""
        rpm = load.rpm
        
        if market.lane_rpm is not None and market.lane_rpm > 0:
            # Relative scoring against market
            ratio = rpm / market.lane_rpm
            if ratio >= 1.3:
                score = 1.0
                explanation = f"${rpm:.2f}/mi is 30%+ above market (${market.lane_rpm:.2f}/mi)"
            elif ratio >= 1.0:
                score = 0.7 + (ratio - 1.0) * 1.0
                explanation = f"${rpm:.2f}/mi is above market average"
            elif ratio >= 0.8:
                score = 0.4 + (ratio - 0.8) * 1.5
                explanation = f"${rpm:.2f}/mi is slightly below market"
            else:
                score = max(0.0, ratio * 0.5)
                explanation = f"${rpm:.2f}/mi is well below market (${market.lane_rpm:.2f}/mi)"
        else:
            # Absolute scoring (no market data)
            if rpm >= 3.50:
                score = 1.0
                explanation = f"Excellent rate at ${rpm:.2f}/mi"
            elif rpm >= 2.50:
                score = 0.7 + (rpm - 2.50) * 0.3
                explanation = f"Good rate at ${rpm:.2f}/mi"
            elif rpm >= 2.00:
                score = 0.5 + (rpm - 2.00) * 0.4
                explanation = f"Average rate at ${rpm:.2f}/mi"
            elif rpm >= 1.50:
                score = 0.2 + (rpm - 1.50) * 0.6
                explanation = f"Below average rate at ${rpm:.2f}/mi"
            else:
                score = max(0.0, rpm / 7.5)
                explanation = f"Poor rate at ${rpm:.2f}/mi"
        
        return score, explanation
    
    def _score_net_profit(
        self,
        load: Load,
        prefs: UserPreferences,
    ) -> tuple[float, str]:
        """Score estimated net profit after operating costs."""
        total_miles = load.distance_miles + load.deadhead_miles
        estimated_cost = total_miles * prefs.cost_per_mile
        net_profit = load.rate_total_usd - estimated_cost
        
        margin_pct = (net_profit / load.rate_total_usd * 100) if load.rate_total_usd > 0 else 0
        
        if margin_pct >= 40:
            score = 1.0
            explanation = f"Excellent margin: ${net_profit:.0f} profit ({margin_pct:.0f}%)"
        elif margin_pct >= 25:
            score = 0.7 + (margin_pct - 25) * 0.02
            explanation = f"Good margin: ${net_profit:.0f} profit ({margin_pct:.0f}%)"
        elif margin_pct >= 15:
            score = 0.5 + (margin_pct - 15) * 0.02
            explanation = f"Moderate margin: ${net_profit:.0f} profit ({margin_pct:.0f}%)"
        elif margin_pct >= 5:
            score = 0.2 + (margin_pct - 5) * 0.03
            explanation = f"Thin margin: ${net_profit:.0f} profit ({margin_pct:.0f}%)"
        elif margin_pct >= 0:
            score = margin_pct * 0.04
            explanation = f"Minimal profit: ${net_profit:.0f} ({margin_pct:.0f}%)"
        else:
            score = 0.0
            explanation = f"Negative margin: ${net_profit:.0f} estimated loss"
        
        return score, explanation
    
    def _score_revenue_per_hour(
        self,
        load: Load,
        market: MarketContext,
    ) -> tuple[float, str]:
        """Score revenue per hour including drive time and dwell."""
        drive_hours = (load.distance_miles + load.deadhead_miles) / self.config.default_avg_speed_mph
        dwell_hours = self.config.default_dwell_hours
        
        # Adjust dwell if market data available
        if market.origin_dwell_avg_minutes is not None:
            dwell_hours = (market.origin_dwell_avg_minutes + (market.dest_dwell_avg_minutes or 120)) / 60
        
        total_hours = drive_hours + dwell_hours
        rph = load.rate_total_usd / total_hours if total_hours > 0 else 0
        
        if rph >= 100:
            score = 1.0
            explanation = f"Excellent ${rph:.0f}/hr revenue"
        elif rph >= 75:
            score = 0.7 + (rph - 75) * 0.012
            explanation = f"Good ${rph:.0f}/hr revenue"
        elif rph >= 50:
            score = 0.4 + (rph - 50) * 0.012
            explanation = f"Average ${rph:.0f}/hr revenue"
        elif rph >= 30:
            score = 0.1 + (rph - 30) * 0.015
            explanation = f"Below average ${rph:.0f}/hr revenue"
        else:
            score = max(0.0, rph / 300)
            explanation = f"Poor ${rph:.0f}/hr revenue"
        
        return score, explanation
    
    def _score_deadhead(
        self,
        load: Load,
        prefs: UserPreferences,
    ) -> tuple[float, str]:
        """Score inversely to deadhead miles."""
        dh = load.deadhead_miles
        max_acc = min(prefs.max_deadhead_miles, self.config.max_acceptable_deadhead)
        hard_limit = self.config.deadhead_hard_limit
        
        if dh <= 0:
            score = 1.0
            explanation = "No deadhead - optimal positioning"
        elif dh <= max_acc * 0.5:
            score = 0.9 + (1 - dh / (max_acc * 0.5)) * 0.1
            explanation = f"Very low deadhead: {dh:.0f} mi"
        elif dh <= max_acc:
            score = 0.6 + (1 - (dh - max_acc * 0.5) / (max_acc * 0.5)) * 0.3
            explanation = f"Acceptable deadhead: {dh:.0f} mi"
        elif dh <= hard_limit:
            score = 0.2 + (1 - (dh - max_acc) / (hard_limit - max_acc)) * 0.4
            explanation = f"High deadhead: {dh:.0f} mi"
        else:
            score = max(0.0, 0.2 * (1 - (dh - hard_limit) / hard_limit))
            explanation = f"Excessive deadhead: {dh:.0f} mi exceeds limit"
        
        return score, explanation
    
    def _score_pickup_urgency(
        self,
        load: Load,
        now: datetime,
    ) -> tuple[float, str]:
        """Score based on time until pickup (sweet spot is 4-24 hours)."""
        delta = (load.pickup_start - now).total_seconds() / 3600
        hours = max(0, delta)
        
        sweet_min = self.config.pickup_sweet_spot_min_hours
        sweet_max = self.config.pickup_sweet_spot_max_hours
        
        if hours < 0:
            score = 0.0
            explanation = "Pickup window already passed"
        elif hours < sweet_min:
            score = 0.5 + (hours / sweet_min) * 0.3
            explanation = f"Very urgent: {hours:.1f}h until pickup"
        elif hours <= sweet_max:
            score = 0.8 + (1 - (hours - sweet_min) / (sweet_max - sweet_min)) * 0.2
            explanation = f"Ideal timing: {hours:.1f}h until pickup"
        elif hours <= 72:
            score = 0.4 + (1 - (hours - sweet_max) / (72 - sweet_max)) * 0.4
            explanation = f"Advance booking: {hours:.1f}h until pickup"
        else:
            score = max(0.1, 0.4 * (1 - (hours - 72) / 168))
            explanation = f"Far out: {hours:.0f}h ({hours/24:.0f} days) until pickup"
        
        return score, explanation
    
    def _score_equipment_match(
        self,
        load: Load,
        prefs: UserPreferences,
    ) -> tuple[float, str]:
        """Score equipment compatibility."""
        load_eq = load.equipment
        user_equipment = prefs.equipment_types
        
        if load_eq in user_equipment:
            return 1.0, f"Equipment match: {load_eq}"
        
        # Check flexible compatibility
        FLEX_COMPATIBLE = {
            "Flatbed": ["Step Deck", "Conestoga"],
            "Dry Van": ["Power Only"],
            "Reefer": ["Dry Van"],
        }
        
        for user_eq in user_equipment:
            if load_eq in FLEX_COMPATIBLE.get(user_eq, []):
                return 0.7, f"Flexible match: {load_eq} (you have {user_eq})"
        
        return 0.0, f"Equipment mismatch: load requires {load_eq}"
    
    def _score_weight_constraint(
        self,
        load: Load,
        prefs: UserPreferences,
    ) -> tuple[float, str]:
        """Score based on weight utilization and constraints."""
        weight = load.weight_lbs
        max_weight = prefs.max_weight_lbs
        optimal_weight = int(max_weight * 0.9)
        
        if weight > max_weight:
            return 0.0, f"Overweight: {weight:,} lbs exceeds {max_weight:,} lb limit"
        elif weight >= optimal_weight:
            return 1.0, f"Good utilization: {weight:,} lbs"
        elif weight >= optimal_weight * 0.7:
            score = 0.7 + (weight - optimal_weight * 0.7) / (optimal_weight * 0.3) * 0.3
            return score, f"Moderate load: {weight:,} lbs"
        else:
            score = 0.5 + (weight / (optimal_weight * 0.7)) * 0.2
            return score, f"Light load: {weight:,} lbs"
    
    def _score_broker_rating(
        self,
        load: Load,
    ) -> tuple[float, str]:
        """Score broker based on rating."""
        rating = load.broker.rating
        
        # Simple normalized score (more sophisticated version would use rating count)
        score = rating / 5.0
        
        if rating >= 4.5:
            explanation = f"Excellent broker: {load.broker.name} ({rating:.1f}★)"
        elif rating >= 4.0:
            explanation = f"Good broker: {load.broker.name} ({rating:.1f}★)"
        elif rating >= 3.0:
            explanation = f"Average broker: {load.broker.name} ({rating:.1f}★)"
        elif rating >= 2.0:
            explanation = f"Below average broker: {load.broker.name} ({rating:.1f}★)"
        else:
            explanation = f"Low-rated broker: {load.broker.name} ({rating:.1f}★)"
        
        return score, explanation
    
    def _score_dwell_risk(
        self,
        load: Load,
        market: MarketContext,
    ) -> tuple[float, str]:
        """Score based on expected dwell/detention time."""
        score = 1.0
        reasons = []
        
        # Detention flag in load
        if load.detention:
            score *= 0.85
            reasons.append("detention likely")
        
        # Market-based detention likelihood
        if market.detention_likelihood == "high":
            score *= 0.7
            reasons.append("high detention area")
        elif market.detention_likelihood == "medium":
            score *= 0.85
            reasons.append("moderate detention area")
        
        # Facility dwell times
        for label, dwell in [("origin", market.origin_dwell_avg_minutes), 
                              ("destination", market.dest_dwell_avg_minutes)]:
            if dwell is not None:
                if dwell <= 60:
                    pass  # No penalty
                elif dwell <= 120:
                    score *= 0.9
                elif dwell <= 180:
                    score *= 0.75
                    reasons.append(f"long {label} dwell")
                elif dwell <= 300:
                    score *= 0.5
                    reasons.append(f"very long {label} dwell")
                else:
                    score *= max(0.2, 0.5 - (dwell - 300) / 600)
                    reasons.append(f"extreme {label} dwell")
        
        if not reasons:
            explanation = "Low dwell/detention risk"
        else:
            explanation = "Dwell risk: " + ", ".join(reasons)
        
        return score, explanation
    
    def _score_preferred_lane(
        self,
        load: Load,
        prefs: UserPreferences,
    ) -> tuple[float, str]:
        """Score based on user lane preferences."""
        origin = f"{load.origin.city}_{load.origin.state}"
        dest = f"{load.destination.city}_{load.destination.state}"
        lane_key = f"{origin}:{dest}"
        reverse_lane = f"{dest}:{origin}"
        
        if lane_key in prefs.preferred_lanes:
            return 1.0, f"Preferred lane: {load.origin.city} → {load.destination.city}"
        
        if reverse_lane in prefs.preferred_lanes:
            return 0.8, f"Reverse of preferred lane (backhaul opportunity)"
        
        # Check if destination is home base
        if prefs.home_base and dest == prefs.home_base:
            return 0.9, "Heading home"
        
        if not prefs.preferred_lanes:
            return 0.5, "No lane preferences set"
        
        return 0.5, "Lane not in preferences"
    
    def _score_backhaul_probability(
        self,
        market: MarketContext,
    ) -> tuple[float, str]:
        """Score likelihood of finding return load."""
        base_score = market.backhaul_probability if market.backhaul_probability is not None else 0.5
        
        # Adjust for market conditions
        if market.market_pressure == "carrier":
            base_score = min(1.0, base_score * 1.2)
            explanation = f"Good backhaul chance ({base_score*100:.0f}%) - carrier's market"
        elif market.market_pressure == "shipper":
            base_score = base_score * 0.8
            explanation = f"Lower backhaul chance ({base_score*100:.0f}%) - shipper's market"
        elif market.lane_volume is not None:
            if market.lane_volume >= 100:
                base_score = min(1.0, base_score * 1.1)
                explanation = f"Decent backhaul chance ({base_score*100:.0f}%) - high volume"
            elif market.lane_volume <= 10:
                base_score = base_score * 0.9
                explanation = f"Lower backhaul chance ({base_score*100:.0f}%) - low volume"
            else:
                explanation = f"Average backhaul chance ({base_score*100:.0f}%)"
        else:
            explanation = "Backhaul probability unknown"
        
        return base_score, explanation
    
    def _score_hazmat_compatibility(
        self,
        load: Load,
        prefs: UserPreferences,
    ) -> tuple[float, str]:
        """Score hazmat load compatibility."""
        if not load.hazmat:
            return 1.0, "Non-hazmat load"
        
        if prefs.hazmat_endorsed:
            return 1.0, "Hazmat load - you are endorsed"
        else:
            return 0.0, "Hazmat load requires endorsement"
    
    # -------------------------------------------------------------------------
    # Confidence Calculation
    # -------------------------------------------------------------------------
    
    def _calculate_confidence(
        self,
        load: Load,
        market: MarketContext,
    ) -> float:
        """Calculate confidence score based on data completeness."""
        checks = [
            load.rpm > 0,
            load.distance_miles > 0,
            load.rate_total_usd > 0,
            load.broker.rating > 0,
            market.lane_rpm is not None,
            market.backhaul_probability is not None,
            market.market_pressure is not None,
        ]
        return sum(1 for c in checks if c) / len(checks)
