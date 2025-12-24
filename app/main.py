from __future__ import annotations

import asyncio
import json
import logging
import os
import random
from contextlib import asynccontextmanager
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, List, Optional

from fastapi import Depends, FastAPI, HTTPException, Query, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, JSONResponse, Response
from fastapi.staticfiles import StaticFiles

from .app_context import AppContext
from .auth import require_admin_api_key
from .config import settings
from .data import Dataset, get_synthetic_dataset, loads_from_csv_bytes, write_sample_files
from .deps import get_ctx, get_ingestion, get_routecast_client, get_scoring
from .filters import apply_filters, apply_sort
from .ingestion.manager import IngestionManager
from .ingestion.models import Provenance
from .models import Load, LoadsQuery, RefreshRequest
from .news import get_news_items
from .metrics import get_metrics_text
from .services.routecast_client import RouteCastClient
from .api_models import (
    AlertRuleCreateRequest,
    AlertRuleModel,
    AlertRuleUpdateRequest,
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
    TriggeredAlertModel,
    TriggeredAlertsResponse,
    TrustResponse,
    TrustReason,
    WatchlistItemCreateRequest,
    WatchlistItemModel,
    WatchlistResponse,
)
from .routecast_cache import RouteCastCache
from .stores import AlertRulesStore, FilterPresetsStore, PersistentWatchlistStore, PreferencesStore, WatchlistStore
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
STATIC_IMAGES_DIR = STATIC_DIR / "images"


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
    watchlist_store: WatchlistStore
    if settings.use_database:
        from .mysql_stores import (
            MySQLAlertRulesStore,
            MySQLFilterPresetsStore,
            MySQLPreferencesStore,
            MySQLWatchlistStore,
        )

        preferences_store = MySQLPreferencesStore()
        watchlist_store = MySQLWatchlistStore()
        alert_rules_store = MySQLAlertRulesStore()
        filter_presets_store = MySQLFilterPresetsStore()
    else:
        if settings.environment in ("production", "staging"):
            watchlist_store = PersistentWatchlistStore(BASE_DIR / ".runtime" / "watchlist.json")
        else:
            watchlist_store = WatchlistStore()

        preferences_store = PreferencesStore()
        alert_rules_store = AlertRulesStore()
        filter_presets_store = FilterPresetsStore()

    # Support deterministic synthetic datasets via SYNTHETIC_SEED env var.
    # Cache is process-local; multi-worker deployments will have one cache per worker.
    seed_val = None
    seed_raw = os.environ.get("SYNTHETIC_SEED")
    if seed_raw is not None:
        try:
            seed_val = int(seed_raw)
        except Exception:
            seed_val = None

    # Prefer loading a committed static synthetic dataset when available. This
    # ensures the dataset is stable and never implicitly regenerated.
    synthetic_file = BASE_DIR / settings.synthetic_dataset_path
    if synthetic_file.exists():
        from .data import load_dataset_from_file

        try:
            dataset = load_dataset_from_file(synthetic_file)
        except Exception:
            logger.exception("Failed to load synthetic dataset from %s", synthetic_file)
            # Fall back to existing behavior to avoid startup failure in dev mode
            dataset = get_synthetic_dataset(settings.synthetic_load_count, seed=seed_val)
    else:
        # If a committed static dataset isn't present, preserve previous behavior
        # and generate a synthetic dataset according to settings. This path does
        # NOT regenerate a committed static dataset automatically.
        if settings.generate_synthetic_loads:
            dataset = get_synthetic_dataset(settings.synthetic_load_count, seed=seed_val)
        else:
            # Fall back to small sample file if available
            sample_path = BASE_DIR / "sample_data" / "sample_loads.json"
            from .data import load_dataset_from_file

            if sample_path.exists():
                dataset = load_dataset_from_file(sample_path)
            else:
                dataset = get_synthetic_dataset(settings.synthetic_load_count, seed=seed_val)

    return AppContext(
        dataset=dataset,
        scoring_engine=ScoringEngine(),
        scoring_service=None,
        routecast_client=None,
        routecast_cache=RouteCastCache(
            ttl_seconds=settings.routecast_cache_ttl_seconds,
            negative_ttl_seconds=settings.routecast_negative_cache_ttl_seconds,
        ),
        ingestion_manager=None,
        ingestion_task=None,
        preferences_store=preferences_store,
        watchlist_store=watchlist_store,
        alert_rules_store=alert_rules_store,
        filter_presets_store=filter_presets_store,
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
    # Production servers run multiple processes; rebuild ctx here so the
    # correct persistence choices are applied. In tests, avoid clobbering the
    # pre-seeded ctx (many tests don't run lifespan).
    if os.environ.get("PYTEST_CURRENT_TEST") is None or getattr(app.state, "ctx", None) is None:
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


# -----------------------------------------------------------------------------
# Metrics middleware: collect HTTP request metrics with low-cardinality labels
# -----------------------------------------------------------------------------
@app.middleware("http")
async def metrics_middleware(request: Request, call_next):
    import time

    from .metrics import http_request_duration_seconds, http_requests_total

    start = time.perf_counter()
    status_code = 500

    try:
        response = await call_next(request)
        status_code = response.status_code
        return response
    finally:
        route_template = getattr(request.scope.get("route"), "path", None) or "unknown_route"
        try:
            http_requests_total.labels(request.method, route_template, str(status_code)).inc()
            http_request_duration_seconds.labels(request.method, route_template).observe(
                time.perf_counter() - start
            )
        except Exception:
            logger.debug("metrics emit skipped", exc_info=True)

# Default app context for request handlers.
# (Starlette TestClient does not run lifespan unless used as a context manager.)
app.state.ctx = _build_default_ctx()

# Default user ID for anonymous/demo usage
DEFAULT_USER_ID = "default"


def _compute_trust(load: Load, provenance: Provenance | None, now: datetime) -> TrustResponse:
    reasons: list[TrustReason] = []

    def _add_reason(factor: str, label: str, contribution: int, details: str) -> None:
        reasons.append(
            TrustReason(
                factor=factor,
                label=label,
                contribution=contribution,
                details={"message": details},
            )
        )

    score = 60

    core_present = load.distance_miles > 0 and load.rate_total_usd > 0 and load.rpm > 0
    core_partial = any([load.distance_miles > 0, load.rate_total_usd > 0, load.rpm > 0]) and not core_present

    if core_present:
        score += 20
        _add_reason(
            "core_fields_present",
            "Core fields verified",
            20,
            "Distance, rate, and RPM present",
        )
    elif core_partial:
        score += 8
        _add_reason(
            "core_fields_partial",
            "Some core fields estimated",
            8,
            "At least one of distance, rate, or RPM is missing",
        )
    else:
        score -= 10
        _add_reason(
            "core_fields_missing",
            "Core fields missing",
            -10,
            "Distance, rate, and RPM are unavailable",
        )

    if provenance and provenance.source_record_id:
        score += 5
        _add_reason(
            "provenance_record_id",
            "Source record ID present",
            5,
            "Source provided a record identifier",
        )
    else:
        score -= 5
        _add_reason(
            "provenance_missing_record_id",
            "Source record ID missing",
            -5,
            "No source record identifier available",
        )

    updated_at = provenance.source_updated_at if provenance else None
    if updated_at:
        score += 5
        _add_reason(
            "provenance_updated_at",
            "Source timestamp present",
            5,
            "Source provided a last-updated timestamp",
        )
        age_seconds = (now - updated_at).total_seconds()
        if age_seconds > 43200:
            score -= 15
            _add_reason(
                "data_expired",
                "Data is expired (>12h old)",
                -15,
                "Source timestamp older than 12 hours",
            )
        elif age_seconds > 14400:
            score -= 8
            _add_reason(
                "data_stale",
                "Data is stale (4-12h old)",
                -8,
                "Source timestamp older than 4 hours",
            )
    else:
        score -= 5
        _add_reason(
            "provenance_missing_updated_at",
            "Source timestamp missing",
            -5,
            "No source last-updated timestamp available",
        )

    rpm_derived = load.rpm <= 0 or load.distance_miles <= 0 or load.rate_total_usd <= 0
    if rpm_derived:
        score -= 10
        _add_reason(
            "rpm_derived",
            "RPM was estimated",
            -10,
            "RPM derived because rate or distance was missing",
        )

    if load.distance_miles <= 0:
        score -= 5
        _add_reason(
            "distance_clamped",
            "Distance was clamped to 1 mi",
            -5,
            "Distance missing or non-positive; clamped for RPM",
        )

    score = max(0, min(100, int(round(score))))
    bucket = "high" if score >= 80 else "medium" if score >= 50 else "low"
    return TrustResponse(load_id=load.id, confidence_score=score, confidence_bucket=bucket, confidence_reasons=reasons)


def _active_loads(ctx: AppContext) -> list[Load]:
    """Return the active load list for all endpoints.

    When ingestion is enabled, reads from ingestion store; otherwise uses the
    existing synthetic/import dataset behavior.
    """

    if settings.ingestion_enabled and ctx.ingestion_manager is not None:
        return ctx.ingestion_manager.get_loads()
    return ctx.dataset.loads


@app.get("/metrics")
def metrics_endpoint() -> Response:
    payload, content_type = get_metrics_text()
    return Response(content=payload, media_type=content_type)


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


def _greenlight_criteria_active(prefs: PreferencesModel) -> bool:
    return any([
        prefs.min_rpm is not None,
        prefs.max_deadhead_miles is not None,
        prefs.max_weight_lbs is not None,
        prefs.min_weight_lbs is not None,
        prefs.min_broker_rating is not None,
        bool(prefs.equipment_types),
        prefs.detention is not None,
        prefs.hazmat is not None,
        prefs.multi_stop is not None,
    ])


def _meets_greenlight_criteria(load: Load, prefs: PreferencesModel) -> bool:
    if not _greenlight_criteria_active(prefs):
        return False

    if prefs.min_rpm is not None and load.rpm < prefs.min_rpm:
        return False
    if prefs.max_deadhead_miles is not None and load.deadhead_miles > prefs.max_deadhead_miles:
        return False
    if prefs.max_weight_lbs is not None and load.weight_lbs > prefs.max_weight_lbs:
        return False
    if prefs.min_weight_lbs is not None and load.weight_lbs < prefs.min_weight_lbs:
        return False
    if prefs.min_broker_rating is not None and load.broker.rating < prefs.min_broker_rating:
        return False
    if prefs.equipment_types:
        if load.equipment not in prefs.equipment_types:
            return False
    if prefs.detention is not None and load.detention is not prefs.detention:
        return False
    if prefs.hazmat is not None and load.hazmat is not prefs.hazmat:
        return False
    if prefs.multi_stop is not None and load.multi_stop is not prefs.multi_stop:
        return False

    return True


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
    total_filtered = len(filtered)
    loads_for_scoring = filtered if sort == "score_desc" else apply_sort(filtered, query, now)[:limit]
    
    # Get user preferences for scoring
    prefs_model, _ = ctx.preferences_store.get(user_id)
    user_prefs = _convert_prefs_to_user_prefs(prefs_model)
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
            greenlight=_meets_greenlight_criteria(load, prefs_model),
            routecast=routecast,
        ))
    
    if sort == "score_desc":
        scored_loads.sort(key=lambda s: s.score, reverse=True)
        scored_loads = scored_loads[:limit]

    return ScoredLoadsResponse(total=total_filtered, loads=scored_loads)


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
    now = datetime.now(timezone.utc)
    composite = scoring.score(load, preferences=user_prefs, now=now)
    
    return ScoredLoadModel(
        load=load,
        score=composite.score,
        top_reasons=[_factor_to_model(f) for f in composite.top_reasons[:3]],
        factors=[_factor_to_model(f) for f in composite.factors],
        confidence=composite.confidence,
        greenlight=_meets_greenlight_criteria(load, prefs_model),
    )


