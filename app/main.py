from __future__ import annotations

import asyncio
import json
import logging
import os
from contextlib import asynccontextmanager
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, List, Optional

from fastapi import Depends, FastAPI, HTTPException, Query, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, JSONResponse
from fastapi.staticfiles import StaticFiles

from .app_context import AppContext
from .auth import require_admin_api_key
from .config import settings
from .data import Dataset, generate_synthetic_loads, loads_from_csv_bytes, write_sample_files
from .deps import get_ctx, get_ingestion, get_routecast_client, get_scoring
from .filters import apply_filters, apply_sort
from .ingestion.manager import IngestionManager
from .models import Load, LoadsQuery, RefreshRequest
from .news import get_news_items
from .services.routecast_client import RouteCastClient
from .api_models import (
    AlertRuleCreateRequest,
    AlertRuleModel,
    AlertRulesResponse,
    CoordinateModel,
    FactorResultModel,
    FilterPresetCreateRequest,
    FilterPresetModel,
    FilterPresetsResponse,
    PreferencesModel,
    PreferencesResponse,
    RouteCastScoreRequest,
    RouteCastScoreResponse,
    ScoredLoadModel,
    ScoredLoadsResponse,
    WatchlistItemCreateRequest,
    WatchlistItemModel,
    WatchlistResponse,
)
from .routecast_cache import RouteCastCache
from .stores import AlertRulesStore, FilterPresetsStore, PreferencesStore, WatchlistStore
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


def _likely_worker_count() -> int | None:
    """Best-effort worker count detection for common deployment envs."""

    for key in ("WEB_CONCURRENCY", "UVICORN_WORKERS", "GUNICORN_WORKERS", "WORKERS"):
        raw = os.environ.get(key)
        if raw:
            try:
                return int(raw)
            except ValueError:
                pass

    cmd = os.environ.get("GUNICORN_CMD_ARGS", "")
    if cmd:
        parts = cmd.split()
        for i, part in enumerate(parts):
            if part in ("--workers", "-w") and i + 1 < len(parts):
                try:
                    return int(parts[i + 1])
                except ValueError:
                    return None
            if part.startswith("--workers="):
                try:
                    return int(part.split("=", 1)[1])
                except ValueError:
                    return None

    return None


def _build_default_ctx() -> AppContext:
    return AppContext(
        dataset=generate_synthetic_loads(settings.synthetic_load_count),
        scoring_engine=ScoringEngine(),
        scoring_service=None,
        routecast_client=None,
        routecast_cache=RouteCastCache(
            ttl_seconds=settings.routecast_cache_ttl_seconds,
            negative_ttl_seconds=settings.routecast_negative_cache_ttl_seconds,
        ),
        ingestion_manager=None,
        ingestion_task=None,
        preferences_store=PreferencesStore(),
        watchlist_store=WatchlistStore(),
        alert_rules_store=AlertRulesStore(),
        filter_presets_store=FilterPresetsStore(),
    )


async def _read_body_bounded(request: Request, *, max_bytes: int) -> bytes:
    """Read request body with a hard cap.

    Enforces Content-Length (if present) and also caps streamed reads.
    """

    max_bytes = int(max_bytes)
    content_length = request.headers.get("content-length")
    if content_length is not None:
        try:
            declared = int(content_length)
        except ValueError as e:
            raise HTTPException(status_code=400, detail="Invalid Content-Length") from e
        if declared > max_bytes:
            raise HTTPException(status_code=413, detail="Import payload too large")

    buf = bytearray()
    async for chunk in request.stream():
        if not chunk:
            continue
        buf.extend(chunk)
        if len(buf) > max_bytes:
            raise HTTPException(status_code=413, detail="Import payload too large")
    return bytes(buf)


# =============================================================================
# Application Lifespan (startup/shutdown)
# =============================================================================

