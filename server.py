#!/usr/bin/env python3
"""
lm-mcp-ai — MCP Server for Docker Compose management on VPS.

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

import docker_client

# ===========================================================================
# GitHub Tools
# Requires: GITHUB_TOKEN and GITHUB_DEFAULT_OWNER in .env
# ===========================================================================

import github_client as gh
from typing import Optional as Opt

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
# Pydantic models for GitHub tools
# ---------------------------------------------------------------------------

class GHRepoInput(BaseModel):
    model_config = ConfigDict(str_strip_whitespace=True, extra="forbid")
    owner: Opt[str] = Field(default=None, description="GitHub owner (user or org). Falls back to GITHUB_DEFAULT_OWNER if omitted.")
    repo: str = Field(..., description="Repository name (without owner prefix).", min_length=1, max_length=100)


class GHBranchInput(GHRepoInput):
    branch: str = Field(..., description="Branch name.", min_length=1, max_length=255)


class GHFileInput(GHRepoInput):
    path: str = Field(..., description="File path within the repo (e.g. 'src/main.py').", min_length=1)
    ref: Opt[str] = Field(default=None, description="Branch, tag, or commit SHA to read from. Defaults to default branch.")


class GHCreateBranchInput(GHRepoInput):
    new_branch: str = Field(..., description="Name of the new branch to create.", min_length=1, max_length=255)
    from_branch: str = Field(default="main", description="Source branch to branch off from.")


class GHCreateFileInput(GHRepoInput):
    path: str = Field(..., description="File path to create or update (e.g. 'docs/notes.md').")
    content: str = Field(..., description="Full file content as a UTF-8 string.")
    message: str = Field(..., description="Commit message.", min_length=1, max_length=500)
    branch: str = Field(default="main", description="Target branch for the commit.")
    sha: Opt[str] = Field(default=None, description="Current file SHA — required when updating an existing file.")


class GHPRCreateInput(GHRepoInput):
    title: str = Field(..., description="Pull request title.", min_length=1, max_length=255)
    head: str = Field(..., description="Source branch (the branch with your changes).")
    base: str = Field(default="main", description="Target branch to merge into.")
    body: str = Field(default="", description="PR description / body text.")
    draft: bool = Field(default=False, description="Create as draft PR.")


class GHPRMergeInput(GHRepoInput):
    pr_number: int = Field(..., description="Pull request number.", ge=1)
    method: str = Field(default="squash", description="Merge method: 'merge', 'squash', or 'rebase'.")


class GHIssueCreateInput(GHRepoInput):
    title: str = Field(..., description="Issue title.", min_length=1, max_length=255)
    body: str = Field(default="", description="Issue body / description.")
    labels: Opt[list[str]] = Field(default=None, description="List of label names to apply.")


class GHListCommitsInput(GHRepoInput):
    branch: Opt[str] = Field(default=None, description="Filter commits by branch. Defaults to default branch.")
    per_page: int = Field(default=20, description="Number of commits to return.", ge=1, le=100)


class GHWorkflowRunInput(GHRepoInput):
    workflow_id: Opt[str] = Field(default=None, description="Workflow filename (e.g. 'deploy.yml') or numeric ID. Omit to list all runs.")
    per_page: int = Field(default=10, description="Number of runs to return.", ge=1, le=50)


class GHTriggerWorkflowInput(GHRepoInput):
    workflow_id: str = Field(..., description="Workflow filename (e.g. 'deploy.yml') or numeric ID.")
    ref: str = Field(default="main", description="Branch or tag to run the workflow on.")
    inputs: Opt[dict] = Field(default=None, description="Workflow dispatch inputs as key-value pairs.")


class GHListDirInput(GHRepoInput):
    path: str = Field(default="", description="Directory path within the repo. Empty string = root.")
    ref: Opt[str] = Field(default=None, description="Branch, tag, or commit SHA. Defaults to default branch.")


# ---------------------------------------------------------------------------
# Tools — Repository
# ---------------------------------------------------------------------------

@mcp.tool(
    name="github_list_repos",
    annotations={"title": "List GitHub Repositories", "readOnlyHint": True, "destructiveHint": False},
)
async def github_list_repos(
    owner: Opt[str] = None,
    type: str = "all",
    per_page: int = 30,
) -> str:
    """
    List repositories for a GitHub user or organization.

    Args:
        owner: GitHub username or org name. Falls back to GITHUB_DEFAULT_OWNER if omitted.
        type: Filter by 'all', 'public', 'private', 'forks', 'sources', 'member'.
        per_page: Number of repos to return (default 30).
    """
    try:
        repos = await gh.list_repos(owner=owner, type=type, per_page=per_page)
        if not repos:
            return "No repositories found."
        lines = ["| Repo | Visibility | Language | Updated | Stars |",
                 "|------|-----------|----------|---------|-------|"]
        for r in repos:
            lines.append(
                f"| [{r['name']}]({r['html_url']}) "
                f"| {'🔒 private' if r.get('private') else '🌐 public'} "
                f"| {r.get('language') or '-'} "
                f"| {r.get('updated_at', '')[:10]} "
                f"| ⭐ {r.get('stargazers_count', 0)} |"
            )
        return "\n".join(lines)
    except Exception as e:
        return _error(str(e))


# ---------------------------------------------------------------------------
# Tools — Branches
# ---------------------------------------------------------------------------

@mcp.tool(
    name="github_list_branches",
    annotations={"title": "List GitHub Branches", "readOnlyHint": True, "destructiveHint": False},
)
async def github_list_branches(params: GHRepoInput) -> str:
    """List all branches in a repository."""
    try:
        branches = await gh.list_branches(params.owner, params.repo)
        if not branches:
            return f"No branches found in '{params.repo}'."
        lines = [f"## Branches in {params.repo}", ""]
        for b in branches:
            protected = "🔒" if b.get("protected") else "  "
            lines.append(f"- {protected} `{b['name']}` — SHA: `{b['commit']['sha'][:7]}`")
        return "\n".join(lines)
    except Exception as e:
        return _error(str(e))


@mcp.tool(
    name="github_create_branch",
    annotations={"title": "Create GitHub Branch", "readOnlyHint": False, "destructiveHint": False},
)
async def github_create_branch(params: GHCreateBranchInput) -> str:
    """
    Create a new branch from an existing branch.

    Args:
        params.new_branch: Name of the branch to create.
        params.from_branch: Source branch (default: 'main').
    """
    try:
        result = await gh.create_branch(params.owner, params.repo, params.new_branch, params.from_branch)
        sha = result.get("object", {}).get("sha", "")[:7]
        return f"✅ Branch `{params.new_branch}` created from `{params.from_branch}` (SHA: `{sha}`) in `{params.repo}`."
    except Exception as e:
        return _error(str(e))


# ---------------------------------------------------------------------------
# Tools — Files
# ---------------------------------------------------------------------------

@mcp.tool(
    name="github_read_file",
    annotations={"title": "Read File from GitHub", "readOnlyHint": True, "destructiveHint": False},
)
async def github_read_file(params: GHFileInput) -> str:
    """
    Read the content of a file from a GitHub repository.

    Args:
        params.path: File path within the repo (e.g. 'server.py').
        params.ref: Branch, tag, or commit SHA. Defaults to default branch.
    """
    try:
        result = await gh.get_file(params.owner, params.repo, params.path, params.ref)
        ref_note = f" @ `{params.ref}`" if params.ref else ""
        header = f"## `{result['path']}`{ref_note} ({result['size']} bytes)\n\n"
        return header + f"```\n{result['content']}\n```"
    except Exception as e:
        return _error(str(e))


@mcp.tool(
    name="github_list_directory",
    annotations={"title": "List Directory in GitHub Repo", "readOnlyHint": True, "destructiveHint": False},
)
async def github_list_directory(params: GHListDirInput) -> str:
    """
    List files and directories at a given path in a repository.

    Args:
        params.path: Directory path (empty = root).
        params.ref: Branch, tag, or commit SHA.
    """
    try:
        items = await gh.list_directory(params.owner, params.repo, params.path, params.ref)
        if not items:
            return "Directory is empty."
        lines = [f"## `{params.repo}/{params.path or ''}`", ""]
        dirs = [i for i in items if i["type"] == "dir"]
        files = [i for i in items if i["type"] == "file"]
        for d in sorted(dirs, key=lambda x: x["name"]):
            lines.append(f"📁 `{d['name']}/`")
        for f in sorted(files, key=lambda x: x["name"]):
            size = f"{f['size']:,} B" if f["size"] else "-"
            lines.append(f"📄 `{f['name']}` ({size})")
        return "\n".join(lines)
    except Exception as e:
        return _error(str(e))


@mcp.tool(
    name="github_write_file",
    annotations={"title": "Write File to GitHub", "readOnlyHint": False, "destructiveHint": False},
)
async def github_write_file(params: GHCreateFileInput) -> str:
    """
    Create or update a file in a GitHub repository (creates a commit).

    For updates, provide the current file SHA (get it via github_read_file first).
    For new files, leave sha empty.

    Args:
        params.path: File path in the repo.
        params.content: Full file content.
        params.message: Commit message.
        params.branch: Target branch (default: 'main').
        params.sha: Current file SHA (required for updates, omit for new files).
    """
    try:
        result = await gh.create_or_update_file(
            params.owner, params.repo, params.path,
            params.content, params.message, params.branch, params.sha,
        )
        action = "Updated" if params.sha else "Created"
        commit_sha = result.get("commit", {}).get("sha", "")[:7]
        url = result.get("content", {}).get("html_url", "")
        return (
            f"✅ {action} `{params.path}` on branch `{params.branch}`.\n"
            f"Commit: `{commit_sha}` — {params.message}\n"
            f"URL: {url}"
        )
    except Exception as e:
        return _error(str(e))


# ---------------------------------------------------------------------------
# Tools — Commits
# ---------------------------------------------------------------------------

@mcp.tool(
    name="github_list_commits",
    annotations={"title": "List Commits", "readOnlyHint": True, "destructiveHint": False},
)
async def github_list_commits(params: GHListCommitsInput) -> str:
    """
    List recent commits in a repository, optionally filtered by branch.

    Args:
        params.branch: Branch name. Defaults to default branch.
        params.per_page: Number of commits (default 20).
    """
    try:
        commits = await gh.list_commits(params.owner, params.repo, params.branch, params.per_page)
        if not commits:
            return "No commits found."
        branch_note = f" on `{params.branch}`" if params.branch else ""
        lines = [f"## Recent commits in `{params.repo}`{branch_note}", "",
                 "| SHA | Message | Author | Date |",
                 "|-----|---------|--------|------|"]
        for c in commits:
            lines.append(f"| `{c['sha']}` | {c['message'][:60]} | {c['author']} | {c['date'][:10]} |")
        return "\n".join(lines)
    except Exception as e:
        return _error(str(e))


# ---------------------------------------------------------------------------
# Tools — Pull Requests
# ---------------------------------------------------------------------------

@mcp.tool(
    name="github_list_prs",
    annotations={"title": "List Pull Requests", "readOnlyHint": True, "destructiveHint": False},
)
async def github_list_prs(params: GHRepoInput, state: str = "open") -> str:
    """
    List pull requests in a repository.

    Args:
        params: repo and optional owner.
        state: 'open', 'closed', or 'all'.
    """
    try:
        prs = await gh.list_prs(params.owner, params.repo, state)
        if not prs:
            return f"No {state} pull requests found in `{params.repo}`."
        lines = [f"## {state.capitalize()} PRs in `{params.repo}`", "",
                 "| # | Title | Author | Head → Base | Draft |",
                 "|---|-------|--------|-------------|-------|"]
        for pr in prs:
            draft = "✏️" if pr["draft"] else ""
            lines.append(
                f"| [#{pr['number']}]({pr['url']}) "
                f"| {pr['title'][:50]} "
                f"| {pr['author']} "
                f"| `{pr['head']}` → `{pr['base']}` "
                f"| {draft} |"
            )
        return "\n".join(lines)
    except Exception as e:
        return _error(str(e))


@mcp.tool(
    name="github_create_pr",
    annotations={"title": "Create Pull Request", "readOnlyHint": False, "destructiveHint": False},
)
async def github_create_pr(params: GHPRCreateInput) -> str:
    """
    Create a new pull request.

    Args:
        params.title: PR title.
        params.head: Source branch (your feature branch).
        params.base: Target branch (default: 'main').
        params.body: PR description.
        params.draft: Create as draft PR (default: false).
    """
    try:
        pr = await gh.create_pr(
            params.owner, params.repo,
            params.title, params.head, params.base,
            params.body, params.draft,
        )
        draft_note = " (draft)" if pr.get("draft") else ""
        return (
            f"✅ PR #{pr['number']} created{draft_note}: **{pr['title']}**\n"
            f"`{params.head}` → `{params.base}`\n"
            f"URL: {pr['html_url']}"
        )
    except Exception as e:
        return _error(str(e))


@mcp.tool(
    name="github_merge_pr",
    annotations={"title": "Merge Pull Request", "readOnlyHint": False, "destructiveHint": True},
)
async def github_merge_pr(params: GHPRMergeInput) -> str:
    """
    Merge a pull request.

    Args:
        params.pr_number: PR number to merge.
        params.method: 'merge', 'squash', or 'rebase' (default: 'squash').
    """
    try:
        result = await gh.merge_pr(params.owner, params.repo, params.pr_number, params.method)
        sha = result.get("sha", "")[:7]
        return (
            f"✅ PR #{params.pr_number} merged ({params.method}).\n"
            f"Merge commit: `{sha}`\n"
            f"Message: {result.get('message', '')}"
        )
    except Exception as e:
        return _error(str(e))


# ---------------------------------------------------------------------------
# Tools — Issues
# ---------------------------------------------------------------------------

@mcp.tool(
    name="github_list_issues",
    annotations={"title": "List GitHub Issues", "readOnlyHint": True, "destructiveHint": False},
)
async def github_list_issues(params: GHRepoInput, state: str = "open") -> str:
    """
    List issues in a repository (excludes pull requests).

    Args:
        state: 'open', 'closed', or 'all'.
    """
    try:
        issues = await gh.list_issues(params.owner, params.repo, state)
        if not issues:
            return f"No {state} issues found in `{params.repo}`."
        lines = [f"## {state.capitalize()} Issues in `{params.repo}`", "",
                 "| # | Title | Author | Labels | Date |",
                 "|---|-------|--------|--------|------|"]
        for i in issues:
            labels = ", ".join(i["labels"]) or "-"
            lines.append(
                f"| [#{i['number']}]({i['url']}) "
                f"| {i['title'][:50]} "
                f"| {i['author']} "
                f"| {labels} "
                f"| {i['created_at'][:10]} |"
            )
        return "\n".join(lines)
    except Exception as e:
        return _error(str(e))


@mcp.tool(
    name="github_create_issue",
    annotations={"title": "Create GitHub Issue", "readOnlyHint": False, "destructiveHint": False},
)
async def github_create_issue(params: GHIssueCreateInput) -> str:
    """
    Create a new issue in a repository.

    Args:
        params.title: Issue title.
        params.body: Issue description.
        params.labels: List of label names.
    """
    try:
        issue = await gh.create_issue(params.owner, params.repo, params.title, params.body, params.labels)
        return (
            f"✅ Issue #{issue['number']} created: **{issue['title']}**\n"
            f"URL: {issue['html_url']}"
        )
    except Exception as e:
        return _error(str(e))


# ---------------------------------------------------------------------------
# Tools — GitHub Actions
# ---------------------------------------------------------------------------

@mcp.tool(
    name="github_list_workflows",
    annotations={"title": "List GitHub Actions Workflows", "readOnlyHint": True, "destructiveHint": False},
)
async def github_list_workflows(params: GHRepoInput) -> str:
    """List all GitHub Actions workflows in a repository."""
    try:
        workflows = await gh.list_workflows(params.owner, params.repo)
        if not workflows:
            return f"No workflows found in `{params.repo}`."
        lines = [f"## Workflows in `{params.repo}`", ""]
        for w in workflows:
            lines.append(f"- `{w['path']}` — **{w['name']}** (ID: {w['id']}, state: {w['state']})")
        return "\n".join(lines)
    except Exception as e:
        return _error(str(e))


@mcp.tool(
    name="github_list_workflow_runs",
    annotations={"title": "List GitHub Actions Runs", "readOnlyHint": True, "destructiveHint": False},
)
async def github_list_workflow_runs(params: GHWorkflowRunInput) -> str:
    """
    List recent GitHub Actions workflow runs.

    Args:
        params.workflow_id: Workflow filename or ID. Omit to list all runs.
        params.per_page: Number of runs to return (default 10).
    """
    try:
        runs = await gh.list_workflow_runs(params.owner, params.repo, params.workflow_id, params.per_page)
        if not runs:
            return "No workflow runs found."
        lines = ["| Run | Workflow | Status | Branch | Commit | Date |",
                 "|-----|----------|--------|--------|--------|------|"]
        for r in runs:
            status_icon = {"success": "✅", "failure": "❌", "cancelled": "⚠️"}.get(r.get("conclusion") or "", "🔄")
            lines.append(
                f"| [{r['id']}]({r['url']}) "
                f"| {r['name']} "
                f"| {status_icon} {r.get('conclusion') or r['status']} "
                f"| `{r['branch']}` "
                f"| `{r['commit']}` "
                f"| {r['created_at'][:10]} |"
            )
        return "\n".join(lines)
    except Exception as e:
        return _error(str(e))


@mcp.tool(
    name="github_trigger_workflow",
    annotations={"title": "Trigger GitHub Actions Workflow", "readOnlyHint": False, "destructiveHint": False},
)
async def github_trigger_workflow(params: GHTriggerWorkflowInput) -> str:
    """
    Manually trigger a GitHub Actions workflow (workflow_dispatch).

    The workflow must have 'workflow_dispatch' trigger in its YAML.

    Args:
        params.workflow_id: Workflow filename (e.g. 'deploy.yml').
        params.ref: Branch or tag to run on (default: 'main').
        params.inputs: Optional workflow input parameters as dict.
    """
    try:
        ok = await gh.trigger_workflow(params.owner, params.repo, params.workflow_id, params.ref, params.inputs)
        if ok:
            inputs_note = f" with inputs: {params.inputs}" if params.inputs else ""
            return (
                f"✅ Workflow `{params.workflow_id}` triggered on `{params.ref}`{inputs_note}.\n"
                f"Check progress: https://github.com/{params.owner or config.GITHUB_DEFAULT_OWNER}/{params.repo}/actions"
            )
        return _error("Workflow trigger failed — check workflow_id and that 'workflow_dispatch' trigger is configured.")
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
