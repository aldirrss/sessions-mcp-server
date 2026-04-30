import json
import logging

from mcp.server.fastmcp import FastMCP

from .client import (
    list_stacks,
    stack_ps,
    stack_logs,
    stack_up,
    stack_down,
    stack_restart,
    stack_pull,
    list_containers,
    inspect_container,
    container_exec,
    docker_stats_snapshot,
)
from .models import (
    StackInput,
    StackServiceInput,
    StackLogsInput,
    StackDownInput,
    ContainerListInput,
    ContainerInput,
    ExecInput,
)

_logger = logging.getLogger("lm-mcp-ai.docker")


def _error(msg: str) -> str:
    _logger.error(msg)
    return f"Error: {msg}"


def register(mcp: FastMCP) -> None:
    """Register all Docker tools on the given FastMCP instance."""

    # -----------------------------------------------------------------------
    # Read-only tools
    # -----------------------------------------------------------------------

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
            stacks = await list_stacks()
            if not stacks:
                return "No Docker Compose stacks found on this host."
            lines = ["| Name | Status | Config Files |", "|------|--------|--------------|"]
            for s in stacks:
                lines.append(
                    f"| {s.get('Name', '-')} | {s.get('Status', '-')} | {s.get('ConfigFiles', '-')} |"
                )
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
            containers = await stack_ps(params.project)
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
                lines.append(
                    f"| {c.get('Name', '-')} | {c.get('Image', '-')} | {c.get('Status', '-')} | {port_str} |"
                )
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
            logs = await stack_logs(params.project, service=params.service, tail=params.tail)
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
            containers = await list_containers(params.all_containers)
            if not containers:
                return "No containers found."
            lines = ["| Name | Image | Status | Ports |", "|------|-------|--------|-------|"]
            for c in containers:
                lines.append(
                    f"| {c.get('Names', '-')} | {c.get('Image', '-')} "
                    f"| {c.get('Status', '-')} | {c.get('Ports', '-')} |"
                )
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
            data = await inspect_container(params.container)
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
            stats = await docker_stats_snapshot()
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

    # -----------------------------------------------------------------------
    # Write / lifecycle tools
    # -----------------------------------------------------------------------

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
            out = await stack_up(params.project, service=params.service)
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
            out = await stack_down(params.project, remove_volumes=params.remove_volumes)
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
            out = await stack_restart(params.project, service=params.service)
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
            out = await stack_pull(params.project, service=params.service)
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
            out = await container_exec(params.container, params.command)
            cmd_str = " ".join(params.command)
            return f"```\n# {params.container}: {cmd_str}\n{out}\n```"
        except Exception as e:
            return _error(str(e))
