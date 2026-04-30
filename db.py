"""
db.py — Async PostgreSQL connection pool and schema management.

Uses asyncpg for high-performance async queries.
Schema is auto-initialized on first startup (idempotent DDL).
"""

import logging
from contextlib import asynccontextmanager
from typing import Optional

import asyncpg

import config

_logger = logging.getLogger("lm-mcp-ai.db")
_pool: Optional[asyncpg.Pool] = None

# ---------------------------------------------------------------------------
# DDL — idempotent, safe to run on every startup
# ---------------------------------------------------------------------------

_SCHEMA_SQL = """
CREATE EXTENSION IF NOT EXISTS pg_trgm;

-- Sessions: main context store
CREATE TABLE IF NOT EXISTS sessions (
    session_id  TEXT        PRIMARY KEY,
    title       TEXT        NOT NULL,
    context     TEXT        NOT NULL,
    source      TEXT        NOT NULL DEFAULT 'unknown',
    tags        TEXT[]      NOT NULL DEFAULT '{}',
    search_vec  TSVECTOR    GENERATED ALWAYS AS (
                    to_tsvector('english',
                        coalesce(title,   '') || ' ' ||
                        coalesce(context, '') || ' ' ||
                        array_to_string(tags, ' ')
                    )
                ) STORED,
    created_at  TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at  TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

-- Notes: timestamped progress/decision log per session
CREATE TABLE IF NOT EXISTS notes (
    id          BIGSERIAL   PRIMARY KEY,
    session_id  TEXT        NOT NULL
                    REFERENCES sessions(session_id) ON DELETE CASCADE,
    content     TEXT        NOT NULL,
    source      TEXT        NOT NULL DEFAULT 'unknown',
    created_at  TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

-- Indexes
CREATE INDEX IF NOT EXISTS idx_sessions_search  ON sessions USING GIN (search_vec);
CREATE INDEX IF NOT EXISTS idx_sessions_tags    ON sessions USING GIN (tags);
CREATE INDEX IF NOT EXISTS idx_sessions_updated ON sessions (updated_at DESC);
CREATE INDEX IF NOT EXISTS idx_notes_session    ON notes (session_id);
CREATE INDEX IF NOT EXISTS idx_notes_created    ON notes (session_id, created_at ASC);

-- Trigram index for ILIKE fallback search
CREATE INDEX IF NOT EXISTS idx_sessions_title_trgm ON sessions USING GIN (title gin_trgm_ops);

-- Auto-bump updated_at on any UPDATE to sessions row
CREATE OR REPLACE FUNCTION fn_touch_updated_at()
RETURNS TRIGGER LANGUAGE plpgsql AS $$
BEGIN
    NEW.updated_at = NOW();
    RETURN NEW;
END;
$$;

DO $$ BEGIN
    IF NOT EXISTS (
        SELECT 1 FROM pg_trigger
        WHERE tgname = 'trg_sessions_updated_at'
    ) THEN
        CREATE TRIGGER trg_sessions_updated_at
            BEFORE UPDATE ON sessions
            FOR EACH ROW
            EXECUTE FUNCTION fn_touch_updated_at();
    END IF;
END; $$;
"""


# ---------------------------------------------------------------------------
# Pool lifecycle
# ---------------------------------------------------------------------------

async def get_pool() -> asyncpg.Pool:
    """Return the shared connection pool, creating it on first call."""
    global _pool
    if _pool is None:
        _pool = await asyncpg.create_pool(
            dsn=config.DATABASE_URL,
            min_size=1,
            max_size=5,
            command_timeout=30,
        )
        _logger.info("PostgreSQL pool created (min=1 max=5)")
    return _pool


async def close_pool() -> None:
    global _pool
    if _pool is not None:
        await _pool.close()
        _pool = None
        _logger.info("PostgreSQL pool closed")


async def init_schema() -> None:
    """Create all tables and indexes if they don't exist. Safe to call every startup."""
    pool = await get_pool()
    async with pool.acquire() as conn:
        async with conn.transaction():
            await conn.execute(_SCHEMA_SQL)
    _logger.info("Database schema ready")


# ---------------------------------------------------------------------------
# Lifespan context manager — used by FastMCP
# ---------------------------------------------------------------------------

@asynccontextmanager
async def lifespan(_server):
    """FastMCP lifespan: init DB on startup, close pool on shutdown."""
    await init_schema()
    _logger.info("Session store (PostgreSQL) ready")
    try:
        yield
    finally:
        await close_pool()
