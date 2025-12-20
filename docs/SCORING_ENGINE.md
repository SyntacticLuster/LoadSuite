# Scoring Engine

## GreenLight: Transparent Load Scoring for Decision Support

**Version:** 1.0  
**Last Updated:** 2024-12-19

---

## Overview

The **GreenLight Scoring Engine** is the heart of FreightLens's decision support. It transforms raw load data into a single, explainable score (0–100) that answers:

> "How good is this load for me, right now?"

### Design Principles

| Principle | Description |
|-----------|-------------|
| **Transparent** | Every score includes labeled reasons explaining why |
| **Configurable** | Users can adjust weights to match their priorities |
| **Deterministic** | Same inputs always produce same outputs (testable) |
| **Fast** | Score computation adds <5ms per load |
| **Explainable** | No black-box ML; pure weighted factors |

---

## Score Composition

The GreenLight score is a weighted sum of **factor scores**, each normalized to 0–1:

```
GreenLight Score = Σ(factor_score × factor_weight) × 100 / Σ(factor_weight)
```

### Factor Categories

| Category | Weight Range | Description |
|----------|--------------|-------------|
| **Profitability** | 0.0 – 2.0 | Financial return metrics |
| **Feasibility** | 0.0 – 2.0 | Operational constraints |
| **Risk** | 0.0 – 2.0 | Payment and reliability concerns |
| **Preference** | 0.0 – 2.0 | User-specific fit |

Default weight: **1.0** (neutral)  
Weight > 1.0: Factor matters more  
Weight < 1.0: Factor matters less  
Weight = 0.0: Factor ignored

---

## Factor Definitions

### Profitability Factors

#### F1: Rate Per Mile (RPM)

**Purpose:** Measures gross revenue efficiency.

| Input | Formula | Output Range |
|-------|---------|--------------|
| `rate_total_usd` | `rpm = rate / distance` | 0.0 – 1.0 |
| `distance_miles` | | |

**Scoring Function:**

```python
def score_rpm(rpm: float, market_rpm: float | None = None) -> float:
    """
    Score RPM relative to market or absolute thresholds.
    
    Args:
        rpm: Load's rate per mile
        market_rpm: Lane average RPM (if available)
    
    Returns:
        Score from 0.0 (poor) to 1.0 (excellent)
    """
    if market_rpm:
        # Relative scoring: compare to market
        ratio = rpm / market_rpm
        if ratio >= 1.3:
            return 1.0  # 30%+ above market
        elif ratio >= 1.0:
            return 0.7 + (ratio - 1.0) * 1.0  # 0.7–1.0
        elif ratio >= 0.8:
            return 0.4 + (ratio - 0.8) * 1.5  # 0.4–0.7
        else:
            return max(0.0, ratio * 0.5)  # 0.0–0.4
    else:
        # Absolute scoring (no market data)
        if rpm >= 3.50:
            return 1.0
        elif rpm >= 2.50:
            return 0.7 + (rpm - 2.50) * 0.3
        elif rpm >= 2.00:
            return 0.5 + (rpm - 2.00) * 0.4
        elif rpm >= 1.50:
            return 0.2 + (rpm - 1.50) * 0.6
        else:
            return max(0.0, rpm / 7.5)  # Linear to 0
```

**Default Weight:** 1.5 (high importance)

---

#### F2: Net Profit Estimate

**Purpose:** Estimates take-home after variable costs.

| Input | Formula | Output Range |
|-------|---------|--------------|
| `rate_total_usd` | `net = rate - (distance + deadhead) × cost_per_mile - tolls - fuel_adjustment` | 0.0 – 1.0 |
| `distance_miles` | | |
| `deadhead_miles` | | |
| `user.cost_per_mile` | | |

**Scoring Function:**

