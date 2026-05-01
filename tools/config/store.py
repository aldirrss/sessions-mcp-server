"""
PostgreSQL-backed key-value config store.

Keys are global (not per-session). Use descriptive prefixes like:
  claude_*  — Claude behavior instructions loaded at conversation start
  vacuum_*  — Auto-vacuum settings (future Ide 4)
  github_*  — GitHub integration defaults
"""

import db


async def read_config(key: str) -> dict | None:
    """Return a config entry or None if not found."""
    pool = await db.get_pool()
    async with pool.acquire() as conn:
        row = await conn.fetchrow("SELECT * FROM config WHERE key = $1", key)
    if row is None:
        return None
    return {
        "key": row["key"],
        "value": row["value"],
        "description": row["description"],
        "updated_at": row["updated_at"].isoformat(),
    }


async def write_config(key: str, value: str, description: str = "") -> dict:
    """Upsert a config entry. Returns the saved entry."""
    pool = await db.get_pool()
    async with pool.acquire() as conn:
        row = await conn.fetchrow(
            """
            INSERT INTO config (key, value, description)
            VALUES ($1, $2, $3)
            ON CONFLICT (key) DO UPDATE
                SET value = EXCLUDED.value,
                    description = CASE
                        WHEN EXCLUDED.description = '' THEN config.description
                        ELSE EXCLUDED.description
                    END
            RETURNING *
            """,
            key,
            value,
            description,
        )
    return {
        "key": row["key"],
        "value": row["value"],
        "description": row["description"],
        "updated_at": row["updated_at"].isoformat(),
    }


async def delete_config(key: str) -> bool:
    """Delete a config entry. Returns True if deleted."""
    pool = await db.get_pool()
    async with pool.acquire() as conn:
        result = await conn.execute("DELETE FROM config WHERE key = $1", key)
    return result == "DELETE 1"


async def list_config(prefix: str | None = None) -> list[dict]:
    """List all config entries, optionally filtered by key prefix."""
    pool = await db.get_pool()
    async with pool.acquire() as conn:
        if prefix:
            rows = await conn.fetch(
                "SELECT * FROM config WHERE key LIKE $1 ORDER BY key",
                f"{prefix}%",
            )
        else:
            rows = await conn.fetch("SELECT * FROM config ORDER BY key")
    return [
        {
            "key": r["key"],
            "value": r["value"],
            "description": r["description"],
            "updated_at": r["updated_at"].isoformat(),
        }
        for r in rows
    ]
