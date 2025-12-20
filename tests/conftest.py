"""Test fixtures for scoring engine tests.

Provides deterministic Load, UserPreferences, and MarketContext
objects for consistent, reproducible testing.
"""

from __future__ import annotations

from datetime import datetime, timezone

import pytest

from app.models import Broker, Load, Location
from app.scoring import ScoringConfig, ScoringEngine
from app.scoring.models import MarketContext, UserPreferences


# =============================================================================
# Time Fixtures
# =============================================================================

@pytest.fixture
def fixed_now() -> datetime:
    """Fixed timestamp for deterministic testing."""
    return datetime(2024, 12, 19, 12, 0, 0, tzinfo=timezone.utc)


# =============================================================================
# Location Fixtures
# =============================================================================

@pytest.fixture
def atlanta() -> Location:
    return Location(city="Atlanta", state="GA")


@pytest.fixture
def chicago() -> Location:
    return Location(city="Chicago", state="IL")


@pytest.fixture
def dallas() -> Location:
    return Location(city="Dallas", state="TX")


@pytest.fixture
def los_angeles() -> Location:
    return Location(city="Los Angeles", state="CA")


# =============================================================================
# Broker Fixtures
# =============================================================================

@pytest.fixture
def excellent_broker() -> Broker:
    """High-rated broker."""
    return Broker(name="Premium Logistics", rating=4.8)


@pytest.fixture
def good_broker() -> Broker:
    """Above-average broker."""
    return Broker(name="Reliable Freight", rating=4.2)


@pytest.fixture
def average_broker() -> Broker:
    """Average broker."""
    return Broker(name="Standard Brokerage", rating=3.5)


@pytest.fixture
def poor_broker() -> Broker:
    """Low-rated broker."""
    return Broker(name="Discount Haulers", rating=2.0)


@pytest.fixture
def terrible_broker() -> Broker:
    """Very low-rated broker."""
    return Broker(name="Fly By Night", rating=1.0)


# =============================================================================
# Load Fixtures - Standard Cases
# =============================================================================

@pytest.fixture
def ideal_load(atlanta: Location, chicago: Location, excellent_broker: Broker, fixed_now: datetime) -> Load:
    """A near-perfect load with excellent metrics."""
    return Load(
        id="IDEAL-001",
        origin=atlanta,
        destination=chicago,
        pickup_start=fixed_now.replace(hour=20),  # 8 hours out (sweet spot)
        pickup_end=fixed_now.replace(hour=22),
        delivery_start=fixed_now.replace(day=20, hour=12),
        delivery_end=fixed_now.replace(day=20, hour=16),
        equipment="Dry Van",
        weight_lbs=38000,
        hazmat=False,
        distance_miles=720.0,
        deadhead_miles=25.0,
        rate_total_usd=2520.0,  # $3.50/mi
        rpm=3.50,
        broker=excellent_broker,
        detention=False,
        multi_stop=False,
        lane_history=True,
        commodity="General Freight",
        posted_at=fixed_now.replace(hour=10),
        updated_at=fixed_now.replace(hour=11),
    )


@pytest.fixture
def average_load(dallas: Location, chicago: Location, average_broker: Broker, fixed_now: datetime) -> Load:
    """A typical average load."""
    return Load(
        id="AVG-001",
        origin=dallas,
        destination=chicago,
        pickup_start=fixed_now.replace(day=20, hour=8),  # ~20 hours out
        pickup_end=fixed_now.replace(day=20, hour=12),
        delivery_start=fixed_now.replace(day=21, hour=8),
        delivery_end=fixed_now.replace(day=21, hour=14),
        equipment="Dry Van",
        weight_lbs=32000,
        hazmat=False,
        distance_miles=920.0,
        deadhead_miles=85.0,
        rate_total_usd=2024.0,  # $2.20/mi
        rpm=2.20,
        broker=average_broker,
        detention=False,
        multi_stop=False,
        lane_history=False,
        commodity="Paper",
        posted_at=fixed_now.replace(hour=8),
        updated_at=fixed_now.replace(hour=9),
    )


