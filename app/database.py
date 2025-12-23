"""MySQL database connection management.

Provides async connection pool for MySQL using aiomysql.

This module is intentionally small and generic: user-facing persistence is
handled by store classes that use this pool.
"""

from __future__ import annotations

import logging
from contextlib import asynccontextmanager
from typing import AsyncIterator, Optional
from urllib.parse import parse_qs, urlparse

import aiomysql

from .config import settings

logger = logging.getLogger(__name__)

# Global connection pool
_pool: Optional[aiomysql.Pool] = None


def _parse_mysql_dsn(dsn: str) -> dict:
    if not dsn:
        raise RuntimeError("DATABASE_URL is required when USE_DATABASE=true")

    parsed = urlparse(dsn)
    scheme = (parsed.scheme or "").lower()
    if not scheme.startswith("mysql"):
        raise RuntimeError(f"Unsupported DATABASE_URL scheme: {parsed.scheme!r} (expected mysql://...)")

    db_name = (parsed.path or "").lstrip("/")
    if not db_name:
        raise RuntimeError("DATABASE_URL must include database name, e.g. mysql://user:pass@host/db")

    qs = parse_qs(parsed.query or "")
    charset = (qs.get("charset", ["utf8mb4"])[0] or "utf8mb4").strip()

    return {
        "host": parsed.hostname or "localhost",
        "port": int(parsed.port or 3306),
        "user": parsed.username or "root",
        "password": parsed.password or "",
        "db": db_name,
        "autocommit": False,
        "charset": charset,
    }


async def init_db_pool() -> aiomysql.Pool:
    """Initialize the database connection pool."""
    global _pool
    
    if _pool is not None:
        return _pool
    
    logger.info("Initializing MySQL connection pool...")

    cfg = _parse_mysql_dsn(str(settings.database_url))
    _pool = await aiomysql.create_pool(
        minsize=settings.db_pool_min_size,
        maxsize=settings.db_pool_max_size,
        connect_timeout=10,
        **cfg,
    )
    
    logger.info(
        "Database pool initialized (min=%d, max=%d)",
        settings.db_pool_min_size,
        settings.db_pool_max_size,
    )
    
    return _pool


async def close_db_pool() -> None:
    """Close the database connection pool."""
    global _pool
    
    if _pool is not None:
        logger.info("Closing database connection pool...")
        await _pool.close()
        _pool = None
        logger.info("Database pool closed")


def get_pool() -> aiomysql.Pool:
    """Get the current connection pool.
    
    Raises:
        RuntimeError: If pool is not initialized.
    """
    if _pool is None:
        raise RuntimeError("Database pool not initialized. Call init_db_pool() first.")
    return _pool


@asynccontextmanager
async def get_connection() -> AsyncIterator[aiomysql.Connection]:
    """Get a database connection from the pool.
    
    Usage:
        async with get_connection() as conn:
            result = await conn.fetch("SELECT * FROM loads")
    """
    pool = get_pool()
    async with pool.acquire() as connection:
        yield connection


@asynccontextmanager
async def get_transaction() -> AsyncIterator[aiomysql.Connection]:
    """Get a database connection with a transaction.
    
    Usage:
        async with get_transaction() as conn:
            await conn.execute("INSERT INTO ...")
            await conn.execute("UPDATE ...")
            # Commits automatically on success, rolls back on exception
    """
    pool = get_pool()
    async with pool.acquire() as connection:
        await connection.begin()
        try:
            yield connection
        except Exception:
            await connection.rollback()
            raise
        else:
            await connection.commit()


async def check_database_health() -> dict:
    """Check database connectivity and return status."""
    try:
        async with get_connection() as conn:
            async with conn.cursor() as cur:
                await cur.execute("SELECT 1")
                row = await cur.fetchone()
                await cur.execute("SELECT VERSION()")
                vrow = await cur.fetchone()
            return {
                "status": "healthy",
                "connected": bool(row and row[0] == 1),
                "version": (vrow[0] if vrow else None),
            }
    except Exception as e:
        logger.error("Database health check failed: %s", e)
        return {
            "status": "unhealthy",
            "connected": False,
            "error": str(e),
        }