```python
def score_net_profit(
    rate: float,
    distance: float,
    deadhead: float,
    cost_per_mile: float = 1.50,
    fuel_adjustment: float = 0.0,
) -> float:
    """
    Score estimated net profit.
    
    Profit = Rate - (All Miles × Cost/Mile) - Adjustments
    """
    total_miles = distance + deadhead
    estimated_cost = total_miles * cost_per_mile + fuel_adjustment
    net_profit = rate - estimated_cost
    
    # Score based on profit margin percentage
    margin_pct = (net_profit / rate) * 100 if rate > 0 else 0
    
    if margin_pct >= 40:
        return 1.0
    elif margin_pct >= 25:
        return 0.7 + (margin_pct - 25) * 0.02
    elif margin_pct >= 15:
        return 0.5 + (margin_pct - 15) * 0.02
    elif margin_pct >= 5:
        return 0.2 + (margin_pct - 5) * 0.03
    elif margin_pct >= 0:
        return margin_pct * 0.04
    else:
        return 0.0  # Negative margin
```

**Default Weight:** 1.3

---

#### F3: Revenue Per Hour

**Purpose:** Time-value efficiency for opportunity cost.

| Input | Formula | Output Range |
|-------|---------|--------------|
| `rate_total_usd` | `rph = rate / estimated_hours` | 0.0 – 1.0 |
| `distance_miles` | `hours = distance / avg_speed + dwell + deadhead_time` | |
| `estimated_dwell` | | |

**Scoring Function:**

```python
def score_revenue_per_hour(
    rate: float,
    distance: float,
    deadhead: float,
    avg_speed_mph: float = 50.0,
    dwell_hours: float = 3.0,
) -> float:
    """
    Score revenue per hour including all time costs.
    """
    drive_hours = (distance + deadhead) / avg_speed_mph
    total_hours = drive_hours + dwell_hours
    rph = rate / total_hours if total_hours > 0 else 0
    
    if rph >= 100:
        return 1.0
    elif rph >= 75:
        return 0.7 + (rph - 75) * 0.012
    elif rph >= 50:
        return 0.4 + (rph - 50) * 0.012
    elif rph >= 30:
        return 0.1 + (rph - 30) * 0.015
    else:
        return max(0.0, rph / 300)
```

**Default Weight:** 0.8

---

### Feasibility Factors

#### F4: Deadhead Penalty

**Purpose:** Penalizes empty miles to pickup.

| Input | Formula | Output Range |
|-------|---------|--------------|
| `deadhead_miles` | `penalty = 1 - normalized_deadhead` | 0.0 – 1.0 |
| `user.max_deadhead` | | |

**Scoring Function:**

```python
def score_deadhead(
    deadhead_miles: float,
    max_acceptable: float = 200.0,
    hard_limit: float = 400.0,
) -> float:
    """
    Score inversely to deadhead miles.
    
    Lower deadhead = higher score.
    """
    if deadhead_miles <= 0:
        return 1.0  # No deadhead is perfect
    elif deadhead_miles <= max_acceptable * 0.5:
        return 0.9 + (1 - deadhead_miles / (max_acceptable * 0.5)) * 0.1
    elif deadhead_miles <= max_acceptable:
        return 0.6 + (1 - (deadhead_miles - max_acceptable * 0.5) / (max_acceptable * 0.5)) * 0.3
    elif deadhead_miles <= hard_limit:
        return 0.2 + (1 - (deadhead_miles - max_acceptable) / (hard_limit - max_acceptable)) * 0.4
    else:
        return max(0.0, 0.2 * (1 - (deadhead_miles - hard_limit) / hard_limit))
```

**Default Weight:** 1.2

---

#### F5: Pickup Urgency

**Purpose:** Prioritizes loads with imminent pickup windows.

| Input | Formula | Output Range |
|-------|---------|--------------|
| `pickup_start` | `hours_until = (pickup_start - now).hours` | 0.0 – 1.0 |
| `current_time` | | |

**Scoring Function:**

