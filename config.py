"""
Configuration loaded from environment variables.
All sensitive values must be set via .env or system env — never hardcoded.
"""

import os


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

# External hostname used by reverse proxy (Cloudflare Tunnel / nginx).
MCP_EXTERNAL_HOST: str = os.environ.get("MCP_EXTERNAL_HOST", "")

# Docker Compose projects base directory on this host
COMPOSE_BASE_DIR: str = os.environ.get("COMPOSE_BASE_DIR", "/opt/stacks")

# Hard limit on log lines returned per request
LOG_MAX_LINES: int = int(os.environ.get("LOG_MAX_LINES", "200"))

# Timeout (seconds) for docker CLI subprocesses
DOCKER_TIMEOUT: int = int(os.environ.get("DOCKER_TIMEOUT", "60"))

# GitHub personal access token (classic or fine-grained)
# Required scopes: repo (full), workflow (for Actions)
# Optional — if not set, GitHub tools will return an error when called
GITHUB_TOKEN: str = os.environ.get("GITHUB_TOKEN", "")

# Default GitHub owner/org — used when repo is passed without owner prefix
# Example: "aldirrss" or "lema-core"
GITHUB_DEFAULT_OWNER: str = os.environ.get("GITHUB_DEFAULT_OWNER", "")