@pytest.fixture
def poor_load(atlanta: Location, los_angeles: Location, poor_broker: Broker, fixed_now: datetime) -> Load:
    """A below-average load with multiple issues."""
    return Load(
        id="POOR-001",
        origin=atlanta,
        destination=los_angeles,
        pickup_start=fixed_now.replace(day=22),  # 3 days out
        pickup_end=fixed_now.replace(day=22, hour=8),
        delivery_start=fixed_now.replace(day=24),
        delivery_end=fixed_now.replace(day=24, hour=12),
        equipment="Dry Van",
        weight_lbs=42000,
        hazmat=False,
        distance_miles=2200.0,
        deadhead_miles=180.0,
        rate_total_usd=3520.0,  # $1.60/mi
        rpm=1.60,
        broker=poor_broker,
        detention=True,
        multi_stop=True,
        lane_history=False,
        commodity="Building Materials",
        posted_at=fixed_now.replace(hour=6),
        updated_at=fixed_now.replace(hour=7),
    )


# =============================================================================
# Load Fixtures - Edge Cases
# =============================================================================

@pytest.fixture
def missing_rate_load(atlanta: Location, chicago: Location, average_broker: Broker, fixed_now: datetime) -> Load:
    """Load with zero/missing rate."""
    return Load(
        id="EDGE-NORATE",
        origin=atlanta,
        destination=chicago,
        pickup_start=fixed_now.replace(hour=20),
        pickup_end=fixed_now.replace(hour=22),
        delivery_start=fixed_now.replace(day=20, hour=12),
        delivery_end=fixed_now.replace(day=20, hour=16),
        equipment="Dry Van",
        weight_lbs=30000,
        hazmat=False,
        distance_miles=720.0,
        deadhead_miles=50.0,
        rate_total_usd=0.0,  # Missing rate
        rpm=0.0,
        broker=average_broker,
        detention=False,
        multi_stop=False,
        lane_history=False,
        commodity="General Freight",
        posted_at=fixed_now.replace(hour=10),
        updated_at=fixed_now.replace(hour=11),
    )


@pytest.fixture
def extreme_deadhead_load(atlanta: Location, los_angeles: Location, good_broker: Broker, fixed_now: datetime) -> Load:
    """Load with extreme deadhead (500+ miles)."""
    return Load(
        id="EDGE-DEADHEAD",
        origin=atlanta,
        destination=los_angeles,
        pickup_start=fixed_now.replace(hour=20),
        pickup_end=fixed_now.replace(hour=22),
        delivery_start=fixed_now.replace(day=21, hour=12),
        delivery_end=fixed_now.replace(day=21, hour=16),
        equipment="Dry Van",
        weight_lbs=35000,
        hazmat=False,
        distance_miles=2200.0,
        deadhead_miles=550.0,  # Extreme deadhead
        rate_total_usd=6600.0,  # $3.00/mi
        rpm=3.00,
        broker=good_broker,
        detention=False,
        multi_stop=False,
        lane_history=False,
        commodity="Automotive",
        posted_at=fixed_now.replace(hour=10),
        updated_at=fixed_now.replace(hour=11),
    )


@pytest.fixture
def hazmat_load(atlanta: Location, chicago: Location, excellent_broker: Broker, fixed_now: datetime) -> Load:
    """Hazmat load requiring endorsement."""
    return Load(
        id="EDGE-HAZMAT",
        origin=atlanta,
        destination=chicago,
        pickup_start=fixed_now.replace(hour=20),
        pickup_end=fixed_now.replace(hour=22),
        delivery_start=fixed_now.replace(day=20, hour=12),
        delivery_end=fixed_now.replace(day=20, hour=16),
        equipment="Dry Van",
        weight_lbs=28000,
        hazmat=True,  # Hazmat
        distance_miles=720.0,
        deadhead_miles=40.0,
        rate_total_usd=2880.0,  # $4.00/mi premium
        rpm=4.00,
        broker=excellent_broker,
        detention=False,
        multi_stop=False,
        lane_history=True,
        commodity="Chemicals",
        posted_at=fixed_now.replace(hour=10),
        updated_at=fixed_now.replace(hour=11),
    )


@pytest.fixture
def high_dwell_risk_load(atlanta: Location, chicago: Location, average_broker: Broker, fixed_now: datetime) -> Load:
    """Load with high detention risk."""
    return Load(
        id="EDGE-DWELL",
        origin=atlanta,
        destination=chicago,
        pickup_start=fixed_now.replace(hour=20),
        pickup_end=fixed_now.replace(hour=22),
        delivery_start=fixed_now.replace(day=20, hour=12),
        delivery_end=fixed_now.replace(day=20, hour=16),
        equipment="Dry Van",
        weight_lbs=40000,
        hazmat=False,
        distance_miles=720.0,
        deadhead_miles=30.0,
        rate_total_usd=2160.0,  # $3.00/mi
        rpm=3.00,
        broker=average_broker,
        detention=True,  # Detention flag set
        multi_stop=True,
        lane_history=False,
        commodity="Food",
        posted_at=fixed_now.replace(hour=10),
        updated_at=fixed_now.replace(hour=11),
    )


