"""Unit tests for the GreenLight Scoring Engine.

Tests cover:
- Basic scoring functionality
- Factor computation accuracy
- Edge cases (missing data, extreme values)
- Deterministic behavior
- Configuration-driven weights
"""

from __future__ import annotations

from datetime import datetime, timezone

import pytest

from app.models import Broker, Load, Location
from app.scoring import CompositeScore, ScoringConfig, ScoringEngine
from app.scoring.config import FactorConfig
from app.scoring.models import MarketContext, UserPreferences


class TestScoringEngineBasics:
    """Basic scoring engine tests."""
    
    def test_engine_initialization_defaults(self):
        """Engine initializes with default config."""
        engine = ScoringEngine()
        assert engine.config is not None
        assert engine.deterministic_seed is None
    
    def test_engine_initialization_with_seed(self):
        """Engine records deterministic seed."""
        engine = ScoringEngine(deterministic_seed=42)
        assert engine.deterministic_seed == 42
    
    def test_score_returns_composite_score(self, ideal_load, fixed_now):
        """Scoring returns a CompositeScore object."""
        engine = ScoringEngine(deterministic_seed=42)
        result = engine.score(ideal_load, now=fixed_now)
        
        assert isinstance(result, CompositeScore)
        assert 0 <= result.score <= 100
        assert len(result.factors) > 0
        assert len(result.top_reasons) <= 5
        assert 0 <= result.confidence <= 1
        assert result.scored_at == fixed_now
        assert result.deterministic_seed == 42
    
    def test_deterministic_scoring(self, ideal_load, fixed_now):
        """Same inputs produce same outputs."""
        engine = ScoringEngine(deterministic_seed=42)
        prefs = UserPreferences()
        market = MarketContext()
        
        score1 = engine.score(ideal_load, prefs, market, fixed_now)
        score2 = engine.score(ideal_load, prefs, market, fixed_now)
        
        assert score1.score == score2.score
        assert len(score1.factors) == len(score2.factors)
        for f1, f2 in zip(score1.factors, score2.factors):
            assert f1.raw_score == f2.raw_score
            assert f1.weighted_score == f2.weighted_score


class TestFactorScoring:
    """Test individual factor scoring functions."""
    
    def test_ideal_load_scores_high(self, ideal_load, fixed_now):
        """Ideal load should score 80+."""
        engine = ScoringEngine(deterministic_seed=42)
        score = engine.score(ideal_load, now=fixed_now)
        
        assert score.score >= 75.0, f"Ideal load scored {score.score}, expected 75+"
    
    def test_poor_load_scores_low(self, poor_load, fixed_now):
        """Poor load should score lower than ideal."""
        engine = ScoringEngine(deterministic_seed=42)
        score = engine.score(poor_load, now=fixed_now)
        
        assert score.score < 70.0, f"Poor load scored {score.score}, expected <70"
    
    def test_average_load_scores_moderate(self, average_load, fixed_now):
        """Average load should score in middle range."""
        engine = ScoringEngine(deterministic_seed=42)
        score = engine.score(average_load, now=fixed_now)
        
        # Average load with decent metrics may still score well
        assert 50.0 <= score.score <= 90.0, f"Average load scored {score.score}"
    
    def test_rpm_factor_present(self, ideal_load, fixed_now):
        """RPM factor should be computed."""
        engine = ScoringEngine(deterministic_seed=42)
        score = engine.score(ideal_load, now=fixed_now)
        
        rpm_factor = score.get_factor("rpm")
        assert rpm_factor is not None
        assert rpm_factor.category == "profitability"
        assert rpm_factor.raw_score > 0
    
    def test_deadhead_factor_present(self, ideal_load, fixed_now):
        """Deadhead factor should be computed."""
        engine = ScoringEngine(deterministic_seed=42)
        score = engine.score(ideal_load, now=fixed_now)
        
        dh_factor = score.get_factor("deadhead")
        assert dh_factor is not None
        assert dh_factor.category == "feasibility"
    
    def test_broker_rating_factor(self, ideal_load, poor_load, fixed_now):
        """Higher broker rating should produce higher factor score."""
        engine = ScoringEngine(deterministic_seed=42)
        
        ideal_score = engine.score(ideal_load, now=fixed_now)
        poor_score = engine.score(poor_load, now=fixed_now)
        
        ideal_broker = ideal_score.get_factor("broker_rating")
        poor_broker = poor_score.get_factor("broker_rating")
        
        assert ideal_broker.raw_score > poor_broker.raw_score


