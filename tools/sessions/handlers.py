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
    compact_session,
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
    NotePinInput,
    NoteUnpinInput,
    SessionCompactInput,
    SessionPinInput,
    SessionArchiveInput,
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
    # Ide 3 — Note pinning + session compact
    # -----------------------------------------------------------------------

    @mcp.tool(
        name="note_pin",
        annotations={
            "title": "Pin a Note",
            "readOnlyHint": False,
            "destructiveHint": False,
            "idempotentHint": True,
            "openWorldHint": False,
        },
    )
    async def note_pin(params: NotePinInput) -> str:
        """
        Pin a note so it always appears at the top of session_read output.

        Use this for critical decisions, blockers, or constraints that must
        remain visible regardless of how many notes accumulate.
        Pinned notes are never deleted by session_compact or auto-vacuum.

        Args:
            params.note_id: ID of the note to pin (shown as [id:N] in session_read).
            params.session_id: Session ID the note belongs to.
        """
        try:
            note = await pin_note(params.note_id, params.session_id, pinned=True)
            if note is None:
                return _error(f"Note {params.note_id} not found in session '{params.session_id}'.")
            return f"Note {params.note_id} pinned. It will always appear at the top of session_read."
        except Exception as e:
            return _error(str(e))

    @mcp.tool(
        name="note_unpin",
        annotations={
            "title": "Unpin a Note",
            "readOnlyHint": False,
            "destructiveHint": False,
            "idempotentHint": True,
            "openWorldHint": False,
        },
    )
    async def note_unpin(params: NoteUnpinInput) -> str:
        """
        Unpin a previously pinned note.

        After unpinning, the note returns to chronological order and becomes
        eligible for session_compact and auto-vacuum.

        Args:
            params.note_id: ID of the note to unpin.
            params.session_id: Session ID the note belongs to.
        """
        try:
            note = await pin_note(params.note_id, params.session_id, pinned=False)
            if note is None:
                return _error(f"Note {params.note_id} not found in session '{params.session_id}'.")
            return f"Note {params.note_id} unpinned."
        except Exception as e:
            return _error(str(e))

    @mcp.tool(
        name="session_compact",
        annotations={
            "title": "Compact Old Notes into Context",
            "readOnlyHint": False,
            "destructiveHint": False,
            "idempotentHint": False,
            "openWorldHint": False,
        },
    )
    async def session_compact(params: SessionCompactInput) -> str:
        """
        Merge old unpinned notes into the session context and delete them.

        Keeps the notes table lean while preserving history in the context field.
        The compacted notes are appended as a formatted '## Compacted Notes' section
        in the context. Pinned notes are never compacted.

        Use this when a session has accumulated many notes and session_read is
        becoming too long to fit in context.

        Args:
            params.session_id: Session to compact.
            params.before_days: Compact notes older than this many days (default 30).
        """
        try:
            result = await compact_session(params.session_id, before_days=params.before_days)
            return result["message"]
        except FileNotFoundError as e:
            return _error(str(e))
        except Exception as e:
            return _error(str(e))

    # -----------------------------------------------------------------------
    # Ide 4 — Session pin / archive lifecycle
    # -----------------------------------------------------------------------

    @mcp.tool(
        name="session_pin",
        annotations={
            "title": "Pin Session",
            "readOnlyHint": False,
            "destructiveHint": False,
            "idempotentHint": True,
            "openWorldHint": False,
        },
    )
    async def session_pin(params: SessionPinInput) -> str:
        """
        Pin a session to prevent it from being archived or deleted by auto-vacuum.

        Pinned sessions are excluded from all vacuum operations regardless of age.

        Args:
            params.session_id: Session ID to pin.
        """
        try:
            found = await set_session_pinned(params.session_id, pinned=True)
            if not found:
                return _error(f"Session '{params.session_id}' not found.")
            return f"Session `{params.session_id}` pinned. Auto-vacuum will never touch it."
        except Exception as e:
            return _error(str(e))

    @mcp.tool(
        name="session_unpin",
        annotations={
            "title": "Unpin Session",
            "readOnlyHint": False,
            "destructiveHint": False,
            "idempotentHint": True,
            "openWorldHint": False,
        },
    )
    async def session_unpin(params: SessionPinInput) -> str:
        """
        Remove the pin from a session, making it eligible for auto-vacuum again.

        Args:
            params.session_id: Session ID to unpin.
        """
        try:
            found = await set_session_pinned(params.session_id, pinned=False)
            if not found:
                return _error(f"Session '{params.session_id}' not found.")
            return f"Session `{params.session_id}` unpinned."
        except Exception as e:
            return _error(str(e))

    @mcp.tool(
        name="session_archive",
        annotations={
            "title": "Archive Session",
            "readOnlyHint": False,
            "destructiveHint": False,
            "idempotentHint": True,
            "openWorldHint": False,
        },
    )
    async def session_archive(params: SessionArchiveInput) -> str:
        """
        Soft-delete a session by marking it as archived.

        Archived sessions are hidden from session_list by default but can be
        restored with session_restore. They will be permanently deleted after
        vacuum_sessions_days (default 180 days) by auto-vacuum.

        Args:
            params.session_id: Session ID to archive.
        """
        try:
            found = await set_session_archived(params.session_id, archived=True)
            if not found:
                return _error(f"Session '{params.session_id}' not found.")
            return (
                f"Session `{params.session_id}` archived.\n"
                "It will be permanently deleted after vacuum_sessions_days (default 180 days).\n"
                "Use `session_restore` to undo."
            )
        except Exception as e:
            return _error(str(e))

    @mcp.tool(
        name="session_restore",
        annotations={
            "title": "Restore Archived Session",
            "readOnlyHint": False,
            "destructiveHint": False,
            "idempotentHint": True,
            "openWorldHint": False,
        },
    )
    async def session_restore(params: SessionArchiveInput) -> str:
        """
        Restore an archived session, making it active again.

        Args:
            params.session_id: Session ID to restore.
        """
        try:
            found = await set_session_archived(params.session_id, archived=False)
            if not found:
                return _error(f"Session '{params.session_id}' not found.")
            return f"Session `{params.session_id}` restored from archive."
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