```python
def score_pickup_urgency(
    hours_until_pickup: float,
    sweet_spot_min: float = 4.0,
    sweet_spot_max: float = 24.0,
) -> float:
    """
    Score based on time until pickup.
    
    Sweet spot: 4-24 hours (optimal planning window)
    Too soon: Risk of missing it
    Too far: Opportunity cost
    """
    if hours_until_pickup < 0:
        return 0.0  # Already past
    elif hours_until_pickup < sweet_spot_min:
        # Too urgent - might not make it
        return 0.5 + (hours_until_pickup / sweet_spot_min) * 0.3
    elif hours_until_pickup <= sweet_spot_max:
        # Sweet spot - ideal timing
        return 0.8 + (1 - (hours_until_pickup - sweet_spot_min) / (sweet_spot_max - sweet_spot_min)) * 0.2
    elif hours_until_pickup <= 72:
        # Acceptable but not urgent
        return 0.4 + (1 - (hours_until_pickup - sweet_spot_max) / (72 - sweet_spot_max)) * 0.4
    else:
        # Far out - less valuable
        return max(0.1, 0.4 * (1 - (hours_until_pickup - 72) / 168))
```

**Default Weight:** 0.6

---

#### F6: Equipment Match

**Purpose:** Binary check for equipment compatibility.

| Input | Formula | Output Range |
|-------|---------|--------------|
| `load.equipment` | `match = load.equipment in user.equipment_types` | 0.0 or 1.0 |
| `user.equipment_types` | | |

**Scoring Function:**

```python
def score_equipment_match(
    load_equipment: str,
    user_equipment: list[str],
    user_can_flex: bool = False,
) -> float:
    """
    Score equipment compatibility.
    """
    if load_equipment in user_equipment:
        return 1.0  # Direct match
    
    # Flexible equipment (e.g., flatbed can sometimes do step deck loads)
    FLEX_COMPATIBLE = {
        "Flatbed": ["Step Deck", "Conestoga"],
        "Dry Van": ["Power Only"],
        "Reefer": ["Dry Van"],  # Reefer can haul dry if needed
    }
    
    if user_can_flex:
        for user_eq in user_equipment:
            if load_equipment in FLEX_COMPATIBLE.get(user_eq, []):
                return 0.7  # Partial match with flexibility
    
    return 0.0  # No match
```

**Default Weight:** 2.0 (hard constraint if no match)

---

#### F7: Weight Constraint

**Purpose:** Ensures load weight within legal/equipment limits.

| Input | Formula | Output Range |
|-------|---------|--------------|
| `load.weight_lbs` | `ok = weight <= user.max_weight` | 0.0 – 1.0 |
| `user.max_weight_lbs` | | |

**Scoring Function:**

```python
def score_weight_constraint(
    load_weight: int,
    max_weight: int = 45000,
    optimal_weight: int = 40000,
) -> float:
    """
    Score based on weight utilization and constraints.
    """
    if load_weight > max_weight:
        return 0.0  # Over limit - hard fail
    elif load_weight >= optimal_weight:
        return 1.0  # Good utilization
    elif load_weight >= optimal_weight * 0.7:
        return 0.7 + (load_weight - optimal_weight * 0.7) / (optimal_weight * 0.3) * 0.3
    else:
        # Light load - less efficient but acceptable
        return 0.5 + (load_weight / (optimal_weight * 0.7)) * 0.2
```

**Default Weight:** 1.0

---

### Risk Factors

#### F8: Broker Rating

**Purpose:** Incorporates community/historical broker reputation.

| Input | Formula | Output Range |
|-------|---------|--------------|
| `broker.rating` | `score = rating / 5.0` | 0.0 – 1.0 |
| `broker.rating_count` | | |

**Scoring Function:**

