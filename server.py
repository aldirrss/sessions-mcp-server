#!/usr/bin/env python3
"""
lm-mcp-ai — MCP Server: Docker management + Claude session continuity.

Transport : Streamable HTTP  (connects to claude.ai web and Claude Code CLI)
Auth      : Two accepted methods (checked in order):
            1. X-API-Key header        → for Claude Code CLI / curl
            2. ?key= query parameter   → for claude.ai web connector
               URL: https://mcp.yourdomain.com/mcp?key=YOUR_API_KEY
"""

import json
import logging
import sys
from typing import Optional

import config

# Monkey-patch TransportSecurityMiddleware BEFORE FastMCP is imported.
# validate_request returning None means "request is valid, continue".
# Safe because nginx enforces TLS and ApiKeyMiddleware handles auth.
import mcp.server.transport_security as _ts

async def _validate_all(self, request, is_post=False):
    return None

_ts.TransportSecurityMiddleware.validate_request = _validate_all

from mcp.server.fastmcp import FastMCP
from pydantic import BaseModel, Field, field_validator, ConfigDict
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import Response

import db
import docker_client
import session_store as ss

# ---------------------------------------------------------------------------
# Logging — use stderr so stdout stays clean for MCP protocol
# ---------------------------------------------------------------------------

logging.basicConfig(
    stream=sys.stderr,
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)
_logger = logging.getLogger("lm-mcp-ai")


# ---------------------------------------------------------------------------
# Auth middleware
# ---------------------------------------------------------------------------

class ApiKeyMiddleware(BaseHTTPMiddleware):
    """
    Enforce API key only on /mcp path.
    All other paths (OAuth discovery, well-known, health) pass through freely
    so claude.ai can complete its OAuth probe before falling back to key auth.

    Accepted key locations (checked in order):
      1. X-API-Key header  — Claude Code CLI / curl
      2. ?key= query param — claude.ai web connector (no header UI support)
    """

    _OPEN_PREFIXES = (
        "/.well-known/",
        "/health",
        "/register",
        "/oauth",
    )

    async def dispatch(self, request: Request, call_next) -> Response:
        path = request.url.path

        for prefix in self._OPEN_PREFIXES:
            if path.startswith(prefix):
                return await call_next(request)

        if not (path.startswith("/mcp") or path == "/"):
            return await call_next(request)

        api_key = (
            request.headers.get("X-API-Key")
            or request.headers.get("x-api-key")
        )

        if not api_key:
            api_key = request.query_params.get("key")

        if api_key != config.MCP_API_KEY:
            _logger.warning("Unauthorized /mcp request from %s", request.client)
            return Response(
                content=json.dumps({"error": "Unauthorized"}),
                status_code=401,
                media_type="application/json",
            )
        return await call_next(request)


# ---------------------------------------------------------------------------
# FastMCP server
# ---------------------------------------------------------------------------

mcp = FastMCP("lm-mcp-ai", lifespan=db.lifespan)


# ---------------------------------------------------------------------------
# Pydantic models — Docker
# ---------------------------------------------------------------------------

class StackInput(BaseModel):
    model_config = ConfigDict(str_strip_whitespace=True, extra="forbid")
    project: str = Field(
        ...,
        description="Docker Compose project name (alphanumeric, dash, underscore, dot only). "
                    "Must match an existing directory under COMPOSE_BASE_DIR.",
        min_length=1,
        max_length=64,
    )

    @field_validator("project")
    @classmethod
    def validate_project(cls, v: str) -> str:
        import re
        if not re.fullmatch(r'[a-zA-Z0-9_\-\.]+', v):
            raise ValueError("project name contains invalid characters")
        return v


class StackServiceInput(StackInput):
    service: Optional[str] = Field(
        default=None,
        description="Specific service name within the compose project. "
                    "Leave empty to target all services.",
        max_length=64,
    )

    @field_validator("service")
    @classmethod
    def validate_service(cls, v: Optional[str]) -> Optional[str]:
        if v is None:
            return v
        import re
        if not re.fullmatch(r'[a-zA-Z0-9_\-\.]+', v):
            raise ValueError("service name contains invalid characters")
        return v