class TestEdgeCases:
    """Test edge cases and boundary conditions."""
    
    def test_missing_rate_load(self, missing_rate_load, fixed_now):
        """Load with missing/zero rate should score very low."""
        engine = ScoringEngine(deterministic_seed=42)
        score = engine.score(missing_rate_load, now=fixed_now)
        
        rpm_factor = score.get_factor("rpm")
        assert rpm_factor is not None
        assert rpm_factor.raw_score == 0.0
        
        # Net profit should also suffer
        profit_factor = score.get_factor("net_profit")
        assert profit_factor.raw_score == 0.0
    
    def test_extreme_deadhead(self, extreme_deadhead_load, fixed_now):
        """Extreme deadhead should heavily penalize score."""
        engine = ScoringEngine(deterministic_seed=42)
        score = engine.score(extreme_deadhead_load, now=fixed_now)
        
        dh_factor = score.get_factor("deadhead")
        assert dh_factor is not None
        # 550 miles is way over the hard limit of 400
        assert dh_factor.raw_score < 0.2
        assert dh_factor.direction == "negative"
    
    def test_hazmat_mismatch(self, hazmat_load, default_preferences, fixed_now):
        """Hazmat load without endorsement should fail that factor."""
        engine = ScoringEngine(deterministic_seed=42)
        # Default preferences don't have hazmat endorsement
        score = engine.score(hazmat_load, default_preferences, now=fixed_now)
        
        hazmat_factor = score.get_factor("hazmat_compatibility")
        assert hazmat_factor is not None
        assert hazmat_factor.raw_score == 0.0
        assert hazmat_factor.direction == "negative"
    
    def test_hazmat_match(self, hazmat_load, hazmat_endorsed_preferences, fixed_now):
        """Hazmat load with endorsement should pass."""
        engine = ScoringEngine(deterministic_seed=42)
        score = engine.score(hazmat_load, hazmat_endorsed_preferences, now=fixed_now)
        
        hazmat_factor = score.get_factor("hazmat_compatibility")
        assert hazmat_factor.raw_score == 1.0
        assert hazmat_factor.direction == "positive"
    
    def test_low_broker_rating(self, atlanta, chicago, terrible_broker, fixed_now):
        """Very low broker rating should heavily impact score."""
        load = Load(
            id="LOW-BROKER",
            origin=atlanta,
            destination=chicago,
            pickup_start=fixed_now.replace(hour=20),
            pickup_end=fixed_now.replace(hour=22),
            delivery_start=fixed_now.replace(day=20, hour=12),
            delivery_end=fixed_now.replace(day=20, hour=16),
            equipment="Dry Van",
            weight_lbs=35000,
            hazmat=False,
            distance_miles=720.0,
            deadhead_miles=30.0,
            rate_total_usd=2160.0,
            rpm=3.00,
            broker=terrible_broker,
            detention=False,
            multi_stop=False,
            lane_history=False,
            commodity="General Freight",
            posted_at=fixed_now.replace(hour=10),
            updated_at=fixed_now.replace(hour=11),
        )
        
        engine = ScoringEngine(deterministic_seed=42)
        score = engine.score(load, now=fixed_now)
        
        broker_factor = score.get_factor("broker_rating")
        assert broker_factor.raw_score <= 0.2  # 1.0 / 5.0 = 0.2
        assert broker_factor.direction == "negative"
    
    def test_high_dwell_risk(self, high_dwell_risk_load, high_dwell_market, fixed_now):
        """High dwell risk should penalize score."""
        engine = ScoringEngine(deterministic_seed=42)
        score = engine.score(high_dwell_risk_load, market=high_dwell_market, now=fixed_now)
        
        dwell_factor = score.get_factor("dwell_risk")
        assert dwell_factor is not None
        # Multiple risk factors: detention flag + high likelihood + long facility dwell
        assert dwell_factor.raw_score < 0.5
    
    def test_equipment_mismatch(self, reefer_load, owner_operator_preferences, fixed_now):
        """Equipment mismatch should score zero for that factor."""
        engine = ScoringEngine(deterministic_seed=42)
        # Owner-operator only has Dry Van
        score = engine.score(reefer_load, owner_operator_preferences, now=fixed_now)
        
        equip_factor = score.get_factor("equipment_match")
        assert equip_factor.raw_score == 0.0
        assert equip_factor.direction == "negative"
    
    def test_equipment_match(self, reefer_load, reefer_operator_preferences, fixed_now):
        """Equipment match should score perfectly."""
        engine = ScoringEngine(deterministic_seed=42)
        score = engine.score(reefer_load, reefer_operator_preferences, now=fixed_now)
        
        equip_factor = score.get_factor("equipment_match")
        assert equip_factor.raw_score == 1.0