```python
def score_broker_rating(
    rating: float,
    rating_count: int,
    min_ratings_for_confidence: int = 10,
) -> float:
    """
    Score broker based on rating with confidence adjustment.
    """
    if rating_count == 0:
        return 0.5  # Unknown - neutral
    
    # Base score from rating (0-5 scale)
    base_score = rating / 5.0
    
    # Confidence adjustment
    confidence = min(1.0, rating_count / min_ratings_for_confidence)
    
    # Blend toward neutral (0.5) for low confidence
    adjusted_score = base_score * confidence + 0.5 * (1 - confidence)
    
    return adjusted_score
```

**Default Weight:** 1.0

---

#### F9: Broker Payment Risk

**Purpose:** Assesses likelihood of timely, full payment.

| Input | Formula | Output Range |
|-------|---------|--------------|
| `broker.days_to_pay_avg` | Complex risk model | 0.0 – 1.0 |
| `broker.dispute_rate` | | |
| `broker.chargeback_rate` | | |

**Scoring Function:**

```python
def score_broker_payment_risk(
    days_to_pay_avg: float | None,
    dispute_rate: float | None,
    chargeback_rate: float | None,
    authority_age_days: int | None,
) -> float:
    """
    Score payment risk based on multiple signals.
    
    Lower risk = higher score.
    """
    score = 1.0
    factors_applied = 0
    
    # Days to pay (target: <30 days)
    if days_to_pay_avg is not None:
        if days_to_pay_avg <= 15:
            dtp_score = 1.0
        elif days_to_pay_avg <= 30:
            dtp_score = 0.8 + (30 - days_to_pay_avg) / 75
        elif days_to_pay_avg <= 45:
            dtp_score = 0.5 + (45 - days_to_pay_avg) / 50
        elif days_to_pay_avg <= 60:
            dtp_score = 0.2 + (60 - days_to_pay_avg) / 75
        else:
            dtp_score = max(0.0, 0.2 - (days_to_pay_avg - 60) / 300)
        score *= dtp_score
        factors_applied += 1
    
    # Dispute rate (target: <2%)
    if dispute_rate is not None:
        if dispute_rate <= 0.01:
            dr_score = 1.0
        elif dispute_rate <= 0.03:
            dr_score = 0.8 + (0.03 - dispute_rate) * 10
        elif dispute_rate <= 0.05:
            dr_score = 0.5 + (0.05 - dispute_rate) * 15
        else:
            dr_score = max(0.0, 0.5 - dispute_rate * 5)
        score *= dr_score
        factors_applied += 1
    
    # Chargeback rate (target: <1%)
    if chargeback_rate is not None:
        if chargeback_rate <= 0.005:
            cb_score = 1.0
        elif chargeback_rate <= 0.02:
            cb_score = 0.7 + (0.02 - chargeback_rate) * 20
        else:
            cb_score = max(0.0, 0.7 - chargeback_rate * 20)
        score *= cb_score
        factors_applied += 1
    
    # Authority age (new brokers are riskier)
    if authority_age_days is not None:
        if authority_age_days >= 730:  # 2+ years
            age_score = 1.0
        elif authority_age_days >= 365:
            age_score = 0.8 + (authority_age_days - 365) / 1825
        elif authority_age_days >= 180:
            age_score = 0.6 + (authority_age_days - 180) / 925
        else:
            age_score = 0.3 + (authority_age_days / 600)
        score *= age_score
        factors_applied += 1
    
    if factors_applied == 0:
        return 0.5  # No data - neutral
    
    # Geometric mean of factors
    return score ** (1.0 / factors_applied)
```

**Default Weight:** 1.3

---

#### F10: Detention/Dwell Risk

**Purpose:** Estimates likelihood of detention at facilities.

| Input | Formula | Output Range |
|-------|---------|--------------|
| `facility.avg_dwell_minutes` | Risk assessment | 0.0 – 1.0 |
| `facility.detention_likelihood` | | |
| `load.detention` flag | | |

**Scoring Function:**

