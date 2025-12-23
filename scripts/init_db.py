"""Initialize the MySQL schema for LoadSuite.

Usage:
  DATABASE_URL=mysql://user:pass@host:3306/orbiizny_loadsuite \
    poetry run python scripts/init_db.py

By default, applies scripts/schema_mysql.sql.
"""

from __future__ import annotations

import os
from pathlib import Path

import aiomysql

from app.database import _parse_mysql_dsn


def _split_sql(sql_text: str) -> list[str]:
    # Minimal splitter: safe for this repo's schema files.
    statements: list[str] = []
    buf: list[str] = []
    for line in sql_text.splitlines():
        stripped = line.strip()
        if not stripped or stripped.startswith("--"):
            continue
        buf.append(line)
        if stripped.endswith(";"):
            stmt = "\n".join(buf).strip()
            if stmt.endswith(";"):
                stmt = stmt[:-1]
            if stmt:
                statements.append(stmt)
            buf = []
    tail = "\n".join(buf).strip()
    if tail:
        statements.append(tail)
    return statements


async def _main() -> None:
    dsn = os.environ.get("DATABASE_URL", "")
    if not dsn:
        raise SystemExit("DATABASE_URL is required")

    cfg = _parse_mysql_dsn(dsn)

    schema_path = Path(__file__).with_name("schema_mysql.sql")
    sql_text = schema_path.read_text(encoding="utf-8")
    statements = _split_sql(sql_text)

    conn = await aiomysql.connect(**cfg)
    try:
        async with conn.cursor() as cur:
            for stmt in statements:
                await cur.execute(stmt)
        await conn.commit()
    finally:
        conn.close()
        await conn.wait_closed()

    print(f"Applied {len(statements)} statements from {schema_path}")


if __name__ == "__main__":
    import asyncio

    asyncio.run(_main())