@asynccontextmanager
async def lifespan(app: FastAPI):
    """Application lifespan handler for startup/shutdown events."""
    # Startup
    logger.info("Starting LoadSuite (environment=%s, use_database=%s)", 
                settings.environment, settings.use_database)

    if settings.ingestion_enabled and not settings.use_database:
        workers = _likely_worker_count()
        if workers is None or workers > 1:
            logger.warning(
                "Ingestion is enabled with in-memory state. State is per-process; multi-worker deployments will diverge "
                "(consider enabling DB-backed persistence or an external shared store like Redis). workers=%s",
                workers,
            )
    
    write_sample_files(BASE_DIR)
    
    if settings.use_database:
        from .database import init_db_pool, check_database_health
        await init_db_pool()
        health = await check_database_health()
        logger.info("Database health: %s", health["status"])

    # Attach live context to app.state for DI.
    # Note: tests instantiate TestClient(app) without running lifespan, so we
    # also initialize a default ctx at module import time. Don't overwrite it.
    if getattr(app.state, "ctx", None) is None:
        app.state.ctx = _build_default_ctx()

    # Ingestion (in-memory, additive)
    if settings.ingestion_enabled:
        _ingestion_manager = IngestionManager.from_settings(
            connector_specs=settings.ingestion_connectors,
            quarantine_mode=settings.ingestion_quarantine_mode,
            default_ttl_seconds=settings.ingestion_default_ttl_seconds,
            raw_payload_ttl_seconds=settings.raw_payload_ttl_seconds,
        )
        app.state.ctx.ingestion_manager = _ingestion_manager

        # Seed once so ingestion-backed /api/loads isn't empty if connectors exist.
        try:
            await _ingestion_manager.run_once()
        except Exception as e:
            logger.warning("Initial ingestion run failed: %s", e)

        if settings.ingestion_poll_interval_seconds > 0:
            interval = int(settings.ingestion_poll_interval_seconds)

            async def _poll_loop() -> None:
                while True:
                    try:
                        if app.state.ctx.ingestion_manager is not None:
                            await app.state.ctx.ingestion_manager.run_once()
                    except asyncio.CancelledError:
                        raise
                    except Exception as e:
                        logger.warning("Background ingestion run failed: %s", e)
                    await asyncio.sleep(interval)

            ingestion_task = asyncio.create_task(_poll_loop())
            app.state.ctx.ingestion_task = ingestion_task
    
    yield
    
    # Shutdown
    ctx = getattr(app.state, "ctx", None)
    if ctx is not None and ctx.ingestion_task is not None:
        ctx.ingestion_task.cancel()
        try:
            await ctx.ingestion_task
        except asyncio.CancelledError:
            pass
        ctx.ingestion_task = None
    if ctx is not None:
        ctx.ingestion_manager = None

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

# Default app context for request handlers.
# (Starlette TestClient does not run lifespan unless used as a context manager.)
app.state.ctx = _build_default_ctx()

# Default user ID for anonymous/demo usage
DEFAULT_USER_ID = "default"


def _active_loads(ctx: AppContext) -> list[Load]:
    """Return the active load list for all endpoints.

    When ingestion is enabled, reads from ingestion store; otherwise uses the
    existing synthetic/import dataset behavior.
    """

    if settings.ingestion_enabled and ctx.ingestion_manager is not None:
        return ctx.ingestion_manager.get_loads()
    return ctx.dataset.loads


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
def meta(ctx: AppContext = Depends(get_ctx)) -> dict[str, Any]:
    loads = _active_loads(ctx)
    source = "ingestion" if (settings.ingestion_enabled and ctx.ingestion_manager is not None) else ctx.dataset.source
    return {
        "source": source,
        "count": len(loads),
        "server_time": datetime.now(timezone.utc).isoformat(),
        "environment": settings.environment,
        "use_database": settings.use_database,
        "ingestion_enabled": settings.ingestion_enabled,
    }


@app.get("/api/ingestion/status")
async def ingestion_status(ingestion: IngestionManager | None = Depends(get_ingestion)) -> dict[str, Any]:
    if not settings.ingestion_enabled or ingestion is None:
        return {
            "enabled": False,
            "last_run_at": None,
            "counts": {},
            "errors": [],
            "last_error": None,
        }
    return {"enabled": True, **ingestion.stats()}