```python
def score_dwell_risk(
    origin_dwell_avg: float | None,
    dest_dwell_avg: float | None,
    detention_flag: bool,
    detention_likelihood: str | None,  # "low", "medium", "high"
) -> float:
    """
    Score based on expected dwell/detention time.
    
    Lower expected dwell = higher score.
    """
    score = 1.0
    
    # Detention flag in load posting
    if detention_flag:
        score *= 0.85  # Known detention - mild penalty
    
    # Detention likelihood category
    if detention_likelihood == "high":
        score *= 0.7
    elif detention_likelihood == "medium":
        score *= 0.85
    elif detention_likelihood == "low":
        score *= 1.0
    
    # Facility-specific dwell times
    for dwell_avg in [origin_dwell_avg, dest_dwell_avg]:
        if dwell_avg is not None:
            if dwell_avg <= 60:  # 1 hour or less
                facility_score = 1.0
            elif dwell_avg <= 120:  # 2 hours
                facility_score = 0.9
            elif dwell_avg <= 180:  # 3 hours
                facility_score = 0.75
            elif dwell_avg <= 300:  # 5 hours
                facility_score = 0.5
            else:
                facility_score = max(0.2, 0.5 - (dwell_avg - 300) / 600)
            score *= facility_score
    
    return score
```

**Default Weight:** 0.9

---

### Preference Factors

#### F11: Preferred Lanes

**Purpose:** Boosts loads in user's preferred lanes.

| Input | Formula | Output Range |
|-------|---------|--------------|
| `load.lane` | `match = lane in user.preferred_lanes` | 0.0 – 1.0 |
| `user.preferred_lanes` | | |

**Scoring Function:**

```python
def score_preferred_lane(
    origin: str,
    destination: str,
    preferred_lanes: list[str],
    home_base: str | None,
) -> float:
    """
    Score based on user lane preferences.
    """
    lane_key = f"{origin}:{destination}"
    reverse_lane = f"{destination}:{origin}"
    
    if lane_key in preferred_lanes:
        return 1.0  # Exact match
    elif reverse_lane in preferred_lanes:
        return 0.8  # Reverse of preferred (backhaul opportunity)
    
    # Check if destination is home base (getting home)
    if home_base and destination == home_base:
        return 0.9
    
    # Check regional preferences
    # (simplified - would use actual region mapping)
    origin_region = origin.split("_")[1] if "_" in origin else origin
    dest_region = destination.split("_")[1] if "_" in destination else destination
    
    for pref_lane in preferred_lanes:
        pref_orig, pref_dest = pref_lane.split(":")
        if origin_region in pref_orig or dest_region in pref_dest:
            return 0.6  # Regional match
    
    return 0.5  # Neutral - no preference data
```

**Default Weight:** 0.7

---

#### F12: Backhaul Probability

**Purpose:** Considers likelihood of finding return load.

| Input | Formula | Output Range |
|-------|---------|--------------|
| `lane.backhaul_probability` | Direct from lane data | 0.0 – 1.0 |
| `destination_market_pressure` | | |

**Scoring Function:**

```python
def score_backhaul_probability(
    backhaul_prob: float | None,
    dest_market_pressure: str | None,  # "shipper", "balanced", "carrier"
    dest_load_volume: int | None,
) -> float:
    """
    Score likelihood of finding return load from destination.
    """
    if backhaul_prob is not None:
        base_score = backhaul_prob  # Direct probability
    else:
        base_score = 0.5  # Unknown - neutral
    
    # Adjust for market conditions
    if dest_market_pressure == "carrier":
        base_score = min(1.0, base_score * 1.2)  # Tight market = easier backhaul
    elif dest_market_pressure == "shipper":
        base_score = base_score * 0.8  # Loose market = harder
    
    # Adjust for volume
    if dest_load_volume is not None:
        if dest_load_volume >= 100:
            base_score = min(1.0, base_score * 1.1)
        elif dest_load_volume <= 10:
            base_score = base_score * 0.9
    
    return base_score
```