@app.get("/api/loads/{load_id}")
def get_load(load_id: str, ctx: AppContext = Depends(get_ctx)) -> dict[str, Any]:
    for load in _active_loads(ctx):
        if load.id == load_id:
            return load.model_dump(mode="json")
    raise HTTPException(status_code=404, detail="Load not found")


@app.get("/api/loads/{load_id}/trust", response_model=TrustResponse)
def get_load_trust(load_id: str, ctx: AppContext = Depends(get_ctx)) -> TrustResponse:
    provenance: Provenance | None = None
    load: Load | None = None

    if ctx.ingestion_manager is not None:
        stored = ctx.ingestion_manager._load_store.get(load_id)  # type: ignore[attr-defined]
        if stored is not None:
            load = stored.load
            provenance = stored.provenance

    if load is None:
        for l in _active_loads(ctx):
            if l.id == load_id:
                load = l
                break

    if load is None:
        raise HTTPException(status_code=404, detail="Load not found")

    now = datetime.now(timezone.utc)
    return _compute_trust(load, provenance, now)


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
    """Refresh synthetic dataset on-demand.

    By default, this endpoint is disabled (returns 403) to protect the committed
    static dataset; enable by setting ALLOW_SYNTH_REFRESH=1 (or using the
    equivalent environment var). When enabled, refresh is deterministic when a
    seed is provided (either via SYNTHETIC_SEED env var or `seed` in the request).
    """
    # Gate by config flag
    if not settings.allow_synth_refresh:
        return JSONResponse(
            status_code=403,
            content={"ok": False, "error": "Synthetic regeneration disabled. Dataset is static (6769 loads)."},
        )

    # Respect explicit seed from request first, then SYNTHETIC_SEED env var.
    seed_val = req.seed
    if seed_val is None:
        seed_raw = os.environ.get("SYNTHETIC_SEED")
        if seed_raw is not None:
            try:
                seed_val = int(seed_raw)
            except Exception:
                seed_val = None

    if seed_val is None:
        # Force generate a fresh, non-deterministic dataset and update cache.
        from .data import _SYNTH_CACHE, generate_synthetic_loads

        ds = generate_synthetic_loads(req.count, rng=random.Random())
        _SYNTH_CACHE[(int(req.count), None)] = ds
    else:
        from .data import get_synthetic_dataset

        ds = get_synthetic_dataset(req.count, seed=seed_val)

    ctx.dataset = ds
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

