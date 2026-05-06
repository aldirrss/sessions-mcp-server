"""
PostgreSQL-backed context store for Claude session continuity.

All public functions are async and use the shared asyncpg pool from db.py.
Sessions persist across Claude Web <-> CLI/VSCode boundaries via a shared
PostgreSQL database on the VPS.
"""

import logging
from typing import Optional

import asyncpg

import db
from auth.context import get_current_user

_logger = logging.getLogger("lm-mcp-ai.session")


def _current_user_id() -> Optional[str]:
    user = get_current_user()
    if user is None:
        return None
    return user.get("id")


async def _resolve_team_id(conn: asyncpg.Connection, team_name: str, user_id: str) -> str:
    """Resolve team slug/name to UUID, validating that user is a member."""
    row = await conn.fetchrow(
        """
        SELECT t.id FROM teams t
        JOIN team_members tm ON tm.team_id = t.id
        WHERE t.name = $1 AND tm.user_id = $2::uuid
        """,
        team_name, user_id,
    )
    if row is None:
        raise PermissionError(
            f"Team '{team_name}' not found or you are not a member of it."
        )
    return str(row["id"])


async def _has_session_access(
    conn: asyncpg.Connection, session_id: str, user_id: Optional[str]
) -> bool:
    """Return True if the current caller may read/write this session."""
    # Admin (unauthenticated server-to-server): full access
    if user_id is None:
        return True

    # Regular user: owns the session personally OR is a member of the session's team
    result = await conn.fetchval(
        """
        SELECT 1 FROM sessions s
        WHERE s.session_id = $1
          AND (
            (s.owner_id = $2::uuid AND s.team_id IS NULL)
            OR EXISTS (
              SELECT 1 FROM team_members tm
              WHERE tm.team_id = s.team_id AND tm.user_id = $2::uuid
            )
          )
        """,
        session_id, user_id,
    )
    return result is not None


def _session_row(row: asyncpg.Record, notes: list[dict] | None = None) -> dict:
    return {
        "session_id": row["session_id"],
        "title":      row["title"],
        "context":    row["context"],
        "source":     row["source"],
        "tags":       list(row["tags"]),
        "pinned":     row["pinned"],
        "archived":   row["archived"],
        "repo_url":   row["repo_url"],
        "notes":      notes or [],
        "created_at": row["created_at"].isoformat(),
        "updated_at": row["updated_at"].isoformat(),
    }


def _note_row(row: asyncpg.Record) -> dict:
    return {
        "id":        row["id"],
        "content":   row["content"],
        "source":    row["source"],
        "pinned":    row["pinned"],
        "timestamp": row["created_at"].isoformat(),
    }


async def read_session(session_id: str) -> Optional[dict]:
    """Return full session with all notes (pinned first), or None if not found or not accessible."""
    pool = await db.get_pool()
    user_id = _current_user_id()
    async with pool.acquire() as conn:
        if not await _has_session_access(conn, session_id, user_id):
            return None

        row = await conn.fetchrow(
            "SELECT * FROM sessions WHERE session_id = $1",
            session_id,
        )
        if row is None:
            return None

        note_rows = await conn.fetch(
            "SELECT * FROM notes WHERE session_id = $1 ORDER BY pinned DESC, created_at ASC",
            session_id,
        )
        return _session_row(row, [_note_row(n) for n in note_rows])


async def write_session(
    session_id: str,
    title: str,
    context: str,
    source: str = "unknown",
    tags: list[str] | None = None,
    team: str | None = None,
) -> dict:
    """
    Create or overwrite a session. If `team` is given, the session is saved to that
    team's namespace (user must be a member). Otherwise saved as a personal session.
    """
    pool = await db.get_pool()
    tags_val = tags or []
    user_id = _current_user_id()

    # Determine team_id: explicit team param > legacy team token
    async with pool.acquire() as conn:
        if team is not None:
            if user_id is None:
                raise PermissionError("Must be authenticated to write team sessions.")
            team_id = await _resolve_team_id(conn, team, user_id)
        else:
            team_id = None

        row = await conn.fetchrow(
            """
            INSERT INTO sessions (session_id, title, context, source, tags, owner_id, team_id)
            VALUES ($1, $2, $3, $4, $5, $6::uuid, $7::uuid)
            ON CONFLICT (session_id) DO UPDATE
                SET title    = EXCLUDED.title,
                    context  = EXCLUDED.context,
                    source   = EXCLUDED.source,
                    tags     = EXCLUDED.tags
            RETURNING *
            """,
            session_id, title, context, source, tags_val, user_id, team_id,
        )
        note_rows = await conn.fetch(
            "SELECT * FROM notes WHERE session_id = $1 ORDER BY created_at ASC",
            session_id,
        )
        return _session_row(row, [_note_row(n) for n in note_rows])


