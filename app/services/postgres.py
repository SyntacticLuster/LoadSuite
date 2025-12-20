"""PostgreSQL repository implementations.

Production-ready database-backed repositories for LoadSuite.
"""

from __future__ import annotations

import json
import logging
from datetime import datetime, timezone
from typing import Any, Dict, Iterable, List, Optional
from uuid import uuid4

import asyncpg

from ..database import get_connection, get_transaction
from ..models import Broker, Load, Location
from ..scoring.models import MarketContext, UserPreferences
from ..api_models import (
    AlertRuleModel,
    FilterPresetModel,
    PreferencesModel,
    WatchlistItemModel,
)
from .repositories import (
    LoadRepository,
    MarketDataRepository,
    PreferencesRepository,
)

logger = logging.getLogger(__name__)


# =============================================================================
# PostgreSQL Load Repository
# =============================================================================

class PostgresLoadRepository(LoadRepository):
    """PostgreSQL-backed load repository."""
    
    def _row_to_load(self, row: asyncpg.Record) -> Load:
        """Convert a database row to a Load model."""
        return Load(
            id=row["id"],
            origin=Location(city=row["origin_city"], state=row["origin_state"]),
            destination=Location(city=row["dest_city"], state=row["dest_state"]),
            pickup_start=row["pickup_start"],
            pickup_end=row["pickup_end"],
            delivery_start=row["delivery_start"],
            delivery_end=row["delivery_end"],
            equipment=row["equipment"],
            weight_lbs=row["weight_lbs"],
            hazmat=row["hazmat"],
            distance_miles=row["distance_miles"],
            deadhead_miles=row["deadhead_miles"],
            rate_total_usd=row["rate_total_usd"],
            rpm=row["rpm"],
            broker=Broker(name=row["broker_name"], rating=row["broker_rating"]),
            detention=row["detention"],
            multi_stop=row["multi_stop"],
            lane_history=row["lane_history"],
            commodity=row["commodity"] or "",
            posted_at=row["posted_at"],
            updated_at=row["updated_at"],
        )
    
    async def get_by_id(self, load_id: str) -> Optional[Load]:
        """Retrieve a single load by ID."""
        async with get_connection() as conn:
            row = await conn.fetchrow(
                "SELECT * FROM loads WHERE id = $1 AND deleted_at IS NULL",
                load_id
            )
            return self._row_to_load(row) if row else None
    
    # Sync wrapper for compatibility with existing interface
    def get_by_id_sync(self, load_id: str) -> Optional[Load]:
        """Sync version - raises error, use async version."""
        raise NotImplementedError("Use async get_by_id() method")
    
    async def get_all(self) -> List[Load]:
        """Retrieve all loads."""
        async with get_connection() as conn:
            rows = await conn.fetch(
                "SELECT * FROM loads WHERE deleted_at IS NULL ORDER BY posted_at DESC"
            )
            return [self._row_to_load(row) for row in rows]
    
    async def find(
        self,
        origin_state: Optional[str] = None,
        destination_state: Optional[str] = None,
        equipment: Optional[str] = None,
        min_rpm: Optional[float] = None,
        max_deadhead: Optional[float] = None,
        limit: int = 100,
    ) -> List[Load]:
        """Find loads matching criteria."""
        conditions = ["deleted_at IS NULL"]
        params: List[Any] = []
        param_idx = 1
        
        if origin_state:
            conditions.append(f"origin_state = ${param_idx}")
            params.append(origin_state)
            param_idx += 1
        
        if destination_state:
            conditions.append(f"dest_state = ${param_idx}")
            params.append(destination_state)
            param_idx += 1
        
        if equipment:
            conditions.append(f"equipment = ${param_idx}")
            params.append(equipment)
            param_idx += 1
        
        if min_rpm is not None:
            conditions.append(f"rpm >= ${param_idx}")
            params.append(min_rpm)
            param_idx += 1
        
        if max_deadhead is not None:
            conditions.append(f"deadhead_miles <= ${param_idx}")
            params.append(max_deadhead)
            param_idx += 1
        
        query = f"""
            SELECT * FROM loads
            WHERE {' AND '.join(conditions)}
            ORDER BY posted_at DESC
            LIMIT ${param_idx}
        """
        params.append(limit)
        
        async with get_connection() as conn:
            rows = await conn.fetch(query, *params)
            return [self._row_to_load(row) for row in rows]
    
    async def save(self, load: Load) -> None:
        """Save or update a load."""
        async with get_transaction() as conn:
            await conn.execute(
                """
                INSERT INTO loads (
                    id, origin_city, origin_state, dest_city, dest_state,
                    pickup_start, pickup_end, delivery_start, delivery_end,
                    equipment, weight_lbs, hazmat, distance_miles, deadhead_miles,
                    rate_total_usd, rpm, broker_name, broker_rating,
                    detention, multi_stop, lane_history, commodity, posted_at
                ) VALUES (
                    $1, $2, $3, $4, $5, $6, $7, $8, $9, $10,
                    $11, $12, $13, $14, $15, $16, $17, $18, $19, $20, $21, $22, $23
                )
                ON CONFLICT (id) DO UPDATE SET
                    origin_city = EXCLUDED.origin_city,
                    origin_state = EXCLUDED.origin_state,
                    dest_city = EXCLUDED.dest_city,
                    dest_state = EXCLUDED.dest_state,
                    pickup_start = EXCLUDED.pickup_start,
                    pickup_end = EXCLUDED.pickup_end,
                    delivery_start = EXCLUDED.delivery_start,
                    delivery_end = EXCLUDED.delivery_end,
                    equipment = EXCLUDED.equipment,
                    weight_lbs = EXCLUDED.weight_lbs,
                    hazmat = EXCLUDED.hazmat,
                    distance_miles = EXCLUDED.distance_miles,
                    deadhead_miles = EXCLUDED.deadhead_miles,
                    rate_total_usd = EXCLUDED.rate_total_usd,
                    rpm = EXCLUDED.rpm,
                    broker_name = EXCLUDED.broker_name,
                    broker_rating = EXCLUDED.broker_rating,
                    detention = EXCLUDED.detention,
                    multi_stop = EXCLUDED.multi_stop,
                    lane_history = EXCLUDED.lane_history,
                    commodity = EXCLUDED.commodity,
                    updated_at = NOW()
                """,
                load.id,
                load.origin.city, load.origin.state,
                load.destination.city, load.destination.state,
                load.pickup_start, load.pickup_end,
                load.delivery_start, load.delivery_end,
                load.equipment, load.weight_lbs, load.hazmat,
                load.distance_miles, load.deadhead_miles,
                load.rate_total_usd, load.rpm,
                load.broker.name, load.broker.rating,
                load.detention, load.multi_stop, load.lane_history,
                load.commodity, load.posted_at,
            )
    
    async def save_many(self, loads: Iterable[Load]) -> int:
        """Save multiple loads. Returns count saved."""
        count = 0
        async with get_transaction() as conn:
            for load in loads:
                await conn.execute(
                    """
                    INSERT INTO loads (
                        id, origin_city, origin_state, dest_city, dest_state,
                        pickup_start, pickup_end, delivery_start, delivery_end,
                        equipment, weight_lbs, hazmat, distance_miles, deadhead_miles,
                        rate_total_usd, rpm, broker_name, broker_rating,
                        detention, multi_stop, lane_history, commodity, posted_at
                    ) VALUES (
                        $1, $2, $3, $4, $5, $6, $7, $8, $9, $10,
                        $11, $12, $13, $14, $15, $16, $17, $18, $19, $20, $21, $22, $23
                    )
                    ON CONFLICT (id) DO UPDATE SET
                        updated_at = NOW()
                    """,
                    load.id,
                    load.origin.city, load.origin.state,
                    load.destination.city, load.destination.state,
                    load.pickup_start, load.pickup_end,
                    load.delivery_start, load.delivery_end,
                    load.equipment, load.weight_lbs, load.hazmat,
                    load.distance_miles, load.deadhead_miles,
                    load.rate_total_usd, load.rpm,
                    load.broker.name, load.broker.rating,
                    load.detention, load.multi_stop, load.lane_history,
                    load.commodity, load.posted_at,
                )
                count += 1
        return count
    
    async def delete(self, load_id: str) -> bool:
        """Soft delete a load. Returns True if found and deleted."""
        async with get_transaction() as conn:
            result = await conn.execute(
                "UPDATE loads SET deleted_at = NOW() WHERE id = $1 AND deleted_at IS NULL",
                load_id
            )
            return result == "UPDATE 1"
    
    async def count(self) -> int:
        """Return total number of active loads."""
        async with get_connection() as conn:
            return await conn.fetchval(
                "SELECT COUNT(*) FROM loads WHERE deleted_at IS NULL"
            )


