from __future__ import annotations

from fastapi import Depends, HTTPException, Request

from .app_context import AppContext
from .config import settings
from .ingestion.manager import IngestionManager
from .routecast_cache import RouteCastCache
from .routing_cache import RoutingCache
from .scoring import ScoringEngine
from .services.routecast_client import RouteCastClient
from .services.routing_client import RoutingClient


def get_ctx(request: Request) -> AppContext:
    ctx = getattr(request.app.state, "ctx", None)
    if ctx is None:
        raise HTTPException(status_code=500, detail="App context not initialized")
    return ctx


def get_ingestion(ctx: AppContext = Depends(get_ctx)) -> IngestionManager | None:
    return ctx.ingestion_manager


def get_scoring(ctx: AppContext = Depends(get_ctx)) -> ScoringEngine:
    return ctx.scoring_engine


def get_routecast_client(ctx: AppContext = Depends(get_ctx)) -> RouteCastClient | None:
    if not settings.routecast_enabled:
        return None

    if ctx.routecast_client is None:
        cache = ctx.routecast_cache or RouteCastCache(
            ttl_seconds=settings.routecast_cache_ttl_seconds,
            negative_ttl_seconds=settings.routecast_negative_cache_ttl_seconds,
        )
        ctx.routecast_cache = cache
        ctx.routecast_client = RouteCastClient(
            base_url=settings.routecast_base_url,
            timeout_seconds=settings.routecast_timeout_seconds,
            provider=settings.routecast_provider,
            cache=cache,
            api_key=settings.routecast_api_key,
        )
    return ctx.routecast_client


def get_routing_client(ctx: AppContext = Depends(get_ctx)) -> RoutingClient | None:
    if not settings.routing_provider or not settings.routing_base_url:
        return None

    if ctx.routing_client is None:
        cache = ctx.routing_cache or RoutingCache(
            ttl_seconds=settings.routing_cache_ttl_seconds,
            negative_ttl_seconds=settings.routing_negative_cache_ttl_seconds,
            max_entries=settings.routing_cache_max_entries,
        )
        ctx.routing_cache = cache
        ctx.routing_client = RoutingClient(
            base_url=settings.routing_base_url,
            timeout_seconds=settings.routing_timeout_seconds,
            provider=settings.routing_provider,
            profile=settings.routing_profile,
            cache=cache,
            max_retries=settings.routing_max_retries,
        )
    return ctx.routing_client
