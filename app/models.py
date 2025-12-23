from __future__ import annotations

from datetime import datetime
from typing import Literal, Optional

from pydantic import BaseModel, Field


class Location(BaseModel):
    city: str
    state: str


class Broker(BaseModel):
    name: str
    rating: float = Field(ge=0, le=5)


class Load(BaseModel):
    id: str
    origin: Location
    destination: Location
    pickup_start: datetime
    pickup_end: datetime
    delivery_start: datetime
    delivery_end: datetime

    equipment: str
    weight_lbs: int = Field(ge=0)
    hazmat: bool

    distance_miles: float = Field(ge=0)
    deadhead_miles: float = Field(ge=0)
    rate_total_usd: float = Field(ge=0)
    rpm: float = Field(ge=0, description="Rate-per-mile, computed as rate_total_usd / distance_miles")

    broker: Broker
    detention: bool
    multi_stop: bool
    lane_history: bool

    commodity: str
    posted_at: datetime
    updated_at: datetime


SortKey = Literal["composite", "rpm_desc", "pickup_soonest", "deadhead_asc", "broker_desc", "score_desc"]


class RefreshRequest(BaseModel):
    count: int = Field(default=200, ge=1, le=5000)


class LoadsQuery(BaseModel):
    q: Optional[str] = None
    equipment: Optional[str] = None

    weight_min: Optional[int] = Field(default=None, ge=0)
    weight_max: Optional[int] = Field(default=None, ge=0)
    hazmat: Optional[bool] = None

    pickup_start: Optional[datetime] = None
    pickup_end: Optional[datetime] = None
    delivery_start: Optional[datetime] = None
    delivery_end: Optional[datetime] = None

    deadhead_max: Optional[float] = Field(default=None, ge=0)
    rpm_min: Optional[float] = Field(default=None, ge=0)
    broker_rating_min: Optional[float] = Field(default=None, ge=0, le=5)

    detention: Optional[bool] = None
    multi_stop: Optional[bool] = None
    lane_history: Optional[bool] = None

    sort: SortKey = "composite"
