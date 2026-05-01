import logging

from mcp.server.fastmcp import FastMCP

from .store import run_vacuum
from .models import VacuumRunInput

_logger = logging.getLogger("lm-mcp-ai.vacuum")


def _error(msg: str) -> str:
    _logger.error(msg)
    return f"Error: {msg}"


def _format_result(result: dict) -> str:
    cfg = result["config"]
    mode = "DRY RUN — no changes made" if result["dry_run"] else "EXECUTED"
    lines = [
        f"## Vacuum {mode}",
        "",
        f"**Settings:** notes_days={cfg['notes_days']} | sessions_days={cfg['sessions_days']} | enabled={cfg['enabled']}",
        "",
        f"**Notes deleted:** {result['notes_deleted']} (unpinned, older than {cfg['notes_days']} days)",
        f"**Sessions archived:** {result['sessions_archived']} (inactive, not pinned, no keep/archive tag)",
        f"**Sessions hard-deleted:** {result['sessions_deleted']} (archived + older than {cfg['sessions_days']} days)",
    ]

    if result["archive_candidates"]:
        lines += ["", "### Sessions that were/would be archived:"]
        for s in result["archive_candidates"]:
            lines.append(f"- `{s['session_id']}` — {s['title']} (last active: {s['updated_at'][:10]})")

    if result["delete_candidates"]:
        lines += ["", "### Sessions that were/would be permanently deleted:"]
        for s in result["delete_candidates"]:
            lines.append(f"- `{s['session_id']}` — {s['title']} (last active: {s['updated_at'][:10]})")

    return "\n".join(lines)


def register(mcp: FastMCP) -> None:
    """Register vacuum tools on the given FastMCP instance."""

    @mcp.tool(
        name="vacuum_run",
        annotations={
            "title": "Run Vacuum",
            "readOnlyHint": False,
            "destructiveHint": True,
            "idempotentHint": False,
            "openWorldHint": False,
        },
    )
    async def vacuum_run(params: VacuumRunInput) -> str:
        """
        Clean up old notes and archive/delete inactive sessions.

        Uses settings from the config table:
        - vacuum_notes_days (default 90): delete unpinned notes older than N days
        - vacuum_sessions_days (default 180): archive inactive sessions, then hard-delete
          sessions that have been archived longer than N days

        Vacuum criteria for sessions (ALL must be true):
        - Not pinned (pinned = false)
        - No tag 'keep' or 'archive'
        - Not updated in the last vacuum_sessions_days days

        Pinned notes and pinned sessions are NEVER touched.

        Use `vacuum_run(dry_run=true)` first to preview what would be deleted.

        Args:
            params.dry_run: Preview mode — shows what WOULD be deleted without changes.
        """
        try:
            result = await run_vacuum(dry_run=params.dry_run)
            _logger.info(
                "Vacuum %s: notes=%d archived=%d deleted=%d",
                "preview" if params.dry_run else "executed",
                result["notes_deleted"],
                result["sessions_archived"],
                result["sessions_deleted"],
            )
            return _format_result(result)
        except Exception as e:
            return _error(str(e))
