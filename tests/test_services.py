"""Tests for the ScoringService application layer."""

from __future__ import annotations

from datetime import datetime, timezone

import pytest

from app.models import Broker, Load, Location
from app.scoring import ScoringConfig, ScoringEngine
from app.scoring.models import MarketContext, UserPreferences
from app.services import (
    InMemoryLoadRepository,
    InMemoryPreferencesRepository,
    ScoringService,
    StubMarketDataRepository,
)


@pytest.fixture
def load_repo(ideal_load, average_load, poor_load):
    """Repository pre-populated with test loads."""
    return InMemoryLoadRepository([ideal_load, average_load, poor_load])


@pytest.fixture
def prefs_repo(owner_operator_preferences):
    """Repository with test user preferences."""
    repo = InMemoryPreferencesRepository()
    repo.save("user-1", owner_operator_preferences)
    return repo


@pytest.fixture
def market_repo(hot_market):
    """Market data repository with test data."""
    repo = StubMarketDataRepository(default_context=hot_market)
    return repo


@pytest.fixture
def scoring_service(load_repo, prefs_repo, market_repo):
    """Configured scoring service."""
    return ScoringService(
        load_repo=load_repo,
        prefs_repo=prefs_repo,
        market_repo=market_repo,
        deterministic_seed=42,
    )


class TestScoringService:
    """Tests for ScoringService."""
    
    def test_score_load_by_id(self, scoring_service, fixed_now):
        """Can score a load by ID."""
        result = scoring_service.score_load("IDEAL-001", user_id="user-1", now=fixed_now)
        
        assert result is not None
        assert 0 <= result.score <= 100
    
    def test_score_load_not_found(self, scoring_service, fixed_now):
        """Returns None for non-existent load."""
        result = scoring_service.score_load("NONEXISTENT", now=fixed_now)
        
        assert result is None
    
    def test_score_load_direct(self, scoring_service, ideal_load, fixed_now):
        """Can score a load object directly."""
        result = scoring_service.score_load_direct(ideal_load, user_id="user-1", now=fixed_now)
        
        assert result is not None
        assert result.score >= 0
    
    def test_score_loads_multiple(self, scoring_service, fixed_now):
        """Can score multiple loads by ID."""
        results = scoring_service.score_loads(
            ["IDEAL-001", "AVG-001", "NONEXISTENT"],
            user_id="user-1",
            now=fixed_now,
        )
        
        assert len(results) == 3
        assert results[0][0] == "IDEAL-001"
        assert results[0][1] is not None
        assert results[1][0] == "AVG-001"
        assert results[1][1] is not None
        assert results[2][0] == "NONEXISTENT"
        assert results[2][1] is None
    
    def test_score_and_rank(self, scoring_service, ideal_load, average_load, poor_load, fixed_now):
        """Loads are ranked by score descending."""
        loads = [poor_load, ideal_load, average_load]
        ranked = scoring_service.score_and_rank(loads, user_id="user-1", now=fixed_now)
        
        assert len(ranked) == 3
        
        # Scores should be in descending order
        scores = [s.score for _, s in ranked]
        assert scores == sorted(scores, reverse=True)
        
        # Ideal should be first (highest score)
        assert ranked[0][0].id == "IDEAL-001"
    
    def test_score_and_rank_with_limit(self, scoring_service, ideal_load, average_load, poor_load, fixed_now):
        """Can limit ranked results."""
        loads = [poor_load, ideal_load, average_load]
        ranked = scoring_service.score_and_rank(loads, user_id="user-1", now=fixed_now, limit=2)
        
        assert len(ranked) == 2
    
    def test_explain_score(self, scoring_service, fixed_now):
        """Can generate human-readable explanation."""
        explanation = scoring_service.explain_score("IDEAL-001", user_id="user-1")
        
        assert explanation is not None
        assert "GreenLight Score" in explanation
        assert "Confidence" in explanation
        assert "Top Factors" in explanation
    
    def test_explain_score_not_found(self, scoring_service):
        """Returns None for non-existent load."""
        explanation = scoring_service.explain_score("NONEXISTENT")
        
        assert explanation is None
    
    def test_uses_default_preferences_when_no_user(self, scoring_service, fixed_now):
        """Falls back to default preferences when no user specified."""
        result = scoring_service.score_load("IDEAL-001", user_id=None, now=fixed_now)
        
        assert result is not None
    
    def test_engine_accessible(self, scoring_service):
        """Scoring engine is accessible for advanced use."""
        assert isinstance(scoring_service.engine, ScoringEngine)


class TestRepositories:
    """Tests for repository implementations."""
    
    def test_in_memory_load_repo_operations(self, ideal_load, average_load):
        """InMemoryLoadRepository CRUD operations work."""
        repo = InMemoryLoadRepository()
        
        # Save
        repo.save(ideal_load)
        assert repo.count() == 1
        
        # Get by ID
        found = repo.get_by_id("IDEAL-001")
        assert found is not None
        assert found.id == "IDEAL-001"
        
        # Get all
        repo.save(average_load)
        all_loads = repo.get_all()
        assert len(all_loads) == 2
        
        # Find with criteria
        found_ga = repo.find(origin_state="GA")
        assert len(found_ga) == 1
        assert found_ga[0].origin.state == "GA"
        
        # Delete
        deleted = repo.delete("IDEAL-001")
        assert deleted is True
        assert repo.count() == 1
        
        # Delete non-existent
        deleted = repo.delete("NONEXISTENT")
        assert deleted is False
    
    def test_in_memory_prefs_repo_operations(self, owner_operator_preferences):
        """InMemoryPreferencesRepository operations work."""
        repo = InMemoryPreferencesRepository()
        
        # Get default
        default = repo.get_default()
        assert default is not None
        
        # Get non-existent user
        prefs = repo.get("user-1")
        assert prefs is None
        
        # Save
        repo.save("user-1", owner_operator_preferences)
        prefs = repo.get("user-1")
        assert prefs is not None
        assert prefs.cost_per_mile == 1.65
        
        # Delete
        deleted = repo.delete("user-1")
        assert deleted is True
        assert repo.get("user-1") is None
    
    def test_stub_market_repo(self, hot_market):
        """StubMarketDataRepository returns injected data."""
        repo = StubMarketDataRepository(default_context=hot_market)
        
        # Get default context for any lane
        ctx = repo.get_lane_context("Atlanta", "GA", "Chicago", "IL")
        assert ctx is not None
        assert ctx.lane_rpm == 2.80
        
        # Inject specific lane data
        custom = MarketContext(lane_rpm=3.50)
        repo.set_lane_data("Dallas", "TX", "Miami", "FL", custom)
        
        ctx = repo.get_lane_context("Dallas", "TX", "Miami", "FL")
        assert ctx.lane_rpm == 3.50
