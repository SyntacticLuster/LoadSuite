"""MySQL-backed stores for user workflow state.

Implements the same synchronous store APIs as app/stores.py, but persists data
in MySQL when Settings.use_database=true.

Storage strategy (minimal): store full model payloads as JSON in LONGTEXT, plus
indexed user_id and timestamp columns for basic querying.

Note: These store methods are synchronous because most API handlers are sync.
They execute async DB I/O by hopping into the running anyio loop from the
threadpool via anyio.from_thread.run.
"""

from __future__ import annotations

import json
from datetime import datetime, timezone
from typing import Optional
from uuid import uuid4

import anyio

from .api_models import AlertRuleModel, FilterPresetModel, PreferencesModel, WatchlistItemModel
from .database import get_connection, get_transaction


def _utc_now_naive() -> datetime:
    # MySQL DATETIME has no tz; store UTC naive.
    return datetime.now(timezone.utc).replace(tzinfo=None)


def _as_utc(dt: Optional[datetime]) -> Optional[datetime]:
    if dt is None:
        return None
    if dt.tzinfo is not None:
        return dt
    return dt.replace(tzinfo=timezone.utc)


class MySQLPreferencesStore:
    def __init__(self):
        self._default = PreferencesModel()

    async def _get(self, user_id: str) -> tuple[PreferencesModel, Optional[datetime]]:
        async with get_connection() as conn:
            async with conn.cursor() as cur:
                await cur.execute(
                    "SELECT payload_json, updated_at FROM user_preferences WHERE user_id=%s",
                    (user_id,),
                )
                row = await cur.fetchone()
                if not row:
                    return (self._default, None)
                payload, updated_at = row
                try:
                    prefs = PreferencesModel.model_validate(json.loads(payload))
                except Exception:
                    prefs = self._default
                return (prefs, _as_utc(updated_at))

    def get(self, user_id: str) -> tuple[PreferencesModel, Optional[datetime]]:
        return anyio.from_thread.run(self._get, user_id)

    async def _set(self, user_id: str, prefs: PreferencesModel) -> datetime:
        updated_at = _utc_now_naive()
        payload = json.dumps(prefs.model_dump(mode="json"), ensure_ascii=False)
        async with get_transaction() as conn:
            async with conn.cursor() as cur:
                await cur.execute(
                    """
                    INSERT INTO user_preferences (user_id, payload_json, updated_at)
                    VALUES (%s, %s, %s)
                    ON DUPLICATE KEY UPDATE payload_json=VALUES(payload_json), updated_at=VALUES(updated_at)
                    """,
                    (user_id, payload, updated_at),
                )
        return updated_at.replace(tzinfo=timezone.utc)

    def set(self, user_id: str, prefs: PreferencesModel) -> datetime:
        return anyio.from_thread.run(self._set, user_id, prefs)

    async def _delete(self, user_id: str) -> bool:
        async with get_transaction() as conn:
            async with conn.cursor() as cur:
                await cur.execute("DELETE FROM user_preferences WHERE user_id=%s", (user_id,))
                return cur.rowcount > 0

    def delete(self, user_id: str) -> bool:
        return anyio.from_thread.run(self._delete, user_id)


