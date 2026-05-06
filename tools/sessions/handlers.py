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
    pin_note,
    set_session_pinned,
    set_session_archived,
)
from .models import (
    SessionWriteInput,
    SessionReadInput,
    SessionAppendInput,
    SessionDeleteInput,
    SessionListInput,
    SessionSearchInput,
    SessionUpdateInput,
    NoteUpdateInput,
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
                team=params.team,
            )
            action = "Updated" if session.get("notes") else "Created"
            tags_note = f" | tags: {', '.join(session['tags'])}" if session["tags"] else ""
            team_note = f" | team: {params.team}" if params.team else ""
            return (
                f"Session `{params.session_id}` {action.lower()}.\n"
                f"**Title:** {session['title']}\n"
                f"**Source:** {session['source']}{tags_note}{team_note}\n"
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

            tags_note = f"**Tags:** {', '.join(session['tags'])}" if session.get("tags") else ""
            pin_marker = " 📌 PINNED" if session.get("pinned") else ""
            archived_marker = " 🗄 ARCHIVED" if session.get("archived") else ""
            repo_line = f"**Repo:** {session['repo_url']}" if session.get("repo_url") else ""

            lines = [
                f"# Session: {session['title']}{pin_marker}{archived_marker}",
                f"**ID:** `{session['session_id']}` | **Source:** {session['source']}",
                f"**Created:** {session['created_at']} | **Updated:** {session['updated_at']}",
            ]
            if tags_note:
                lines.append(tags_note)
            if repo_line:
                lines.append(repo_line)
            lines += ["---", "## Context", session["context"]]

            notes = session.get("notes", [])
            pinned_notes = [n for n in notes if n.get("pinned")]
            regular_notes = [n for n in notes if not n.get("pinned")]

            if pinned_notes:
                lines += ["", "---", f"## 📌 Pinned Notes ({len(pinned_notes)})"]
                for note in pinned_notes:
                    lines.append(f"\n**{note['timestamp']} ({note['source']}) [id:{note['id']}]**")
                    lines.append(note["content"])

            if regular_notes:
                lines += ["", "---", f"## Notes ({len(regular_notes)})"]
                for i, note in enumerate(regular_notes, 1):
                    lines.append(f"\n**[{i}] {note['timestamp']} ({note['source']}) [id:{note['id']}]**")
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

        Pinned sessions appear first. Archived sessions are hidden by default.

        Args:
            params.tag: Optional tag to filter by. Omit to list all.
            params.show_archived: Include archived sessions (default false).
        """
        try:
            sessions = await list_sessions(tag=params.tag, show_archived=params.show_archived, team=params.team)
            stats = await get_stats()

            if not sessions:
                filter_note = f" with tag '{params.tag}'" if params.tag else ""
                scope_note = f" in team '{params.team}'" if params.team else " (personal)"
                return f"No sessions found{filter_note}{scope_note}."

            scope_label = f"team '{params.team}'" if params.team else "personal"
            lines = [
                f"## Sessions — {scope_label} ({len(sessions)} shown, {stats['total_sessions']} total)",
                f"*Last updated: {stats['last_updated']}*",
                "",
                "| ID | Title | Source | Tags | Notes | Flags | Updated |",
                "|----|-------|--------|------|-------|-------|---------|",
            ]
            for s in sessions:
                tags = ", ".join(s["tags"]) or "-"
                flags = " ".join(filter(None, [
                    "📌" if s.get("pinned") else "",
                    "🗄" if s.get("archived") else "",
                ]))
                lines.append(
                    f"| `{s['session_id']}` | {s['title']} | {s['source']} "
                    f"| {tags} | {s['notes_count']} | {flags or '-'} | {s['updated_at'][:10]} |"
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

    # -----------------------------------------------------------------------
    # Session lifecycle (pin / archive) — merged into one tool
    # -----------------------------------------------------------------------

    @mcp.tool(
        name="session_update",
        annotations={
            "title": "Update Session Lifecycle State",
            "readOnlyHint": False,
            "destructiveHint": False,
            "idempotentHint": True,
            "openWorldHint": False,
        },
    )
    async def session_update(params: SessionUpdateInput) -> str:
        """
        Change the lifecycle state of a session.

        Actions:
        - 'pin'     — protect from auto-vacuum indefinitely
        - 'unpin'   — make eligible for auto-vacuum again
        - 'archive' — soft-delete (hidden from list; recoverable)
        - 'restore' — un-archive a previously archived session

        Args:
            params.session_id: Session ID to update.
            params.action: One of 'pin', 'unpin', 'archive', 'restore'.
        """
        try:
            if params.action in ("pin", "unpin"):
                found = await set_session_pinned(params.session_id, pinned=(params.action == "pin"))
                if not found:
                    return _error(f"Session '{params.session_id}' not found.")
                if params.action == "pin":
                    return f"Session `{params.session_id}` pinned. Auto-vacuum will never touch it."
                return f"Session `{params.session_id}` unpinned."
            else:
                found = await set_session_archived(params.session_id, archived=(params.action == "archive"))
                if not found:
                    return _error(f"Session '{params.session_id}' not found.")
                if params.action == "archive":
                    return (
                        f"Session `{params.session_id}` archived.\n"
                        "It will be permanently deleted after vacuum_sessions_days (default 180 days).\n"
                        "Use `session_update(action='restore')` to undo."
                    )
                return f"Session `{params.session_id}` restored from archive."
        except Exception as e:
            return _error(str(e))

    # -----------------------------------------------------------------------
    # Note pin / unpin — merged into one tool
    # -----------------------------------------------------------------------

    @mcp.tool(
        name="note_update",
        annotations={
            "title": "Pin or Unpin a Note",
            "readOnlyHint": False,
            "destructiveHint": False,
            "idempotentHint": True,
            "openWorldHint": False,
        },
    )
    async def note_update(params: NoteUpdateInput) -> str:
        """
        Pin or unpin a note.

        Pinned notes always appear at the top of session_read and are never
        deleted by auto-vacuum. Use 'pin' for critical decisions or blockers;
        use 'unpin' to return the note to chronological order.

        Args:
            params.note_id: ID of the note (shown as [id:N] in session_read).
            params.session_id: Session ID the note belongs to.
            params.action: 'pin' or 'unpin'.
        """
        try:
            note = await pin_note(params.note_id, params.session_id, pinned=(params.action == "pin"))
            if note is None:
                return _error(f"Note {params.note_id} not found in session '{params.session_id}'.")
            if params.action == "pin":
                return f"Note {params.note_id} pinned. It will always appear at the top of session_read."
            return f"Note {params.note_id} unpinned."
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
            results = await search_sessions(params.query, team=params.team)
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