@app.post("/api/ingestion/run")
async def ingestion_run(
    _: None = Depends(require_admin_api_key),
    ingestion: IngestionManager | None = Depends(get_ingestion),
) -> dict[str, Any]:
    if not settings.ingestion_enabled or ingestion is None:
        raise HTTPException(status_code=409, detail="Ingestion is not enabled")
    counts = await ingestion.run_once()
    return {"ok": True, "counts": counts, "last_run_at": ingestion.stats().get("last_run_at")}


@app.get("/api/ingestion/sources")
async def ingestion_sources(
    _: None = Depends(require_admin_api_key),
    ingestion: IngestionManager | None = Depends(get_ingestion),
) -> dict[str, Any]:
    if not settings.ingestion_enabled or ingestion is None:
        return {"enabled": False, "sources": []}
    sources = await ingestion.sources()
    return {
        "enabled": True,
        "sources": [
            {
                "name": s.name,
                "enabled": s.enabled,
                "kind": s.kind,
                "spec": s.spec,
                "healthy": s.healthy,
                "last_error": s.last_error,
            }
            for s in sources
        ],
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


@app.post("/api/routecast/score", response_model=RouteCastScoreResponse)
def routecast_score(
    req: RouteCastScoreRequest,
    client: RouteCastClient | None = Depends(get_routecast_client),
) -> RouteCastScoreResponse:
    if not settings.routecast_enabled or client is None:
        raise HTTPException(status_code=501, detail="RouteCast integration is disabled")

    return client.score_route(req)


@app.get("/api/loads")
def list_loads(
    ctx: AppContext = Depends(get_ctx),
    scoring: ScoringEngine = Depends(get_scoring),
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
    user_id: str = Query(default=DEFAULT_USER_ID, description="User ID for preferences when sorting by score"),
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
    filtered = apply_filters(_active_loads(ctx), query)
    if sort == "score_desc":
        prefs_model, _ = ctx.preferences_store.get(user_id)
        user_prefs = _convert_prefs_to_user_prefs(prefs_model)
        scored = [(load, scoring.score(load, preferences=user_prefs, now=now).score) for load in filtered]
        ranked = [item[0] for item in sorted(scored, key=lambda t: t[1], reverse=True)]
    else:
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


def _routecast_unavailable(reason: str) -> RouteCastScoreResponse:
    return RouteCastScoreResponse(
        overlays=[],
        risk_score=None,
        summary="Route risk unavailable",
        reasons=[reason],
        provider=settings.routecast_provider,
        confidence="degraded",
    )


@app.get("/api/loads/scored", response_model=ScoredLoadsResponse)
def list_scored_loads(
    ctx: AppContext = Depends(get_ctx),
    scoring: ScoringEngine = Depends(get_scoring),
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
    include_routecast: bool = Query(default=False, description="Include RouteCast scores for up to 25 loads"),
    routecast_client: RouteCastClient | None = Depends(get_routecast_client),
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
    filtered = apply_filters(_active_loads(ctx), query)
    loads_for_scoring = filtered if sort == "score_desc" else apply_sort(filtered, query, now)[:limit]
    
    # Get user preferences for scoring
    prefs_model, _ = ctx.preferences_store.get(user_id)
    user_prefs = _convert_prefs_to_user_prefs(prefs_model)
    greenlight_threshold = prefs_model.greenlight_threshold or 70.0

    scored_loads: List[ScoredLoadModel] = []
    allow_routecast = include_routecast and settings.routecast_enabled and routecast_client is not None
    max_routecast = 25

    for idx, load in enumerate(loads_for_scoring):
        composite = scoring.score(load, preferences=user_prefs, now=now)

        routecast: RouteCastScoreResponse | None = None
        if allow_routecast and idx < max_routecast:
            try:
                origin = geocode_city_state(load.origin.city, load.origin.state)
                destination = geocode_city_state(load.destination.city, load.destination.state)
                req = RouteCastScoreRequest(
                    origin=CoordinateModel(lat=float(origin["lat"]), lon=float(origin["lon"])),
                    destination=CoordinateModel(lat=float(destination["lat"]), lon=float(destination["lon"])),
                    via=[],
                    equipment_type=load.equipment,
                    weight_lbs=float(load.weight_lbs) if load.weight_lbs is not None else None,
                    departure_time=load.pickup_start,
                )
                routecast = routecast_client.score_route(req)
            except (ValueError, LookupError):
                routecast = _routecast_unavailable("geocode_failed")
            except Exception:
                logger.exception("routecast attach failed")
                routecast = _routecast_unavailable("routecast_unavailable")

        scored_loads.append(ScoredLoadModel(
            load=load,
            score=composite.score,
            top_reasons=[_factor_to_model(f) for f in composite.top_reasons[:3]],
            factors=[_factor_to_model(f) for f in composite.factors],
            confidence=composite.confidence,
            greenlight=composite.score >= greenlight_threshold,
            routecast=routecast,
        ))
    
    if sort == "score_desc":
        scored_loads.sort(key=lambda s: s.score, reverse=True)
        scored_loads = scored_loads[:limit]

    return ScoredLoadsResponse(total=len(scored_loads), loads=scored_loads)


@app.get("/api/loads/{load_id}/score")
def get_load_score(
    load_id: str,
    ctx: AppContext = Depends(get_ctx),
    scoring: ScoringEngine = Depends(get_scoring),
    user_id: str = Query(default=DEFAULT_USER_ID),
) -> ScoredLoadModel:
    """Get score details for a specific load."""
    load = None
    for l in _active_loads(ctx):
        if l.id == load_id:
            load = l
            break
    if load is None:
        raise HTTPException(status_code=404, detail="Load not found")
    
    prefs_model, _ = ctx.preferences_store.get(user_id)
    user_prefs = _convert_prefs_to_user_prefs(prefs_model)
    greenlight_threshold = prefs_model.greenlight_threshold or 70.0
    
    now = datetime.now(timezone.utc)
    composite = scoring.score(load, preferences=user_prefs, now=now)
    
    return ScoredLoadModel(
        load=load,
        score=composite.score,
        top_reasons=[_factor_to_model(f) for f in composite.top_reasons[:3]],
        factors=[_factor_to_model(f) for f in composite.factors],
        confidence=composite.confidence,
        greenlight=composite.score >= greenlight_threshold,
    )


@app.get("/api/loads/{load_id}")
def get_load(load_id: str, ctx: AppContext = Depends(get_ctx)) -> dict[str, Any]:
    for load in _active_loads(ctx):
        if load.id == load_id:
            return load.model_dump(mode="json")
    raise HTTPException(status_code=404, detail="Load not found")


@app.get("/api/loads/{load_id}/routecast")
def get_routecast(load_id: str, ctx: AppContext = Depends(get_ctx)) -> dict[str, Any]:
    load: Load | None = None
    for l in _active_loads(ctx):
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
def refresh(ctx: AppContext = Depends(get_ctx), req: RefreshRequest = RefreshRequest()) -> dict[str, Any]:
    ctx.dataset = generate_synthetic_loads(req.count)
    return {"ok": True, "source": ctx.dataset.source, "count": len(ctx.dataset.loads)}


@app.post("/api/import")
async def import_data(
    request: Request,
    filename: str,
    _: None = Depends(require_admin_api_key),
    ctx: AppContext = Depends(get_ctx),
) -> dict[str, Any]:
    if not filename:
        raise HTTPException(status_code=400, detail="Missing filename")

    lower = filename.lower()
    if not (lower.endswith(".json") or lower.endswith(".csv")):
        raise HTTPException(status_code=400, detail="Unsupported import format")

    content = await _read_body_bounded(request, max_bytes=settings.import_max_bytes)

    if lower.endswith(".json"):
        try:
            raw = json.loads(content.decode("utf-8"))
        except Exception as e:
            raise HTTPException(status_code=400, detail="Import failed: invalid JSON") from e

        if not isinstance(raw, list):
            raise HTTPException(status_code=400, detail="JSON must be an array of load objects")

        if len(raw) > int(settings.import_max_records):
            raise HTTPException(
                status_code=400,
                detail=f"Too many records (max {int(settings.import_max_records)})",
            )

        loads: list[Load] = []
        for idx, item in enumerate(raw):
            if not isinstance(item, dict):
                raise HTTPException(status_code=400, detail=f"Record {idx}: must be an object")
            try:
                loads.append(Load.model_validate(item))
            except Exception as e:
                raise HTTPException(status_code=400, detail=f"Record {idx}: invalid load") from e

        ctx.dataset = Dataset(loads=loads, source="import:json")
        return {"ok": True, "source": ctx.dataset.source, "count": len(ctx.dataset.loads)}

    # CSV
    try:
        loads = loads_from_csv_bytes(
            content,
            max_records=int(settings.import_max_records),
            max_line_length=int(settings.import_max_csv_line_length),
            max_field_length=int(settings.import_max_csv_field_length),
        )
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e)) from e
    except Exception as e:
        raise HTTPException(status_code=400, detail="Import failed: invalid CSV") from e

    ctx.dataset = Dataset(loads=loads, source="import:csv")
    return {"ok": True, "source": ctx.dataset.source, "count": len(ctx.dataset.loads)}


# =============================================================================
# Preferences Endpoints
# =============================================================================

@app.get("/api/preferences", response_model=PreferencesResponse)
def get_preferences(
    ctx: AppContext = Depends(get_ctx),
    user_id: str = Query(default=DEFAULT_USER_ID),
) -> PreferencesResponse:
    """Get user preferences."""
    prefs, updated_at = ctx.preferences_store.get(user_id)
    return PreferencesResponse(
        user_id=user_id,
        preferences=prefs,
        updated_at=updated_at,
    )


@app.put("/api/preferences", response_model=PreferencesResponse)
def set_preferences(
    prefs: PreferencesModel,
    ctx: AppContext = Depends(get_ctx),
    user_id: str = Query(default=DEFAULT_USER_ID),
) -> PreferencesResponse:
    """Set user preferences."""
    updated_at = ctx.preferences_store.set(user_id, prefs)
    return PreferencesResponse(
        user_id=user_id,
        preferences=prefs,
        updated_at=updated_at,
    )


@app.delete("/api/preferences")
def delete_preferences(
    ctx: AppContext = Depends(get_ctx),
    user_id: str = Query(default=DEFAULT_USER_ID),
) -> dict[str, Any]:
    """Reset user preferences to defaults."""
    deleted = ctx.preferences_store.delete(user_id)
    return {"ok": True, "deleted": deleted}


# =============================================================================
# Watchlist Endpoints (Stub)
# =============================================================================

@app.get("/api/watchlist", response_model=WatchlistResponse)
def list_watchlist(
    ctx: AppContext = Depends(get_ctx),
    user_id: str = Query(default=DEFAULT_USER_ID),
) -> WatchlistResponse:
    """List all watchlist items for a user."""
    items = ctx.watchlist_store.list(user_id)
    return WatchlistResponse(user_id=user_id, items=items, total=len(items))


@app.post("/api/watchlist", response_model=WatchlistItemModel)
def create_watchlist_item(
    req: WatchlistItemCreateRequest,
    ctx: AppContext = Depends(get_ctx),
    user_id: str = Query(default=DEFAULT_USER_ID),
) -> WatchlistItemModel:
    """Add an item to the watchlist."""
    return ctx.watchlist_store.create(
        user_id=user_id,
        item_type=req.item_type,
        load_id=req.load_id,
        lane=req.lane,
        notes=req.notes,
    )


@app.delete("/api/watchlist/{item_id}")
def delete_watchlist_item(
    item_id: str,
    ctx: AppContext = Depends(get_ctx),
    user_id: str = Query(default=DEFAULT_USER_ID),
) -> dict[str, Any]:
    """Remove an item from the watchlist."""
    deleted = ctx.watchlist_store.delete(user_id, item_id)
    if not deleted:
        raise HTTPException(status_code=404, detail="Watchlist item not found")
    return {"ok": True, "deleted": True}


@app.get("/api/watchlist/check/{load_id}")
def check_watchlist(
    load_id: str,
    ctx: AppContext = Depends(get_ctx),
    user_id: str = Query(default=DEFAULT_USER_ID),
) -> dict[str, Any]:
    """Check if a load is in the user's watchlist."""
    return {"watched": ctx.watchlist_store.has_load(user_id, load_id)}


# =============================================================================
# Alert Rules Endpoints (Stub - Execution is TODO)
# =============================================================================

@app.get("/api/alerts", response_model=AlertRulesResponse)
def list_alert_rules(
    ctx: AppContext = Depends(get_ctx),
    user_id: str = Query(default=DEFAULT_USER_ID),
) -> AlertRulesResponse:
    """List all alert rules for a user."""
    rules = ctx.alert_rules_store.list(user_id)
    return AlertRulesResponse(user_id=user_id, rules=rules, total=len(rules))


@app.post("/api/alerts", response_model=AlertRuleModel)
def create_alert_rule(
    req: AlertRuleCreateRequest,
    ctx: AppContext = Depends(get_ctx),
    user_id: str = Query(default=DEFAULT_USER_ID),
) -> AlertRuleModel:
    """Create a new alert rule. Note: Execution is TODO."""
    return ctx.alert_rules_store.create(
        user_id=user_id,
        name=req.name,
        description=req.description,
        conditions=req.conditions,
        enabled=req.enabled,
    )


@app.delete("/api/alerts/{rule_id}")
def delete_alert_rule(
    rule_id: str,
    ctx: AppContext = Depends(get_ctx),
    user_id: str = Query(default=DEFAULT_USER_ID),
) -> dict[str, Any]:
    """Delete an alert rule."""
    deleted = ctx.alert_rules_store.delete(user_id, rule_id)
    if not deleted:
        raise HTTPException(status_code=404, detail="Alert rule not found")
    return {"ok": True, "deleted": True}


# =============================================================================
# Filter Presets Endpoints
# =============================================================================

@app.get("/api/presets", response_model=FilterPresetsResponse)
def list_filter_presets(
    ctx: AppContext = Depends(get_ctx),
    user_id: str = Query(default=DEFAULT_USER_ID),
) -> FilterPresetsResponse:
    """List all saved filter presets."""
    presets = ctx.filter_presets_store.list(user_id)
    return FilterPresetsResponse(user_id=user_id, presets=presets, total=len(presets))


@app.post("/api/presets", response_model=FilterPresetModel)
def create_filter_preset(
    req: FilterPresetCreateRequest,
    ctx: AppContext = Depends(get_ctx),
    user_id: str = Query(default=DEFAULT_USER_ID),
) -> FilterPresetModel:
    """Save current filters as a preset."""
    return ctx.filter_presets_store.create(
        user_id=user_id,
        name=req.name,
        filters=req.filters,
    )


@app.delete("/api/presets/{preset_id}")
def delete_filter_preset(
    preset_id: str,
    ctx: AppContext = Depends(get_ctx),
    user_id: str = Query(default=DEFAULT_USER_ID),
) -> dict[str, Any]:
    """Delete a filter preset."""
    deleted = ctx.filter_presets_store.delete(user_id, preset_id)
    if not deleted:
        raise HTTPException(status_code=404, detail="Preset not found")
    return {"ok": True, "deleted": True}


# Static UI
app.mount("/static", StaticFiles(directory=str(STATIC_DIR)), name="static")


@app.get("/")
def index() -> FileResponse:
    return FileResponse(str(STATIC_DIR / "index.html"))