**Default Weight:** 0.8

---

## Score Aggregation

### Weighted Sum Formula

```python
from dataclasses import dataclass
from typing import List

@dataclass
class FactorResult:
    name: str
    category: str
    raw_score: float      # 0.0 - 1.0
    weight: float         # User-adjusted weight
    weighted_score: float # raw_score × weight
    contribution_pct: float  # % of final score
    direction: str        # "positive", "negative", "neutral"
    explanation: str      # Human-readable reason

@dataclass
class ScoreResult:
    score: float                    # 0 - 100
    factors: List[FactorResult]     # All computed factors
    top_reasons: List[FactorResult] # Top 5 by |contribution|
    confidence: float               # Data completeness (0-1)


def calculate_greenlight_score(
    load: Load,
    user_prefs: UserPreferences,
    market_data: MarketData | None,
    facility_data: FacilityData | None,
) -> ScoreResult:
    """
    Calculate composite GreenLight score with explainability.
    """
    factors: List[FactorResult] = []
    
    # Calculate each factor
    factors.append(compute_rpm_factor(load, market_data, user_prefs))
    factors.append(compute_net_profit_factor(load, user_prefs))
    factors.append(compute_rph_factor(load, facility_data))
    factors.append(compute_deadhead_factor(load, user_prefs))
    factors.append(compute_pickup_urgency_factor(load))
    factors.append(compute_equipment_factor(load, user_prefs))
    factors.append(compute_weight_factor(load, user_prefs))
    factors.append(compute_broker_rating_factor(load))
    factors.append(compute_broker_risk_factor(load))
    factors.append(compute_dwell_risk_factor(load, facility_data))
    factors.append(compute_preferred_lane_factor(load, user_prefs))
    factors.append(compute_backhaul_factor(load, market_data))
    
    # Aggregate
    total_weight = sum(f.weight for f in factors if f.weight > 0)
    total_weighted_score = sum(f.weighted_score for f in factors)
    
    if total_weight > 0:
        raw_score = total_weighted_score / total_weight
    else:
        raw_score = 0.5  # Neutral if no weights
    
    final_score = round(raw_score * 100, 1)
    
    # Calculate contribution percentages
    for factor in factors:
        if total_weighted_score > 0:
            factor.contribution_pct = (factor.weighted_score / total_weighted_score) * 100
        else:
            factor.contribution_pct = 0
    
    # Top 5 reasons (by absolute contribution)
    sorted_factors = sorted(factors, key=lambda f: abs(f.weighted_score - 0.5 * f.weight), reverse=True)
    top_reasons = sorted_factors[:5]
    
    # Confidence based on data availability
    data_points = sum(1 for f in factors if f.raw_score != 0.5)  # Non-neutral scores
    confidence = data_points / len(factors)
    
    return ScoreResult(
        score=final_score,
        factors=factors,
        top_reasons=top_reasons,
        confidence=confidence,
    )
```

---

## Default Weight Configuration

```python
DEFAULT_WEIGHTS = {
    # Profitability (category weight: 1.3)
    "rpm": 1.5,
    "net_profit": 1.3,
    "revenue_per_hour": 0.8,
    
    # Feasibility (category weight: 1.0)
    "deadhead": 1.2,
    "pickup_urgency": 0.6,
    "equipment_match": 2.0,  # Hard constraint
    "weight_constraint": 1.0,
    
    # Risk (category weight: 1.1)
    "broker_rating": 1.0,
    "broker_payment_risk": 1.3,
    "dwell_risk": 0.9,
    
    # Preference (category weight: 0.8)
    "preferred_lane": 0.7,
    "backhaul_probability": 0.8,
}
```

---

## User Preference Tuning

Users can adjust weights via the Preferences API:

