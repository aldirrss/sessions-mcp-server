"""
Configuration loaded from environment variables.
All sensitive values must be set via .env or system env — never hardcoded.
"""

import os
import secrets
from typing import Optional


def _require(key: str) -> str:
    value = os.environ.get(key)
    if not value:
        raise RuntimeError(f"Required environment variable '{key}' is not set.")
    return value


# MCP server
MCP_HOST: str = os.environ.get("MCP_HOST", "0.0.0.0")
MCP_PORT: int = int(os.environ.get("MCP_PORT", "8765"))

# API key — required, used to authenticate claude.ai web requests
MCP_API_KEY: str = _require("MCP_API_KEY")

# Docker Compose projects base directory on this host
# Each subdirectory is treated as a separate compose project.
COMPOSE_BASE_DIR: str = os.environ.get("COMPOSE_BASE_DIR", "/opt/stacks")

# Hard limit on log lines returned per request
LOG_MAX_LINES: int = int(os.environ.get("LOG_MAX_LINES", "200"))

# Timeout (seconds) for docker CLI subprocesses
DOCKER_TIMEOUT: int = int(os.environ.get("DOCKER_TIMEOUT", "60"))