class MySQLWatchlistStore:
    async def _list(self, user_id: str) -> list[WatchlistItemModel]:
        async with get_connection() as conn:
            async with conn.cursor() as cur:
                await cur.execute(
                    "SELECT payload_json FROM watchlist_items WHERE user_id=%s ORDER BY created_at ASC",
                    (user_id,),
                )
                rows = await cur.fetchall()
        items: list[WatchlistItemModel] = []
        for (payload,) in rows or []:
            try:
                items.append(WatchlistItemModel.model_validate(json.loads(payload)))
            except Exception:
                continue
        return items

    def list(self, user_id: str) -> list[WatchlistItemModel]:
        return anyio.from_thread.run(self._list, user_id)

    async def _get(self, user_id: str, item_id: str) -> Optional[WatchlistItemModel]:
        async with get_connection() as conn:
            async with conn.cursor() as cur:
                await cur.execute(
                    "SELECT payload_json FROM watchlist_items WHERE user_id=%s AND id=%s",
                    (user_id, item_id),
                )
                row = await cur.fetchone()
        if not row:
            return None
        try:
            return WatchlistItemModel.model_validate(json.loads(row[0]))
        except Exception:
            return None

    def get(self, user_id: str, item_id: str) -> Optional[WatchlistItemModel]:
        return anyio.from_thread.run(self._get, user_id, item_id)

    async def _create(
        self,
        user_id: str,
        item_type: str,
        load_id: Optional[str] = None,
        lane: Optional[str] = None,
        notes: Optional[str] = None,
    ) -> WatchlistItemModel:
        created_at = _utc_now_naive()

        # De-dupe load items by load_id (matches PersistentWatchlistStore behavior).
        if item_type == "load" and load_id:
            async with get_connection() as conn:
                async with conn.cursor() as cur:
                    await cur.execute(
                        "SELECT payload_json FROM watchlist_items WHERE user_id=%s AND item_type='load' AND load_id=%s LIMIT 1",
                        (user_id, load_id),
                    )
                    row = await cur.fetchone()
            if row:
                try:
                    return WatchlistItemModel.model_validate(json.loads(row[0]))
                except Exception:
                    pass

        item = WatchlistItemModel(
            id=str(uuid4()),
            user_id=user_id,
            item_type=item_type,  # type: ignore
            load_id=load_id,
            lane=lane,
            notes=notes,
            created_at=created_at.replace(tzinfo=timezone.utc),
        )
        payload = json.dumps(item.model_dump(mode="json"), ensure_ascii=False)

        async with get_transaction() as conn:
            async with conn.cursor() as cur:
                await cur.execute(
                    """
                    INSERT INTO watchlist_items (id, user_id, item_type, load_id, lane, payload_json, created_at)
                    VALUES (%s, %s, %s, %s, %s, %s, %s)
                    """,
                    (item.id, user_id, item_type, load_id, lane, payload, created_at),
                )

        return item

    def create(
        self,
        user_id: str,
        item_type: str,
        load_id: Optional[str] = None,
        lane: Optional[str] = None,
        notes: Optional[str] = None,
    ) -> WatchlistItemModel:
        return anyio.from_thread.run(self._create, user_id, item_type, load_id, lane, notes)

    async def _delete(self, user_id: str, item_id: str) -> bool:
        async with get_transaction() as conn:
            async with conn.cursor() as cur:
                await cur.execute(
                    "DELETE FROM watchlist_items WHERE user_id=%s AND id=%s",
                    (user_id, item_id),
                )
                return cur.rowcount > 0

    def delete(self, user_id: str, item_id: str) -> bool:
        return anyio.from_thread.run(self._delete, user_id, item_id)

    async def _has_load(self, user_id: str, load_id: str) -> bool:
        async with get_connection() as conn:
            async with conn.cursor() as cur:
                await cur.execute(
                    "SELECT 1 FROM watchlist_items WHERE user_id=%s AND item_type='load' AND load_id=%s LIMIT 1",
                    (user_id, load_id),
                )
                row = await cur.fetchone()
        return bool(row)

    def has_load(self, user_id: str, load_id: str) -> bool:
        return anyio.from_thread.run(self._has_load, user_id, load_id)


