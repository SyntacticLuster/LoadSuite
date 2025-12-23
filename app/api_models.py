"""API Request/Response models for LoadSuite endpoints.

Provides Pydantic models for the extended API:
- PreferencesModel: User-configurable scoring preferences
- ScoredLoadModel: Load with composite score and reasons
- WatchlistItemModel: Watchlist item for tracking loads/lanes
- AlertRuleModel: User-defined alert rules
"""

from __future__ import annotations

from datetime import datetime
from typing import Any, List, Literal, Optional

from pydantic import BaseModel, Field

from .models import Load


# =============================================================================
# Factor/Score Response Models
# =============================================================================

# =============================================================================
# RouteCast Models
# =============================================================================


class CoordinateModel(BaseModel):
    lat: float
    lon: float


class RouteCastScoreRequest(BaseModel):
    origin: CoordinateModel
    destination: CoordinateModel
    via: List[CoordinateModel] = Field(default_factory=list)
    equipment_type: Optional[str] = None
    weight_lbs: Optional[float] = Field(default=None, ge=0)
    departure_time: Optional[datetime] = None


class RouteCastScoreResponse(BaseModel):
    overlays: List[Any] = Field(default_factory=list)
    risk_score: Optional[float] = None
    summary: str
    reasons: List[str] = Field(default_factory=list)
    provider: str
    confidence: str


# =============================================================================
# Factor/Score Response Models
# =============================================================================


class FactorResultModel(BaseModel):
    """API representation of a scoring factor result."""
    name: str
    display_name: str
    category: Literal["profitability", "feasibility", "risk", "preference"]
    raw_score: float = Field(ge=0.0, le=1.0)
    weight: float
    weighted_score: float
    contribution_pct: float
    direction: Literal["positive", "negative", "neutral"]
    explanation: str


class ScoredLoadModel(BaseModel):
    """Load with composite score and factor breakdown."""
    load: Load
    score: float = Field(ge=0.0, le=100.0, description="Composite GreenLight score (0-100)")
    top_reasons: List[FactorResultModel] = Field(
        default_factory=list,
        description="Top contributing factors (positive or negative)"
    )
    factors: List[FactorResultModel] = Field(
        default_factory=list,
        description="Full factor breakdown"
    )
    confidence: float = Field(
        ge=0.0, le=1.0,
        description="Data completeness indicator"
    )
    greenlight: bool = Field(
        default=False,
        description="Whether load meets user's GreenLight threshold"
    )
    routecast: Optional[RouteCastScoreResponse] = Field(
        default=None,
        description="RouteCast route risk data when requested",
    )


class ScoredLoadsResponse(BaseModel):
    """Response for bulk scored loads endpoint."""
    total: int
    loads: List[ScoredLoadModel]


# =============================================================================
# Preferences Models
# =============================================================================

class PreferencesModel(BaseModel):
    """User preferences for scoring and filtering.
    
    All fields are optional - unset fields use system defaults.
    """
    equipment_types: Optional[List[str]] = Field(
        default=None,
        description="Preferred equipment types (e.g., ['Dry Van', 'Reefer'])"
    )
    max_deadhead_miles: Optional[float] = Field(
        default=None, ge=0,
        description="Maximum acceptable empty miles to pickup"
    )
    max_weight_lbs: Optional[int] = Field(
        default=None, ge=0,
        description="Maximum weight capacity"
    )
    min_weight_lbs: Optional[int] = Field(
        default=None, ge=0,
        description="Minimum acceptable weight"
    )
    cost_per_mile: Optional[float] = Field(
        default=None, ge=0,
        description="Operating cost per mile for profit calculations"
    )
    preferred_lanes: Optional[List[str]] = Field(
        default=None,
        description="Preferred lanes as 'origin:destination' strings"
    )
    home_base: Optional[str] = Field(
        default=None,
        description="Home location (city, state) for backhaul scoring"
    )
    hazmat_endorsed: Optional[bool] = Field(
        default=None,
        description="Whether user has hazmat endorsement"
    )
    min_broker_rating: Optional[float] = Field(
        default=None, ge=0, le=5,
        description="Minimum acceptable broker rating"
    )
    min_rpm: Optional[float] = Field(
        default=None, ge=0,
        description="Minimum rate per mile"
    )
    greenlight_threshold: Optional[float] = Field(
        default=None, ge=0, le=100,
        description="Minimum score to qualify as GreenLight"
    )


