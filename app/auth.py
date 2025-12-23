from __future__ import annotations

import secrets
from typing import Optional

from fastapi import Depends, HTTPException, Request

from .config import settings


def _extract_api_key(request: Request) -> Optional[str]:
    # Prefer standard Authorization header.
    auth = request.headers.get("authorization")
    if auth:
        parts = auth.split(None, 1)
        if len(parts) == 2 and parts[0].lower() == "bearer":
            return parts[1].strip() or None

    # Allow simple API key header.
    api_key = request.headers.get("x-api-key")
    if api_key:
        return api_key.strip() or None

    return None


def require_admin_api_key(request: Request) -> None:
    """Minimal API-key auth gate.

    Enable with env vars:
    - AUTH_ENABLED=true
    - ADMIN_API_KEY=your-secret

    If AUTH_ENABLED=false, this is a no-op.

    If AUTH_ENABLED=true, requires either:
    - Authorization: Bearer <ADMIN_API_KEY>
    - X-API-Key: <ADMIN_API_KEY>

    Returns 401 on missing/invalid.
    """

    if not bool(settings.auth_enabled):
        return

    expected = str(settings.admin_api_key or "")
    provided = _extract_api_key(request) or ""

    if not expected or not secrets.compare_digest(provided, expected):
        raise HTTPException(status_code=401, detail="Unauthorized")


def admin_auth() -> Depends:
    """Dependency wrapper for readability in route signatures."""

    return Depends(require_admin_api_key)