class StackLogsInput(StackServiceInput):
    tail: int = Field(
        default=100,
        description=f"Number of log lines to return (max {config.LOG_MAX_LINES}).",
        ge=1,
        le=500,
    )


class StackDownInput(StackInput):
    remove_volumes: bool = Field(
        default=False,
        description="If true, also remove named volumes declared in the compose file. "
                    "WARNING: this is destructive and irreversible.",
    )


class ContainerListInput(BaseModel):
    model_config = ConfigDict(extra="forbid")
    all_containers: bool = Field(
        default=False,
        description="If true, include stopped containers as well.",
    )


class ContainerInput(BaseModel):
    model_config = ConfigDict(str_strip_whitespace=True, extra="forbid")
    container: str = Field(
        ...,
        description="Container name or ID (alphanumeric, dash, underscore, dot only).",
        min_length=1,
        max_length=128,
    )

    @field_validator("container")
    @classmethod
    def validate_container(cls, v: str) -> str:
        import re
        if not re.fullmatch(r'[a-zA-Z0-9_\-\.]+', v):
            raise ValueError("container name contains invalid characters")
        return v


class ExecInput(ContainerInput):
    command: list[str] = Field(
        ...,
        description="Command to execute inside the container as a list of tokens. "
                    "Example: ['cat', '/etc/os-release']. No shell expansion is performed.",
        min_length=1,
        max_length=20,
    )


# ---------------------------------------------------------------------------
# Pydantic models — Session Store
# ---------------------------------------------------------------------------

class SessionWriteInput(BaseModel):
    model_config = ConfigDict(str_strip_whitespace=True, extra="forbid")
    session_id: str = Field(
        ...,
        description="Unique session identifier (letters, digits, hyphens, underscores). "
                    "Example: 'feat-auth-dev', 'odoo-refactor-2026'.",
        min_length=1,
        max_length=100,
    )
    title: str = Field(
        ...,
        description="Short human-readable title for the session.",
        min_length=1,
        max_length=200,
    )
    context: str = Field(
        ...,
        description="Full context to store: current state, goals, decisions, next steps. "
                    "This is the main body that will be read when resuming the session.",
        min_length=1,
    )
    source: str = Field(
        default="unknown",
        description="Origin client: 'web', 'cli', 'vscode', or any identifier.",
        max_length=50,
    )
    tags: Optional[list[str]] = Field(
        default=None,
        description="Optional list of tags for filtering (e.g. ['odoo', 'backend']).",
    )

    @field_validator("session_id")
    @classmethod
    def validate_id(cls, v: str) -> str:
        ss.validate_session_id(v)
        return v


class SessionReadInput(BaseModel):
    model_config = ConfigDict(str_strip_whitespace=True, extra="forbid")
    session_id: str = Field(..., description="Session ID to read.", min_length=1, max_length=100)

    @field_validator("session_id")
    @classmethod
    def validate_id(cls, v: str) -> str:
        ss.validate_session_id(v)
        return v


class SessionAppendInput(BaseModel):
    model_config = ConfigDict(str_strip_whitespace=True, extra="forbid")
    session_id: str = Field(..., description="Session ID to append the note to.", min_length=1, max_length=100)
    content: str = Field(..., description="Note content to append (progress update, decision, blocker, etc.).", min_length=1)
    source: str = Field(
        default="unknown",
        description="Origin client: 'web', 'cli', 'vscode'.",
        max_length=50,
    )

    @field_validator("session_id")
    @classmethod
    def validate_id(cls, v: str) -> str:
        ss.validate_session_id(v)
        return v


class SessionDeleteInput(BaseModel):
    model_config = ConfigDict(str_strip_whitespace=True, extra="forbid")
    session_id: str = Field(..., description="Session ID to delete.", min_length=1, max_length=100)

    @field_validator("session_id")
    @classmethod
    def validate_id(cls, v: str) -> str:
        ss.validate_session_id(v)
        return v


class SessionListInput(BaseModel):
    model_config = ConfigDict(extra="forbid")
    tag: Optional[str] = Field(default=None, description="Filter sessions by tag. Omit to list all.")


