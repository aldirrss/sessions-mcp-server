"""
PostgreSQL-backed skills library store.

Handles CRUD for skills, version history, and session-skill tracking.
"""

import logging
from typing import Optional

import asyncpg

import db

_logger = logging.getLogger("lm-mcp-ai.skills")


# ---------------------------------------------------------------------------
# Row helpers
# ---------------------------------------------------------------------------

def _skill_row(row: asyncpg.Record, full_content: bool = True) -> dict:
    data = {
        "slug":       row["slug"],
        "name":       row["name"],
        "summary":    row["summary"],
        "source":     row["source"],
        "category":   row["category"],
        "tags":       list(row["tags"]),
        "is_global":  row["is_global"],
        "created_at": row["created_at"].isoformat(),
        "updated_at": row["updated_at"].isoformat(),
    }
    if full_content:
        data["content"] = row["content"]
    return data


# ---------------------------------------------------------------------------
# Skills CRUD
# ---------------------------------------------------------------------------

async def read_skill(slug: str) -> Optional[dict]:
    """Return full skill including content, or None if not found."""
    pool = await db.get_pool()
    async with pool.acquire() as conn:
        row = await conn.fetchrow("SELECT * FROM skills WHERE slug = $1", slug)
    return _skill_row(row) if row else None


async def write_skill(
    slug: str,
    name: str,
    content: str,
    summary: str = "",
    source: str = "manual",
    category: Optional[str] = None,
    tags: Optional[list[str]] = None,
    is_global: bool = False,
) -> dict:
    """
    Create or update a skill.
    On update: saves old content to skill_versions before overwriting.
    Returns the full skill dict.
    """
    pool = await db.get_pool()
    tags_val = tags or []

    async with pool.acquire() as conn:
        async with conn.transaction():
            existing = await conn.fetchrow(
                "SELECT content FROM skills WHERE slug = $1", slug
            )

            if existing and existing["content"] != content:
                await conn.execute(
                    "INSERT INTO skill_versions (slug, content) VALUES ($1, $2)",
                    slug, existing["content"],
                )

            row = await conn.fetchrow(
                """
                INSERT INTO skills (slug, name, summary, content, source, category, tags, is_global)
                VALUES ($1, $2, $3, $4, $5, $6, $7, $8)
                ON CONFLICT (slug) DO UPDATE
                    SET name      = EXCLUDED.name,
                        summary   = EXCLUDED.summary,
                        content   = EXCLUDED.content,
                        source    = EXCLUDED.source,
                        category  = EXCLUDED.category,
                        tags      = EXCLUDED.tags,
                        is_global = EXCLUDED.is_global
                RETURNING *
                """,
                slug, name, summary, content, source, category, tags_val, is_global,
            )
    return _skill_row(row)


async def delete_skill(slug: str) -> bool:
    """Delete a skill and cascade to session_skills. Returns True if deleted."""
    pool = await db.get_pool()
    async with pool.acquire() as conn:
        result = await conn.execute("DELETE FROM skills WHERE slug = $1", slug)
    return result == "DELETE 1"


async def list_skills(
    category: Optional[str] = None,
    tag: Optional[str] = None,
    source: Optional[str] = None,
    is_global: Optional[bool] = None,
) -> list[dict]:
    """
    List all skills ordered by name.
    Returns summary only (no content) to keep response size small.
    Supports filtering by category, tag, source, or is_global.
    """
    pool = await db.get_pool()

    conditions = []
    args = []

    if category:
        args.append(category)
        conditions.append(f"category = ${len(args)}")
    if tag:
        args.append(tag)
        conditions.append(f"${len(args)} = ANY(tags)")
    if source:
        args.append(source)
        conditions.append(f"source = ${len(args)}")
    if is_global is not None:
        args.append(is_global)
        conditions.append(f"is_global = ${len(args)}")

    where = f"WHERE {' AND '.join(conditions)}" if conditions else ""

    async with pool.acquire() as conn:
        rows = await conn.fetch(
            f"""
            SELECT slug, name, summary, source, category, tags, is_global, created_at, updated_at
            FROM skills
            {where}
            ORDER BY name ASC
            """,
            *args,
        )

    return [_skill_row(r, full_content=False) for r in rows]


