from __future__ import annotations

import logging
from contextlib import asynccontextmanager
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, List, Optional

from fastapi import FastAPI, HTTPException, Query, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, JSONResponse
from fastapi.staticfiles import StaticFiles

from .config import settings
from .data import Dataset, detect_and_parse_import, generate_synthetic_loads, write_sample_files
from .filters import apply_filters, apply_sort
from .models import Load, LoadsQuery, RefreshRequest
from .news import get_news_items
from .api_models import (
    AlertRuleCreateRequest,
    AlertRuleModel,
    AlertRulesResponse,
    FactorResultModel,
    FilterPresetCreateRequest,
    FilterPresetModel,
    FilterPresetsResponse,
    PreferencesModel,
    PreferencesResponse,
    ScoredLoadModel,
    ScoredLoadsResponse,
    WatchlistItemCreateRequest,
    WatchlistItemModel,
    WatchlistResponse,
)
from .stores import (
    alert_rules_store,
    filter_presets_store,
    preferences_store,
    watchlist_store,
)
from .scoring import ScoringEngine
from .scoring.models import UserPreferences
from .weather import (
    alerts_for_zip,
    forecast_for_zip,
    geocode_city_state,
    merge_alerts_for_points,
    nws_current_by_point,
)

logger = logging.getLogger(__name__)

BASE_DIR = Path(__file__).resolve().parent.parent
STATIC_DIR = BASE_DIR / "static"


# =============================================================================
# Application Lifespan (startup/shutdown)
# =============================================================================

@asynccontextmanager
async def lifespan(app: FastAPI):
    """Application lifespan handler for startup/shutdown events."""
    # Startup
    logger.info("Starting LoadSuite (environment=%s, use_database=%s)", 
                settings.environment, settings.use_database)
    
    write_sample_files(BASE_DIR)
    
    if settings.use_database:
        from .database import init_db_pool, check_database_health
        await init_db_pool()
        health = await check_database_health()
        logger.info("Database health: %s", health["status"])
    
    yield
    
    # Shutdown
    if settings.use_database:
        from .database import close_db_pool
        await close_db_pool()
    
    logger.info("LoadSuite shutdown complete")


app = FastAPI(
    title="LoadSuite - Freight Load Scoring",
    version="0.3.0",
    lifespan=lifespan,
)

# CORS middleware for orbitsuite.cloud
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins_list,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

_dataset: Dataset = generate_synthetic_loads(settings.synthetic_load_count)
_scoring_engine: ScoringEngine = ScoringEngine()

# Default user ID for anonymous/demo usage
DEFAULT_USER_ID = "default"


@app.get("/api/health")
async def health_check() -> dict[str, Any]:
    """Health check endpoint for monitoring."""
    result = {
        "status": "healthy",
        "environment": settings.environment,
        "use_database": settings.use_database,
        "server_time": datetime.now(timezone.utc).isoformat(),
    }
    
    if settings.use_database:
        from .database import check_database_health
        db_health = await check_database_health()
        result["database"] = db_health
        if db_health["status"] != "healthy":
            result["status"] = "degraded"
    
    return result


@app.get("/api/meta")
def meta() -> dict[str, Any]:
    return {
        "source": _dataset.source,
        "count": len(_dataset.loads),
        "server_time": datetime.now(timezone.utc).isoformat(),
        "environment": settings.environment,
        "use_database": settings.use_database,
    }


# =============================================================================
# Weather Widgets (Forecast + Alerts)
# =============================================================================


@app.get("/api/weather/forecast")
def weather_forecast(zip: str = Query(..., description="5-digit US ZIP code")) -> dict[str, Any]:
    try:
        return forecast_for_zip(zip)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e)) from e
    except LookupError as e:
        raise HTTPException(status_code=404, detail=str(e)) from e
    except Exception as e:
        logger.exception("weather forecast fetch failed")
        raise HTTPException(status_code=502, detail="weather provider unavailable") from e


