from __future__ import annotations

from datetime import datetime
from typing import List, Literal, Optional

from pydantic import BaseModel, Field


class Coordinate(BaseModel):
    lat: float
    lon: float


class RouteLeg(BaseModel):
    start: Coordinate
    end: Coordinate
    distance_miles: float = Field(ge=0)
    duration_minutes: float = Field(ge=0)
    polyline: List[Coordinate]


class RouteRequest(BaseModel):
    origin: Coordinate
    destination: Coordinate
    via: Optional[List[Coordinate]] = None


class RouteResponse(BaseModel):
    origin: Coordinate
    destination: Coordinate
    legs: List[RouteLeg]
    polyline: List[Coordinate]
    distance_miles: float
    duration_minutes: float
    duration_seconds: float
    provider: str


class Overlay(BaseModel):
    kind: Literal["weather", "traffic", "restriction", "event"]
    description: str
    severity: Literal["info", "minor", "moderate", "major"]
    geometry: List[Coordinate]
    source: str


class OverlayCollection(BaseModel):
    overlays: List[Overlay] = Field(default_factory=list)
    generated_at: datetime = Field(default_factory=datetime.utcnow)


class ScoreBreakdown(BaseModel):
    overall: float
    risk_score: float
    summary: str
    reasons: List[str]
    factors: List[str]
    rationale: str
    confidence: float = Field(ge=0.0, le=1.0, default=0.5)

