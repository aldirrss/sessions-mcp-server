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

# DDL dipisah per statement — asyncpg.execute() lebih reliable per blok
# GENERATED ALWAYS AS tidak bisa pakai to_tsvector('english',...) karena
# to_tsvector dengan text config dianggap STABLE bukan IMMUTABLE oleh PG.
# Solusi: pakai trigger BEFORE INSERT OR UPDATE untuk mengisi search_vec.

_DDL_STEPS = [
    # 1. Extension
    "CREATE EXTENSION IF NOT EXISTS pg_trgm",

    # 2. Tabel sessions — search_vec diisi oleh trigger, bukan GENERATED
    """
    CREATE TABLE IF NOT EXISTS sessions (
        session_id  TEXT        PRIMARY KEY,
        title       TEXT        NOT NULL,
        context     TEXT        NOT NULL,
        source      TEXT        NOT NULL DEFAULT 'unknown',
        tags        TEXT[]      NOT NULL DEFAULT '{}',
        search_vec  TSVECTOR,
        created_at  TIMESTAMPTZ NOT NULL DEFAULT NOW(),
        updated_at  TIMESTAMPTZ NOT NULL DEFAULT NOW()
    )
    """,

    # 3. Tabel notes
    """
    CREATE TABLE IF NOT EXISTS notes (
        id          BIGSERIAL   PRIMARY KEY,
        session_id  TEXT        NOT NULL
                        REFERENCES sessions(session_id) ON DELETE CASCADE,
        content     TEXT        NOT NULL,
        source      TEXT        NOT NULL DEFAULT 'unknown',
        created_at  TIMESTAMPTZ NOT NULL DEFAULT NOW()
    )
    """,

    # 4. Indexes
    "CREATE INDEX IF NOT EXISTS idx_sessions_search  ON sessions USING GIN (search_vec)",
    "CREATE INDEX IF NOT EXISTS idx_sessions_tags    ON sessions USING GIN (tags)",
    "CREATE INDEX IF NOT EXISTS idx_sessions_updated ON sessions (updated_at DESC)",
    "CREATE INDEX IF NOT EXISTS idx_sessions_title_trgm ON sessions USING GIN (title gin_trgm_ops)",
    "CREATE INDEX IF NOT EXISTS idx_notes_session    ON notes (session_id)",
    "CREATE INDEX IF NOT EXISTS idx_notes_created    ON notes (session_id, created_at ASC)",

    # 5. Fungsi: isi search_vec dari title + context + tags
    """
    CREATE OR REPLACE FUNCTION fn_sessions_search_vec()
    RETURNS TRIGGER LANGUAGE plpgsql AS $$
    BEGIN
        NEW.search_vec := to_tsvector('english',
            coalesce(NEW.title,   '') || ' ' ||
            coalesce(NEW.context, '') || ' ' ||
            array_to_string(NEW.tags, ' ')
        );
        RETURN NEW;
    END;
    $$
    """,

    # 6. Fungsi: auto-bump updated_at
    """
    CREATE OR REPLACE FUNCTION fn_touch_updated_at()
    RETURNS TRIGGER LANGUAGE plpgsql AS $$
    BEGIN
        NEW.updated_at = NOW();
        RETURN NEW;
    END;
    $$
    """,

    # 7. Trigger search_vec — BEFORE INSERT OR UPDATE OF title/context/tags
    """
    DO $$ BEGIN
        IF NOT EXISTS (
            SELECT 1 FROM pg_trigger WHERE tgname = 'trg_sessions_search_vec'
        ) THEN
            CREATE TRIGGER trg_sessions_search_vec
                BEFORE INSERT OR UPDATE OF title, context, tags ON sessions
                FOR EACH ROW
                EXECUTE FUNCTION fn_sessions_search_vec();
        END IF;
    END; $$
    """,

    # 8. Trigger updated_at — BEFORE UPDATE
    """
    DO $$ BEGIN
        IF NOT EXISTS (
            SELECT 1 FROM pg_trigger WHERE tgname = 'trg_sessions_updated_at'
        ) THEN
            CREATE TRIGGER trg_sessions_updated_at
                BEFORE UPDATE ON sessions
                FOR EACH ROW
                EXECUTE FUNCTION fn_touch_updated_at();
        END IF;
    END; $$
    """,

    # -----------------------------------------------------------------------
    # Skills library
    # -----------------------------------------------------------------------

    # 9. Tabel skills
    """
    CREATE TABLE IF NOT EXISTS skills (
        slug        TEXT        PRIMARY KEY,
        name        TEXT        NOT NULL,
        summary     TEXT        NOT NULL DEFAULT '',
        content     TEXT        NOT NULL,
        source      TEXT        NOT NULL DEFAULT 'manual',
        category    TEXT,
        tags        TEXT[]      NOT NULL DEFAULT '{}',
        search_vec  TSVECTOR,
        created_at  TIMESTAMPTZ NOT NULL DEFAULT NOW(),
        updated_at  TIMESTAMPTZ NOT NULL DEFAULT NOW()
    )
    """,

    # 10. Tabel skill_versions — history konten sebelum diubah
    """
    CREATE TABLE IF NOT EXISTS skill_versions (
        id          BIGSERIAL   PRIMARY KEY,
        slug        TEXT        NOT NULL,
        content     TEXT        NOT NULL,
        changed_at  TIMESTAMPTZ NOT NULL DEFAULT NOW()
    )
    """,

    # 11. Tabel session_skills — junction many-to-many
    """
    CREATE TABLE IF NOT EXISTS session_skills (
        session_id  TEXT        NOT NULL
                        REFERENCES sessions(session_id) ON DELETE CASCADE,
        skill_slug  TEXT        NOT NULL
                        REFERENCES skills(slug) ON DELETE CASCADE,
        used_at     TIMESTAMPTZ NOT NULL DEFAULT NOW(),
        PRIMARY KEY (session_id, skill_slug)
    )
    """,

    # 12. Indexes untuk skills
    "CREATE INDEX IF NOT EXISTS idx_skills_search   ON skills USING GIN (search_vec)",
    "CREATE INDEX IF NOT EXISTS idx_skills_tags     ON skills USING GIN (tags)",
    "CREATE INDEX IF NOT EXISTS idx_skills_category ON skills (category)",
    "CREATE INDEX IF NOT EXISTS idx_skills_updated  ON skills (updated_at DESC)",
    "CREATE INDEX IF NOT EXISTS idx_skill_versions_slug ON skill_versions (slug, changed_at DESC)",
    "CREATE INDEX IF NOT EXISTS idx_session_skills_session ON session_skills (session_id, used_at DESC)",
    "CREATE INDEX IF NOT EXISTS idx_session_skills_slug    ON session_skills (skill_slug, used_at DESC)",

    # 13. Fungsi: isi search_vec untuk skills dari name + summary + content + tags
    """
    CREATE OR REPLACE FUNCTION fn_skills_search_vec()
    RETURNS TRIGGER LANGUAGE plpgsql AS $$
    BEGIN
        NEW.search_vec := to_tsvector('english',
            coalesce(NEW.name,    '') || ' ' ||
            coalesce(NEW.summary, '') || ' ' ||
            coalesce(NEW.content, '') || ' ' ||
            array_to_string(NEW.tags, ' ')
        );
        RETURN NEW;
    END;
    $$
    """,

    # 14. Trigger search_vec untuk skills
    """
    DO $$ BEGIN
        IF NOT EXISTS (
            SELECT 1 FROM pg_trigger WHERE tgname = 'trg_skills_search_vec'
        ) THEN
            CREATE TRIGGER trg_skills_search_vec
                BEFORE INSERT OR UPDATE OF name, summary, content, tags ON skills
                FOR EACH ROW
                EXECUTE FUNCTION fn_skills_search_vec();
        END IF;
    END; $$
    """,

    # 15. Trigger updated_at untuk skills
    """
    DO $$ BEGIN
        IF NOT EXISTS (
            SELECT 1 FROM pg_trigger WHERE tgname = 'trg_skills_updated_at'
        ) THEN
            CREATE TRIGGER trg_skills_updated_at
                BEFORE UPDATE ON skills
                FOR EACH ROW
                EXECUTE FUNCTION fn_touch_updated_at();
        END IF;
    END; $$
    """,
]


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
    """Create all tables, indexes, functions, and triggers. Safe to call every startup."""
    pool = await get_pool()
    async with pool.acquire() as conn:
        async with conn.transaction():
            for sql in _DDL_STEPS:
                await conn.execute(sql)
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
