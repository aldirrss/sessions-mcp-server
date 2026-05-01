import logging

from mcp.server.fastmcp import FastMCP

from .store import read_config, write_config, delete_config, list_config
from .models import ConfigWriteInput, ConfigReadInput, ConfigDeleteInput, ConfigListInput

_logger = logging.getLogger("lm-mcp-ai.config")


def _error(msg: str) -> str:
    _logger.error(msg)
    return f"Error: {msg}"


def register(mcp: FastMCP) -> None:
    """Register all config tools on the given FastMCP instance."""

    @mcp.tool(
        name="config_write",
        annotations={
            "title": "Write Config",
            "readOnlyHint": False,
            "destructiveHint": False,
            "idempotentHint": True,
            "openWorldHint": False,
        },
    )
    async def config_write(params: ConfigWriteInput) -> str:
        """
        Create or update a configuration entry.

        Config keys control Claude behavior across all sessions. Common keys:
        - claude_project_instructions: Additional instructions loaded at conversation start.
        - claude_response_language: Preferred response language override.
        - vacuum_notes_days: Days before notes are auto-deleted (Ide 4).
        - vacuum_sessions_days: Days before inactive sessions are archived (Ide 4).

        Args:
            params.key: Config key (use snake_case, descriptive prefixes).
            params.value: Value to store.
            params.description: What this config controls (optional, preserved if omitted).
        """
        try:
            entry = await write_config(params.key, params.value, params.description)
            return (
                f"Config `{entry['key']}` saved.\n"
                f"**Value:** {entry['value']}\n"
                f"**Description:** {entry['description'] or '(none)'}\n"
                f"**Updated:** {entry['updated_at']}"
            )
        except Exception as e:
            return _error(str(e))

    @mcp.tool(
        name="config_read",
        annotations={
            "title": "Read Config",
            "readOnlyHint": True,
            "destructiveHint": False,
            "idempotentHint": True,
            "openWorldHint": False,
        },
    )
    async def config_read(params: ConfigReadInput) -> str:
        """
        Read a single config entry by key.

        Args:
            params.key: Config key to read.
        """
        try:
            entry = await read_config(params.key)
            if entry is None:
                return f"Config key `{params.key}` not found."
            return (
                f"**Key:** `{entry['key']}`\n"
                f"**Value:** {entry['value']}\n"
                f"**Description:** {entry['description'] or '(none)'}\n"
                f"**Updated:** {entry['updated_at']}"
            )
        except Exception as e:
            return _error(str(e))

    @mcp.tool(
        name="config_list",
        annotations={
            "title": "List Config",
            "readOnlyHint": True,
            "destructiveHint": False,
            "idempotentHint": True,
            "openWorldHint": False,
        },
    )
    async def config_list(params: ConfigListInput) -> str:
        """
        List all config entries, optionally filtered by key prefix.

        Call this at the start of each conversation to load any dynamic
        project instructions stored in the database.

        Args:
            params.prefix: Filter keys by prefix (e.g. 'claude_' for all Claude settings).
        """
        try:
            entries = await list_config(prefix=params.prefix)
            if not entries:
                label = f"with prefix '{params.prefix}'" if params.prefix else ""
                return f"No config entries found {label}."

            lines = [
                f"## Config ({len(entries)} entries)",
                "",
                "| Key | Value | Description | Updated |",
                "|-----|-------|-------------|---------|",
            ]
            for e in entries:
                val = e["value"][:60] + "…" if len(e["value"]) > 60 else e["value"]
                desc = e["description"][:40] + "…" if len(e["description"]) > 40 else e["description"]
                lines.append(f"| `{e['key']}` | {val} | {desc or '-'} | {e['updated_at'][:10]} |")
            return "\n".join(lines)
        except Exception as e:
            return _error(str(e))

    @mcp.tool(
        name="config_delete",
        annotations={
            "title": "Delete Config",
            "readOnlyHint": False,
            "destructiveHint": True,
            "idempotentHint": True,
            "openWorldHint": False,
        },
    )
    async def config_delete(params: ConfigDeleteInput) -> str:
        """
        Delete a config entry permanently.

        Args:
            params.key: Config key to delete.
        """
        try:
            deleted = await delete_config(params.key)
            if deleted:
                return f"Config `{params.key}` deleted."
            return f"Config key `{params.key}` not found — nothing deleted."
        except Exception as e:
            return _error(str(e))