class MySQLAlertRulesStore:
    async def _list(self, user_id: str) -> list[AlertRuleModel]:
        async with get_connection() as conn:
            async with conn.cursor() as cur:
                await cur.execute(
                    "SELECT payload_json FROM alert_rules WHERE user_id=%s ORDER BY created_at ASC",
                    (user_id,),
                )
                rows = await cur.fetchall()
        out: list[AlertRuleModel] = []
        for (payload,) in rows or []:
            try:
                out.append(AlertRuleModel.model_validate(json.loads(payload)))
            except Exception:
                continue
        return out

    def list(self, user_id: str) -> list[AlertRuleModel]:
        return anyio.from_thread.run(self._list, user_id)

    async def _get(self, user_id: str, rule_id: str) -> Optional[AlertRuleModel]:
        async with get_connection() as conn:
            async with conn.cursor() as cur:
                await cur.execute(
                    "SELECT payload_json FROM alert_rules WHERE user_id=%s AND id=%s",
                    (user_id, rule_id),
                )
                row = await cur.fetchone()
        if not row:
            return None
        try:
            return AlertRuleModel.model_validate(json.loads(row[0]))
        except Exception:
            return None

    def get(self, user_id: str, rule_id: str) -> Optional[AlertRuleModel]:
        return anyio.from_thread.run(self._get, user_id, rule_id)

    async def _create(
        self,
        user_id: str,
        name: str,
        description: Optional[str] = None,
        conditions: Optional[list] = None,
        enabled: bool = True,
    ) -> AlertRuleModel:
        now = _utc_now_naive()
        rule = AlertRuleModel(
            id=str(uuid4()),
            user_id=user_id,
            name=name,
            description=description,
            conditions=conditions or [],
            enabled=enabled,
            created_at=now.replace(tzinfo=timezone.utc),
            last_triggered=None,
        )
        payload = json.dumps(rule.model_dump(mode="json"), ensure_ascii=False)
        async with get_transaction() as conn:
            async with conn.cursor() as cur:
                await cur.execute(
                    """
                    INSERT INTO alert_rules (id, user_id, payload_json, created_at, updated_at)
                    VALUES (%s, %s, %s, %s, %s)
                    """,
                    (rule.id, user_id, payload, now, now),
                )
        return rule

    def create(
        self,
        user_id: str,
        name: str,
        description: Optional[str] = None,
        conditions: Optional[list] = None,
        enabled: bool = True,
    ) -> AlertRuleModel:
        return anyio.from_thread.run(self._create, user_id, name, description, conditions, enabled)

    async def _delete(self, user_id: str, rule_id: str) -> bool:
        async with get_transaction() as conn:
            async with conn.cursor() as cur:
                await cur.execute("DELETE FROM alert_rules WHERE user_id=%s AND id=%s", (user_id, rule_id))
                return cur.rowcount > 0

    def delete(self, user_id: str, rule_id: str) -> bool:
        return anyio.from_thread.run(self._delete, user_id, rule_id)

    async def _update_enabled(self, user_id: str, rule_id: str, enabled: bool) -> bool:
        existing = await self._get(user_id, rule_id)
        if existing is None:
            return False
        updated = AlertRuleModel(
            id=existing.id,
            user_id=existing.user_id,
            name=existing.name,
            description=existing.description,
            conditions=existing.conditions,
            enabled=enabled,
            created_at=existing.created_at,
            last_triggered=existing.last_triggered,
        )
        payload = json.dumps(updated.model_dump(mode="json"), ensure_ascii=False)
        now = _utc_now_naive()
        async with get_transaction() as conn:
            async with conn.cursor() as cur:
                await cur.execute(
                    "UPDATE alert_rules SET payload_json=%s, updated_at=%s WHERE user_id=%s AND id=%s",
                    (payload, now, user_id, rule_id),
                )
                return cur.rowcount > 0

    def update_enabled(self, user_id: str, rule_id: str, enabled: bool) -> bool:
        return anyio.from_thread.run(self._update_enabled, user_id, rule_id, enabled)

    async def _update(
        self,
        user_id: str,
        rule_id: str,
        *,
        name: Optional[str] = None,
        description: Optional[str] = None,
        conditions: Optional[list] = None,
        enabled: Optional[bool] = None,
    ) -> Optional[AlertRuleModel]:
        existing = await self._get(user_id, rule_id)
        if existing is None:
            return None

        updated = AlertRuleModel(
            id=existing.id,
            user_id=existing.user_id,
            name=existing.name if name is None else name,
            description=existing.description if description is None else description,
            conditions=existing.conditions if conditions is None else conditions,
            enabled=existing.enabled if enabled is None else enabled,
            created_at=existing.created_at,
            last_triggered=existing.last_triggered,
        )
        payload = json.dumps(updated.model_dump(mode="json"), ensure_ascii=False)
        now = _utc_now_naive()
        async with get_transaction() as conn:
            async with conn.cursor() as cur:
                await cur.execute(
                    "UPDATE alert_rules SET payload_json=%s, updated_at=%s WHERE user_id=%s AND id=%s",
                    (payload, now, user_id, rule_id),
                )
                if cur.rowcount <= 0:
                    return None
        return updated

    def update(
        self,
        user_id: str,
        rule_id: str,
        *,
        name: Optional[str] = None,
        description: Optional[str] = None,
        conditions: Optional[list] = None,
        enabled: Optional[bool] = None,
    ) -> Optional[AlertRuleModel]:
        return anyio.from_thread.run(self._update, user_id, rule_id, name=name, description=description, conditions=conditions, enabled=enabled)

    async def _mark_triggered(
        self,
        user_id: str,
        rule_id: str,
        *,
        now: datetime,
        min_interval,
    ) -> Optional[AlertRuleModel]:
        existing = await self._get(user_id, rule_id)
        if existing is None:
            return None

        if existing.last_triggered is not None and (now - existing.last_triggered) < min_interval:
            return existing

        updated = AlertRuleModel(
            id=existing.id,
            user_id=existing.user_id,
            name=existing.name,
            description=existing.description,
            conditions=existing.conditions,
            enabled=existing.enabled,
            created_at=existing.created_at,
            last_triggered=now,
        )
        payload = json.dumps(updated.model_dump(mode="json"), ensure_ascii=False)
        write_now = _utc_now_naive()
        async with get_transaction() as conn:
            async with conn.cursor() as cur:
                await cur.execute(
                    "UPDATE alert_rules SET payload_json=%s, updated_at=%s WHERE user_id=%s AND id=%s",
                    (payload, write_now, user_id, rule_id),
                )
                if cur.rowcount <= 0:
                    return None
        return updated

    def mark_triggered(self, user_id: str, rule_id: str, *, now, min_interval):
        return anyio.from_thread.run(self._mark_triggered, user_id, rule_id, now=now, min_interval=min_interval)