@app.get("/api/weather/alerts")
def weather_alerts(zip: str = Query(..., description="5-digit US ZIP code")) -> dict[str, Any]:
    try:
        return alerts_for_zip(zip)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e)) from e
    except LookupError as e:
        raise HTTPException(status_code=404, detail=str(e)) from e
    except Exception as e:
        logger.warning("weather alerts fetch failed: %s", e)
        # For transient provider issues (timeouts, upstream slowness), return a stable
        # payload so the UI can render an 'unavailable' state without retry-storming.
        return {
            "zip": (zip or "")[:5],
            "location": None,
            "lat": None,
            "lon": None,
            "alerts": {"count": 0, "alerts": [], "updated": None, "unavailable": True},
        }


@app.get("/api/loads")
def list_loads(
    q: Optional[str] = None,
    equipment: Optional[str] = None,
    weight_min: Optional[int] = None,
    weight_max: Optional[int] = None,
    hazmat: Optional[bool] = None,
    pickup_start: Optional[datetime] = None,
    pickup_end: Optional[datetime] = None,
    delivery_start: Optional[datetime] = None,
    delivery_end: Optional[datetime] = None,
    deadhead_max: Optional[float] = None,
    rpm_min: Optional[float] = None,
    broker_rating_min: Optional[float] = None,
    detention: Optional[bool] = None,
    multi_stop: Optional[bool] = None,
    lane_history: Optional[bool] = None,
    sort: str = "composite",
) -> dict[str, Any]:
    query = LoadsQuery(
        q=q,
        equipment=equipment,
        weight_min=weight_min,
        weight_max=weight_max,
        hazmat=hazmat,
        pickup_start=pickup_start,
        pickup_end=pickup_end,
        delivery_start=delivery_start,
        delivery_end=delivery_end,
        deadhead_max=deadhead_max,
        rpm_min=rpm_min,
        broker_rating_min=broker_rating_min,
        detention=detention,
        multi_stop=multi_stop,
        lane_history=lane_history,
        sort=sort,  # validated by pydantic literal
    )
    now = datetime.now(timezone.utc)
    filtered = apply_filters(_dataset.loads, query)
    ranked = apply_sort(filtered, query, now)
    return {
        "total": len(ranked),
        "loads": [l.model_dump(mode="json") for l in ranked],
    }


@app.get("/api/news")
async def news(limit: int = 20) -> dict[str, Any]:
    """Return cached headlines for the ticker."""
    items = await get_news_items(limit=limit)
    return {"items": [item.to_dict() for item in items]}


# =============================================================================
# Scored Loads Endpoints (must be before /api/loads/{load_id})
# =============================================================================

def _convert_prefs_to_user_prefs(prefs: PreferencesModel) -> UserPreferences:
    """Convert API PreferencesModel to scoring UserPreferences."""
    return UserPreferences(
        equipment_types=tuple(prefs.equipment_types) if prefs.equipment_types else ("Dry Van",),
        max_deadhead_miles=prefs.max_deadhead_miles or 200.0,
        max_weight_lbs=prefs.max_weight_lbs or 45000,
        cost_per_mile=prefs.cost_per_mile or 1.50,
        preferred_lanes=tuple(prefs.preferred_lanes) if prefs.preferred_lanes else (),
        home_base=prefs.home_base,
        hazmat_endorsed=prefs.hazmat_endorsed or False,
        min_broker_rating=prefs.min_broker_rating or 0.0,
    )


def _factor_to_model(factor) -> FactorResultModel:
    """Convert scoring FactorResult to API model."""
    return FactorResultModel(
        name=factor.name,
        display_name=factor.display_name,
        category=factor.category,
        raw_score=factor.raw_score,
        weight=factor.weight,
        weighted_score=factor.weighted_score,
        contribution_pct=factor.contribution_pct,
        direction=factor.direction,
        explanation=factor.explanation,
    )