def _get_alert_field_value(
    load: Load,
    field: str,
    *,
    scoring: ScoringEngine,
    user_prefs: UserPreferences,
    now: datetime,
) -> Any:
    f = (field or "").strip().lower()

    if f in ("rpm",):
        return load.rpm
    if f in ("equipment",):
        return load.equipment
    if f in ("weight", "weight_lbs"):
        return load.weight_lbs
    if f in ("distance", "distance_miles"):
        return load.distance_miles
    if f in ("deadhead", "deadhead_miles"):
        return load.deadhead_miles
    if f in ("broker_rating", "broker.rating"):
        return load.broker.rating
    if f in ("commodity",):
        return load.commodity
    if f in ("hazmat",):
        return load.hazmat
    if f in ("detention",):
        return load.detention
    if f in ("multi_stop",):
        return load.multi_stop
    if f in ("lane_history",):
        return load.lane_history
    if f in ("origin_city",):
        return load.origin.city
    if f in ("origin_state",):
        return load.origin.state
    if f in ("destination_city",):
        return load.destination.city
    if f in ("destination_state",):
        return load.destination.state
    if f in ("lane",):
        return f"{load.origin.city}, {load.origin.state} -> {load.destination.city}, {load.destination.state}"
    if f in ("q", "search"):
        return " ".join(
            [
                load.origin.city,
                load.origin.state,
                load.destination.city,
                load.destination.state,
                load.commodity,
                load.broker.name,
            ]
        )
    if f in ("score",):
        return scoring.score(load, preferences=user_prefs, now=now).score

    return None