# =============================================================================
# PostgreSQL Preferences Repository
# =============================================================================

class PostgresPreferencesRepository(PreferencesRepository):
    """PostgreSQL-backed preferences repository."""
    
    def _row_to_user_prefs(self, row: asyncpg.Record) -> UserPreferences:
        """Convert database row to UserPreferences."""
        return UserPreferences(
            equipment_types=tuple(row["equipment_types"] or ["Dry Van"]),
            max_deadhead_miles=row["max_deadhead_miles"] or 150.0,
            max_weight_lbs=row["max_weight_lbs"] or 45000,
            cost_per_mile=row["cost_per_mile"] or 1.75,
            preferred_lanes=tuple(row["preferred_lanes"] or []),
            home_base=row["home_base"],
            hazmat_endorsed=row["hazmat_endorsed"] or False,
            min_broker_rating=row["min_broker_rating"] or 3.0,
            greenlight_threshold=row["greenlight_threshold"] or 70.0,
        )
    
    async def get(self, user_id: str) -> Optional[UserPreferences]:
        """Get preferences for a user."""
        async with get_connection() as conn:
            row = await conn.fetchrow(
                "SELECT * FROM user_preferences WHERE user_id = $1",
                user_id
            )
            return self._row_to_user_prefs(row) if row else None
    
    async def get_default(self) -> UserPreferences:
        """Get default preferences."""
        return UserPreferences()
    
    async def save(self, user_id: str, preferences: UserPreferences) -> None:
        """Save preferences for a user."""
        async with get_transaction() as conn:
            # Ensure user exists
            await conn.execute(
                "INSERT INTO users (id) VALUES ($1) ON CONFLICT (id) DO NOTHING",
                user_id
            )
            
            await conn.execute(
                """
                INSERT INTO user_preferences (
                    user_id, equipment_types, max_deadhead_miles, max_weight_lbs,
                    cost_per_mile, preferred_lanes, home_base, hazmat_endorsed,
                    min_broker_rating, greenlight_threshold
                ) VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9, $10)
                ON CONFLICT (user_id) DO UPDATE SET
                    equipment_types = EXCLUDED.equipment_types,
                    max_deadhead_miles = EXCLUDED.max_deadhead_miles,
                    max_weight_lbs = EXCLUDED.max_weight_lbs,
                    cost_per_mile = EXCLUDED.cost_per_mile,
                    preferred_lanes = EXCLUDED.preferred_lanes,
                    home_base = EXCLUDED.home_base,
                    hazmat_endorsed = EXCLUDED.hazmat_endorsed,
                    min_broker_rating = EXCLUDED.min_broker_rating,
                    greenlight_threshold = EXCLUDED.greenlight_threshold,
                    updated_at = NOW()
                """,
                user_id,
                list(preferences.equipment_types),
                preferences.max_deadhead_miles,
                preferences.max_weight_lbs,
                preferences.cost_per_mile,
                list(preferences.preferred_lanes),
                preferences.home_base,
                preferences.hazmat_endorsed,
                preferences.min_broker_rating,
                preferences.greenlight_threshold,
            )
    
    async def delete(self, user_id: str) -> bool:
        """Delete preferences for a user."""
        async with get_transaction() as conn:
            result = await conn.execute(
                "DELETE FROM user_preferences WHERE user_id = $1",
                user_id
            )
            return result == "DELETE 1"


