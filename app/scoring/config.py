"""Scoring configuration with default weights.

Provides config-driven factor weights following the GreenLight spec.
Weights can be loaded from YAML/JSON or Python dict.
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, Optional


@dataclass(frozen=True)
class FactorConfig:
    """Configuration for a single scoring factor.
    
    Attributes:
        weight: Factor weight (0.0-2.0, default 1.0)
        enabled: Whether this factor is included in scoring
    """
    weight: float = 1.0
    enabled: bool = True


@dataclass
class ScoringConfig:
    """Complete scoring configuration with all factor weights.
    
    Default weights are based on the GreenLight specification.
    Weight ranges: 0.0 (ignored) to 2.0 (high importance)
    """
    
    # Profitability factors
    rpm: FactorConfig = field(default_factory=lambda: FactorConfig(weight=1.5))
    net_profit: FactorConfig = field(default_factory=lambda: FactorConfig(weight=1.3))
    revenue_per_hour: FactorConfig = field(default_factory=lambda: FactorConfig(weight=0.8))
    
    # Feasibility factors
    deadhead: FactorConfig = field(default_factory=lambda: FactorConfig(weight=1.2))
    pickup_urgency: FactorConfig = field(default_factory=lambda: FactorConfig(weight=0.6))
    equipment_match: FactorConfig = field(default_factory=lambda: FactorConfig(weight=2.0))
    weight_constraint: FactorConfig = field(default_factory=lambda: FactorConfig(weight=1.0))
    
    # Risk factors
    broker_rating: FactorConfig = field(default_factory=lambda: FactorConfig(weight=1.0))
    broker_payment_risk: FactorConfig = field(default_factory=lambda: FactorConfig(weight=1.3))
    dwell_risk: FactorConfig = field(default_factory=lambda: FactorConfig(weight=0.9))
    
    # Preference factors
    preferred_lane: FactorConfig = field(default_factory=lambda: FactorConfig(weight=0.7))
    backhaul_probability: FactorConfig = field(default_factory=lambda: FactorConfig(weight=0.8))
    hazmat_compatibility: FactorConfig = field(default_factory=lambda: FactorConfig(weight=2.0))
    
    # Scoring thresholds and constants
    max_acceptable_deadhead: float = 200.0
    deadhead_hard_limit: float = 400.0
    pickup_sweet_spot_min_hours: float = 4.0
    pickup_sweet_spot_max_hours: float = 24.0
    default_dwell_hours: float = 3.0
    default_avg_speed_mph: float = 50.0
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "ScoringConfig":
        """Create config from a dictionary (e.g., loaded from JSON/YAML)."""
        config = cls()
        
        factors = data.get("factors", {})
        for factor_name, factor_data in factors.items():
            if hasattr(config, factor_name):
                if isinstance(factor_data, dict):
                    setattr(config, factor_name, FactorConfig(
                        weight=factor_data.get("weight", 1.0),
                        enabled=factor_data.get("enabled", True),
                    ))
                elif isinstance(factor_data, (int, float)):
                    setattr(config, factor_name, FactorConfig(weight=float(factor_data)))
        
        thresholds = data.get("thresholds", {})
        for key, value in thresholds.items():
            if hasattr(config, key):
                setattr(config, key, value)
        
        return config
    
    @classmethod
    def from_json_file(cls, path: Path) -> "ScoringConfig":
        """Load configuration from a JSON file."""
        with open(path, "r") as f:
            data = json.load(f)
        return cls.from_dict(data)
    
    def to_dict(self) -> Dict[str, Any]:
        """Export configuration to a dictionary."""
        factors = {}
        thresholds = {}
        
        for name in [
            "rpm", "net_profit", "revenue_per_hour",
            "deadhead", "pickup_urgency", "equipment_match", "weight_constraint",
            "broker_rating", "broker_payment_risk", "dwell_risk",
            "preferred_lane", "backhaul_probability", "hazmat_compatibility",
        ]:
            fc = getattr(self, name)
            factors[name] = {"weight": fc.weight, "enabled": fc.enabled}
        
        for name in [
            "max_acceptable_deadhead", "deadhead_hard_limit",
            "pickup_sweet_spot_min_hours", "pickup_sweet_spot_max_hours",
            "default_dwell_hours", "default_avg_speed_mph",
        ]:
            thresholds[name] = getattr(self, name)
        
        return {"factors": factors, "thresholds": thresholds}
    
    def get_factor_weight(self, name: str) -> float:
        """Get weight for a factor, returning 0.0 if disabled or missing."""
        fc = getattr(self, name, None)
        if fc is None or not fc.enabled:
            return 0.0
        return fc.weight


# Default configuration instance
DEFAULT_CONFIG = ScoringConfig()


# Example JSON configuration format (for documentation)
EXAMPLE_CONFIG_JSON = """
{
    "factors": {
        "rpm": {"weight": 1.5, "enabled": true},
        "net_profit": {"weight": 1.3, "enabled": true},
        "revenue_per_hour": {"weight": 0.8, "enabled": true},
        "deadhead": {"weight": 1.2, "enabled": true},
        "pickup_urgency": {"weight": 0.6, "enabled": true},
        "equipment_match": {"weight": 2.0, "enabled": true},
        "weight_constraint": {"weight": 1.0, "enabled": true},
        "broker_rating": {"weight": 1.0, "enabled": true},
        "broker_payment_risk": {"weight": 1.3, "enabled": true},
        "dwell_risk": {"weight": 0.9, "enabled": true},
        "preferred_lane": {"weight": 0.7, "enabled": true},
        "backhaul_probability": {"weight": 0.8, "enabled": true},
        "hazmat_compatibility": {"weight": 2.0, "enabled": true}
    },
    "thresholds": {
        "max_acceptable_deadhead": 200.0,
        "deadhead_hard_limit": 400.0,
        "pickup_sweet_spot_min_hours": 4.0,
        "pickup_sweet_spot_max_hours": 24.0,
        "default_dwell_hours": 3.0,
        "default_avg_speed_mph": 50.0
    }
}
"""