class SessionSearchInput(BaseModel):
    model_config = ConfigDict(str_strip_whitespace=True, extra="forbid")
    query: str = Field(..., description="Keyword to search across title, context, notes, and tags.", min_length=1)


# ---------------------------------------------------------------------------
# Error helper
# ---------------------------------------------------------------------------

def _error(msg: str) -> str:
    _logger.error(msg)
    return f"Error: {msg}"


# ===========================================================================
# Tools — Docker (READ-ONLY)
# ===========================================================================

@mcp.tool(
    name="docker_list_stacks",
    annotations={
        "title": "List Docker Compose Stacks",
        "readOnlyHint": True,
        "destructiveHint": False,
        "idempotentHint": True,
        "openWorldHint": False,
    },
)
async def docker_list_stacks() -> str:
    """
    List all Docker Compose stacks known to this host.

    Returns a Markdown table with each stack's name, status, and compose file path.
    Uses `docker compose ls --all` under the hood.
    """
    try:
        stacks = await docker_client.list_stacks()
        if not stacks:
            return "No Docker Compose stacks found on this host."
        lines = ["| Name | Status | Config Files |", "|------|--------|--------------|"]
        for s in stacks:
            lines.append(f"| {s.get('Name', '-')} | {s.get('Status', '-')} | {s.get('ConfigFiles', '-')} |")
        return "\n".join(lines)
    except Exception as e:
        return _error(str(e))


@mcp.tool(
    name="docker_stack_ps",
    annotations={
        "title": "List Containers in Stack",
        "readOnlyHint": True,
        "destructiveHint": False,
        "idempotentHint": True,
        "openWorldHint": False,
    },
)
async def docker_stack_ps(params: StackInput) -> str:
    """
    List all containers in a Docker Compose stack with their current state.

    Args:
        params.project: Compose project name.
    """
    try:
        containers = await docker_client.stack_ps(params.project)
        if not containers:
            return f"No containers found for project '{params.project}'."
        lines = [
            f"## Stack: {params.project}", "",
            "| Name | Image | Status | Ports |",
            "|------|-------|--------|-------|",
        ]
        for c in containers:
            ports = c.get("Publishers", [])
            port_str = ", ".join(
                f"{p.get('PublishedPort', '?')}→{p.get('TargetPort', '?')}/{p.get('Protocol', 'tcp')}"
                for p in ports if p.get("PublishedPort")
            ) or "-"
            lines.append(f"| {c.get('Name', '-')} | {c.get('Image', '-')} | {c.get('Status', '-')} | {port_str} |")
        return "\n".join(lines)
    except Exception as e:
        return _error(str(e))


@mcp.tool(
    name="docker_stack_logs",
    annotations={
        "title": "Get Stack Logs",
        "readOnlyHint": True,
        "destructiveHint": False,
        "idempotentHint": True,
        "openWorldHint": False,
    },
)
async def docker_stack_logs(params: StackLogsInput) -> str:
    """
    Retrieve recent log output from a Docker Compose stack or a specific service.

    Args:
        params.project: Compose project name.
        params.service: Specific service to fetch logs from. Omit for all.
        params.tail: Number of lines to return (default 100, max 500).
    """
    try:
        logs = await docker_client.stack_logs(params.project, service=params.service, tail=params.tail)
        if not logs.strip():
            target = f"{params.project}/{params.service}" if params.service else params.project
            return f"No log output for '{target}'."
        return logs
    except Exception as e:
        return _error(str(e))


@mcp.tool(
    name="docker_list_containers",
    annotations={
        "title": "List All Docker Containers",
        "readOnlyHint": True,
        "destructiveHint": False,
        "idempotentHint": True,
        "openWorldHint": False,
    },
)
async def docker_list_containers(params: ContainerListInput) -> str:
    """
    List Docker containers on this host.

    Args:
        params.all_containers: Include stopped containers if true (default: false).
    """
    try:
        containers = await docker_client.list_containers(params.all_containers)
        if not containers:
            return "No containers found."
        lines = ["| Name | Image | Status | Ports |", "|------|-------|--------|-------|"]
        for c in containers:
            lines.append(f"| {c.get('Names', '-')} | {c.get('Image', '-')} | {c.get('Status', '-')} | {c.get('Ports', '-')} |")
        return "\n".join(lines)
    except Exception as e:
        return _error(str(e))


