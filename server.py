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
import logging
import sys

import config

# Patch TransportSecurityMiddleware BEFORE FastMCP is imported.
# Instead of bypassing validation entirely, validate Host/Origin against a whitelist
# derived from MCP_EXTERNAL_URL (+ optional MCP_ALLOWED_ORIGINS env var).
import mcp.server.transport_security as _ts
from urllib.parse import urlparse as _urlparse
from starlette.responses import Response as _Response


async def _validate_origin(self, request, is_post=False):
    allowed = config.MCP_ALLOWED_ORIGINS
    if not allowed:
        return None  # empty list = dev mode, allow all

    host = request.headers.get("host", "").split(":")[0].lower()
    if host in allowed:
        return None

    origin_header = request.headers.get("origin", "")
    if origin_header:
        hostname = _urlparse(origin_header).hostname or ""
        if hostname in allowed:
            return None

    _logger_ts = logging.getLogger("lm-mcp-ai.transport")
    _logger_ts.warning("Blocked request: host=%r origin=%r allowed=%r", host, origin_header, allowed)
    return _Response(content="Forbidden: host not allowed", status_code=403)


_ts.TransportSecurityMiddleware.validate_request = _validate_origin

from mcp.server.fastmcp import FastMCP

import db
from auth.middleware import UserAuthMiddleware
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
# FastMCP — register all tools
# ---------------------------------------------------------------------------

mcp = FastMCP("lm-mcp-ai")
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
    from auth.oauth import oauth_routes

    _logger.info(
        "Starting lm-mcp-ai on %s:%d (streamable_http)",
        config.MCP_HOST,
        config.MCP_PORT,
    )

    app = mcp.streamable_http_app()

    # Inject OAuth routes + browser redirect routes BEFORE MCP catch-all
    from starlette.routing import Route as StarletteRoute
    from starlette.responses import RedirectResponse as _Redirect

    _user_login_url = config.MCP_EXTERNAL_URL.rstrip("/") + "/panel/mcp-user/login"

    async def _redirect_to_portal(request):
        return _Redirect(_user_login_url, status_code=302)

    browser_routes = [
        StarletteRoute("/", endpoint=_redirect_to_portal, methods=["GET"]),
        StarletteRoute("/panel", endpoint=_redirect_to_portal, methods=["GET"]),
    ]
    app.router.routes = browser_routes + list(oauth_routes) + list(app.router.routes)

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
