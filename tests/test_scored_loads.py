"""Integration tests for the scored loads and terminal workflow API endpoints.

Verifies:
- Scored loads endpoint returns expected shape
- Score data includes factors and reasons
- Preferences, watchlist, and alerts endpoints work
- No breaking changes to existing endpoints
"""

from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

from app.main import app


client = TestClient(app)


class TestScoredLoadsEndpoint:
    """Tests for /api/loads/scored endpoint."""

    def test_scored_loads_returns_expected_shape(self):
        """Verify scored loads endpoint returns loads with scores."""
        response = client.get("/api/loads/scored")
        assert response.status_code == 200
        
        data = response.json()
        assert "total" in data
        assert "loads" in data
        assert isinstance(data["loads"], list)
        
        if data["total"] > 0:
            first = data["loads"][0]
            # Verify ScoredLoadModel structure
            assert "load" in first
            assert "score" in first
            assert "top_reasons" in first
            assert "factors" in first
            assert "confidence" in first
            assert "greenlight" in first
            
            # Verify score is in valid range
            assert 0 <= first["score"] <= 100
            assert 0 <= first["confidence"] <= 1
            assert isinstance(first["greenlight"], bool)
            
            # Verify load structure preserved
            load = first["load"]
            assert "id" in load
            assert "origin" in load
            assert "destination" in load
            assert "rate_total_usd" in load

    def test_scored_loads_with_limit(self):
        """Verify limit parameter works."""
        response = client.get("/api/loads/scored", params={"limit": 5})
        assert response.status_code == 200
        data = response.json()
        assert len(data["loads"]) <= 5

    def test_scored_loads_with_filters(self):
        """Verify filters work with scored endpoint."""
        response = client.get("/api/loads/scored", params={"equipment": "Dry Van"})
        assert response.status_code == 200
        data = response.json()
        for item in data["loads"]:
            assert item["load"]["equipment"] == "Dry Van"

    def test_scored_loads_greenlight_respects_preferences(self):
        """GreenLight should only apply when user criteria are met."""
        user_id = "test-greenlight-criteria"
        response = client.put(
            "/api/preferences",
            params={"user_id": user_id},
            json={"min_rpm": 10.0},
        )
        assert response.status_code == 200

        response = client.get("/api/loads/scored", params={"user_id": user_id, "limit": 50})
        assert response.status_code == 200
        data = response.json()
        assert data["loads"]
        assert all(not item["greenlight"] for item in data["loads"])

    def test_individual_load_score(self):
        """Verify individual load score endpoint."""
        # First get a load ID
        loads_response = client.get("/api/loads")
        assert loads_response.status_code == 200
        loads = loads_response.json()["loads"]
        assert len(loads) > 0
        
        load_id = loads[0]["id"]
        
        # Get score for that load
        response = client.get(f"/api/loads/{load_id}/score")
        assert response.status_code == 200
        
        data = response.json()
        assert data["load"]["id"] == load_id
        assert "score" in data
        assert "top_reasons" in data
        assert "factors" in data

    def test_individual_load_score_not_found(self):
        """Verify 404 for non-existent load."""
        response = client.get("/api/loads/nonexistent-load-id/score")
        assert response.status_code == 404


class TestPreferencesEndpoint:
    """Tests for /api/preferences endpoints."""

    def test_get_preferences_default(self):
        """Verify default preferences returned."""
        response = client.get("/api/preferences")
        assert response.status_code == 200
        
        data = response.json()
        assert "user_id" in data
        assert "preferences" in data

    def test_set_and_get_preferences(self):
        """Verify preferences can be set and retrieved."""
        prefs = {
            "min_rpm": 2.50,
            "max_deadhead_miles": 150,
            "equipment_types": ["Dry Van", "Reefer"],
            "detention": True,
            "hazmat": False,
            "multi_stop": True,
        }
        
        # Set preferences
        response = client.put("/api/preferences", json=prefs)
        assert response.status_code == 200
        
        # Get preferences
        response = client.get("/api/preferences")
        assert response.status_code == 200
        data = response.json()
        assert data["preferences"]["min_rpm"] == 2.50
        assert data["preferences"]["max_deadhead_miles"] == 150
        assert data["preferences"]["detention"] is True
        assert data["preferences"]["hazmat"] is False
        assert data["preferences"]["multi_stop"] is True


class TestWatchlistEndpoint:
    """Tests for /api/watchlist endpoints."""

    def test_list_watchlist_empty(self):
        """Verify empty watchlist returned for new user."""
        response = client.get("/api/watchlist", params={"user_id": "test-watchlist-user"})
        assert response.status_code == 200
        data = response.json()
        assert data["items"] == []
        assert data["total"] == 0

    def test_create_and_list_watchlist_item(self):
        """Verify watchlist items can be created and listed."""
        user_id = "test-watchlist-create"
        
        # Create item
        response = client.post(
            "/api/watchlist",
            params={"user_id": user_id},
            json={"item_type": "load", "load_id": "TEST-LOAD-123"},
        )
        assert response.status_code == 200
        item = response.json()
        assert item["load_id"] == "TEST-LOAD-123"
        assert "id" in item
        
        # List items
        response = client.get("/api/watchlist", params={"user_id": user_id})
        assert response.status_code == 200
        data = response.json()
        assert data["total"] >= 1

    def test_delete_watchlist_item(self):
        """Verify watchlist items can be deleted."""
        user_id = "test-watchlist-delete"
        
        # Create item
        response = client.post(
            "/api/watchlist",
            params={"user_id": user_id},
            json={"item_type": "load", "load_id": "DELETE-ME"},
        )
        item_id = response.json()["id"]
        
        # Delete item
        response = client.delete(f"/api/watchlist/{item_id}", params={"user_id": user_id})
        assert response.status_code == 200
        assert response.json()["ok"] is True