@mcp.tool(
    name="docker_inspect_container",
    annotations={
        "title": "Inspect Container",
        "readOnlyHint": True,
        "destructiveHint": False,
        "idempotentHint": True,
        "openWorldHint": False,
    },
)
async def docker_inspect_container(params: ContainerInput) -> str:
    """
    Return low-level JSON information about a container (like `docker inspect`).

    Args:
        params.container: Container name or ID.
    """
    try:
        data = await docker_client.inspect_container(params.container)
        return json.dumps(data, indent=2)
    except Exception as e:
        return _error(str(e))


@mcp.tool(
    name="docker_stats",
    annotations={
        "title": "Container Resource Usage Snapshot",
        "readOnlyHint": True,
        "destructiveHint": False,
        "idempotentHint": True,
        "openWorldHint": False,
    },
)
async def docker_stats() -> str:
    """
    Return a one-shot CPU, memory, and network usage snapshot for all running containers.

    Uses `docker stats --no-stream`. Does NOT stream — returns current values only.
    """
    try:
        stats = await docker_client.docker_stats_snapshot()
        if not stats:
            return "No running containers found."
        lines = [
            "| Container | CPU % | Mem Usage | Mem % | Net I/O | Block I/O |",
            "|-----------|-------|-----------|-------|---------|-----------|",
        ]
        for s in stats:
            lines.append(
                f"| {s.get('Name', '-')} | {s.get('CPUPerc', '-')} | {s.get('MemUsage', '-')} "
                f"| {s.get('MemPerc', '-')} | {s.get('NetIO', '-')} | {s.get('BlockIO', '-')} |"
            )
        return "\n".join(lines)
    except Exception as e:
        return _error(str(e))


# ===========================================================================
# Tools — Docker (WRITE / LIFECYCLE)
# ===========================================================================

@mcp.tool(
    name="docker_stack_up",
    annotations={
        "title": "Start Compose Stack",
        "readOnlyHint": False,
        "destructiveHint": False,
        "idempotentHint": True,
        "openWorldHint": False,
    },
)
async def docker_stack_up(params: StackServiceInput) -> str:
    """
    Start a Docker Compose stack (or a specific service) in detached mode.

    Args:
        params.project: Compose project name.
        params.service: Start only this service. Omit to start all.
    """
    try:
        out = await docker_client.stack_up(params.project, service=params.service)
        target = f"{params.project}/{params.service}" if params.service else params.project
        return f"Started '{target}'.\n\n```\n{out}\n```"
    except Exception as e:
        return _error(str(e))


@mcp.tool(
    name="docker_stack_down",
    annotations={
        "title": "Stop Compose Stack",
        "readOnlyHint": False,
        "destructiveHint": True,
        "idempotentHint": False,
        "openWorldHint": False,
    },
)
async def docker_stack_down(params: StackDownInput) -> str:
    """
    Stop and remove containers for a Docker Compose stack.

    Args:
        params.project: Compose project name.
        params.remove_volumes: Also remove named volumes (default: false). IRREVERSIBLE.
    """
    try:
        out = await docker_client.stack_down(params.project, remove_volumes=params.remove_volumes)
        vol_note = " (volumes removed)" if params.remove_volumes else ""
        return f"Stopped '{params.project}'{vol_note}.\n\n```\n{out}\n```"
    except Exception as e:
        return _error(str(e))


@mcp.tool(
    name="docker_stack_restart",
    annotations={
        "title": "Restart Compose Stack or Service",
        "readOnlyHint": False,
        "destructiveHint": False,
        "idempotentHint": False,
        "openWorldHint": False,
    },
)
async def docker_stack_restart(params: StackServiceInput) -> str:
    """
    Restart all services (or one) in a Docker Compose stack.

    Args:
        params.project: Compose project name.
        params.service: Restart only this service. Omit to restart all.
    """
    try:
        out = await docker_client.stack_restart(params.project, service=params.service)
        target = f"{params.project}/{params.service}" if params.service else params.project
        return f"Restarted '{target}'.\n\n```\n{out}\n```"
    except Exception as e:
        return _error(str(e))