class PreferencesResponse(BaseModel):
    """Response for preferences get/set endpoints."""
    user_id: str
    preferences: PreferencesModel
    updated_at: Optional[datetime] = None


# =============================================================================
# Watchlist Models
# =============================================================================

class WatchlistItemModel(BaseModel):
    """A watchlist item for tracking loads or lanes."""
    id: str = Field(description="Unique watchlist item ID")
    user_id: str = Field(description="Owner user ID")
    item_type: Literal["load", "lane"] = Field(
        description="Type of watched item"
    )
    load_id: Optional[str] = Field(
        default=None,
        description="Load ID if watching a specific load"
    )
    lane: Optional[str] = Field(
        default=None,
        description="Lane as 'origin:destination' if watching a lane"
    )
    notes: Optional[str] = Field(
        default=None,
        description="User notes for this watchlist item"
    )
    created_at: datetime = Field(description="When item was added")


class WatchlistItemCreateRequest(BaseModel):
    """Request to create a watchlist item."""
    item_type: Literal["load", "lane"]
    load_id: Optional[str] = None
    lane: Optional[str] = None
    notes: Optional[str] = None


class WatchlistResponse(BaseModel):
    """Response for watchlist listing."""
    user_id: str
    items: List[WatchlistItemModel]
    total: int


# =============================================================================
# Alert Models
# =============================================================================

class AlertCondition(BaseModel):
    """A single condition for an alert rule."""
    field: str = Field(description="Field to evaluate (e.g., 'rpm', 'score', 'lane')")
    operator: Literal["gt", "gte", "lt", "lte", "eq", "contains"] = Field(
        description="Comparison operator"
    )
    value: str | float | int | bool = Field(description="Value to compare against")


class AlertRuleModel(BaseModel):
    """User-defined alert rule."""
    id: str = Field(description="Unique rule ID")
    user_id: str = Field(description="Owner user ID")
    name: str = Field(description="Human-readable rule name")
    description: Optional[str] = Field(default=None, description="Rule description")
    conditions: List[AlertCondition] = Field(
        default_factory=list,
        description="Conditions that must all be met to trigger alert"
    )
    enabled: bool = Field(default=True, description="Whether rule is active")
    created_at: datetime = Field(description="When rule was created")
    last_triggered: Optional[datetime] = Field(
        default=None,
        description="When rule last triggered"
    )


class AlertRuleCreateRequest(BaseModel):
    """Request to create an alert rule."""
    name: str
    description: Optional[str] = None
    conditions: List[AlertCondition] = Field(default_factory=list)
    enabled: bool = True


class AlertRulesResponse(BaseModel):
    """Response for alert rules listing."""
    user_id: str
    rules: List[AlertRuleModel]
    total: int


# =============================================================================
# Filter Preset Models (for "Save filter preset" workflow)
# =============================================================================

class FilterPresetModel(BaseModel):
    """A saved filter preset."""
    id: str = Field(description="Unique preset ID")
    user_id: str = Field(description="Owner user ID")
    name: str = Field(description="Preset name")
    filters: dict = Field(description="Saved filter parameters")
    created_at: datetime


class FilterPresetCreateRequest(BaseModel):
    """Request to create a filter preset."""
    name: str
    filters: dict


class FilterPresetsResponse(BaseModel):
    """Response for filter presets listing."""
    user_id: str
    presets: List[FilterPresetModel]
    total: int