async def search_skills(query: str) -> list[dict]:
    """
    Full-text search across name, summary, content, and tags.
    Returns summary + snippet, ordered by relevance.
    """
    pool = await db.get_pool()

    async with pool.acquire() as conn:
        rows = await conn.fetch(
            """
            SELECT
                slug, name, summary, source, category, tags,
                created_at, updated_at,
                LEFT(content, 200) AS snippet,
                COALESCE(ts_rank(search_vec, plainto_tsquery('english', $1)), 0) AS rank
            FROM skills
            WHERE
                search_vec @@ plainto_tsquery('english', $1)
                OR name    ILIKE $2
                OR summary ILIKE $2
                OR $1 = ANY(tags)
            ORDER BY rank DESC, name ASC
            """,
            query, f"%{query}%",
        )

    return [
        {
            **_skill_row(r, full_content=False),
            "snippet": r["snippet"],
        }
        for r in rows
    ]


async def sync_skills(skills: list[dict]) -> dict:
    """
    Bulk upsert skills from a list of dicts (slug, name, summary, content, category, tags).
    Used for importing from files. Returns counts of created and updated.
    """
    pool = await db.get_pool()
    created = updated = 0

    async with pool.acquire() as conn:
        for s in skills:
            existing = await conn.fetchrow(
                "SELECT content FROM skills WHERE slug = $1", s["slug"]
            )
            if existing:
                if existing["content"] != s.get("content", ""):
                    async with conn.transaction():
                        await conn.execute(
                            "INSERT INTO skill_versions (slug, content) VALUES ($1, $2)",
                            s["slug"], existing["content"],
                        )
                        await conn.execute(
                            """
                            UPDATE skills SET
                                name = $2, summary = $3, content = $4,
                                category = $5, tags = $6, source = 'file'
                            WHERE slug = $1
                            """,
                            s["slug"], s.get("name", s["slug"]),
                            s.get("summary", ""), s.get("content", ""),
                            s.get("category"), s.get("tags", []),
                        )
                updated += 1
            else:
                await conn.execute(
                    """
                    INSERT INTO skills (slug, name, summary, content, source, category, tags)
                    VALUES ($1, $2, $3, $4, 'file', $5, $6)
                    """,
                    s["slug"], s.get("name", s["slug"]),
                    s.get("summary", ""), s.get("content", ""),
                    s.get("category"), s.get("tags", []),
                )
                created += 1

    return {"created": created, "updated": updated, "total": len(skills)}


async def get_skill_versions(slug: str) -> list[dict]:
    """Return version history for a skill, newest first."""
    pool = await db.get_pool()
    async with pool.acquire() as conn:
        rows = await conn.fetch(
            "SELECT id, slug, changed_at FROM skill_versions WHERE slug = $1 ORDER BY changed_at DESC",
            slug,
        )
    return [{"id": r["id"], "slug": r["slug"], "changed_at": r["changed_at"].isoformat()} for r in rows]


# ---------------------------------------------------------------------------
# Session-skill tracking
# ---------------------------------------------------------------------------

async def track_skill(session_id: str, skill_slug: str) -> dict:
    """
    Record that a skill was used in a session.
    Returns {"first_use": bool, "skipped": bool}.
    skipped=True when the slug is not present in the skills table (external/user skills).
    """
    pool = await db.get_pool()

    async with pool.acquire() as conn:
        skill = await conn.fetchrow(
            "SELECT name, summary FROM skills WHERE slug = $1", skill_slug
        )

        if skill is None:
            return {
                "session_id": session_id,
                "skill_slug": skill_slug,
                "skill_name": skill_slug,
                "first_use": False,
                "skipped": True,
            }

        result = await conn.execute(
            """
            INSERT INTO session_skills (session_id, skill_slug)
            VALUES ($1, $2)
            ON CONFLICT (session_id, skill_slug) DO NOTHING
            """,
            session_id, skill_slug,
        )
        first_use = result == "INSERT 0 1"

    return {
        "session_id": session_id,
        "skill_slug": skill_slug,
        "skill_name": skill["name"],
        "first_use": first_use,
        "skipped": False,
    }


