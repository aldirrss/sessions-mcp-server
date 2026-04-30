#!/usr/bin/env python3
"""
lm-docker-mcp — MCP Server for Docker Compose management on VPS.

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

from mcp.server.fastmcp import FastMCP
from pydantic import BaseModel, Field, field_validator, ConfigDict
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import Response

import docker_client

# ---------------------------------------------------------------------------
# Logging — use stderr so stdout stays clean for MCP protocol
# ---------------------------------------------------------------------------

logging.basicConfig(
    stream=sys.stderr,
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)
_logger = logging.getLogger("lm-docker-mcp")


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

    # Paths that must be reachable without auth (OAuth discovery by claude.ai)
    _OPEN_PREFIXES = (
        "/.well-known/",
        "/health",
        "/register",
        "/oauth",
    )

    async def dispatch(self, request: Request, call_next) -> Response:
        path = request.url.path

        # Let OAuth discovery and health checks through without auth
        for prefix in self._OPEN_PREFIXES:
            if path.startswith(prefix):
                return await call_next(request)

        # Only enforce auth on /mcp and root / (MCP clients may POST to either)
        if not (path.startswith("/mcp") or path == "/"):
            return await call_next(request)

        # Method 1: header
        api_key = (
            request.headers.get("X-API-Key")
            or request.headers.get("x-api-key")
        )

        # Method 2: query parameter (claude.ai web connector)
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

mcp = FastMCP("docker_mcp")


# ---------------------------------------------------------------------------
# Pydantic input models
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
# Error helper
# ---------------------------------------------------------------------------

def _error(msg: str) -> str:
    _logger.error(msg)
    return f"Error: {msg}"


# ---------------------------------------------------------------------------
# Tools — READ-ONLY
# ---------------------------------------------------------------------------

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

    Returns:
        str: Markdown table of stacks, or a message if none are found.
    """
    try:
        stacks = await docker_client.list_stacks()
        if not stacks:
            return "No Docker Compose stacks found on this host."

        lines = ["| Name | Status | Config Files |", "|------|--------|--------------|"]
        for s in stacks:
            name = s.get("Name", "-")
            status = s.get("Status", "-")
            config_files = s.get("ConfigFiles", "-")
            lines.append(f"| {name} | {status} | {config_files} |")
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

    Shows container name, image, status, and port bindings for each service.

    Args:
        params (StackInput):
            - project (str): Compose project name.

    Returns:
        str: Markdown table of containers in the stack.
    """
    try:
        containers = await docker_client.stack_ps(params.project)
        if not containers:
            return f"No containers found for project '{params.project}'."

        lines = [
            f"## Stack: {params.project}",
            "",
            "| Name | Image | Status | Ports |",
            "|------|-------|--------|-------|",
        ]
        for c in containers:
            name = c.get("Name", "-")
            image = c.get("Image", "-")
            status = c.get("Status", "-")
            ports = c.get("Publishers", [])
            port_str = ", ".join(
                f"{p.get('PublishedPort', '?')}→{p.get('TargetPort', '?')}/{p.get('Protocol', 'tcp')}"
                for p in ports if p.get("PublishedPort")
            ) or "-"
            lines.append(f"| {name} | {image} | {status} | {port_str} |")
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
        params (StackLogsInput):
            - project (str): Compose project name.
            - service (Optional[str]): Specific service to fetch logs from. Omit for all.
            - tail (int): Number of lines to return (default 100, max 200).

    Returns:
        str: Raw log output from the container(s).
    """
    try:
        logs = await docker_client.stack_logs(
            params.project,
            service=params.service,
            tail=params.tail,
        )
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
        params (ContainerListInput):
            - all_containers (bool): Include stopped containers if true (default: false).

    Returns:
        str: Markdown table of container name, image, status, and ports.
    """
    try:
        containers = await docker_client.list_containers(params.all_containers)
        if not containers:
            return "No containers found."

        lines = ["| Name | Image | Status | Ports |", "|------|-------|--------|-------|"]
        for c in containers:
            name = c.get("Names", "-")
            image = c.get("Image", "-")
            status = c.get("Status", "-")
            ports = c.get("Ports", "-")
            lines.append(f"| {name} | {image} | {status} | {ports} |")
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

    Useful for diagnosing network, volume, environment, and health configuration.

    Args:
        params (ContainerInput):
            - container (str): Container name or ID.

    Returns:
        str: JSON-formatted container inspection data.
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

    Returns:
        str: Markdown table with resource usage per container.
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
            name = s.get("Name", "-")
            cpu = s.get("CPUPerc", "-")
            mem_usage = s.get("MemUsage", "-")
            mem_perc = s.get("MemPerc", "-")
            net_io = s.get("NetIO", "-")
            block_io = s.get("BlockIO", "-")
            lines.append(f"| {name} | {cpu} | {mem_usage} | {mem_perc} | {net_io} | {block_io} |")
        return "\n".join(lines)
    except Exception as e:
        return _error(str(e))


# ---------------------------------------------------------------------------
# Tools — WRITE / LIFECYCLE
# ---------------------------------------------------------------------------

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

    Equivalent to `docker compose -p <project> up -d [service]`.

    Args:
        params (StackServiceInput):
            - project (str): Compose project name.
            - service (Optional[str]): Start only this service. Omit to start all.

    Returns:
        str: Output from docker compose up.
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

    Equivalent to `docker compose -p <project> down [-v]`.

    Args:
        params (StackDownInput):
            - project (str): Compose project name.
            - remove_volumes (bool): Also remove named volumes (default: false). IRREVERSIBLE.

    Returns:
        str: Output from docker compose down.
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

    Equivalent to `docker compose -p <project> restart [service]`.

    Args:
        params (StackServiceInput):
            - project (str): Compose project name.
            - service (Optional[str]): Restart only this service. Omit to restart all.

    Returns:
        str: Output from docker compose restart.
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

    Equivalent to `docker compose -p <project> pull [service]`.
    Does NOT restart containers — use docker_stack_restart after pulling.

    Args:
        params (StackServiceInput):
            - project (str): Compose project name.
            - service (Optional[str]): Pull only this service's image. Omit for all.

    Returns:
        str: Output from docker compose pull.
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
    This prevents injection attacks.

    Examples of safe usage:
        - command: ["cat", "/etc/os-release"]
        - command: ["python", "-c", "import sys; print(sys.version)"]
        - command: ["ls", "-la", "/var/log"]

    Args:
        params (ExecInput):
            - container (str): Container name or ID.
            - command (list[str]): Command tokens to execute (max 20 tokens).

    Returns:
        str: stdout output from the command.
    """
    try:
        out = await docker_client.container_exec(params.container, params.command)
        cmd_str = " ".join(params.command)
        return f"```\n# {params.container}: {cmd_str}\n{out}\n```"
    except Exception as e:
        return _error(str(e))


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    import uvicorn

    _logger.info(
        "Starting lm-docker-mcp on %s:%d (streamable_http)",
        config.MCP_HOST,
        config.MCP_PORT,
    )

    # Disable DNS rebinding protection — we run behind a trusted reverse proxy
    # (nginx) that enforces TLS and rewrites Host. Auth is handled by
    # ApiKeyMiddleware. Leaving protection ON with empty allowed_hosts blocks
    # every request including localhost.
    from mcp.server.transport_security import TransportSecurityMiddleware, TransportSecuritySettings

    # Get the Starlette ASGI app from FastMCP, then attach middleware to it.
    app = mcp.streamable_http_app()

    # Disable DNS rebinding protection by patching the TransportSecurityMiddleware
    # instance that FastMCP embeds in the app. We run behind a trusted nginx proxy
    # (with Host rewrite to localhost) so this protection is redundant and
    # conflicts with reverse-proxy deployments.
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
