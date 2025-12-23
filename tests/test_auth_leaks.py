from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

from app.config import settings
from app.main import app


client = TestClient(app)


SENSITIVE_KEYS = {
    # Connector / ingestion config-ish fields we don't want leaking publicly.
    "spec",
    "path",
    "file_path",
    "dir_path",
    "connector_specs",
    # Common secret-ish fields
    "api_key",
    "client_secret",
    "password",
    "token",
    "authorization",
}


def _contains_sensitive_keys(obj) -> bool:
    """Best-effort recursive scan for sensitive-ish keys.

    This is intentionally conservative: it flags only on keys, not arbitrary string values.
    """

    if isinstance(obj, dict):
        for k, v in obj.items():
            if isinstance(k, str) and k.lower() in SENSITIVE_KEYS:
                return True
            if _contains_sensitive_keys(v):
                return True
        return False

    if isinstance(obj, list):
        return any(_contains_sensitive_keys(v) for v in obj)

    return False


@pytest.fixture()
def _restore_auth_settings():
    old_enabled = settings.auth_enabled
    old_key = settings.admin_api_key
    yield
    settings.auth_enabled = old_enabled
    settings.admin_api_key = old_key


def test_ingestion_sources_is_protected_when_auth_enabled(_restore_auth_settings) -> None:
    """Regression guard: connector source specs must not be public when auth is enabled."""

    settings.auth_enabled = True
    settings.admin_api_key = "secret"

    # If the endpoint ever gets removed/renamed, skip rather than failing.
    probe = client.get("/api/ingestion/sources")
    if probe.status_code == 404:
        pytest.skip("/api/ingestion/sources does not exist in this build")

    assert probe.status_code == 401

    ok = client.get("/api/ingestion/sources", headers={"Authorization": "Bearer secret"})
    assert ok.status_code == 200


@pytest.mark.parametrize(
    "path",
    [
        "/api/ingestion/status",
        "/api/meta",
    ],
)
def test_public_endpoints_do_not_leak_connector_metadata_when_auth_enabled(path: str, _restore_auth_settings) -> None:
    """If an endpoint is public under auth-enabled mode, it must stay non-sensitive.

    Today:
    - /api/meta is intentionally public and returns only aggregate info.
    - /api/ingestion/status is intentionally public and should not expose connector specs/paths/secrets.

    If either endpoint starts returning sensitive connector/config fields (e.g., `spec`, `path`, secrets),
    this test will fail and force you to either:
    - protect it with admin auth, OR
    - remove/redact the sensitive fields.
    """

    settings.auth_enabled = True
    settings.admin_api_key = "secret"

    resp = client.get(path)
    if resp.status_code == 404:
        pytest.skip(f"{path} does not exist in this build")

    # If the endpoint is already protected under auth-enabled mode, that's fine.
    if resp.status_code == 401:
        return

    assert resp.status_code == 200

    payload = resp.json()
    assert not _contains_sensitive_keys(payload), (
        f"{path} appears to include sensitive connector/config keys while remaining public. "
        "Either protect it (admin auth) or redact those fields."
    )