@app.get("/api/loads/scored", response_model=ScoredLoadsResponse)
def list_scored_loads(
    user_id: str = Query(default=DEFAULT_USER_ID, description="User ID for preferences"),
    q: Optional[str] = None,
    equipment: Optional[str] = None,
    weight_min: Optional[int] = None,
    weight_max: Optional[int] = None,
    hazmat: Optional[bool] = None,
    pickup_start: Optional[datetime] = None,
    pickup_end: Optional[datetime] = None,
    delivery_start: Optional[datetime] = None,
    delivery_end: Optional[datetime] = None,
    deadhead_max: Optional[float] = None,
    rpm_min: Optional[float] = None,
    broker_rating_min: Optional[float] = None,
    detention: Optional[bool] = None,
    multi_stop: Optional[bool] = None,
    lane_history: Optional[bool] = None,
    sort: str = "composite",
    limit: int = Query(default=50, ge=1, le=200),
) -> ScoredLoadsResponse:
    """Get loads with composite scores and factor breakdowns."""
    query = LoadsQuery(
        q=q,
        equipment=equipment,
        weight_min=weight_min,
        weight_max=weight_max,
        hazmat=hazmat,
        pickup_start=pickup_start,
        pickup_end=pickup_end,
        delivery_start=delivery_start,
        delivery_end=delivery_end,
        deadhead_max=deadhead_max,
        rpm_min=rpm_min,
        broker_rating_min=broker_rating_min,
        detention=detention,
        multi_stop=multi_stop,
        lane_history=lane_history,
        sort=sort,
    )
    now = datetime.now(timezone.utc)
    filtered = apply_filters(_dataset.loads, query)
    ranked = apply_sort(filtered, query, now)[:limit]
    
    # Get user preferences for scoring
    prefs_model, _ = preferences_store.get(user_id)
    user_prefs = _convert_prefs_to_user_prefs(prefs_model)
    greenlight_threshold = prefs_model.greenlight_threshold or 70.0
    
    scored_loads: List[ScoredLoadModel] = []
    for load in ranked:
        composite = _scoring_engine.score(load, preferences=user_prefs, now=now)
        scored_loads.append(ScoredLoadModel(
            load=load,
            score=composite.score,
            top_reasons=[_factor_to_model(f) for f in composite.top_reasons[:3]],
            factors=[_factor_to_model(f) for f in composite.factors],
            confidence=composite.confidence,
            greenlight=composite.score >= greenlight_threshold,
        ))
    
    return ScoredLoadsResponse(total=len(scored_loads), loads=scored_loads)


@app.get("/api/loads/{load_id}/score")
def get_load_score(
    load_id: str,
    user_id: str = Query(default=DEFAULT_USER_ID),
) -> ScoredLoadModel:
    """Get score details for a specific load."""
    load = None
    for l in _dataset.loads:
        if l.id == load_id:
            load = l
            break
    if load is None:
        raise HTTPException(status_code=404, detail="Load not found")
    
    prefs_model, _ = preferences_store.get(user_id)
    user_prefs = _convert_prefs_to_user_prefs(prefs_model)
    greenlight_threshold = prefs_model.greenlight_threshold or 70.0
    
    now = datetime.now(timezone.utc)
    composite = _scoring_engine.score(load, preferences=user_prefs, now=now)
    
    return ScoredLoadModel(
        load=load,
        score=composite.score,
        top_reasons=[_factor_to_model(f) for f in composite.top_reasons[:3]],
        factors=[_factor_to_model(f) for f in composite.factors],
        confidence=composite.confidence,
        greenlight=composite.score >= greenlight_threshold,
    )


@app.get("/api/loads/{load_id}")
def get_load(load_id: str) -> dict[str, Any]:
    for load in _dataset.loads:
        if load.id == load_id:
            return load.model_dump(mode="json")
    raise HTTPException(status_code=404, detail="Load not found")


