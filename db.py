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
    # Schema migrations — idempotent ALTER TABLE statements
    # -----------------------------------------------------------------------

    # Add repo_url column to sessions (GitHub Integration — Ide 1)
    "ALTER TABLE sessions ADD COLUMN IF NOT EXISTS repo_url TEXT",

    # Ide 3 — pinned flag on notes (important notes shown prominently in session_read)
    "ALTER TABLE notes ADD COLUMN IF NOT EXISTS pinned BOOLEAN NOT NULL DEFAULT false",

    # Ide 4 — pinned + archived flags on sessions
    "ALTER TABLE sessions ADD COLUMN IF NOT EXISTS pinned  BOOLEAN NOT NULL DEFAULT false",
    "ALTER TABLE sessions ADD COLUMN IF NOT EXISTS archived BOOLEAN NOT NULL DEFAULT false",

    # Index for archived filter — most queries exclude archived sessions
    "CREATE INDEX IF NOT EXISTS idx_sessions_archived ON sessions (archived, updated_at DESC)",

    # Seed default vacuum config (do nothing if already set — ON CONFLICT DO NOTHING)
    """
    INSERT INTO config (key, value, description) VALUES
        ('vacuum_enabled',       'false', 'Enable scheduled auto-vacuum (true/false)'),
        ('vacuum_notes_days',    '90',    'Delete notes older than this many days'),
        ('vacuum_sessions_days', '180',   'Hard-delete archived sessions older than this many days')
    ON CONFLICT (key) DO NOTHING
    """,

    # -----------------------------------------------------------------------
    # Config table — key-value store for Claude behavior configuration (Ide 2)
    # -----------------------------------------------------------------------

    """
    CREATE TABLE IF NOT EXISTS config (
        key         TEXT        PRIMARY KEY,
        value       TEXT        NOT NULL,
        description TEXT        NOT NULL DEFAULT '',
        updated_at  TIMESTAMPTZ NOT NULL DEFAULT NOW()
    )
    """,

    # Trigger updated_at for config
    """
    DO $$ BEGIN
        IF NOT EXISTS (
            SELECT 1 FROM pg_trigger WHERE tgname = 'trg_config_updated_at'
        ) THEN
            CREATE TRIGGER trg_config_updated_at
                BEFORE UPDATE ON config
                FOR EACH ROW
                EXECUTE FUNCTION fn_touch_updated_at();
        END IF;
    END; $$
    """,

    # -----------------------------------------------------------------------
    # Auth — users, tokens, OAuth codes, session ownership
    # -----------------------------------------------------------------------

    # Users table
    """
    CREATE TABLE IF NOT EXISTS users (
        id            UUID        PRIMARY KEY DEFAULT gen_random_uuid(),
        username      TEXT        UNIQUE NOT NULL,
        email         TEXT        UNIQUE NOT NULL,
        password_hash TEXT        NOT NULL,
        role          TEXT        NOT NULL DEFAULT 'user',
        is_active     BOOLEAN     NOT NULL DEFAULT true,
        created_at    TIMESTAMPTZ NOT NULL DEFAULT NOW(),
        updated_at    TIMESTAMPTZ NOT NULL DEFAULT NOW()
    )
    """,

    # Trigger updated_at for users
    """
    DO $$ BEGIN
        IF NOT EXISTS (
            SELECT 1 FROM pg_trigger WHERE tgname = 'trg_users_updated_at'
        ) THEN
            CREATE TRIGGER trg_users_updated_at
                BEFORE UPDATE ON users
                FOR EACH ROW
                EXECUTE FUNCTION fn_touch_updated_at();
        END IF;
    END; $$
    """,

    # Personal Access Tokens — token_hash is SHA-256 of the raw token
    """
    CREATE TABLE IF NOT EXISTS user_tokens (
        id           UUID        PRIMARY KEY DEFAULT gen_random_uuid(),
        user_id      UUID        NOT NULL REFERENCES users(id) ON DELETE CASCADE,
        token_hash   TEXT        UNIQUE NOT NULL,
        name         TEXT        NOT NULL DEFAULT 'Default',
        last_used_at TIMESTAMPTZ,
        expires_at   TIMESTAMPTZ,
        revoked      BOOLEAN     NOT NULL DEFAULT false,
        created_at   TIMESTAMPTZ NOT NULL DEFAULT NOW()
    )
    """,

    # OAuth authorization codes — short-lived, single-use (PKCE S256)
    """
    CREATE TABLE IF NOT EXISTS oauth_codes (
        code            TEXT        PRIMARY KEY,
        user_id         UUID        NOT NULL REFERENCES users(id) ON DELETE CASCADE,
        client_id       TEXT        NOT NULL,
        redirect_uri    TEXT        NOT NULL,
        code_challenge  TEXT        NOT NULL,
        expires_at      TIMESTAMPTZ NOT NULL,
        used            BOOLEAN     NOT NULL DEFAULT false
    )
    """,

    # Session ownership — many-to-many (owner + collaborators)
    """
    CREATE TABLE IF NOT EXISTS session_users (
        session_id  TEXT        NOT NULL REFERENCES sessions(session_id) ON DELETE CASCADE,
        user_id     UUID        NOT NULL REFERENCES users(id) ON DELETE CASCADE,
        role        TEXT        NOT NULL DEFAULT 'owner',
        joined_at   TIMESTAMPTZ NOT NULL DEFAULT NOW(),
        PRIMARY KEY (session_id, user_id)
    )
    """,

    # owner_id shortcut on sessions (denormalized for fast lookup)
    "ALTER TABLE sessions ADD COLUMN IF NOT EXISTS owner_id UUID REFERENCES users(id)",

    # OAuth server-side sessions — keeps user logged in on the authorize page
    """
    CREATE TABLE IF NOT EXISTS oauth_sessions (
        token       TEXT        PRIMARY KEY,
        user_id     UUID        NOT NULL REFERENCES users(id) ON DELETE CASCADE,
        expires_at  TIMESTAMPTZ NOT NULL,
        created_at  TIMESTAMPTZ NOT NULL DEFAULT NOW()
    )
    """,

    # Per-user GitHub Personal Access Token (nullable, stored in plaintext)
    "ALTER TABLE users ADD COLUMN IF NOT EXISTS github_token TEXT",

    # Global skills — visible in user portal and auto-available in MCP
    "ALTER TABLE skills ADD COLUMN IF NOT EXISTS is_global BOOLEAN NOT NULL DEFAULT false",

    # Indexes
    "CREATE INDEX IF NOT EXISTS idx_oauth_sessions_user ON oauth_sessions (user_id)",
    "CREATE INDEX IF NOT EXISTS idx_users_email       ON users (email)",
    "CREATE INDEX IF NOT EXISTS idx_users_username    ON users (username)",
    "CREATE INDEX IF NOT EXISTS idx_user_tokens_user  ON user_tokens (user_id)",
    "CREATE INDEX IF NOT EXISTS idx_user_tokens_hash  ON user_tokens (token_hash)",
    "CREATE INDEX IF NOT EXISTS idx_oauth_codes_code  ON oauth_codes (code)",
    "CREATE INDEX IF NOT EXISTS idx_session_users_session ON session_users (session_id)",
    "CREATE INDEX IF NOT EXISTS idx_session_users_user    ON session_users (user_id)",
    "CREATE INDEX IF NOT EXISTS idx_sessions_owner        ON sessions (owner_id)",

    # -----------------------------------------------------------------------
    # Teams — shared workspaces with team-scoped sessions and tokens
    # -----------------------------------------------------------------------

    """
    CREATE TABLE IF NOT EXISTS teams (
        id         UUID  PRIMARY KEY DEFAULT gen_random_uuid(),
        name       TEXT  UNIQUE NOT NULL,
        created_by UUID  NOT NULL REFERENCES users(id),
        created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
    )
    """,

    """
    CREATE TABLE IF NOT EXISTS team_members (
        team_id    UUID  NOT NULL REFERENCES teams(id) ON DELETE CASCADE,
        user_id    UUID  NOT NULL REFERENCES users(id) ON DELETE CASCADE,
        role       TEXT  NOT NULL DEFAULT 'member',
        joined_at  TIMESTAMPTZ NOT NULL DEFAULT NOW(),
        PRIMARY KEY (team_id, user_id)
    )
    """,

    "DROP TABLE IF EXISTS team_tokens CASCADE",

    """
    CREATE TABLE IF NOT EXISTS team_requests (
        id           UUID  PRIMARY KEY DEFAULT gen_random_uuid(),
        requested_by UUID  NOT NULL REFERENCES users(id),
        team_name    TEXT  NOT NULL,
        reason       TEXT  NOT NULL DEFAULT '',
        status       TEXT  NOT NULL DEFAULT 'pending',
        reviewed_by  UUID  REFERENCES users(id),
        reviewed_at  TIMESTAMPTZ,
        created_at   TIMESTAMPTZ NOT NULL DEFAULT NOW()
    )
    """,

    """
    CREATE TABLE IF NOT EXISTS team_skills (
        team_id    UUID  NOT NULL REFERENCES teams(id) ON DELETE CASCADE,
        skill_slug TEXT  NOT NULL REFERENCES skills(slug) ON DELETE CASCADE,
        added_at   TIMESTAMPTZ NOT NULL DEFAULT NOW(),
        PRIMARY KEY (team_id, skill_slug)
    )
    """,

    # team_id on sessions — NULL = personal session, non-NULL = team session
    "ALTER TABLE sessions ADD COLUMN IF NOT EXISTS team_id UUID REFERENCES teams(id) ON DELETE CASCADE",

    "CREATE INDEX IF NOT EXISTS idx_team_members_team   ON team_members (team_id)",
    "CREATE INDEX IF NOT EXISTS idx_team_members_user   ON team_members (user_id)",
    "CREATE INDEX IF NOT EXISTS idx_team_requests_user  ON team_requests (requested_by)",
    "CREATE INDEX IF NOT EXISTS idx_team_requests_status ON team_requests (status)",
    "CREATE INDEX IF NOT EXISTS idx_sessions_team       ON sessions (team_id)",

    # Email blacklist — specific emails blocked from registering
    """
    CREATE TABLE IF NOT EXISTS email_blacklist (
        id         UUID        PRIMARY KEY DEFAULT gen_random_uuid(),
        email      TEXT        UNIQUE NOT NULL,
        reason     TEXT        NOT NULL DEFAULT '',
        created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
    )
    """,
    "CREATE INDEX IF NOT EXISTS idx_email_blacklist_email ON email_blacklist (email)",

    # Team invites — single-use links, expires after 7 days or when claimed
    """
    CREATE TABLE IF NOT EXISTS team_invites (
        token       TEXT        PRIMARY KEY,
        team_id     UUID        NOT NULL REFERENCES teams(id) ON DELETE CASCADE,
        created_by  UUID        NOT NULL REFERENCES users(id),
        used_by     UUID        REFERENCES users(id),
        used_at     TIMESTAMPTZ,
        expires_at  TIMESTAMPTZ NOT NULL,
        created_at  TIMESTAMPTZ NOT NULL DEFAULT NOW()
    )
    """,
    "CREATE INDEX IF NOT EXISTS idx_team_invites_team    ON team_invites (team_id)",
    "CREATE INDEX IF NOT EXISTS idx_team_invites_token   ON team_invites (token)",

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

    # token_prefix — store first 8 chars of raw token for display
    "ALTER TABLE user_tokens ADD COLUMN IF NOT EXISTS token_prefix TEXT",

    # 1 admin per user across all teams (DB-enforced)
    """
    CREATE UNIQUE INDEX IF NOT EXISTS idx_team_members_one_admin_per_user
      ON team_members (user_id)
      WHERE role = 'admin'
    """,

    # 1 pending request per user at a time
    """
    CREATE UNIQUE INDEX IF NOT EXISTS idx_team_requests_one_pending_per_user
      ON team_requests (requested_by)
      WHERE status = 'pending'
    """,

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
