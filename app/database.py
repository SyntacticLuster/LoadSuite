"""PostgreSQL database connection management.

Provides async connection pool for PostgreSQL using asyncpg.
"""

from __future__ import annotations

import logging
from contextlib import asynccontextmanager
from typing import AsyncIterator, Optional

import asyncpg

from .config import settings

logger = logging.getLogger(__name__)

# Global connection pool
_pool: Optional[asyncpg.Pool] = None


async def init_db_pool() -> asyncpg.Pool:
    """Initialize the database connection pool."""
    global _pool
    
    if _pool is not None:
        return _pool
    
    logger.info("Initializing database connection pool...")
    
    _pool = await asyncpg.create_pool(
        str(settings.database_url),
        min_size=settings.db_pool_min_size,
        max_size=settings.db_pool_max_size,
        command_timeout=60,
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


def get_pool() -> asyncpg.Pool:
    """Get the current connection pool.
    
    Raises:
        RuntimeError: If pool is not initialized.
    """
    if _pool is None:
        raise RuntimeError("Database pool not initialized. Call init_db_pool() first.")
    return _pool


@asynccontextmanager
async def get_connection() -> AsyncIterator[asyncpg.Connection]:
    """Get a database connection from the pool.
    
    Usage:
        async with get_connection() as conn:
            result = await conn.fetch("SELECT * FROM loads")
    """
    pool = get_pool()
    async with pool.acquire() as connection:
        yield connection


@asynccontextmanager
async def get_transaction() -> AsyncIterator[asyncpg.Connection]:
    """Get a database connection with a transaction.
    
    Usage:
        async with get_transaction() as conn:
            await conn.execute("INSERT INTO ...")
            await conn.execute("UPDATE ...")
            # Commits automatically on success, rolls back on exception
    """
    pool = get_pool()
    async with pool.acquire() as connection:
        async with connection.transaction():
            yield connection


async def check_database_health() -> dict:
    """Check database connectivity and return status."""
    try:
        async with get_connection() as conn:
            result = await conn.fetchval("SELECT 1")
            version = await conn.fetchval("SELECT version()")
            return {
                "status": "healthy",
                "connected": result == 1,
                "version": version,
            }
    except Exception as e:
        logger.error("Database health check failed: %s", e)
        return {
            "status": "unhealthy",
            "connected": False,
            "error": str(e),
        }
