"""Repository abstractions for LoadSuite.

Provides clean interfaces for data access, following repository pattern:
- LoadRepository: Load data access
- PreferencesRepository: User preferences access
- MarketDataRepository: Market data access

Includes in-memory and stub implementations for development and testing.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Iterable, List, Optional

from ..models import Load
from ..scoring.models import MarketContext, UserPreferences


# =============================================================================
# Repository Interfaces (Abstract)
# =============================================================================

class LoadRepository(ABC):
    """Abstract interface for load data access."""
    
    @abstractmethod
    def get_by_id(self, load_id: str) -> Optional[Load]:
        """Retrieve a single load by ID."""
        ...
    
    @abstractmethod
    def get_all(self) -> List[Load]:
        """Retrieve all loads."""
        ...
    
    @abstractmethod
    def find(
        self,
        origin_state: Optional[str] = None,
        destination_state: Optional[str] = None,
        equipment: Optional[str] = None,
        min_rpm: Optional[float] = None,
        max_deadhead: Optional[float] = None,
        limit: int = 100,
    ) -> List[Load]:
        """Find loads matching criteria."""
        ...
    
    @abstractmethod
    def save(self, load: Load) -> None:
        """Save or update a load."""
        ...
    
    @abstractmethod
    def save_many(self, loads: Iterable[Load]) -> int:
        """Save multiple loads. Returns count saved."""
        ...
    
    @abstractmethod
    def delete(self, load_id: str) -> bool:
        """Delete a load. Returns True if found and deleted."""
        ...
    
    @abstractmethod
    def count(self) -> int:
        """Return total number of loads."""
        ...


class PreferencesRepository(ABC):
    """Abstract interface for user preferences access."""
    
    @abstractmethod
    def get(self, user_id: str) -> Optional[UserPreferences]:
        """Get preferences for a user."""
        ...
    
    @abstractmethod
    def get_default(self) -> UserPreferences:
        """Get default preferences."""
        ...
    
    @abstractmethod
    def save(self, user_id: str, preferences: UserPreferences) -> None:
        """Save preferences for a user."""
        ...
    
    @abstractmethod
    def delete(self, user_id: str) -> bool:
        """Delete preferences for a user."""
        ...


class MarketDataRepository(ABC):
    """Abstract interface for market data access."""
    
    @abstractmethod
    def get_lane_context(
        self,
        origin_city: str,
        origin_state: str,
        dest_city: str,
        dest_state: str,
    ) -> Optional[MarketContext]:
        """Get market context for a specific lane."""
        ...
    
    @abstractmethod
    def get_region_context(
        self,
        origin_state: str,
        dest_state: str,
    ) -> Optional[MarketContext]:
        """Get market context for a regional lane."""
        ...


# =============================================================================
# In-Memory Implementations (Development/Testing)
# =============================================================================

class InMemoryLoadRepository(LoadRepository):
    """In-memory implementation of LoadRepository.
    
    Useful for development, testing, and demos.
    Data is not persisted across restarts.
    """
    
    def __init__(self, initial_loads: Optional[Iterable[Load]] = None):
        self._loads: dict[str, Load] = {}
        if initial_loads:
            for load in initial_loads:
                self._loads[load.id] = load
    
    def get_by_id(self, load_id: str) -> Optional[Load]:
        return self._loads.get(load_id)
    
    def get_all(self) -> List[Load]:
        return list(self._loads.values())
    
    def find(
        self,
        origin_state: Optional[str] = None,
        destination_state: Optional[str] = None,
        equipment: Optional[str] = None,
        min_rpm: Optional[float] = None,
        max_deadhead: Optional[float] = None,
        limit: int = 100,
    ) -> List[Load]:
        results = []
        for load in self._loads.values():
            if origin_state and load.origin.state != origin_state:
                continue
            if destination_state and load.destination.state != destination_state:
                continue
            if equipment and load.equipment != equipment:
                continue
            if min_rpm is not None and load.rpm < min_rpm:
                continue
            if max_deadhead is not None and load.deadhead_miles > max_deadhead:
                continue
            results.append(load)
            if len(results) >= limit:
                break
        return results
    
    def save(self, load: Load) -> None:
        self._loads[load.id] = load
    
    def save_many(self, loads: Iterable[Load]) -> int:
        count = 0
        for load in loads:
            self._loads[load.id] = load
            count += 1
        return count
    
    def delete(self, load_id: str) -> bool:
        if load_id in self._loads:
            del self._loads[load_id]
            return True
        return False
    
    def count(self) -> int:
        return len(self._loads)
    
    def clear(self) -> None:
        """Clear all loads (test utility)."""
        self._loads.clear()


class InMemoryPreferencesRepository(PreferencesRepository):
    """In-memory implementation of PreferencesRepository."""
    
    def __init__(self):
        self._preferences: dict[str, UserPreferences] = {}
        self._default = UserPreferences()
    
    def get(self, user_id: str) -> Optional[UserPreferences]:
        return self._preferences.get(user_id)
    
    def get_default(self) -> UserPreferences:
        return self._default
    
    def save(self, user_id: str, preferences: UserPreferences) -> None:
        self._preferences[user_id] = preferences
    
    def delete(self, user_id: str) -> bool:
        if user_id in self._preferences:
            del self._preferences[user_id]
            return True
        return False
    
    def set_default(self, preferences: UserPreferences) -> None:
        """Set the default preferences."""
        self._default = preferences


class StubMarketDataRepository(MarketDataRepository):
    """Stub implementation of MarketDataRepository.
    
    Returns neutral/default market context.
    Replace with real implementation when market data integration is ready.
    """
    
    def __init__(self, default_context: Optional[MarketContext] = None):
        self._default = default_context or MarketContext()
        self._lane_data: dict[str, MarketContext] = {}
        self._region_data: dict[str, MarketContext] = {}
    
    def get_lane_context(
        self,
        origin_city: str,
        origin_state: str,
        dest_city: str,
        dest_state: str,
    ) -> Optional[MarketContext]:
        key = f"{origin_city}_{origin_state}:{dest_city}_{dest_state}"
        return self._lane_data.get(key, self._default)
    
    def get_region_context(
        self,
        origin_state: str,
        dest_state: str,
    ) -> Optional[MarketContext]:
        key = f"{origin_state}:{dest_state}"
        return self._region_data.get(key, self._default)
    
    def set_lane_data(
        self,
        origin_city: str,
        origin_state: str,
        dest_city: str,
        dest_state: str,
        context: MarketContext,
    ) -> None:
        """Inject lane data for testing."""
        key = f"{origin_city}_{origin_state}:{dest_city}_{dest_state}"
        self._lane_data[key] = context
    
    def set_region_data(
        self,
        origin_state: str,
        dest_state: str,
        context: MarketContext,
    ) -> None:
        """Inject region data for testing."""
        key = f"{origin_state}:{dest_state}"
        self._region_data[key] = context
