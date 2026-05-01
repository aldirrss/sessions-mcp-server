"""
UserAuthMiddleware — validates Bearer tokens on /mcp paths.

Accepted auth methods (checked in order):
  1. Authorization: Bearer <token>  — user PAT or OAuth token
  2. ?token=<token>                 — query param fallback (claude.ai web)
  3. X-API-Key / ?key=              — legacy master key (MCP_API_KEY env var)

Returns 401 with WWW-Authenticate header pointing to OAuth resource metadata
so MCP clients (VSCode, Claude Code CLI) can auto-discover the OAuth server
and open the browser authorization flow.
"""

import json
import logging

from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import Response

import config
from auth.context import set_current_user

_logger = logging.getLogger("lm-mcp-ai.auth")


class UserAuthMiddleware(BaseHTTPMiddleware):

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

        # Master key — backward compat / emergency access
        if config.MCP_API_KEY and token == config.MCP_API_KEY:
            set_current_user({"id": None, "username": "admin", "role": "admin", "email": ""})
            return await call_next(request)

        # Per-user token from DB
        from auth.store import validate_token
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
            content=json.dumps({
                "error": "Unauthorized",
                "error_description": "Valid Bearer token required",
            }),
            status_code=401,
            media_type="application/json",
            headers={
                "WWW-Authenticate": (
                    f'Bearer realm="lm-mcp-ai", '
                    f'resource_metadata="{base}/.well-known/oauth-protected-resource"'
                )
            },
        )