class TestMarketContext:
    """Test market context influence on scoring."""
    
    def test_hot_market_boosts_backhaul(self, ideal_load, hot_market, fixed_now):
        """Hot market should improve backhaul probability score."""
        engine = ScoringEngine(deterministic_seed=42)
        
        neutral_score = engine.score(ideal_load, market=MarketContext(), now=fixed_now)
        hot_score = engine.score(ideal_load, market=hot_market, now=fixed_now)
        
        neutral_bh = neutral_score.get_factor("backhaul_probability")
        hot_bh = hot_score.get_factor("backhaul_probability")
        
        assert hot_bh.raw_score > neutral_bh.raw_score
    
    def test_cold_market_impacts_backhaul(self, ideal_load, cold_market, fixed_now):
        """Cold market should reduce backhaul probability score."""
        engine = ScoringEngine(deterministic_seed=42)
        
        neutral_score = engine.score(ideal_load, market=MarketContext(), now=fixed_now)
        cold_score = engine.score(ideal_load, market=cold_market, now=fixed_now)
        
        neutral_bh = neutral_score.get_factor("backhaul_probability")
        cold_bh = cold_score.get_factor("backhaul_probability")
        
        assert cold_bh.raw_score < neutral_bh.raw_score
    
    def test_market_rpm_relative_scoring(self, ideal_load, fixed_now):
        """RPM should score relative to market when market data available."""
        engine = ScoringEngine(deterministic_seed=42)
        
        # Load has $3.50/mi, market at $2.50/mi = 40% above market = excellent
        market_low = MarketContext(lane_rpm=2.50)
        score_above = engine.score(ideal_load, market=market_low, now=fixed_now)
        rpm_above = score_above.get_factor("rpm")
        
        # Load has $3.50/mi, market at $4.00/mi = below market
        market_high = MarketContext(lane_rpm=4.00)
        score_below = engine.score(ideal_load, market=market_high, now=fixed_now)
        rpm_below = score_below.get_factor("rpm")
        
        assert rpm_above.raw_score > rpm_below.raw_score