@app.get("/api/loads/{load_id}/routecast")
def get_routecast(load_id: str) -> dict[str, Any]:
    load: Load | None = None
    for l in _dataset.loads:
        if l.id == load_id:
            load = l
            break
    if load is None:
        raise HTTPException(status_code=404, detail="Load not found")

    try:
        o = geocode_city_state(load.origin.city, load.origin.state)
        d = geocode_city_state(load.destination.city, load.destination.state)
    except (ValueError, LookupError) as e:
        raise HTTPException(status_code=400, detail=str(e)) from e

    try:
        origin_current = nws_current_by_point(o["lat"], o["lon"])
    except Exception:
        logger.exception("routecast origin current failed")
        origin_current = None

    try:
        destination_current = nws_current_by_point(d["lat"], d["lon"])
    except Exception:
        logger.exception("routecast destination current failed")
        destination_current = None

    # Sample a handful of points along the straight-line route.
    samples: list[tuple[float, float]] = []
    steps = 5
    for i in range(steps):
        t = i / max(steps - 1, 1)
        lat = o["lat"] + (d["lat"] - o["lat"]) * t
        lon = o["lon"] + (d["lon"] - o["lon"]) * t
        samples.append((float(lat), float(lon)))

    try:
        route_alerts = merge_alerts_for_points(samples)
    except Exception:
        logger.exception("routecast alerts failed")
        route_alerts = {"count": 0, "alerts": []}

    return {
        "load_id": load.id,
        "origin": {
            "city": load.origin.city,
            "state": load.origin.state,
            "lat": o["lat"],
            "lon": o["lon"],
            "current": origin_current,
        },
        "destination": {
            "city": load.destination.city,
            "state": load.destination.state,
            "lat": d["lat"],
            "lon": d["lon"],
            "current": destination_current,
        },
        "route_alerts": route_alerts,
    }


@app.post("/api/refresh")
def refresh(req: RefreshRequest = RefreshRequest()) -> dict[str, Any]:
    global _dataset
    _dataset = generate_synthetic_loads(req.count)
    return {"ok": True, "source": _dataset.source, "count": len(_dataset.loads)}


@app.post("/api/import")
async def import_data(request: Request, filename: str) -> dict[str, Any]:
    global _dataset
    if not filename:
        raise HTTPException(status_code=400, detail="Missing filename")
    content = await request.body()
    try:
        loads, kind = detect_and_parse_import(filename, content)
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"Import failed: {e}")
    _dataset = Dataset(loads=loads, source=f"import:{kind}")
    return {"ok": True, "source": _dataset.source, "count": len(_dataset.loads)}


# =============================================================================
# Preferences Endpoints
# =============================================================================

@app.get("/api/preferences", response_model=PreferencesResponse)
def get_preferences(
    user_id: str = Query(default=DEFAULT_USER_ID),
) -> PreferencesResponse:
    """Get user preferences."""
    prefs, updated_at = preferences_store.get(user_id)
    return PreferencesResponse(
        user_id=user_id,
        preferences=prefs,
        updated_at=updated_at,
    )


@app.put("/api/preferences", response_model=PreferencesResponse)
def set_preferences(
    prefs: PreferencesModel,
    user_id: str = Query(default=DEFAULT_USER_ID),
) -> PreferencesResponse:
    """Set user preferences."""
    updated_at = preferences_store.set(user_id, prefs)
    return PreferencesResponse(
        user_id=user_id,
        preferences=prefs,
        updated_at=updated_at,
    )


@app.delete("/api/preferences")
def delete_preferences(
    user_id: str = Query(default=DEFAULT_USER_ID),
) -> dict[str, Any]:
    """Reset user preferences to defaults."""
    deleted = preferences_store.delete(user_id)
    return {"ok": True, "deleted": deleted}


# =============================================================================
# Watchlist Endpoints (Stub)
# =============================================================================

@app.get("/api/watchlist", response_model=WatchlistResponse)
def list_watchlist(
    user_id: str = Query(default=DEFAULT_USER_ID),
) -> WatchlistResponse:
    """List all watchlist items for a user."""
    items = watchlist_store.list(user_id)
    return WatchlistResponse(user_id=user_id, items=items, total=len(items))


