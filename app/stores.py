"""In-memory stores for terminal workflow features.

Provides simple in-memory storage for:
- User preferences (API-level)
- Watchlist items
- Alert rules
- Filter presets

Data persists only for the lifetime of the server process.
For production, replace with database-backed implementations.
"""

from __future__ import annotations

import json
import os
from contextlib import contextmanager
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Dict, List, Optional
from uuid import uuid4

from .api_models import (
    AlertRuleModel,
    FilterPresetModel,
    PreferencesModel,
    WatchlistItemModel,
)


class PreferencesStore:
    """In-memory preferences storage."""
    
    def __init__(self):
        self._data: Dict[str, tuple[PreferencesModel, datetime]] = {}
        self._default = PreferencesModel()
    
    def get(self, user_id: str) -> tuple[PreferencesModel, Optional[datetime]]:
        """Get preferences for a user. Returns (prefs, updated_at)."""
        if user_id in self._data:
            return self._data[user_id]
        return (self._default, None)
    
    def set(self, user_id: str, prefs: PreferencesModel) -> datetime:
        """Set preferences for a user. Returns updated_at timestamp."""
        updated_at = datetime.now(timezone.utc)
        self._data[user_id] = (prefs, updated_at)
        return updated_at
    
    def delete(self, user_id: str) -> bool:
        """Delete preferences for a user."""
        if user_id in self._data:
            del self._data[user_id]
            return True
        return False


class WatchlistStore:
    """In-memory watchlist storage."""
    
    def __init__(self):
        self._data: Dict[str, List[WatchlistItemModel]] = {}
    
    def list(self, user_id: str) -> List[WatchlistItemModel]:
        """List all watchlist items for a user."""
        return self._data.get(user_id, [])
    
    def get(self, user_id: str, item_id: str) -> Optional[WatchlistItemModel]:
        """Get a specific watchlist item."""
        for item in self._data.get(user_id, []):
            if item.id == item_id:
                return item
        return None
    
    def create(
        self,
        user_id: str,
        item_type: str,
        load_id: Optional[str] = None,
        lane: Optional[str] = None,
        notes: Optional[str] = None,
    ) -> WatchlistItemModel:
        """Create a new watchlist item."""
        item = WatchlistItemModel(
            id=str(uuid4()),
            user_id=user_id,
            item_type=item_type,  # type: ignore
            load_id=load_id,
            lane=lane,
            notes=notes,
            created_at=datetime.now(timezone.utc),
        )
        if user_id not in self._data:
            self._data[user_id] = []
        self._data[user_id].append(item)
        return item
    
    def delete(self, user_id: str, item_id: str) -> bool:
        """Delete a watchlist item."""
        if user_id not in self._data:
            return False
        items = self._data[user_id]
        for i, item in enumerate(items):
            if item.id == item_id:
                items.pop(i)
                return True
        return False
    
    def has_load(self, user_id: str, load_id: str) -> bool:
        """Check if a load is in the user's watchlist."""
        for item in self._data.get(user_id, []):
            if item.load_id == load_id:
                return True
        return False


@contextmanager
def _locked_lockfile(lock_path: Path):
    """Cross-process lock using flock on a lockfile.

    Safe for Linux-based deployments. If flock isn't available, falls back to
    best-effort (still correct for single-process).
    """

    lock_path.parent.mkdir(parents=True, exist_ok=True)
    fh = open(lock_path, "a+", encoding="utf-8")
    try:
        try:
            import fcntl  # type: ignore

            fcntl.flock(fh.fileno(), fcntl.LOCK_EX)
        except Exception:
            # Best-effort if flock isn't available.
            pass
        yield
    finally:
        try:
            try:
                import fcntl  # type: ignore

                fcntl.flock(fh.fileno(), fcntl.LOCK_UN)
            except Exception:
                pass
        finally:
            fh.close()