# =============================================================================
# PostgreSQL Watchlist Store
# =============================================================================

class PostgresWatchlistStore:
    """PostgreSQL-backed watchlist storage."""
    
    def _row_to_item(self, row: asyncpg.Record) -> WatchlistItemModel:
        """Convert database row to WatchlistItemModel."""
        return WatchlistItemModel(
            id=row["id"],
            user_id=row["user_id"],
            item_type=row["item_type"],
            load_id=row["load_id"],
            lane=row["lane"],
            notes=row["notes"],
            created_at=row["created_at"],
        )
    
    async def list(self, user_id: str) -> List[WatchlistItemModel]:
        """List all watchlist items for a user."""
        async with get_connection() as conn:
            rows = await conn.fetch(
                "SELECT * FROM watchlist_items WHERE user_id = $1 ORDER BY created_at DESC",
                user_id
            )
            return [self._row_to_item(row) for row in rows]
    
    async def get(self, user_id: str, item_id: str) -> Optional[WatchlistItemModel]:
        """Get a specific watchlist item."""
        async with get_connection() as conn:
            row = await conn.fetchrow(
                "SELECT * FROM watchlist_items WHERE id = $1 AND user_id = $2",
                item_id, user_id
            )
            return self._row_to_item(row) if row else None
    
    async def create(
        self,
        user_id: str,
        item_type: str,
        load_id: Optional[str] = None,
        lane: Optional[str] = None,
        notes: Optional[str] = None,
    ) -> WatchlistItemModel:
        """Create a new watchlist item."""
        item_id = str(uuid4())
        now = datetime.now(timezone.utc)
        
        async with get_transaction() as conn:
            # Ensure user exists
            await conn.execute(
                "INSERT INTO users (id) VALUES ($1) ON CONFLICT (id) DO NOTHING",
                user_id
            )
            
            await conn.execute(
                """
                INSERT INTO watchlist_items (id, user_id, item_type, load_id, lane, notes, created_at)
                VALUES ($1, $2, $3, $4, $5, $6, $7)
                """,
                item_id, user_id, item_type, load_id, lane, notes, now
            )
        
        return WatchlistItemModel(
            id=item_id,
            user_id=user_id,
            item_type=item_type,  # type: ignore
            load_id=load_id,
            lane=lane,
            notes=notes,
            created_at=now,
        )
    
    async def delete(self, user_id: str, item_id: str) -> bool:
        """Delete a watchlist item."""
        async with get_transaction() as conn:
            result = await conn.execute(
                "DELETE FROM watchlist_items WHERE id = $1 AND user_id = $2",
                item_id, user_id
            )
            return result == "DELETE 1"
    
    async def has_load(self, user_id: str, load_id: str) -> bool:
        """Check if a load is in the user's watchlist."""
        async with get_connection() as conn:
            result = await conn.fetchval(
                """
                SELECT EXISTS(
                    SELECT 1 FROM watchlist_items 
                    WHERE user_id = $1 AND load_id = $2
                )
                """,
                user_id, load_id
            )
            return result