def _evaluate_alert_condition(value: Any, operator: str, target: Any) -> bool:
    if value is None:
        return False

    op = (operator or "").strip().lower()

    # Bool comparison (explicit)
    if isinstance(value, bool) or isinstance(target, bool):
        if op != "eq":
            return False
        return bool(value) is bool(target)

    # Numeric comparisons (best-effort)
    try:
        v = float(value)
        t = float(target)
        if op == "gt":
            return v > t
        if op == "gte":
            return v >= t
        if op == "lt":
            return v < t
        if op == "lte":
            return v <= t
        if op == "eq":
            return v == t
    except (TypeError, ValueError):
        pass

    # String comparisons
    v = str(value).strip().lower()
    t = str(target).strip().lower()
    if op == "eq":
        return v == t
    if op == "contains":
        return t in v
    return False

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
    """Create a new alert rule."""
    return ctx.alert_rules_store.create(
        user_id=user_id,
        name=req.name,
        description=req.description,
        conditions=req.conditions,
        enabled=req.enabled,
    )


@app.put("/api/alerts/{rule_id}", response_model=AlertRuleModel)
def update_alert_rule(
    rule_id: str,
    req: AlertRuleUpdateRequest,
    ctx: AppContext = Depends(get_ctx),
    user_id: str = Query(default=DEFAULT_USER_ID),
) -> AlertRuleModel:
    """Update an existing alert rule."""

    updated = ctx.alert_rules_store.update(
        user_id,
        rule_id,
        name=req.name,
        description=req.description,
        conditions=req.conditions,
        enabled=req.enabled,
    )
    if updated is None:
        raise HTTPException(status_code=404, detail="Alert rule not found")
    return updated


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


