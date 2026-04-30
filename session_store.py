"""
session_store.py — PostgreSQL-backed context store for Claude session continuity.

All public functions are async and use the shared asyncpg pool from db.py.
Sessions persist across Claude Web <-> CLI/VSCode boundaries via a shared
PostgreSQL database on the VPS.
"""

import re
import logging
from typing import Optional

import asyncpg

import db

_logger = logging.getLogger("lm-mcp-ai.session")

_SESSION_ID_RE = re.compile(r'^[a-zA-Z0-9_\-]{1,100}$')


# ---------------------------------------------------------------------------
# Validation
# ---------------------------------------------------------------------------

def validate_session_id(session_id: str) -> str:
    if not _SESSION_ID_RE.match(session_id):
        raise ValueError(
            f"Invalid session_id '{session_id}'. "
            "Use only letters, digits, hyphens, underscores (max 100 chars)."
        )
    return session_id


# ---------------------------------------------------------------------------
# Row → dict helpers
# ---------------------------------------------------------------------------

def _session_row(row: asyncpg.Record, notes: list[dict] | None = None) -> dict:
    return {
        "session_id": row["session_id"],
        "title":      row["title"],
        "context":    row["context"],
        "source":     row["source"],
        "tags":       list(row["tags"]),
        "notes":      notes or [],
        "created_at": row["created_at"].isoformat(),
        "updated_at": row["updated_at"].isoformat(),
    }


def _note_row(row: asyncpg.Record) -> dict:
    return {
        "id":        row["id"],
        "content":   row["content"],
        "source":    row["source"],
        "timestamp": row["created_at"].isoformat(),
    }


# ---------------------------------------------------------------------------
# CRUD
# ---------------------------------------------------------------------------

async def read_session(session_id: str) -> Optional[dict]:
    """
    Return full session with all notes, or None if not found.
    """
    pool = await db.get_pool()
    async with pool.acquire() as conn:
        row = await conn.fetchrow(
            "SELECT * FROM sessions WHERE session_id = $1",
            session_id,
        )
        if row is None:
            return None

        note_rows = await conn.fetch(
            "SELECT * FROM notes WHERE session_id = $1 ORDER BY created_at ASC",
            session_id,
        )
        return _session_row(row, [_note_row(n) for n in note_rows])


async def write_session(
    session_id: str,
    title: str,
    context: str,
    source: str = "unknown",
    tags: list[str] | None = None,
) -> dict:
    """
    Create a new session or overwrite title/context/source/tags of an existing one.
    Notes are preserved on update. updated_at is auto-bumped by DB trigger.
    """
    pool = await db.get_pool()
    tags_val = tags or []

    async with pool.acquire() as conn:
        row = await conn.fetchrow(
            """
            INSERT INTO sessions (session_id, title, context, source, tags)
            VALUES ($1, $2, $3, $4, $5)
            ON CONFLICT (session_id) DO UPDATE
                SET title   = EXCLUDED.title,
                    context = EXCLUDED.context,
                    source  = EXCLUDED.source,
                    tags    = EXCLUDED.tags
            RETURNING *
            """,
            session_id, title, context, source, tags_val,
        )
        # Fetch notes separately so the returned dict is complete
        note_rows = await conn.fetch(
            "SELECT * FROM notes WHERE session_id = $1 ORDER BY created_at ASC",
            session_id,
        )
        return _session_row(row, [_note_row(n) for n in note_rows])


async def append_note(session_id: str, content: str, source: str = "unknown") -> dict:
    """
    Append a timestamped note to an existing session.
    Runs in a single transaction: verify session exists → insert note → touch updated_at.
    Raises FileNotFoundError if the session does not exist.
    """
    pool = await db.get_pool()

    async with pool.acquire() as conn:
        async with conn.transaction():
            exists = await conn.fetchval(
                "SELECT 1 FROM sessions WHERE session_id = $1",
                session_id,
            )
            if not exists:
                raise FileNotFoundError(
                    f"Session '{session_id}' not found. "
                    "Create it first with session_write."
                )

            await conn.execute(
                "INSERT INTO notes (session_id, content, source) VALUES ($1, $2, $3)",
                session_id, content, source,
            )
            # Manually touch updated_at so the trigger fires and the value is current
            await conn.execute(
                "UPDATE sessions SET updated_at = NOW() WHERE session_id = $1",
                session_id,
            )

    return await read_session(session_id)