class PersistentWatchlistStore(WatchlistStore):
    """File-backed watchlist storage.

    Why this exists: production often runs multiple workers/processes. The
    original in-memory WatchlistStore is per-process, so state "randomly"
    disappears depending on which worker handles the next request.

    This store uses a JSON file + a lock to share state across workers.
    """

    def __init__(self, path: Path):
        super().__init__()
        self._path = Path(path)
        self._lock_path = self._path.with_suffix(self._path.suffix + ".lock")
        self._path.parent.mkdir(parents=True, exist_ok=True)

    def _read_raw(self) -> Dict[str, List[dict]]:
        if not self._path.exists():
            return {}
        try:
            raw = json.loads(self._path.read_text(encoding="utf-8") or "{}")
        except Exception:
            return {}
        if not isinstance(raw, dict):
            return {}
        out: Dict[str, List[dict]] = {}
        for k, v in raw.items():
            if isinstance(k, str) and isinstance(v, list):
                out[k] = [x for x in v if isinstance(x, dict)]
        return out

    def _write_raw(self, raw: Dict[str, List[dict]]) -> None:
        tmp = self._path.with_suffix(self._path.suffix + ".tmp")
        tmp.write_text(json.dumps(raw, ensure_ascii=False), encoding="utf-8")
        os.replace(tmp, self._path)

    def _load_items(self, user_id: str) -> List[WatchlistItemModel]:
        raw = self._read_raw()
        items_raw = raw.get(user_id, [])
        items: List[WatchlistItemModel] = []
        for d in items_raw:
            try:
                items.append(WatchlistItemModel.model_validate(d))
            except Exception:
                continue
        return items

    def _save_items(self, user_id: str, items: List[WatchlistItemModel]) -> None:
        raw = self._read_raw()
        raw[user_id] = [i.model_dump(mode="json") for i in items]
        self._write_raw(raw)

    def list(self, user_id: str) -> List[WatchlistItemModel]:
        with _locked_lockfile(self._lock_path):
            return self._load_items(user_id)

    def get(self, user_id: str, item_id: str) -> Optional[WatchlistItemModel]:
        with _locked_lockfile(self._lock_path):
            for item in self._load_items(user_id):
                if item.id == item_id:
                    return item
        return None

    def create(
        self,
        user_id: str,
        item_type: str,
        load_id: Optional[str] = None,
        lane: Optional[str] = None,
        notes: Optional[str] = None,
    ) -> WatchlistItemModel:
        with _locked_lockfile(self._lock_path):
            items = self._load_items(user_id)

            # De-dupe load items by load_id (prevents accidental duplicates under latency/retries).
            if item_type == "load" and load_id:
                for existing in items:
                    if existing.load_id == load_id:
                        return existing

            item = WatchlistItemModel(
                id=str(uuid4()),
                user_id=user_id,
                item_type=item_type,  # type: ignore
                load_id=load_id,
                lane=lane,
                notes=notes,
                created_at=datetime.now(timezone.utc),
            )
            items.append(item)
            self._save_items(user_id, items)
            return item

    def delete(self, user_id: str, item_id: str) -> bool:
        with _locked_lockfile(self._lock_path):
            items = self._load_items(user_id)
            before = len(items)
            items = [i for i in items if i.id != item_id]
            if len(items) == before:
                return False
            self._save_items(user_id, items)
            return True

    def has_load(self, user_id: str, load_id: str) -> bool:
        with _locked_lockfile(self._lock_path):
            for item in self._load_items(user_id):
                if item.load_id == load_id:
                    return True
        return False