class MySQLFilterPresetsStore:
    async def _list(self, user_id: str) -> list[FilterPresetModel]:
        async with get_connection() as conn:
            async with conn.cursor() as cur:
                await cur.execute(
                    "SELECT payload_json FROM filter_presets WHERE user_id=%s ORDER BY created_at ASC",
                    (user_id,),
                )
                rows = await cur.fetchall()
        out: list[FilterPresetModel] = []
        for (payload,) in rows or []:
            try:
                out.append(FilterPresetModel.model_validate(json.loads(payload)))
            except Exception:
                continue
        return out

    def list(self, user_id: str) -> list[FilterPresetModel]:
        return anyio.from_thread.run(self._list, user_id)

    async def _get(self, user_id: str, preset_id: str) -> Optional[FilterPresetModel]:
        async with get_connection() as conn:
            async with conn.cursor() as cur:
                await cur.execute(
                    "SELECT payload_json FROM filter_presets WHERE user_id=%s AND id=%s",
                    (user_id, preset_id),
                )
                row = await cur.fetchone()
        if not row:
            return None
        try:
            return FilterPresetModel.model_validate(json.loads(row[0]))
        except Exception:
            return None

    def get(self, user_id: str, preset_id: str) -> Optional[FilterPresetModel]:
        return anyio.from_thread.run(self._get, user_id, preset_id)

    async def _create(self, user_id: str, name: str, filters: dict) -> FilterPresetModel:
        now = _utc_now_naive()
        preset = FilterPresetModel(
            id=str(uuid4()),
            user_id=user_id,
            name=name,
            filters=filters,
            created_at=now.replace(tzinfo=timezone.utc),
        )
        payload = json.dumps(preset.model_dump(mode="json"), ensure_ascii=False)
        async with get_transaction() as conn:
            async with conn.cursor() as cur:
                await cur.execute(
                    """
                    INSERT INTO filter_presets (id, user_id, payload_json, created_at)
                    VALUES (%s, %s, %s, %s)
                    """,
                    (preset.id, user_id, payload, now),
                )
        return preset

    def create(self, user_id: str, name: str, filters: dict) -> FilterPresetModel:
        return anyio.from_thread.run(self._create, user_id, name, filters)

    async def _delete(self, user_id: str, preset_id: str) -> bool:
        async with get_transaction() as conn:
            async with conn.cursor() as cur:
                await cur.execute(
                    "DELETE FROM filter_presets WHERE user_id=%s AND id=%s",
                    (user_id, preset_id),
                )
                return cur.rowcount > 0

    def delete(self, user_id: str, preset_id: str) -> bool:
        return anyio.from_thread.run(self._delete, user_id, preset_id)
