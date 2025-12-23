import os
import asyncio

import pytest


pytestmark = pytest.mark.skipif(
    not os.environ.get("MYSQL_TEST_DATABASE_URL"),
    reason="MYSQL_TEST_DATABASE_URL not set; skipping MySQL persistence tests",
)


def test_mysql_schema_bootstrap_and_preferences_roundtrip():
    # Minimal smoke test. Expects a reachable MySQL test DB.
    os.environ["DATABASE_URL"] = os.environ["MYSQL_TEST_DATABASE_URL"]

    async def _run():
        from app.database import close_db_pool, init_db_pool
        from app.mysql_stores import MySQLPreferencesStore

        await init_db_pool()

        # Apply schema using the same statements as scripts/init_db.py
        from pathlib import Path
        from scripts.init_db import _split_sql

        schema_path = Path(__file__).resolve().parents[1] / "scripts" / "schema_mysql.sql"
        statements = _split_sql(schema_path.read_text(encoding="utf-8"))

        from app.database import get_transaction

        async with get_transaction() as conn:
            async with conn.cursor() as cur:
                for stmt in statements:
                    await cur.execute(stmt)

        store = MySQLPreferencesStore()
        user_id = "u-test"
        prefs, updated_at = store.get(user_id)
        assert updated_at is None

        from app.api_models import PreferencesModel

        ts = store.set(user_id, PreferencesModel(min_rpm=2.5))
        assert ts is not None

        prefs2, updated_at2 = store.get(user_id)
        assert prefs2.min_rpm == 2.5
        assert updated_at2 is not None

        await close_db_pool()

    asyncio.run(_run())