class AlertRulesStore:
    """In-memory alert rules storage."""
    
    def __init__(self):
        self._data: Dict[str, List[AlertRuleModel]] = {}
    
    def list(self, user_id: str) -> List[AlertRuleModel]:
        """List all alert rules for a user."""
        return self._data.get(user_id, [])
    
    def get(self, user_id: str, rule_id: str) -> Optional[AlertRuleModel]:
        """Get a specific alert rule."""
        for rule in self._data.get(user_id, []):
            if rule.id == rule_id:
                return rule
        return None
    
    def create(
        self,
        user_id: str,
        name: str,
        description: Optional[str] = None,
        conditions: Optional[list] = None,
        enabled: bool = True,
    ) -> AlertRuleModel:
        """Create a new alert rule."""
        rule = AlertRuleModel(
            id=str(uuid4()),
            user_id=user_id,
            name=name,
            description=description,
            conditions=conditions or [],
            enabled=enabled,
            created_at=datetime.now(timezone.utc),
            last_triggered=None,
        )
        if user_id not in self._data:
            self._data[user_id] = []
        self._data[user_id].append(rule)
        return rule
    
    def delete(self, user_id: str, rule_id: str) -> bool:
        """Delete an alert rule."""
        if user_id not in self._data:
            return False
        rules = self._data[user_id]
        for i, rule in enumerate(rules):
            if rule.id == rule_id:
                rules.pop(i)
                return True
        return False
    
    def update_enabled(self, user_id: str, rule_id: str, enabled: bool) -> bool:
        """Update the enabled state of a rule."""
        for i, rule in enumerate(self._data.get(user_id, [])):
            if rule.id == rule_id:
                self._data[user_id][i] = AlertRuleModel(
                    id=rule.id,
                    user_id=rule.user_id,
                    name=rule.name,
                    description=rule.description,
                    conditions=rule.conditions,
                    enabled=enabled,
                    created_at=rule.created_at,
                    last_triggered=rule.last_triggered,
                )
                return True
        return False

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
        """Update fields on an alert rule."""

        for i, rule in enumerate(self._data.get(user_id, [])):
            if rule.id != rule_id:
                continue

            updated = AlertRuleModel(
                id=rule.id,
                user_id=rule.user_id,
                name=rule.name if name is None else name,
                description=rule.description if description is None else description,
                conditions=rule.conditions if conditions is None else conditions,
                enabled=rule.enabled if enabled is None else enabled,
                created_at=rule.created_at,
                last_triggered=rule.last_triggered,
            )
            self._data[user_id][i] = updated
            return updated

        return None

    def mark_triggered(
        self,
        user_id: str,
        rule_id: str,
        *,
        now: datetime,
        min_interval: timedelta = timedelta(minutes=5),
    ) -> Optional[AlertRuleModel]:
        """Update last_triggered for a rule, throttled to avoid spam."""

        for i, rule in enumerate(self._data.get(user_id, [])):
            if rule.id != rule_id:
                continue

            if rule.last_triggered is not None and (now - rule.last_triggered) < min_interval:
                return rule

            updated = AlertRuleModel(
                id=rule.id,
                user_id=rule.user_id,
                name=rule.name,
                description=rule.description,
                conditions=rule.conditions,
                enabled=rule.enabled,
                created_at=rule.created_at,
                last_triggered=now,
            )
            self._data[user_id][i] = updated
            return updated

        return None


class FilterPresetsStore:
    """In-memory filter presets storage."""
    
    def __init__(self):
        self._data: Dict[str, List[FilterPresetModel]] = {}
    
    def list(self, user_id: str) -> List[FilterPresetModel]:
        """List all filter presets for a user."""
        return self._data.get(user_id, [])
    
    def get(self, user_id: str, preset_id: str) -> Optional[FilterPresetModel]:
        """Get a specific filter preset."""
        for preset in self._data.get(user_id, []):
            if preset.id == preset_id:
                return preset
        return None
    
    def create(
        self,
        user_id: str,
        name: str,
        filters: dict,
    ) -> FilterPresetModel:
        """Create a new filter preset."""
        preset = FilterPresetModel(
            id=str(uuid4()),
            user_id=user_id,
            name=name,
            filters=filters,
            created_at=datetime.now(timezone.utc),
        )
        if user_id not in self._data:
            self._data[user_id] = []
        self._data[user_id].append(preset)
        return preset
    
    def delete(self, user_id: str, preset_id: str) -> bool:
        """Delete a filter preset."""
        if user_id not in self._data:
            return False
        presets = self._data[user_id]
        for i, preset in enumerate(presets):
            if preset.id == preset_id:
                presets.pop(i)
                return True
        return False