async def append_note(session_id: str, content: str, source: str = "unknown") -> dict:
    """Append a timestamped note to an existing session."""
    pool = await db.get_pool()
    user_id = _current_user_id()

    async with pool.acquire() as conn:
        async with conn.transaction():
            if not await _has_session_access(conn, session_id, user_id):
                raise PermissionError(f"Access denied to session '{session_id}'.")

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
            await conn.execute(
                "UPDATE sessions SET updated_at = NOW() WHERE session_id = $1",
                session_id,
            )

    return await read_session(session_id)


async def pin_note(note_id: int, session_id: str, pinned: bool) -> Optional[dict]:
    """Set pinned flag on a note. Returns updated note dict, or None if not found."""
    pool = await db.get_pool()
    async with pool.acquire() as conn:
        row = await conn.fetchrow(
            """
            UPDATE notes SET pinned = $1
            WHERE id = $2 AND session_id = $3
            RETURNING *
            """,
            pinned, note_id, session_id,
        )
    return _note_row(row) if row else None


async def compact_session(session_id: str, before_days: int = 30) -> dict:
    """Merge unpinned notes older than `before_days` days into the context field."""
    pool = await db.get_pool()
    user_id = _current_user_id()
    async with pool.acquire() as conn:
        async with conn.transaction():
            if not await _has_session_access(conn, session_id, user_id):
                raise PermissionError(f"Access denied to session '{session_id}'.")

            session = await conn.fetchrow(
                "SELECT * FROM sessions WHERE session_id = $1",
                session_id,
            )
            if session is None:
                raise FileNotFoundError(f"Session '{session_id}' not found.")

            old_notes = await conn.fetch(
                """
                SELECT * FROM notes
                WHERE session_id = $1
                  AND pinned = false
                  AND created_at < NOW() - ($2 || ' days')::INTERVAL
                ORDER BY created_at ASC
                """,
                session_id,
                str(before_days),
            )

            if not old_notes:
                return {
                    "session_id": session_id,
                    "compacted": 0,
                    "message": f"No unpinned notes older than {before_days} days to compact.",
                }

            cutoff_date = old_notes[-1]["created_at"].strftime("%Y-%m-%d")
            compact_block = (
                f"\n\n---\n## Compacted Notes (before {cutoff_date})\n\n"
                + "\n\n".join(
                    f"### [{n['created_at'].isoformat()[:19]}] ({n['source']})\n{n['content']}"
                    for n in old_notes
                )
            )

            new_context = session["context"] + compact_block
            note_ids = [n["id"] for n in old_notes]

            await conn.execute(
                "UPDATE sessions SET context = $1, updated_at = NOW() WHERE session_id = $2",
                new_context, session_id,
            )
            await conn.execute(
                "DELETE FROM notes WHERE id = ANY($1::bigint[])",
                note_ids,
            )

    return {
        "session_id": session_id,
        "compacted":  len(old_notes),
        "message": (
            f"Compacted {len(old_notes)} note(s) older than {before_days} days into context. "
            "Pinned notes were preserved."
        ),
    }


async def set_session_pinned(session_id: str, pinned: bool) -> bool:
    pool = await db.get_pool()
    user_id = _current_user_id()
    async with pool.acquire() as conn:
        if not await _has_session_access(conn, session_id, user_id):
            return False
        result = await conn.execute(
            "UPDATE sessions SET pinned = $1, updated_at = NOW() WHERE session_id = $2",
            pinned, session_id,
        )
    return result == "UPDATE 1"


