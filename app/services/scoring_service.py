"""Scoring Service - Application layer for scoring operations.

Wraps the pure ScoringEngine with repository integrations
and provides a clean interface for application use.
"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import List, Optional

from ..models import Load
from ..scoring import CompositeScore, ScoringConfig, ScoringEngine
from ..scoring.models import MarketContext, UserPreferences
from .repositories import (
    LoadRepository,
    MarketDataRepository,
    PreferencesRepository,
)


class ScoringService:
    """Application service for scoring freight loads.
    
    Orchestrates scoring by:
    1. Retrieving user preferences from repository
    2. Fetching market context for the load's lane
    3. Invoking the pure scoring engine
    4. Returning explainable scores
    
    Example:
        >>> service = ScoringService(
        ...     load_repo=InMemoryLoadRepository(loads),
        ...     prefs_repo=InMemoryPreferencesRepository(),
        ...     market_repo=StubMarketDataRepository(),
        ... )
        >>> score = service.score_load("LOAD-123", user_id="user-1")
        >>> print(f"Score: {score.score}")
    """
    
    def __init__(
        self,
        load_repo: LoadRepository,
        prefs_repo: PreferencesRepository,
        market_repo: MarketDataRepository,
        config: ScoringConfig | None = None,
        deterministic_seed: int | None = None,
    ):
        """Initialize the scoring service.
        
        Args:
            load_repo: Repository for load data access
            prefs_repo: Repository for user preferences
            market_repo: Repository for market data
            config: Scoring configuration (uses default if None)
            deterministic_seed: If set, enables deterministic mode for testing
        """
        self._load_repo = load_repo
        self._prefs_repo = prefs_repo
        self._market_repo = market_repo
        self._engine = ScoringEngine(
            config=config,
            deterministic_seed=deterministic_seed,
        )
    
    @property
    def engine(self) -> ScoringEngine:
        """Direct access to the scoring engine (for advanced use cases)."""
        return self._engine
    
    def score_load(
        self,
        load_id: str,
        user_id: str | None = None,
        now: datetime | None = None,
    ) -> CompositeScore | None:
        """Score a single load by ID.
        
        Args:
            load_id: ID of the load to score
            user_id: User ID for preferences lookup (uses default if None)
            now: Current timestamp (uses UTC now if None)
        
        Returns:
            CompositeScore if load found, None otherwise
        """
        load = self._load_repo.get_by_id(load_id)
        if load is None:
            return None
        
        return self.score_load_direct(load, user_id, now)
    
    def score_load_direct(
        self,
        load: Load,
        user_id: str | None = None,
        now: datetime | None = None,
    ) -> CompositeScore:
        """Score a load object directly.
        
        Args:
            load: The load to score
            user_id: User ID for preferences lookup (uses default if None)
            now: Current timestamp (uses UTC now if None)
        
        Returns:
            CompositeScore with full factor breakdown
        """
        # Get user preferences
        if user_id:
            prefs = self._prefs_repo.get(user_id)
        else:
            prefs = None
        
        if prefs is None:
            prefs = self._prefs_repo.get_default()
        
        # Get market context
        market = self._market_repo.get_lane_context(
            origin_city=load.origin.city,
            origin_state=load.origin.state,
            dest_city=load.destination.city,
            dest_state=load.destination.state,
        )
        
        if market is None:
            market = self._market_repo.get_region_context(
                origin_state=load.origin.state,
                dest_state=load.destination.state,
            )
        
        # Score the load
        return self._engine.score(
            load=load,
            preferences=prefs,
            market=market,
            now=now,
        )
    
    def score_loads(
        self,
        load_ids: List[str],
        user_id: str | None = None,
        now: datetime | None = None,
    ) -> List[tuple[str, CompositeScore | None]]:
        """Score multiple loads by ID.
        
        Args:
            load_ids: List of load IDs to score
            user_id: User ID for preferences lookup
            now: Current timestamp
        
        Returns:
            List of (load_id, score) tuples. Score is None if load not found.
        """
        results = []
        current_time = now or datetime.now(timezone.utc)
        
        for load_id in load_ids:
            score = self.score_load(load_id, user_id, current_time)
            results.append((load_id, score))
        
        return results
    
    def score_and_rank(
        self,
        loads: List[Load],
        user_id: str | None = None,
        now: datetime | None = None,
        limit: int | None = None,
    ) -> List[tuple[Load, CompositeScore]]:
        """Score and rank a list of loads.
        
        Args:
            loads: List of loads to score
            user_id: User ID for preferences lookup
            now: Current timestamp
            limit: Maximum number of results to return
        
        Returns:
            List of (load, score) tuples sorted by score descending
        """
        current_time = now or datetime.now(timezone.utc)
        scored = []
        
        for load in loads:
            score = self.score_load_direct(load, user_id, current_time)
            scored.append((load, score))
        
        # Sort by score descending
        scored.sort(key=lambda x: x[1].score, reverse=True)
        
        if limit:
            scored = scored[:limit]
        
        return scored
    
    def explain_score(
        self,
        load_id: str,
        user_id: str | None = None,
    ) -> str | None:
        """Generate a human-readable score explanation.
        
        Args:
            load_id: ID of the load to explain
            user_id: User ID for preferences lookup
        
        Returns:
            Formatted explanation string, or None if load not found
        """
        score = self.score_load(load_id, user_id)
        if score is None:
            return None
        
        lines = [
            f"GreenLight Score: {score.score:.1f}/100",
            f"Confidence: {score.confidence * 100:.0f}%",
            "",
            "Top Factors:",
        ]
        
        for i, reason in enumerate(score.top_reasons, 1):
            icon = "✓" if reason.direction == "positive" else ("✗" if reason.direction == "negative" else "○")
            lines.append(f"  {i}. {icon} {reason.explanation}")
        
        return "\n".join(lines)