@app.get("/api/alerts/triggered", response_model=TriggeredAlertsResponse)
def list_triggered_alerts(
    ctx: AppContext = Depends(get_ctx),
    scoring: ScoringEngine = Depends(get_scoring),
    user_id: str = Query(default=DEFAULT_USER_ID),
    matching_load_limit: int = Query(default=5, ge=0, le=50),
) -> TriggeredAlertsResponse:
    """Evaluate enabled alert rules against the current active loads."""

    now = datetime.now(timezone.utc)
    rules = ctx.alert_rules_store.list(user_id)
    loads = _active_loads(ctx)

    prefs_model, _ = ctx.preferences_store.get(user_id)
    user_prefs = _convert_prefs_to_user_prefs(prefs_model)

    triggered: List[TriggeredAlertModel] = []
    for rule in rules:
        if not rule.enabled or not rule.conditions:
            triggered.append(
                TriggeredAlertModel(
                    rule_id=rule.id,
                    name=rule.name,
                    description=rule.description,
                    enabled=rule.enabled,
                    matches_count=0,
                    matching_load_ids=[],
                    evaluated_at=now,
                    last_triggered=rule.last_triggered,
                )
            )
            continue

        matched_ids: List[str] = []
        for load in loads:
            ok = True
            for cond in rule.conditions:
                val = _get_alert_field_value(
                    load,
                    cond.field,
                    scoring=scoring,
                    user_prefs=user_prefs,
                    now=now,
                )
                if not _evaluate_alert_condition(val, cond.operator, cond.value):
                    ok = False
                    break
            if ok:
                matched_ids.append(load.id)

        if matched_ids:
            ctx.alert_rules_store.mark_triggered(user_id, rule.id, now=now)

        triggered.append(
            TriggeredAlertModel(
                rule_id=rule.id,
                name=rule.name,
                description=rule.description,
                enabled=rule.enabled,
                matches_count=len(matched_ids),
                matching_load_ids=matched_ids[:matching_load_limit] if matching_load_limit else [],
                evaluated_at=now,
                last_triggered=ctx.alert_rules_store.get(user_id, rule.id).last_triggered
                if ctx.alert_rules_store.get(user_id, rule.id)
                else rule.last_triggered,
            )
        )

    return TriggeredAlertsResponse(user_id=user_id, triggered=triggered, evaluated_at=now)


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


def _static_file(path: str) -> FileResponse:
    resolved = (STATIC_IMAGES_DIR / path).resolve()
    # Simple traversal guard.
    if not str(resolved).startswith(str(STATIC_IMAGES_DIR.resolve())):
        raise HTTPException(status_code=400, detail="Invalid static path")
    if not resolved.exists():
        raise HTTPException(status_code=404, detail="Static asset not found")
    return FileResponse(str(resolved))


# Favicons / PWA assets at domain root (browsers often request these from '/').
@app.get("/favicon.ico")
def favicon() -> FileResponse:
    # Default to the mixed-UI round favicon (navy fill) to stay visible on light tabs.
    return _static_file("favicon.ico")


@app.get("/favicon-bg.ico")
def favicon_bg() -> FileResponse:
    # Keep route for backwards-compat.
    return _static_file("favicon.ico")


@app.get("/favicon-transparent.ico")
def favicon_transparent() -> FileResponse:
    return _static_file("favicon-round-transparent.ico")


@app.get("/favicon-16x16.png")
def favicon_16() -> FileResponse:
    return _static_file("favicon-16x16.png")


@app.get("/favicon-32x32.png")
def favicon_32() -> FileResponse:
    return _static_file("favicon-32x32.png")


@app.get("/favicon-48x48.png")
def favicon_48() -> FileResponse:
    return _static_file("favicon-48x48.png")


@app.get("/favicon-bg-16x16.png")
def favicon_bg_16() -> FileResponse:
    return _static_file("favicon-bg-16x16.png")


@app.get("/favicon-bg-32x32.png")
def favicon_bg_32() -> FileResponse:
    return _static_file("favicon-bg-32x32.png")


@app.get("/favicon-bg-48x48.png")
def favicon_bg_48() -> FileResponse:
    return _static_file("favicon-bg-48x48.png")


@app.get("/apple-touch-icon.png")
def apple_touch_icon() -> FileResponse:
    return _static_file("apple-touch-icon.png")


@app.get("/android-chrome-192x192.png")
def android_192() -> FileResponse:
    return _static_file("android-chrome-192x192.png")


@app.get("/android-chrome-512x512.png")
def android_512() -> FileResponse:
    return _static_file("android-chrome-512x512.png")


@app.get("/android-chrome-512x512-maskable.png")
def android_512_maskable() -> FileResponse:
    return _static_file("android-chrome-512x512-maskable.png")


@app.get("/site.webmanifest")
def site_manifest() -> FileResponse:
    return _static_file("site.webmanifest")


@app.get("/")
def index() -> FileResponse:
    return FileResponse(str(STATIC_DIR / "index.html"))