async def set_session_archived(session_id: str, archived: bool) -> bool:
    pool = await db.get_pool()
    user_id = _current_user_id()
    async with pool.acquire() as conn:
        if not await _has_session_access(conn, session_id, user_id):
            return False
        result = await conn.execute(
            "UPDATE sessions SET archived = $1, updated_at = NOW() WHERE session_id = $2",
            archived, session_id,
        )
    return result == "UPDATE 1"


async def list_sessions(
    tag: str | None = None,
    show_archived: bool = False,
    team: str | None = None,
) -> list[dict]:
    """
    List sessions. Pass `team` (team name) to list that team's sessions — user must be a member.
    Without `team`, lists personal sessions only.
    """
    pool = await db.get_pool()
    user_id = _current_user_id()

    base_query = """
        SELECT
            s.session_id,
            s.title,
            s.source,
            s.tags,
            s.pinned,
            s.archived,
            s.updated_at,
            COUNT(n.id) AS notes_count
        FROM sessions s
        LEFT JOIN notes n ON n.session_id = s.session_id
        {where}
        GROUP BY s.session_id
        ORDER BY s.pinned DESC, s.updated_at DESC
    """

    async with pool.acquire() as conn:
        conditions: list[str] = []
        args: list = []

        if not show_archived:
            conditions.append("s.archived = false")

        if tag:
            args.append(tag)
            conditions.append(f"${len(args)} = ANY(s.tags)")

        if team is not None and user_id is not None:
            team_id = await _resolve_team_id(conn, team, user_id)
            args.append(team_id)
            conditions.append(f"s.team_id = ${len(args)}::uuid")
        elif user_id is not None:
            # Personal scope: owned by user, no team — strict, no IS NULL fallback
            args.append(user_id)
            conditions.append(f"s.owner_id = ${len(args)}::uuid AND s.team_id IS NULL")
        # else: admin (user_id=None) — no scope filter, sees all

        where_clause = ("WHERE " + " AND ".join(conditions)) if conditions else ""
        rows = await conn.fetch(base_query.format(where=where_clause), *args)

    return [
        {
            "session_id":  r["session_id"],
            "title":       r["title"],
            "source":      r["source"],
            "tags":        list(r["tags"]),
            "pinned":      r["pinned"],
            "archived":    r["archived"],
            "notes_count": r["notes_count"],
            "updated_at":  r["updated_at"].isoformat(),
        }
        for r in rows
    ]


async def delete_session(session_id: str) -> bool:
    pool = await db.get_pool()
    user_id = _current_user_id()
    async with pool.acquire() as conn:
        if not await _has_session_access(conn, session_id, user_id):
            return False
        result = await conn.execute(
            "DELETE FROM sessions WHERE session_id = $1",
            session_id,
        )
    return result == "DELETE 1"


async def search_sessions(query: str, team: str | None = None) -> list[dict]:
    """Search sessions. Pass `team` to scope search to that team's sessions."""
    pool = await db.get_pool()
    user_id = _current_user_id()

    async with pool.acquire() as conn:
        args: list = [query, f"%{query}%"]

        if team is not None and user_id is not None:
            resolved = await _resolve_team_id(conn, team, user_id)
            args.append(resolved)
            scope_clause = f"AND s.team_id = ${len(args)}::uuid"
        elif user_id is not None:
            args.append(user_id)
            scope_clause = f"AND s.owner_id = ${len(args)}::uuid AND s.team_id IS NULL"
        else:
            scope_clause = ""

        rows = await conn.fetch(
            f"""
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
            WHERE (
                s.search_vec @@ plainto_tsquery('english', $1)
                OR s.title ILIKE $2
                OR s.context ILIKE $2
                OR n.content ILIKE $2
                OR $1 = ANY(s.tags)
            )
            {scope_clause}
            ORDER BY s.session_id, rank DESC, s.updated_at DESC
            """,
            *args,
        )

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


async def get_stats() -> dict:
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
