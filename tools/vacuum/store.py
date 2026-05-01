"""
Auto-vacuum logic for sessions and notes.

Reads settings from the config table (seeded with defaults on startup):
  vacuum_enabled       — 'true'/'false', controls the daily auto-vacuum task
  vacuum_notes_days    — int: hard-delete notes older than N days (default 90)
  vacuum_sessions_days — int: hard-delete archived sessions older than N days (default 180)

Vacuum criteria for sessions (ALL must be true to archive/delete):
  1. Not pinned (pinned = false)
  2. No tag 'keep' or 'archive'
  3. inactive: updated_at older than vacuum_sessions_days

Notes vacuum:
  - Hard-delete unpinned notes older than vacuum_notes_days
  - Pinned notes are never touched
"""

import logging

import db

_logger = logging.getLogger("lm-mcp-ai.vacuum")


async def _get_vacuum_config() -> dict:
    """Read vacuum settings from config table. Returns defaults if keys missing."""
    pool = await db.get_pool()
    async with pool.acquire() as conn:
        rows = await conn.fetch(
            "SELECT key, value FROM config WHERE key LIKE 'vacuum_%'"
        )
    cfg = {r["key"]: r["value"] for r in rows}
    return {
        "enabled":       cfg.get("vacuum_enabled", "false").lower() == "true",
        "notes_days":    int(cfg.get("vacuum_notes_days", "90")),
        "sessions_days": int(cfg.get("vacuum_sessions_days", "180")),
    }


async def run_vacuum(dry_run: bool = False) -> dict:
    """
    Execute vacuum or preview (dry_run=True) based on config table settings.

    Returns a dict with counts of what was (or would be) deleted.
    """
    cfg = await _get_vacuum_config()

    pool = await db.get_pool()
    async with pool.acquire() as conn:

        # --- Notes: find unpinned notes older than vacuum_notes_days ---
        old_notes = await conn.fetch(
            """
            SELECT n.id, n.session_id, n.created_at
            FROM notes n
            WHERE n.pinned = false
              AND n.created_at < NOW() - ($1 || ' days')::INTERVAL
            """,
            str(cfg["notes_days"]),
        )

        # --- Sessions: find candidates for archiving ---
        # Criteria: not pinned, no keep/archive tag, inactive > sessions_days
        archive_candidates = await conn.fetch(
            """
            SELECT session_id, title, updated_at, tags
            FROM sessions
            WHERE pinned = false
              AND archived = false
              AND updated_at < NOW() - ($1 || ' days')::INTERVAL
              AND NOT (tags && ARRAY['keep', 'archive'])
            """,
            str(cfg["sessions_days"]),
        )

        # --- Sessions: find archived sessions ready for hard-delete ---
        # Archived + past sessions_days since last update
        delete_candidates = await conn.fetch(
            """
            SELECT session_id, title, updated_at
            FROM sessions
            WHERE archived = true
              AND pinned = false
              AND updated_at < NOW() - ($1 || ' days')::INTERVAL
            """,
            str(cfg["sessions_days"]),
        )

        if not dry_run:
            async with conn.transaction():
                # 1. Hard-delete old notes
                if old_notes:
                    note_ids = [n["id"] for n in old_notes]
                    await conn.execute(
                        "DELETE FROM notes WHERE id = ANY($1::bigint[])",
                        note_ids,
                    )

                # 2. Soft-delete inactive sessions → archived=true
                if archive_candidates:
                    ids = [s["session_id"] for s in archive_candidates]
                    await conn.execute(
                        "UPDATE sessions SET archived = true, updated_at = NOW() WHERE session_id = ANY($1::text[])",
                        ids,
                    )

                # 3. Hard-delete sessions that have been archived long enough
                if delete_candidates:
                    ids = [s["session_id"] for s in delete_candidates]
                    await conn.execute(
                        "DELETE FROM sessions WHERE session_id = ANY($1::text[])",
                        ids,
                    )

    return {
        "dry_run":            dry_run,
        "notes_deleted":      len(old_notes),
        "sessions_archived":  len(archive_candidates),
        "sessions_deleted":   len(delete_candidates),
        "config":             cfg,
        "archive_candidates": [
            {"session_id": s["session_id"], "title": s["title"], "updated_at": s["updated_at"].isoformat()}
            for s in archive_candidates
        ],
        "delete_candidates": [
            {"session_id": s["session_id"], "title": s["title"], "updated_at": s["updated_at"].isoformat()}
            for s in delete_candidates
        ],
    }