async def list_sessions(tag: str | None = None) -> list[dict]:
    """
    List all sessions ordered by most-recently updated.
    Pass tag to filter by a specific tag value (exact match, case-sensitive).
    """
    pool = await db.get_pool()

    base_query = """
        SELECT
            s.session_id,
            s.title,
            s.source,
            s.tags,
            s.updated_at,
            COUNT(n.id) AS notes_count
        FROM sessions s
        LEFT JOIN notes n ON n.session_id = s.session_id
        {where}
        GROUP BY s.session_id
        ORDER BY s.updated_at DESC
    """

    async with pool.acquire() as conn:
        if tag:
            rows = await conn.fetch(
                base_query.format(where="WHERE $1 = ANY(s.tags)"),
                tag,
            )
        else:
            rows = await conn.fetch(base_query.format(where=""))

    return [
        {
            "session_id":  r["session_id"],
            "title":       r["title"],
            "source":      r["source"],
            "tags":        list(r["tags"]),
            "notes_count": r["notes_count"],
            "updated_at":  r["updated_at"].isoformat(),
        }
        for r in rows
    ]


async def delete_session(session_id: str) -> bool:
    """
    Delete a session and all its notes (CASCADE).
    Returns True if a row was deleted, False if not found.
    """
    pool = await db.get_pool()
    async with pool.acquire() as conn:
        result = await conn.execute(
            "DELETE FROM sessions WHERE session_id = $1",
            session_id,
        )
    return result == "DELETE 1"


async def search_sessions(query: str) -> list[dict]:
    """
    Search sessions using PostgreSQL full-text search (tsvector) with ILIKE fallback.
    Returns sessions ranked by relevance, most relevant first.
    Also searches note content via a subquery.
    """
    pool = await db.get_pool()

    async with pool.acquire() as conn:
        rows = await conn.fetch(
            """
            SELECT DISTINCT ON (s.session_id)
                s.session_id,
                s.title,
                s.updated_at,
                LEFT(s.context, 200) AS snippet,
                COALESCE(
                    ts_rank(s.search_vec, plainto_tsquery('english', $1)),
                    0
                ) AS rank
            FROM sessions s
            LEFT JOIN notes n ON n.session_id = s.session_id
            WHERE
                s.search_vec @@ plainto_tsquery('english', $1)
                OR s.title ILIKE $2
                OR s.context ILIKE $2
                OR n.content ILIKE $2
                OR $1 = ANY(s.tags)
            ORDER BY s.session_id, rank DESC, s.updated_at DESC
            """,
            query,
            f"%{query}%",
        )

    # Re-sort by rank after DISTINCT ON
    sorted_rows = sorted(rows, key=lambda r: (-r["rank"], r["updated_at"]))

    return [
        {
            "session_id": r["session_id"],
            "title":      r["title"],
            "updated_at": r["updated_at"].isoformat(),
            "snippet":    r["snippet"],
        }
        for r in sorted_rows
    ]


# ---------------------------------------------------------------------------
# Stats helper (bonus — used by session_list for summary)
# ---------------------------------------------------------------------------

async def get_stats() -> dict:
    """Return aggregate stats: total sessions, total notes, last update."""
    pool = await db.get_pool()
    async with pool.acquire() as conn:
        row = await conn.fetchrow(
            """
            SELECT
                COUNT(DISTINCT s.session_id)  AS total_sessions,
                COUNT(n.id)                   AS total_notes,
                MAX(s.updated_at)             AS last_updated
            FROM sessions s
            LEFT JOIN notes n ON n.session_id = s.session_id
            """
        )
    return {
        "total_sessions": row["total_sessions"],
        "total_notes":    row["total_notes"],
        "last_updated":   row["last_updated"].isoformat() if row["last_updated"] else None,
    }