class TestAlertRulesEndpoint:
    """Tests for /api/alerts endpoints."""

    def test_list_alerts_empty(self):
        """Verify empty alerts list for new user."""
        response = client.get("/api/alerts", params={"user_id": "test-alerts-user"})
        assert response.status_code == 200
        data = response.json()
        assert data["rules"] == []

    def test_create_alert_rule(self):
        """Verify alert rules can be created."""
        user_id = "test-alerts-create"
        
        response = client.post(
            "/api/alerts",
            params={"user_id": user_id},
            json={
                "name": "High RPM Alert",
                "description": "Alert when RPM > $3.00",
                "conditions": [{"field": "rpm", "operator": "gte", "value": 3.0}],
            },
        )
        assert response.status_code == 200
        rule = response.json()
        assert rule["name"] == "High RPM Alert"
        assert "id" in rule

    def test_update_alert_rule_enabled(self):
        """Verify alert rules can be updated (enabled flag)."""
        user_id = "test-alerts-update"

        create = client.post(
            "/api/alerts",
            params={"user_id": user_id},
            json={
                "name": "Toggle Me",
                "description": "flip enabled",
                "conditions": [{"field": "rpm", "operator": "gte", "value": 0.0}],
                "enabled": True,
            },
        )
        assert create.status_code == 200
        rule_id = create.json()["id"]

        update = client.put(
            f"/api/alerts/{rule_id}",
            params={"user_id": user_id},
            json={"enabled": False},
        )
        assert update.status_code == 200
        updated = update.json()
        assert updated["enabled"] is False

    def test_triggered_alerts_endpoint(self):
        """Verify /api/alerts/triggered returns evaluations with match counts."""
        user_id = "test-alerts-triggered"

        create = client.post(
            "/api/alerts",
            params={"user_id": user_id},
            json={
                "name": "Always Matches",
                "description": "rpm >= 0 should match synthetic loads",
                "conditions": [{"field": "rpm", "operator": "gte", "value": 0.0}],
                "enabled": True,
            },
        )
        assert create.status_code == 200
        rule_id = create.json()["id"]

        res = client.get("/api/alerts/triggered", params={"user_id": user_id})
        assert res.status_code == 200
        payload = res.json()
        assert "triggered" in payload
        item = next((t for t in payload["triggered"] if t["rule_id"] == rule_id), None)
        assert item is not None
        assert item["matches_count"] >= 0


class TestFilterPresetsEndpoint:
    """Tests for /api/presets endpoints."""

    def test_create_and_list_preset(self):
        """Verify filter presets work."""
        user_id = "test-presets-user"
        
        # Create preset
        response = client.post(
            "/api/presets",
            params={"user_id": user_id},
            json={
                "name": "My Dry Van Search",
                "filters": {"equipment": "Dry Van", "rpm_min": "2.5"},
            },
        )
        assert response.status_code == 200
        preset = response.json()
        assert preset["name"] == "My Dry Van Search"
        
        # List presets
        response = client.get("/api/presets", params={"user_id": user_id})
        assert response.status_code == 200
        data = response.json()
        assert data["total"] >= 1


class TestExistingEndpointsNotBroken:
    """Verify existing endpoints still work."""

    def test_meta_endpoint(self):
        """Verify /api/meta works."""
        response = client.get("/api/meta")
        assert response.status_code == 200
        data = response.json()
        assert "source" in data
        assert "count" in data

    def test_loads_endpoint(self):
        """Verify /api/loads works."""
        response = client.get("/api/loads")
        assert response.status_code == 200
        data = response.json()
        assert "total" in data
        assert "loads" in data

    def test_load_detail_endpoint(self):
        """Verify /api/loads/{id} works."""
        loads_response = client.get("/api/loads")
        load_id = loads_response.json()["loads"][0]["id"]
        
        response = client.get(f"/api/loads/{load_id}")
        assert response.status_code == 200
        assert response.json()["id"] == load_id

    def test_refresh_endpoint(self):
        """Verify /api/refresh is gated by config and works when enabled."""
        # Default: refresh is disabled and should return 403
        response = client.post("/api/refresh", json={"count": 50})
        assert response.status_code == 403
        assert response.json().get("ok") is False

        # Enable refresh dynamically and verify it succeeds (deterministic with seed).
        # Use a fresh TestClient context so the mutated dataset does not leak into
        # other tests (each context runs the lifespan handler).
        from app.config import settings

        settings.allow_synth_refresh = True
        try:
            from fastapi.testclient import TestClient

            # Ensure the lifespan handler will rebuild the AppContext (avoid using
            # any previously mutated ctx).
            app.state.ctx = None
            with TestClient(app) as c2:
                response2 = c2.post("/api/refresh", json={"count": 50, "seed": 12345})
                assert response2.status_code == 200
                assert response2.json()["ok"] is True
        finally:
            settings.allow_synth_refresh = False

    def test_news_endpoint(self):
        """Verify /api/news works."""
        response = client.get("/api/news")
        assert response.status_code == 200
        assert "items" in response.json()