# =============================================================================
# PostgreSQL Alert Rules Store
# =============================================================================

class PostgresAlertRulesStore:
    """PostgreSQL-backed alert rules storage."""
    
    def _row_to_rule(self, row: asyncpg.Record) -> AlertRuleModel:
        """Convert database row to AlertRuleModel."""
        return AlertRuleModel(
            id=row["id"],
            user_id=row["user_id"],
            name=row["name"],
            description=row["description"],
            conditions=row["conditions"] or [],
            enabled=row["enabled"],
            created_at=row["created_at"],
            last_triggered=row["last_triggered"],
        )
    
    async def list(self, user_id: str) -> List[AlertRuleModel]:
        """List all alert rules for a user."""
        async with get_connection() as conn:
            rows = await conn.fetch(
                "SELECT * FROM alert_rules WHERE user_id = $1 ORDER BY created_at DESC",
                user_id
            )
            return [self._row_to_rule(row) for row in rows]
    
    async def get(self, user_id: str, rule_id: str) -> Optional[AlertRuleModel]:
        """Get a specific alert rule."""
        async with get_connection() as conn:
            row = await conn.fetchrow(
                "SELECT * FROM alert_rules WHERE id = $1 AND user_id = $2",
                rule_id, user_id
            )
            return self._row_to_rule(row) if row else None
    
    async def create(
        self,
        user_id: str,
        name: str,
        description: Optional[str] = None,
        conditions: Optional[list] = None,
        enabled: bool = True,
    ) -> AlertRuleModel:
        """Create a new alert rule."""
        rule_id = str(uuid4())
        now = datetime.now(timezone.utc)
        conditions_json = conditions or []
        
        async with get_transaction() as conn:
            # Ensure user exists
            await conn.execute(
                "INSERT INTO users (id) VALUES ($1) ON CONFLICT (id) DO NOTHING",
                user_id
            )
            
            await conn.execute(
                """
                INSERT INTO alert_rules (id, user_id, name, description, conditions, enabled, created_at)
                VALUES ($1, $2, $3, $4, $5, $6, $7)
                """,
                rule_id, user_id, name, description,
                json.dumps(conditions_json), enabled, now
            )
        
        return AlertRuleModel(
            id=rule_id,
            user_id=user_id,
            name=name,
            description=description,
            conditions=conditions_json,
            enabled=enabled,
            created_at=now,
            last_triggered=None,
        )
    
    async def delete(self, user_id: str, rule_id: str) -> bool:
        """Delete an alert rule."""
        async with get_transaction() as conn:
            result = await conn.execute(
                "DELETE FROM alert_rules WHERE id = $1 AND user_id = $2",
                rule_id, user_id
            )
            return result == "DELETE 1"
    
    async def update_enabled(self, user_id: str, rule_id: str, enabled: bool) -> bool:
        """Update the enabled state of a rule."""
        async with get_transaction() as conn:
            result = await conn.execute(
                "UPDATE alert_rules SET enabled = $1 WHERE id = $2 AND user_id = $3",
                enabled, rule_id, user_id
            )
            return result == "UPDATE 1"


