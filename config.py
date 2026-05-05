"""
Configuration loaded from environment variables.
All sensitive values must be set via .env or system env — never hardcoded.
"""

import os
from urllib.parse import urlparse


def _require(key: str) -> str:
    value = os.environ.get(key)
    if not value:
        raise RuntimeError(f"Required environment variable '{key}' is not set.")
    return value


# MCP server
MCP_HOST: str = os.environ.get("MCP_HOST", "0.0.0.0")
MCP_PORT: int = int(os.environ.get("MCP_PORT", "8765"))

# API key — optional master key for backward compat (bypasses per-user token auth)
MCP_API_KEY: str = os.environ.get("MCP_API_KEY", "")

# External hostname used by reverse proxy (Cloudflare Tunnel / nginx)
MCP_EXTERNAL_HOST: str = os.environ.get("MCP_EXTERNAL_HOST", "")

# PostgreSQL connection string for the session context store
# Format: postgresql://user:password@host:port/dbname
DATABASE_URL: str = _require("DATABASE_URL")

# GitHub personal access token (optional) — enables higher rate limits and private repo access
# Generate at: https://github.com/settings/tokens (scope: repo read-only)
GITHUB_TOKEN: str = os.environ.get("GITHUB_TOKEN", "")

# External base URL of this MCP server — used in OAuth metadata responses
# Example: https://mcp.yourdomain.com
MCP_EXTERNAL_URL: str = os.environ.get("MCP_EXTERNAL_URL", "http://localhost:8765")

# Allowed hostnames for MCP transport security (DNS rebinding + CSRF protection).
# Derived from MCP_EXTERNAL_URL + optional comma-separated MCP_ALLOWED_ORIGINS env var.
# Set MCP_ALLOWED_ORIGINS="" to allow all origins (development only).
_external_hostname: str = urlparse(MCP_EXTERNAL_URL).hostname or ""
_extra: list[str] = [
    h.strip()
    for h in os.environ.get("MCP_ALLOWED_ORIGINS", "").split(",")
    if h.strip()
]
MCP_ALLOWED_ORIGINS: list[str] = list(
    {_external_hostname, "localhost", "127.0.0.1", *_extra} - {""}
)

# OAuth token lifetime — default 30 days
TOKEN_TTL_DAYS: int = int(os.environ.get("TOKEN_TTL_DAYS", "30"))
TOKEN_TTL_SECONDS: int = TOKEN_TTL_DAYS * 86400
