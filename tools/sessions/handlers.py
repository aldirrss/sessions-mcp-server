import logging

from mcp.server.fastmcp import FastMCP

from .store import (
    read_session,
    write_session,
    append_note,
    list_sessions,
    delete_session,
    search_sessions,
    get_stats,
)
from .models import (
    SessionWriteInput,
    SessionReadInput,
    SessionAppendInput,
    SessionDeleteInput,
    SessionListInput,
    SessionSearchInput,
)

_logger = logging.getLogger("lm-mcp-ai.sessions")


def _error(msg: str) -> str:
    _logger.error(msg)
    return f"Error: {msg}"


def register(mcp: FastMCP) -> None:
    """Register all session store tools on the given FastMCP instance."""

    @mcp.tool(
        name="session_write",
        annotations={
            "title": "Write Session Context",
            "readOnlyHint": False,
            "destructiveHint": False,
            "idempotentHint": True,
            "openWorldHint": False,
        },
    )
    async def session_write(params: SessionWriteInput) -> str:
        """
        Create or overwrite a session context in the shared store.

        Use this to save the current state of work so it can be resumed from
        Claude Web, Claude CLI, or VSCode. Overwrites context but preserves notes.

        Args:
            params.session_id: Unique key for this session (e.g. 'feat-auth-dev').
            params.title: Short human-readable title.
            params.context: Full context — goals, current state, decisions, next steps.
            params.source: Origin client ('web', 'cli', 'vscode').
            params.tags: Optional tags for filtering.
        """
        try:
            session = await write_session(
                params.session_id,
                params.title,
                params.context,
                source=params.source,
                tags=params.tags,
            )
            action = "Updated" if session.get("notes") else "Created"
            tags_note = f" | tags: {', '.join(session['tags'])}" if session["tags"] else ""
            return (
                f"Session `{params.session_id}` {action.lower()}.\n"
                f"**Title:** {session['title']}\n"
                f"**Source:** {session['source']}{tags_note}\n"
                f"**Updated:** {session['updated_at']}"
            )
        except Exception as e:
            return _error(str(e))

    @mcp.tool(
        name="session_read",
        annotations={
            "title": "Read Session Context",
            "readOnlyHint": True,
            "destructiveHint": False,
            "idempotentHint": True,
            "openWorldHint": False,
        },
    )
    async def session_read(params: SessionReadInput) -> str:
        """
        Read the full context of a session from the shared store.

        Use this at the start of a conversation to resume where you left off.

        Args:
            params.session_id: Session ID to read.
        """
        try:
            session = await read_session(params.session_id)
            if session is None:
                return f"Session `{params.session_id}` not found."

            tags_note = f"**Tags:** {', '.join(session['tags'])}\n" if session.get("tags") else ""
            lines = [
                f"# Session: {session['title']}",
                f"**ID:** `{session['session_id']}` | **Source:** {session['source']}",
                f"**Created:** {session['created_at']} | **Updated:** {session['updated_at']}",
                tags_note,
                "---",
                "## Context",
                session["context"],
            ]

            notes = session.get("notes", [])
            if notes:
                lines += ["", "---", f"## Notes ({len(notes)})"]
                for i, note in enumerate(notes, 1):
                    lines.append(f"\n**[{i}] {note['timestamp']} ({note['source']})**")
                    lines.append(note["content"])

            return "\n".join(lines)
        except Exception as e:
            return _error(str(e))

    @mcp.tool(
        name="session_list",
        annotations={
            "title": "List All Sessions",
            "readOnlyHint": True,
            "destructiveHint": False,
            "idempotentHint": True,
            "openWorldHint": False,
        },
    )
    async def session_list(params: SessionListInput) -> str:
        """
        List all sessions in the shared store.

        Args:
            params.tag: Optional tag to filter by. Omit to list all.
        """
        try:
            sessions = await list_sessions(tag=params.tag)
            stats = await get_stats()

            if not sessions:
                filter_note = f" with tag '{params.tag}'" if params.tag else ""
                return f"No sessions found{filter_note}."

            lines = [
                f"## Sessions ({stats['total_sessions']} total, {stats['total_notes']} notes)",
                f"*Last updated: {stats['last_updated']}*",
                "",
                "| ID | Title | Source | Tags | Notes | Updated |",
                "|----|-------|--------|------|-------|---------|",
            ]
            for s in sessions:
                tags = ", ".join(s["tags"]) or "-"
                lines.append(
                    f"| `{s['session_id']}` | {s['title']} | {s['source']} "
                    f"| {tags} | {s['notes_count']} | {s['updated_at']} |"
                )
            return "\n".join(lines)
        except Exception as e:
            return _error(str(e))

    @mcp.tool(
        name="session_append",
        annotations={
            "title": "Append Note to Session",
            "readOnlyHint": False,
            "destructiveHint": False,
            "idempotentHint": False,
            "openWorldHint": False,
        },
    )
    async def session_append(params: SessionAppendInput) -> str:
        """
        Append a timestamped note to an existing session without overwriting its context.

        Use this to log progress updates, decisions, or blockers mid-session.

        Args:
            params.session_id: Session ID to append to.
            params.content: Note content (progress update, decision, blocker, etc.).
            params.source: Origin client ('web', 'cli', 'vscode').
        """
        try:
            session = await append_note(params.session_id, params.content, source=params.source)
            note_count = len(session["notes"])
            return (
                f"Note appended to `{params.session_id}` (total notes: {note_count}).\n"
                f"**Timestamp:** {session['notes'][-1]['timestamp']} | **Source:** {params.source}"
            )
        except FileNotFoundError:
            return _error(
                f"Session '{params.session_id}' not found. Use session_write to create it first."
            )
        except Exception as e:
            return _error(str(e))

    @mcp.tool(
        name="session_delete",
        annotations={
            "title": "Delete Session",
            "readOnlyHint": False,
            "destructiveHint": True,
            "idempotentHint": True,
            "openWorldHint": False,
        },
    )
    async def session_delete(params: SessionDeleteInput) -> str:
        """
        Permanently delete a session from the store.

        Args:
            params.session_id: Session ID to delete.
        """
        try:
            deleted = await delete_session(params.session_id)
            if deleted:
                return f"Session `{params.session_id}` deleted."
            return f"Session `{params.session_id}` not found — nothing deleted."
        except Exception as e:
            return _error(str(e))

    @mcp.tool(
        name="session_search",
        annotations={
            "title": "Search Sessions",
            "readOnlyHint": True,
            "destructiveHint": False,
            "idempotentHint": True,
            "openWorldHint": False,
        },
    )
    async def session_search(params: SessionSearchInput) -> str:
        """
        Search sessions by keyword across title, context, notes, and tags.

        Args:
            params.query: Keyword to search for.
        """
        try:
            results = await search_sessions(params.query)
            if not results:
                return f"No sessions found matching '{params.query}'."

            lines = [f"## Search results for '{params.query}' ({len(results)} found)", ""]
            for r in results:
                lines.append(f"### `{r['session_id']}` — {r['title']}")
                lines.append(f"*Updated: {r['updated_at']}*")
                lines.append(f"> {r['snippet']}")
                lines.append("")
            return "\n".join(lines)
        except Exception as e:
            return _error(str(e))