# =============================================================================
# PostgreSQL Filter Presets Store
# =============================================================================

class PostgresFilterPresetsStore:
    """PostgreSQL-backed filter presets storage."""
    
    def _row_to_preset(self, row: asyncpg.Record) -> FilterPresetModel:
        """Convert database row to FilterPresetModel."""
        return FilterPresetModel(
            id=row["id"],
            user_id=row["user_id"],
            name=row["name"],
            filters=row["filters"] or {},
            created_at=row["created_at"],
        )
    
    async def list(self, user_id: str) -> List[FilterPresetModel]:
        """List all filter presets for a user."""
        async with get_connection() as conn:
            rows = await conn.fetch(
                "SELECT * FROM filter_presets WHERE user_id = $1 ORDER BY created_at DESC",
                user_id
            )
            return [self._row_to_preset(row) for row in rows]
    
    async def get(self, user_id: str, preset_id: str) -> Optional[FilterPresetModel]:
        """Get a specific filter preset."""
        async with get_connection() as conn:
            row = await conn.fetchrow(
                "SELECT * FROM filter_presets WHERE id = $1 AND user_id = $2",
                preset_id, user_id
            )
            return self._row_to_preset(row) if row else None
    
    async def create(
        self,
        user_id: str,
        name: str,
        filters: dict,
    ) -> FilterPresetModel:
        """Create a new filter preset."""
        preset_id = str(uuid4())
        now = datetime.now(timezone.utc)
        
        async with get_transaction() as conn:
            # Ensure user exists
            await conn.execute(
                "INSERT INTO users (id) VALUES ($1) ON CONFLICT (id) DO NOTHING",
                user_id
            )
            
            await conn.execute(
                """
                INSERT INTO filter_presets (id, user_id, name, filters, created_at)
                VALUES ($1, $2, $3, $4, $5)
                """,
                preset_id, user_id, name, json.dumps(filters), now
            )
        
        return FilterPresetModel(
            id=preset_id,
            user_id=user_id,
            name=name,
            filters=filters,
            created_at=now,
        )
    
    async def delete(self, user_id: str, preset_id: str) -> bool:
        """Delete a filter preset."""
        async with get_transaction() as conn:
            result = await conn.execute(
                "DELETE FROM filter_presets WHERE id = $1 AND user_id = $2",
                preset_id, user_id
            )
            return result == "DELETE 1"


