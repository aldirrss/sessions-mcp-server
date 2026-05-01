#!/usr/bin/env python3
"""
lm-mcp-ai — MCP Server entry point.

Transport : Streamable HTTP  (connects to claude.ai web and Claude Code CLI/VSCode)
Auth      : Two accepted methods (checked in order):
            1. X-API-Key header        → for Claude Code CLI / VSCode / curl
            2. ?key= query parameter   → for claude.ai web connector (no header UI)
               URL: https://mcp.yourdomain.com/mcp?key=YOUR_API_KEY
"""

import asyncio
import json
import logging
import sys

import config

# Monkey-patch TransportSecurityMiddleware BEFORE FastMCP is imported.
# validate_request returning None means "request is valid, continue".
# Safe because nginx enforces TLS and ApiKeyMiddleware handles all auth.
import mcp.server.transport_security as _ts

async def _validate_all(self, request, is_post=False):
    return None

_ts.TransportSecurityMiddleware.validate_request = _validate_all

from mcp.server.fastmcp import FastMCP
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import Response

import db
from tools.docker import register as register_docker
from tools.sessions import register as register_sessions
from tools.skills import register as register_skills
from tools.github import register as register_github
from tools.config import register as register_config
from tools.vacuum import register as register_vacuum

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
# FastMCP — register all tools
# ---------------------------------------------------------------------------

mcp = FastMCP("lm-mcp-ai")
register_docker(mcp)
register_sessions(mcp)
register_skills(mcp)
register_github(mcp)
register_config(mcp)
register_vacuum(mcp)


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    import uvicorn
    from contextlib import asynccontextmanager

    _logger.info(
        "Starting lm-mcp-ai on %s:%d (streamable_http)",
        config.MCP_HOST,
        config.MCP_PORT,
    )

    app = mcp.streamable_http_app()

    # Wrap FastMCP's own lifespan — must not replace it, only extend it.
    # FastMCP's lifespan initializes the StreamableHTTPSessionManager task group
    # that is required before any request can be handled.
    _fastmcp_lifespan = app.router.lifespan_context

    async def _daily_vacuum_loop():
        """Run vacuum once per day if vacuum_enabled=true in config."""
        while True:
            await asyncio.sleep(24 * 3600)
            try:
                from tools.vacuum.store import run_vacuum, _get_vacuum_config
                cfg = await _get_vacuum_config()
                if cfg["enabled"]:
                    result = await run_vacuum(dry_run=False)
                    _logger.info(
                        "Auto-vacuum: notes=%d archived=%d deleted=%d",
                        result["notes_deleted"],
                        result["sessions_archived"],
                        result["sessions_deleted"],
                    )
                else:
                    _logger.debug("Auto-vacuum skipped (vacuum_enabled=false)")
            except Exception as exc:
                _logger.error("Auto-vacuum error: %s", exc)

    @asynccontextmanager
    async def _combined_lifespan(_app):
        await db.init_schema()
        _logger.info("Session store (PostgreSQL) ready")
        vacuum_task = asyncio.create_task(_daily_vacuum_loop())
        async with _fastmcp_lifespan(_app):
            yield
        vacuum_task.cancel()
        await db.close_pool()

    app.router.lifespan_context = _combined_lifespan

    # TransportSecurityMiddleware is already neutralized via the class-level
    # monkey-patch at module load time (_validate_all returns None).
    # No instance patching needed.

    app.add_middleware(ApiKeyMiddleware)

    uvicorn.run(
        app,
        host=config.MCP_HOST,
        port=config.MCP_PORT,
    )
