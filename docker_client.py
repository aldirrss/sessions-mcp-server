"""
Async wrapper around the Docker CLI.

All subprocesses use asyncio.create_subprocess_exec (no shell=True)
to prevent command injection. Inputs are validated before reaching here.
"""

import asyncio
import json
import os
import re
import shlex
from pathlib import Path
from typing import Optional

import config


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------

def _safe_name(value: str) -> str:
    """Allow only alphanumeric, dash, underscore, dot in names."""
    if not re.fullmatch(r'[a-zA-Z0-9_\-\.]+', value):
        raise ValueError(f"Invalid characters in name: '{value}'")
    return value


async def _run(
    *args: str,
    cwd: Optional[str] = None,
    timeout: int = config.DOCKER_TIMEOUT,
) -> tuple[int, str, str]:
    """
    Run a subprocess, return (returncode, stdout, stderr).
    Never uses shell=True.
    """
    proc = await asyncio.create_subprocess_exec(
        *args,
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.PIPE,
        cwd=cwd,
    )
    try:
        stdout, stderr = await asyncio.wait_for(proc.communicate(), timeout=timeout)
    except asyncio.TimeoutError:
        proc.kill()
        await proc.communicate()
        return -1, "", f"Command timed out after {timeout}s: {' '.join(args)}"

    return proc.returncode, stdout.decode(), stderr.decode()


def _compose_dir(project: str) -> str:
    """Resolve and validate a compose project directory."""
    _safe_name(project)
    base = Path(config.COMPOSE_BASE_DIR).resolve()
    target = (base / project).resolve()
    if not str(target).startswith(str(base)):
        raise ValueError(f"Path traversal detected for project '{project}'")
    if not target.is_dir():
        raise FileNotFoundError(f"Project directory not found: {target}")
    return str(target)


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

async def list_stacks() -> list[dict]:
    """
    Return all docker compose stacks known to Docker.
    Uses `docker compose ls --format json`.
    """
    code, out, err = await _run("docker", "compose", "ls", "--format", "json", "--all")
    if code != 0:
        raise RuntimeError(f"docker compose ls failed: {err.strip()}")
    try:
        return json.loads(out) if out.strip() else []
    except json.JSONDecodeError:
        return []


async def stack_ps(project: str) -> list[dict]:
    """List containers in a compose project (`docker compose ps --format json`)."""
    cwd = _compose_dir(project)
    code, out, err = await _run(
        "docker", "compose", "-p", project, "ps", "--format", "json",
        cwd=cwd,
    )
    if code != 0:
        raise RuntimeError(f"docker compose ps failed: {err.strip()}")

    # Docker outputs one JSON object per line (not a JSON array)
    results = []
    for line in out.strip().splitlines():
        line = line.strip()
        if line:
            try:
                results.append(json.loads(line))
            except json.JSONDecodeError:
                pass
    return results


async def stack_logs(
    project: str,
    service: Optional[str] = None,
    tail: int = 100,
) -> str:
    """Fetch logs from a compose stack (all services or a specific one)."""
    cwd = _compose_dir(project)
    tail = min(tail, config.LOG_MAX_LINES)

    cmd = ["docker", "compose", "-p", project, "logs", "--no-color", f"--tail={tail}"]
    if service:
        _safe_name(service)
        cmd.append(service)

    code, out, err = await _run(*cmd, cwd=cwd)
    if code != 0:
        raise RuntimeError(f"docker compose logs failed: {err.strip()}")
    return out


async def stack_up(project: str, service: Optional[str] = None) -> str:
    """Start a compose stack (or a single service) in detached mode."""
    cwd = _compose_dir(project)
    cmd = ["docker", "compose", "-p", project, "up", "-d", "--remove-orphans"]
    if service:
        _safe_name(service)
        cmd.append(service)

    code, out, err = await _run(*cmd, cwd=cwd)
    combined = (out + err).strip()
    if code != 0:
        raise RuntimeError(f"docker compose up failed: {combined}")
    return combined


async def stack_down(project: str, remove_volumes: bool = False) -> str:
    """Stop and remove containers for a compose stack."""
    cwd = _compose_dir(project)
    cmd = ["docker", "compose", "-p", project, "down"]
    if remove_volumes:
        cmd.append("-v")

    code, out, err = await _run(*cmd, cwd=cwd)
    combined = (out + err).strip()
    if code != 0:
        raise RuntimeError(f"docker compose down failed: {combined}")
    return combined


async def stack_restart(project: str, service: Optional[str] = None) -> str:
    """Restart all services (or one) in a compose stack."""
    cwd = _compose_dir(project)
    cmd = ["docker", "compose", "-p", project, "restart"]
    if service:
        _safe_name(service)
        cmd.append(service)

    code, out, err = await _run(*cmd, cwd=cwd)
    combined = (out + err).strip()
    if code != 0:
        raise RuntimeError(f"docker compose restart failed: {combined}")
    return combined


async def stack_pull(project: str, service: Optional[str] = None) -> str:
    """Pull latest images for a compose stack (or a specific service)."""
    cwd = _compose_dir(project)
    cmd = ["docker", "compose", "-p", project, "pull"]
    if service:
        _safe_name(service)
        cmd.append(service)

    code, out, err = await _run(*cmd, cwd=cwd)
    combined = (out + err).strip()
    if code != 0:
        raise RuntimeError(f"docker compose pull failed: {combined}")
    return combined


async def list_containers(all_containers: bool = False) -> list[dict]:
    """List Docker containers (`docker ps --format json`)."""
    cmd = ["docker", "ps", "--format", "json"]
    if all_containers:
        cmd.append("-a")

    code, out, err = await _run(*cmd)
    if code != 0:
        raise RuntimeError(f"docker ps failed: {err.strip()}")

    results = []
    for line in out.strip().splitlines():
        line = line.strip()
        if line:
            try:
                results.append(json.loads(line))
            except json.JSONDecodeError:
                pass
    return results


async def inspect_container(container: str) -> dict:
    """Return low-level information about a container (`docker inspect`)."""
    _safe_name(container)
    code, out, err = await _run("docker", "inspect", container)
    if code != 0:
        raise RuntimeError(f"docker inspect failed: {err.strip()}")
    data = json.loads(out)
    return data[0] if data else {}


async def container_exec(container: str, command: list[str]) -> str:
    """
    Execute a command inside a running container.
    The command list is passed directly — no shell expansion.
    """
    _safe_name(container)
    # Validate each command token: only printable ASCII, no shell metacharacters
    for token in command:
        if not re.fullmatch(r'[\x20-\x7E]+', token):
            raise ValueError(f"Invalid characters in command token: '{token}'")

    cmd = ["docker", "exec", container] + command
    code, out, err = await _run(*cmd)
    if code != 0:
        raise RuntimeError(f"docker exec failed (exit {code}): {err.strip()}")
    return out


async def docker_stats_snapshot() -> list[dict]:
    """
    Return a one-shot resource usage snapshot for all running containers.
    Uses `docker stats --no-stream --format json`.
    """
    code, out, err = await _run(
        "docker", "stats", "--no-stream", "--format", "json"
    )
    if code != 0:
        raise RuntimeError(f"docker stats failed: {err.strip()}")

    results = []
    for line in out.strip().splitlines():
        line = line.strip()
        if line:
            try:
                results.append(json.loads(line))
            except json.JSONDecodeError:
                pass
    return results