async def list_session_skills(session_id: str) -> list[dict]:
    """List all skills used in a session, ordered by first use."""
    pool = await db.get_pool()
    async with pool.acquire() as conn:
        rows = await conn.fetch(
            """
            SELECT ss.skill_slug, ss.used_at, sk.name, sk.summary, sk.category, sk.tags
            FROM session_skills ss
            JOIN skills sk ON sk.slug = ss.skill_slug
            WHERE ss.session_id = $1
            ORDER BY ss.used_at ASC
            """,
            session_id,
        )
    return [
        {
            "slug":     r["skill_slug"],
            "name":     r["name"],
            "summary":  r["summary"],
            "category": r["category"],
            "tags":     list(r["tags"]),
            "used_at":  r["used_at"].isoformat(),
        }
        for r in rows
    ]


async def list_skill_sessions(skill_slug: str) -> list[dict]:
    """List all sessions that used a skill, ordered by most recent."""
    pool = await db.get_pool()
    async with pool.acquire() as conn:
        rows = await conn.fetch(
            """
            SELECT ss.session_id, ss.used_at, s.title, s.source, s.updated_at
            FROM session_skills ss
            JOIN sessions s ON s.session_id = ss.session_id
            WHERE ss.skill_slug = $1
            ORDER BY ss.used_at DESC
            """,
            skill_slug,
        )
    return [
        {
            "session_id": r["session_id"],
            "title":      r["title"],
            "source":     r["source"],
            "used_at":    r["used_at"].isoformat(),
            "updated_at": r["updated_at"].isoformat(),
        }
        for r in rows
    ]


# ---------------------------------------------------------------------------
# Analytics
# ---------------------------------------------------------------------------

async def get_skill_stats() -> list[dict]:
    """Usage stats per skill: total sessions, ordered by most-used."""
    pool = await db.get_pool()
    async with pool.acquire() as conn:
        rows = await conn.fetch(
            """
            SELECT
                sk.slug, sk.name, sk.category,
                COUNT(ss.session_id) AS session_count,
                MAX(ss.used_at)      AS last_used_at
            FROM skills sk
            LEFT JOIN session_skills ss ON ss.skill_slug = sk.slug
            GROUP BY sk.slug, sk.name, sk.category
            ORDER BY session_count DESC, sk.name ASC
            """
        )
    return [
        {
            "slug":          r["slug"],
            "name":          r["name"],
            "category":      r["category"],
            "session_count": r["session_count"],
            "last_used_at":  r["last_used_at"].isoformat() if r["last_used_at"] else None,
        }
        for r in rows
    ]


async def recommend_skills(session_id: str, limit: int = 5) -> list[dict]:
    """
    Recommend skills not yet used in this session, ranked by:
    1. Tag overlap with the session's tags
    2. Overall usage frequency
    """
    pool = await db.get_pool()
    async with pool.acquire() as conn:
        session = await conn.fetchrow(
            "SELECT tags FROM sessions WHERE session_id = $1", session_id
        )
        if not session:
            return []

        session_tags = list(session["tags"])

        rows = await conn.fetch(
            """
            SELECT
                sk.slug, sk.name, sk.summary, sk.category, sk.tags,
                COUNT(ss2.session_id) AS usage_count,
                (
                    SELECT COUNT(*) FROM unnest(sk.tags) t
                    WHERE t = ANY($3::text[])
                ) AS tag_overlap
            FROM skills sk
            LEFT JOIN session_skills ss2 ON ss2.skill_slug = sk.slug
            WHERE sk.slug NOT IN (
                SELECT skill_slug FROM session_skills WHERE session_id = $1
            )
            GROUP BY sk.slug, sk.name, sk.summary, sk.category, sk.tags
            ORDER BY tag_overlap DESC, usage_count DESC, sk.name ASC
            LIMIT $2
            """,
            session_id, limit, session_tags,
        )

    return [
        {
            "slug":        r["slug"],
            "name":        r["name"],
            "summary":     r["summary"],
            "category":    r["category"],
            "tags":        list(r["tags"]),
            "usage_count": r["usage_count"],
            "tag_overlap": r["tag_overlap"],
        }
        for r in rows
    ]