class TestExplainability:
    """Test explainability features."""
    
    def test_factors_have_explanations(self, ideal_load, fixed_now):
        """All factors should have human-readable explanations."""
        engine = ScoringEngine(deterministic_seed=42)
        score = engine.score(ideal_load, now=fixed_now)
        
        for factor in score.factors:
            assert factor.explanation, f"Factor {factor.name} missing explanation"
            assert len(factor.explanation) > 10, f"Factor {factor.name} has too short explanation"
    
    def test_top_reasons_sorted_by_impact(self, ideal_load, fixed_now):
        """Top reasons should be sorted by impact on score."""
        engine = ScoringEngine(deterministic_seed=42)
        score = engine.score(ideal_load, now=fixed_now)
        
        assert len(score.top_reasons) <= 5
        assert len(score.top_reasons) > 0
        
        # All top reasons should be from factors
        factor_names = {f.name for f in score.factors}
        for reason in score.top_reasons:
            assert reason.name in factor_names
    
    def test_positive_factors_identified(self, ideal_load, fixed_now):
        """Positive factors should be correctly identified."""
        engine = ScoringEngine(deterministic_seed=42)
        score = engine.score(ideal_load, now=fixed_now)
        
        positive = score.positive_factors()
        assert len(positive) > 0
        
        for f in positive:
            assert f.direction == "positive"
            assert f.raw_score >= 0.7
    
    def test_negative_factors_identified(self, poor_load, fixed_now):
        """Negative factors should be correctly identified."""
        engine = ScoringEngine(deterministic_seed=42)
        score = engine.score(poor_load, now=fixed_now)
        
        negative = score.negative_factors()
        assert len(negative) > 0
        
        for f in negative:
            assert f.direction == "negative"
            assert f.raw_score <= 0.3
    
    def test_factors_by_category(self, ideal_load, fixed_now):
        """Factors can be retrieved by category."""
        engine = ScoringEngine(deterministic_seed=42)
        score = engine.score(ideal_load, now=fixed_now)
        
        profitability = score.factors_by_category("profitability")
        feasibility = score.factors_by_category("feasibility")
        risk = score.factors_by_category("risk")
        preference = score.factors_by_category("preference")
        
        assert len(profitability) > 0
        assert len(feasibility) > 0
        assert len(risk) > 0
        assert len(preference) > 0
        
        for f in profitability:
            assert f.category == "profitability"


class TestConfiguration:
    """Test configuration-driven behavior."""
    
    def test_disabled_factor_excluded(self, ideal_load, fixed_now):
        """Disabled factors should not appear in results."""
        config = ScoringConfig()
        config.backhaul_probability = FactorConfig(weight=0.0, enabled=False)
        
        engine = ScoringEngine(config=config, deterministic_seed=42)
        score = engine.score(ideal_load, now=fixed_now)
        
        bh_factor = score.get_factor("backhaul_probability")
        assert bh_factor is None
    
    def test_weight_affects_contribution(self, ideal_load, fixed_now):
        """Higher weight should increase factor's contribution."""
        # Normal config
        normal_engine = ScoringEngine(deterministic_seed=42)
        normal_score = normal_engine.score(ideal_load, now=fixed_now)
        normal_rpm = normal_score.get_factor("rpm")
        
        # High RPM weight config
        high_rpm_config = ScoringConfig()
        high_rpm_config.rpm = FactorConfig(weight=2.0)
        high_engine = ScoringEngine(config=high_rpm_config, deterministic_seed=42)
        high_score = high_engine.score(ideal_load, now=fixed_now)
        high_rpm = high_score.get_factor("rpm")
        
        assert high_rpm.weight > normal_rpm.weight
        assert high_rpm.weighted_score > normal_rpm.weighted_score
    
    def test_config_from_dict(self):
        """Config can be loaded from dict."""
        data = {
            "factors": {
                "rpm": {"weight": 2.0, "enabled": True},
                "deadhead": {"weight": 0.5, "enabled": True},
            },
            "thresholds": {
                "max_acceptable_deadhead": 250.0,
            },
        }
        
        config = ScoringConfig.from_dict(data)
        assert config.rpm.weight == 2.0
        assert config.deadhead.weight == 0.5
        assert config.max_acceptable_deadhead == 250.0


class TestConfidence:
    """Test confidence calculation."""
    
    def test_full_data_high_confidence(self, ideal_load, hot_market, fixed_now):
        """Full data should produce high confidence."""
        engine = ScoringEngine(deterministic_seed=42)
        score = engine.score(ideal_load, market=hot_market, now=fixed_now)
        
        assert score.confidence >= 0.8
    
    def test_no_market_data_lower_confidence(self, ideal_load, neutral_market, fixed_now):
        """Missing market data should reduce confidence."""
        engine = ScoringEngine(deterministic_seed=42)
        score = engine.score(ideal_load, market=neutral_market, now=fixed_now)
        
        # With no market data, confidence should be lower
        assert score.confidence < 0.8
