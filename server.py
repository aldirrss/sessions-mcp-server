#!/usr/bin/env python3
"""
lm-mcp-ai — MCP Server entry point.

Transport : Streamable HTTP  (connects to claude.ai web and Claude Code CLI/VSCode)
Auth      : Per-user Bearer tokens (from /oauth flow or user dashboard).
            Fallback: MCP_API_KEY env var as master key (backward compat).

OAuth 2.0 Authorization Server (MCP spec):
  GET  /.well-known/oauth-authorization-server
  GET  /.well-known/oauth-protected-resource
  POST /oauth/register   — dynamic client registration (RFC 7591)
  GET  /oauth/authorize  — browser login + authorize form
  POST /oauth/authorize
  POST /oauth/token      — exchange code for Bearer token
  POST /oauth/revoke
"""

import asyncio
import json
import logging
import sys

import config

# Monkey-patch TransportSecurityMiddleware BEFORE FastMCP is imported.
import mcp.server.transport_security as _ts

async def _validate_all(self, request, is_post=False):
    return None

_ts.TransportSecurityMiddleware.validate_request = _validate_all

from mcp.server.fastmcp import FastMCP
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import Response

import db
from tools.auth.context import set_current_user
from tools.docker import register as register_docker
from tools.sessions import register as register_sessions
from tools.skills import register as register_skills
from tools.github import register as register_github
from tools.config import register as register_config
from tools.vacuum import register as register_vacuum
from tools.auth import register as register_auth

# ---------------------------------------------------------------------------
# Logging
# ---------------------------------------------------------------------------

logging.basicConfig(
    stream=sys.stderr,
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)
_logger = logging.getLogger("lm-mcp-ai")


# ---------------------------------------------------------------------------
# Auth middleware — per-user Bearer token (OAuth) or master API key
# ---------------------------------------------------------------------------

class UserAuthMiddleware(BaseHTTPMiddleware):
    """
    Authenticate requests on /mcp paths using:
      1. Authorization: Bearer <token>  — user PAT or OAuth token
      2. ?token=<token>                 — query param fallback (claude.ai web)
      3. X-API-Key / ?key=              — legacy master key (backward compat)

    Public paths (no auth required): /.well-known/*, /oauth/*, /health
    WWW-Authenticate header is set on 401 so MCP clients auto-discover OAuth server.
    """

    _OPEN_PREFIXES = ("/.well-known/", "/oauth/", "/health")

    async def dispatch(self, request: Request, call_next) -> Response:
        path = request.url.path

        if any(path.startswith(p) for p in self._OPEN_PREFIXES):
            return await call_next(request)

        if not (path.startswith("/mcp") or path == "/"):
            return await call_next(request)

        token = (
            self._bearer(request)
            or request.query_params.get("token")
            or request.headers.get("X-API-Key")
            or request.headers.get("x-api-key")
            or request.query_params.get("key")
        )

        if not token:
            return self._unauthorized()

        # Master key (backward compat / admin operations)
        if config.MCP_API_KEY and token == config.MCP_API_KEY:
            set_current_user({"id": None, "username": "admin", "role": "admin", "email": ""})
            return await call_next(request)

        # Per-user token from DB
        from tools.auth.store import validate_token
        user = await validate_token(token)
        if not user:
            return self._unauthorized()

        set_current_user(user)
        try:
            return await call_next(request)
        finally:
            set_current_user(None)

    @staticmethod
    def _bearer(request: Request) -> str:
        auth = request.headers.get("Authorization", "")
        if auth.startswith("Bearer "):
            return auth[7:].strip()
        return ""

    @staticmethod
    def _unauthorized() -> Response:
        base = config.MCP_EXTERNAL_URL.rstrip("/")
        return Response(
            content=json.dumps({"error": "Unauthorized", "error_description": "Valid Bearer token required"}),
            status_code=401,
            media_type="application/json",
            headers={
                "WWW-Authenticate": (
                    f'Bearer realm="lm-mcp-ai", '
                    f'resource_metadata="{base}/.well-known/oauth-protected-resource"'
                )
            },
        )


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
register_auth(mcp)


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    import uvicorn
    from contextlib import asynccontextmanager
    from tools.auth.oauth import oauth_routes

    _logger.info(
        "Starting lm-mcp-ai on %s:%d (streamable_http)",
        config.MCP_HOST,
        config.MCP_PORT,
    )

    app = mcp.streamable_http_app()

    # Inject OAuth routes into Starlette router BEFORE MCP catch-all
    from starlette.routing import Route as StarletteRoute
    app.router.routes = list(oauth_routes) + list(app.router.routes)

    # Extend FastMCP's own lifespan
    _fastmcp_lifespan = app.router.lifespan_context

    async def _daily_vacuum_loop():
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
    app.add_middleware(UserAuthMiddleware)

    uvicorn.run(app, host=config.MCP_HOST, port=config.MCP_PORT)