@mcp.tool(
    name="docker_stack_pull",
    annotations={
        "title": "Pull Latest Images for Stack",
        "readOnlyHint": False,
        "destructiveHint": False,
        "idempotentHint": True,
        "openWorldHint": True,
    },
)
async def docker_stack_pull(params: StackServiceInput) -> str:
    """
    Pull the latest Docker images for a compose stack or specific service.

    Args:
        params.project: Compose project name.
        params.service: Pull only this service's image. Omit for all.
    """
    try:
        out = await docker_client.stack_pull(params.project, service=params.service)
        target = f"{params.project}/{params.service}" if params.service else params.project
        return f"Pulled images for '{target}'.\n\n```\n{out}\n```"
    except Exception as e:
        return _error(str(e))


@mcp.tool(
    name="docker_exec",
    annotations={
        "title": "Execute Command in Container",
        "readOnlyHint": False,
        "destructiveHint": True,
        "idempotentHint": False,
        "openWorldHint": False,
    },
)
async def docker_exec(params: ExecInput) -> str:
    """
    Execute a command inside a running container.

    The command is passed as a list of tokens — no shell expansion occurs.

    Args:
        params.container: Container name or ID.
        params.command: Command tokens to execute (max 20 tokens).
    """
    try:
        out = await docker_client.container_exec(params.container, params.command)
        cmd_str = " ".join(params.command)
        return f"```\n# {params.container}: {cmd_str}\n{out}\n```"
    except Exception as e:
        return _error(str(e))


# ===========================================================================
# Tools — Session Context Store
# ===========================================================================

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

    Returns:
        Confirmation with session summary.
    """
    try:
        session = await ss.write_session(
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

    Returns:
        Full session context including notes history.
    """
    try:
        session = await ss.read_session(params.session_id)
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

    Returns:
        Markdown table of sessions with ID, title, source, tags, note count, and last update.
    """
    try:
        sessions = await ss.list_sessions(tag=params.tag)
        stats = await ss.get_stats()

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

    Returns:
        Confirmation with note count.
    """
    try:
        session = await ss.append_note(params.session_id, params.content, source=params.source)
        note_count = len(session["notes"])
        return (
            f"Note appended to `{params.session_id}` (total notes: {note_count}).\n"
            f"**Timestamp:** {session['notes'][-1]['timestamp']} | **Source:** {params.source}"
        )
    except FileNotFoundError:
        return _error(f"Session '{params.session_id}' not found. Use session_write to create it first.")
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

    Returns:
        Confirmation or not-found message.
    """
    try:
        deleted = await ss.delete_session(params.session_id)
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

    Returns:
        List of matching sessions with a context snippet.
    """
    try:
        results = await ss.search_sessions(params.query)
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


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    import uvicorn

    _logger.info(
        "Starting lm-mcp-ai on %s:%d (streamable_http)",
        config.MCP_HOST,
        config.MCP_PORT,
    )

    from mcp.server.transport_security import TransportSecurityMiddleware, TransportSecuritySettings

    app = mcp.streamable_http_app()

    _disabled = TransportSecuritySettings(enable_dns_rebinding_protection=False)

    def _patch_transport_security(obj, depth: int = 0) -> bool:
        if depth > 15:
            return False
        if isinstance(obj, TransportSecurityMiddleware):
            obj.settings = _disabled
            _logger.info("TransportSecurityMiddleware: DNS rebinding protection disabled")
            return True
        for attr in ("app", "_app", "middleware", "handler"):
            child = getattr(obj, attr, None)
            if child is not None and _patch_transport_security(child, depth + 1):
                return True
        if hasattr(obj, "__dict__"):
            for child in obj.__dict__.values():
                if child is not obj and _patch_transport_security(child, depth + 1):
                    return True
        return False

    if not _patch_transport_security(app):
        _logger.warning(
            "Could not locate TransportSecurityMiddleware — "
            "requests with external Host headers may return 421"
        )

    app.add_middleware(ApiKeyMiddleware)

    uvicorn.run(
        app,
        host=config.MCP_HOST,
        port=config.MCP_PORT,
    )
