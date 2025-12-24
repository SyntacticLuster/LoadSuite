from __future__ import annotations

from datetime import timezone

from app.api_models import PreferencesModel
from app.stores import (
    PersistentAlertRulesStore,
    PersistentFilterPresetsStore,
    PersistentPreferencesStore,
)


def test_persistent_preferences_store_roundtrip(tmp_path):
    path = tmp_path / "prefs.json"
    store = PersistentPreferencesStore(path)
    prefs = PreferencesModel(min_rpm=2.5)
    updated_at = store.set("user-1", prefs)

    store2 = PersistentPreferencesStore(path)
    loaded, ts = store2.get("user-1")

    assert loaded.min_rpm == 2.5
    assert ts is not None
    assert ts.tzinfo == timezone.utc
    assert updated_at.tzinfo == timezone.utc


def test_persistent_alert_rules_store_roundtrip(tmp_path):
    path = tmp_path / "alerts.json"
    store = PersistentAlertRulesStore(path)
    rule = store.create("user-1", "Rule A", conditions=[{"field": "rpm", "operator": "gte", "value": 2}])

    store2 = PersistentAlertRulesStore(path)
    rules = store2.list("user-1")

    assert len(rules) == 1
    assert rules[0].id == rule.id
    assert rules[0].name == "Rule A"


def test_persistent_filter_presets_store_roundtrip(tmp_path):
    path = tmp_path / "presets.json"
    store = PersistentFilterPresetsStore(path)
    preset = store.create("user-1", "Preset A", filters={"equipment": "Dry Van"})

    store2 = PersistentFilterPresetsStore(path)
    presets = store2.list("user-1")

    assert len(presets) == 1
    assert presets[0].id == preset.id
    assert presets[0].name == "Preset A"