@app.post("/api/watchlist", response_model=WatchlistItemModel)
def create_watchlist_item(
    req: WatchlistItemCreateRequest,
    user_id: str = Query(default=DEFAULT_USER_ID),
) -> WatchlistItemModel:
    """Add an item to the watchlist."""
    return watchlist_store.create(
        user_id=user_id,
        item_type=req.item_type,
        load_id=req.load_id,
        lane=req.lane,
        notes=req.notes,
    )


@app.delete("/api/watchlist/{item_id}")
def delete_watchlist_item(
    item_id: str,
    user_id: str = Query(default=DEFAULT_USER_ID),
) -> dict[str, Any]:
    """Remove an item from the watchlist."""
    deleted = watchlist_store.delete(user_id, item_id)
    if not deleted:
        raise HTTPException(status_code=404, detail="Watchlist item not found")
    return {"ok": True, "deleted": True}


@app.get("/api/watchlist/check/{load_id}")
def check_watchlist(
    load_id: str,
    user_id: str = Query(default=DEFAULT_USER_ID),
) -> dict[str, Any]:
    """Check if a load is in the user's watchlist."""
    return {"watched": watchlist_store.has_load(user_id, load_id)}


# =============================================================================
# Alert Rules Endpoints (Stub - Execution is TODO)
# =============================================================================

@app.get("/api/alerts", response_model=AlertRulesResponse)
def list_alert_rules(
    user_id: str = Query(default=DEFAULT_USER_ID),
) -> AlertRulesResponse:
    """List all alert rules for a user."""
    rules = alert_rules_store.list(user_id)
    return AlertRulesResponse(user_id=user_id, rules=rules, total=len(rules))


@app.post("/api/alerts", response_model=AlertRuleModel)
def create_alert_rule(
    req: AlertRuleCreateRequest,
    user_id: str = Query(default=DEFAULT_USER_ID),
) -> AlertRuleModel:
    """Create a new alert rule. Note: Execution is TODO."""
    return alert_rules_store.create(
        user_id=user_id,
        name=req.name,
        description=req.description,
        conditions=req.conditions,
        enabled=req.enabled,
    )


@app.delete("/api/alerts/{rule_id}")
def delete_alert_rule(
    rule_id: str,
    user_id: str = Query(default=DEFAULT_USER_ID),
) -> dict[str, Any]:
    """Delete an alert rule."""
    deleted = alert_rules_store.delete(user_id, rule_id)
    if not deleted:
        raise HTTPException(status_code=404, detail="Alert rule not found")
    return {"ok": True, "deleted": True}


# =============================================================================
# Filter Presets Endpoints
# =============================================================================

@app.get("/api/presets", response_model=FilterPresetsResponse)
def list_filter_presets(
    user_id: str = Query(default=DEFAULT_USER_ID),
) -> FilterPresetsResponse:
    """List all saved filter presets."""
    presets = filter_presets_store.list(user_id)
    return FilterPresetsResponse(user_id=user_id, presets=presets, total=len(presets))


@app.post("/api/presets", response_model=FilterPresetModel)
def create_filter_preset(
    req: FilterPresetCreateRequest,
    user_id: str = Query(default=DEFAULT_USER_ID),
) -> FilterPresetModel:
    """Save current filters as a preset."""
    return filter_presets_store.create(
        user_id=user_id,
        name=req.name,
        filters=req.filters,
    )


@app.delete("/api/presets/{preset_id}")
def delete_filter_preset(
    preset_id: str,
    user_id: str = Query(default=DEFAULT_USER_ID),
) -> dict[str, Any]:
    """Delete a filter preset."""
    deleted = filter_presets_store.delete(user_id, preset_id)
    if not deleted:
        raise HTTPException(status_code=404, detail="Preset not found")
    return {"ok": True, "deleted": True}


# Static UI
app.mount("/static", StaticFiles(directory=str(STATIC_DIR)), name="static")


@app.get("/")
def index() -> FileResponse:
    return FileResponse(str(STATIC_DIR / "index.html"))