@pytest.fixture
def reefer_load(chicago: Location, los_angeles: Location, good_broker: Broker, fixed_now: datetime) -> Load:
    """Reefer equipment load."""
    return Load(
        id="EDGE-REEFER",
        origin=chicago,
        destination=los_angeles,
        pickup_start=fixed_now.replace(hour=18),
        pickup_end=fixed_now.replace(hour=20),
        delivery_start=fixed_now.replace(day=21, hour=8),
        delivery_end=fixed_now.replace(day=21, hour=12),
        equipment="Reefer",
        weight_lbs=36000,
        hazmat=False,
        distance_miles=2000.0,
        deadhead_miles=45.0,
        rate_total_usd=6000.0,  # $3.00/mi
        rpm=3.00,
        broker=good_broker,
        detention=False,
        multi_stop=False,
        lane_history=True,
        commodity="Food",
        posted_at=fixed_now.replace(hour=10),
        updated_at=fixed_now.replace(hour=11),
    )


# =============================================================================
# User Preferences Fixtures
# =============================================================================

@pytest.fixture
def default_preferences() -> UserPreferences:
    """Default user preferences."""
    return UserPreferences()


@pytest.fixture
def owner_operator_preferences() -> UserPreferences:
    """Typical owner-operator preferences."""
    return UserPreferences(
        equipment_types=("Dry Van",),
        max_deadhead_miles=150.0,
        max_weight_lbs=45000,
        cost_per_mile=1.65,
        preferred_lanes=("Atlanta_GA:Chicago_IL", "Dallas_TX:Atlanta_GA"),
        home_base="Atlanta_GA",
        hazmat_endorsed=False,
        min_broker_rating=3.0,
    )


@pytest.fixture
def hazmat_endorsed_preferences() -> UserPreferences:
    """Preferences for hazmat-endorsed driver."""
    return UserPreferences(
        equipment_types=("Dry Van", "Flatbed"),
        max_deadhead_miles=200.0,
        max_weight_lbs=45000,
        cost_per_mile=1.50,
        preferred_lanes=(),
        home_base=None,
        hazmat_endorsed=True,
        min_broker_rating=2.5,
    )


@pytest.fixture
def reefer_operator_preferences() -> UserPreferences:
    """Preferences for reefer operator."""
    return UserPreferences(
        equipment_types=("Reefer",),
        max_deadhead_miles=175.0,
        max_weight_lbs=44000,
        cost_per_mile=1.75,
        preferred_lanes=(),
        home_base="Chicago_IL",
        hazmat_endorsed=False,
        min_broker_rating=3.5,
    )


# =============================================================================
# Market Context Fixtures
# =============================================================================

@pytest.fixture
def neutral_market() -> MarketContext:
    """Neutral/unknown market context."""
    return MarketContext()


@pytest.fixture
def hot_market() -> MarketContext:
    """Carrier-favorable (hot) market."""
    return MarketContext(
        lane_rpm=2.80,
        lane_volume=150,
        market_pressure="carrier",
        backhaul_probability=0.75,
        origin_dwell_avg_minutes=45,
        dest_dwell_avg_minutes=60,
        detention_likelihood="low",
    )


@pytest.fixture
def cold_market() -> MarketContext:
    """Shipper-favorable (soft) market."""
    return MarketContext(
        lane_rpm=2.20,
        lane_volume=30,
        market_pressure="shipper",
        backhaul_probability=0.35,
        origin_dwell_avg_minutes=90,
        dest_dwell_avg_minutes=120,
        detention_likelihood="medium",
    )


@pytest.fixture
def high_dwell_market() -> MarketContext:
    """Market with high detention risk."""
    return MarketContext(
        lane_rpm=2.50,
        lane_volume=50,
        market_pressure="balanced",
        backhaul_probability=0.50,
        origin_dwell_avg_minutes=240,
        dest_dwell_avg_minutes=300,
        detention_likelihood="high",
    )


# =============================================================================
# Engine Fixtures
# =============================================================================

@pytest.fixture
def scoring_engine() -> ScoringEngine:
    """Default scoring engine."""
    return ScoringEngine(deterministic_seed=42)


@pytest.fixture
def custom_config() -> ScoringConfig:
    """Custom scoring configuration for testing."""
    config = ScoringConfig()
    # Increase RPM importance
    config.rpm = config.rpm.__class__(weight=2.0)
    return config
