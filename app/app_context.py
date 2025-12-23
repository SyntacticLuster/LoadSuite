from __future__ import annotations

import asyncio
from dataclasses import dataclass
from typing import TYPE_CHECKING, Optional

from .data import Dataset
from .ingestion.manager import IngestionManager
from .scoring import ScoringEngine
from .stores import AlertRulesStore, FilterPresetsStore, PreferencesStore, WatchlistStore
from .routecast_cache import RouteCastCache

if TYPE_CHECKING:  # pragma: no cover
    from .services.scoring_service import ScoringService
    from .services.routecast_client import RouteCastClient


@dataclass
class AppContext:
    """Holds live application state attached to app.state.ctx.

    This is the minimal DI seam to keep request handlers off module globals.
    """

    dataset: Dataset
    scoring_engine: ScoringEngine
    scoring_service: Optional["ScoringService"]
    routecast_client: Optional["RouteCastClient"]
    routecast_cache: Optional[RouteCastCache]

    ingestion_manager: Optional[IngestionManager]
    ingestion_task: asyncio.Task[None] | None

    preferences_store: PreferencesStore
    watchlist_store: WatchlistStore
    alert_rules_store: AlertRulesStore
    filter_presets_store: FilterPresetsStore