```python
class UserScoringPreferences(BaseModel):
    """User-adjustable scoring weights."""
    
    # Category multipliers (0.0 - 2.0)
    category_profitability: float = Field(default=1.0, ge=0.0, le=2.0)
    category_feasibility: float = Field(default=1.0, ge=0.0, le=2.0)
    category_risk: float = Field(default=1.0, ge=0.0, le=2.0)
    category_preference: float = Field(default=1.0, ge=0.0, le=2.0)
    
    # Individual factor overrides (optional)
    factor_rpm: float | None = Field(default=None, ge=0.0, le=3.0)
    factor_deadhead: float | None = Field(default=None, ge=0.0, le=3.0)
    factor_broker_risk: float | None = Field(default=None, ge=0.0, le=3.0)
    
    # User-specific inputs for calculations
    cost_per_mile_usd: float = Field(default=1.50, ge=0.5, le=5.0)
    max_deadhead_miles: float = Field(default=200, ge=0, le=1000)
    max_weight_lbs: int = Field(default=45000, ge=10000, le=80000)
    preferred_equipment: list[str] = Field(default_factory=list)
    preferred_lanes: list[str] = Field(default_factory=list)
    home_base: str | None = None


def apply_user_preferences(
    default_weights: dict,
    user_prefs: UserScoringPreferences,
) -> dict:
    """
    Compute effective weights by applying user preferences.
    """
    effective = default_weights.copy()
    
    # Apply category multipliers
    profitability_factors = ["rpm", "net_profit", "revenue_per_hour"]
    feasibility_factors = ["deadhead", "pickup_urgency", "equipment_match", "weight_constraint"]
    risk_factors = ["broker_rating", "broker_payment_risk", "dwell_risk"]
    preference_factors = ["preferred_lane", "backhaul_probability"]
    
    for factor in profitability_factors:
        effective[factor] *= user_prefs.category_profitability
    for factor in feasibility_factors:
        effective[factor] *= user_prefs.category_feasibility
    for factor in risk_factors:
        effective[factor] *= user_prefs.category_risk
    for factor in preference_factors:
        effective[factor] *= user_prefs.category_preference
    
    # Apply individual overrides
    if user_prefs.factor_rpm is not None:
        effective["rpm"] = user_prefs.factor_rpm
    if user_prefs.factor_deadhead is not None:
        effective["deadhead"] = user_prefs.factor_deadhead
    if user_prefs.factor_broker_risk is not None:
        effective["broker_payment_risk"] = user_prefs.factor_broker_risk
    
    return effective
```

---

## Explainability Output

Every score includes human-readable explanations:

```json
{
  "score": 78.5,
  "confidence": 0.85,
  "top_reasons": [
    {
      "factor": "rpm",
      "category": "profitability",
      "direction": "positive",
      "contribution_pct": 22.3,
      "explanation": "Rate of $2.85/mi is 14% above market average for this lane"
    },
    {
      "factor": "deadhead",
      "category": "feasibility",
      "direction": "negative",
      "contribution_pct": -15.2,
      "explanation": "Deadhead of 175 miles reduces profitability"
    },
    {
      "factor": "broker_rating",
      "category": "risk",
      "direction": "positive",
      "contribution_pct": 12.1,
      "explanation": "Broker rated 4.5/5 with 127 reviews"
    },
    {
      "factor": "backhaul_probability",
      "category": "preference",
      "direction": "positive",
      "contribution_pct": 9.8,
      "explanation": "Chicago destination has 73% backhaul probability"
    },
    {
      "factor": "pickup_urgency",
      "category": "feasibility",
      "direction": "neutral",
      "contribution_pct": 5.4,
      "explanation": "Pickup in 18 hours is in optimal planning window"
    }
  ]
}
```

---

## Deterministic Mode

For testing and debugging, enable deterministic mode:

```python
class ScoringEngine:
    def __init__(self, deterministic: bool = False, seed: int = 42):
        self.deterministic = deterministic
        self.seed = seed
        if deterministic:
            self._init_deterministic()
    
    def _init_deterministic(self):
        """
        In deterministic mode:
        - Use fixed timestamp for "now"
        - Disable any randomized tie-breakers
        - Use fixed market data if not provided
        """
        self.fixed_now = datetime(2024, 12, 19, 12, 0, 0, tzinfo=timezone.utc)
        self.default_market_rpm = 2.50  # Fixed fallback
    
    def score(self, load: Load, ...) -> ScoreResult:
        now = self.fixed_now if self.deterministic else datetime.now(timezone.utc)
        # ... rest of scoring logic
```

### Test Example

```python
def test_score_determinism():
    """Same inputs must produce identical scores."""
    engine = ScoringEngine(deterministic=True)
    load = make_test_load(seed=123)
    prefs = UserScoringPreferences()
    
    score1 = engine.score(load, prefs)
    score2 = engine.score(load, prefs)
    
    assert score1.score == score2.score
    assert score1.top_reasons == score2.top_reasons
```

---

## Performance Considerations

| Metric | Target | Notes |
|--------|--------|-------|
| Score computation | <5ms per load | Pure Python, no I/O |
| Batch scoring (1000 loads) | <500ms | Parallelizable |
| Memory overhead | <1KB per load | Minimal object allocation |

### Optimization Techniques

1. **Pre-compute constants** — Market averages, regional data cached
2. **Lazy evaluation** — Skip unused factors if weight = 0
3. **Batch mode** — Score multiple loads with shared context
4. **Caching** — Cache broker/facility lookups

```python
class ScoringEngine:
    def __init__(self):
        self._broker_cache: dict[str, BrokerData] = {}
        self._facility_cache: dict[str, FacilityData] = {}
        self._lane_cache: dict[str, LaneData] = {}
    
    def score_batch(
        self,
        loads: list[Load],
        user_prefs: UserScoringPreferences,
    ) -> list[ScoreResult]:
        """
        Score multiple loads efficiently.
        """
        # Pre-fetch all needed broker/facility data
        broker_ids = {load.broker.mc_number for load in loads}
        self._prefetch_brokers(broker_ids)
        
        # Score in parallel (if available)
        results = [self.score(load, user_prefs) for load in loads]
        return results
```

---

## Future Enhancements

### Phase 2: ML-Assisted Calibration

- Use historical booking data to calibrate factor weights
- A/B test different weight configurations
- Personalize based on user booking patterns

### Phase 3: Dynamic Factors

- Real-time fuel price adjustments
- Weather/traffic impact factors
- Time-of-day market adjustments

### Phase 4: Confidence Intervals

- Score ranges instead of point estimates
- Monte Carlo simulation for uncertainty
- Sensitivity analysis ("what if deadhead was 50 miles less?")

---

## Appendix: Current Implementation

The existing `_composite_score()` function in [filters.py](../app/filters.py) provides a simplified version:

```python
def _composite_score(load: Load, now: datetime) -> float:
    hours_to_pickup = max((load.pickup_start - now).total_seconds() / 3600.0, 0.0)
    pickup_bonus = max(0.0, 48.0 - min(hours_to_pickup, 48.0)) / 48.0
    deadhead_penalty = min(load.deadhead_miles, 300.0) / 300.0
    broker_bonus = load.broker.rating / 5.0
    accessorial_bonus = (0.05 if load.detention else 0.0) + \
                        (0.03 if load.multi_stop else 0.0) + \
                        (0.02 if load.lane_history else 0.0)

    return (load.rpm * 2.0) + (broker_bonus * 0.75) + \
           (pickup_bonus * 0.5) + accessorial_bonus - (deadhead_penalty * 0.85)
```

This will be replaced by the full `ScoringEngine` class while maintaining backward compatibility through the same sort interface.
