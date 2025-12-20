"""Service layer package for LoadSuite.

Provides repository abstractions and domain services for:
- Load data access (LoadRepository)
- User preferences (PreferencesRepository)
- Market data (MarketDataRepository)
- Scoring operations (ScoringService)

Includes both in-memory and PostgreSQL implementations.
"""

from .repositories import (
    LoadRepository,
    PreferencesRepository,
    MarketDataRepository,
    InMemoryLoadRepository,
    InMemoryPreferencesRepository,
    StubMarketDataRepository,
)
from .scoring_service import ScoringService

# PostgreSQL implementations (imported separately to avoid asyncpg import at module load)
# Usage: from app.services.postgres import PostgresLoadRepository, ...

__all__ = [
    # Abstract interfaces
    "LoadRepository",
    "PreferencesRepository",
    "MarketDataRepository",
    # In-memory implementations
    "InMemoryLoadRepository",
    "InMemoryPreferencesRepository",
    "StubMarketDataRepository",
    # Domain services
    "ScoringService",
]
