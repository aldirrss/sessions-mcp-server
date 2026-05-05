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