# =============================================================================
# PostgreSQL Preferences Store (API-level, matches stores.py interface)
# =============================================================================

class PostgresPreferencesStore:
    """PostgreSQL-backed preferences storage (API-level)."""
    
    def _row_to_model(self, row: asyncpg.Record) -> PreferencesModel:
        """Convert database row to PreferencesModel."""
        return PreferencesModel(
            equipment_types=row["equipment_types"],
            max_deadhead_miles=row["max_deadhead_miles"],
            max_weight_lbs=row["max_weight_lbs"],
            min_weight_lbs=row["min_weight_lbs"],
            cost_per_mile=row["cost_per_mile"],
            preferred_lanes=row["preferred_lanes"],
            home_base=row["home_base"],
            hazmat_endorsed=row["hazmat_endorsed"],
            min_broker_rating=row["min_broker_rating"],
            min_rpm=row["min_rpm"],
            greenlight_threshold=row["greenlight_threshold"],
        )
    
    async def get(self, user_id: str) -> tuple[PreferencesModel, Optional[datetime]]:
        """Get preferences for a user. Returns (prefs, updated_at)."""
        async with get_connection() as conn:
            row = await conn.fetchrow(
                "SELECT * FROM user_preferences WHERE user_id = $1",
                user_id
            )
            if row:
                return (self._row_to_model(row), row["updated_at"])
            return (PreferencesModel(), None)
    
    async def set(self, user_id: str, prefs: PreferencesModel) -> datetime:
        """Set preferences for a user. Returns updated_at timestamp."""
        now = datetime.now(timezone.utc)
        
        async with get_transaction() as conn:
            # Ensure user exists
            await conn.execute(
                "INSERT INTO users (id) VALUES ($1) ON CONFLICT (id) DO NOTHING",
                user_id
            )
            
            await conn.execute(
                """
                INSERT INTO user_preferences (
                    user_id, equipment_types, max_deadhead_miles, max_weight_lbs,
                    min_weight_lbs, cost_per_mile, preferred_lanes, home_base,
                    hazmat_endorsed, min_broker_rating, min_rpm, greenlight_threshold, updated_at
                ) VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9, $10, $11, $12, $13)
                ON CONFLICT (user_id) DO UPDATE SET
                    equipment_types = EXCLUDED.equipment_types,
                    max_deadhead_miles = EXCLUDED.max_deadhead_miles,
                    max_weight_lbs = EXCLUDED.max_weight_lbs,
                    min_weight_lbs = EXCLUDED.min_weight_lbs,
                    cost_per_mile = EXCLUDED.cost_per_mile,
                    preferred_lanes = EXCLUDED.preferred_lanes,
                    home_base = EXCLUDED.home_base,
                    hazmat_endorsed = EXCLUDED.hazmat_endorsed,
                    min_broker_rating = EXCLUDED.min_broker_rating,
                    min_rpm = EXCLUDED.min_rpm,
                    greenlight_threshold = EXCLUDED.greenlight_threshold,
                    updated_at = EXCLUDED.updated_at
                """,
                user_id,
                prefs.equipment_types,
                prefs.max_deadhead_miles,
                prefs.max_weight_lbs,
                prefs.min_weight_lbs,
                prefs.cost_per_mile,
                prefs.preferred_lanes,
                prefs.home_base,
                prefs.hazmat_endorsed,
                prefs.min_broker_rating,
                prefs.min_rpm,
                prefs.greenlight_threshold,
                now,
            )
        
        return now
    
    async def delete(self, user_id: str) -> bool:
        """Delete preferences for a user."""
        async with get_transaction() as conn:
            result = await conn.execute(
                "DELETE FROM user_preferences WHERE user_id = $1",
                user_id
            )
            return result == "DELETE 1"
