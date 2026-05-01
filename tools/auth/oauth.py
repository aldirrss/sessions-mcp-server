"""
OAuth 2.0 Authorization Server — MCP spec compliant.

Endpoints:
  GET  /.well-known/oauth-authorization-server  — server metadata discovery
  GET  /.well-known/oauth-protected-resource    — resource metadata
  POST /oauth/register                           — dynamic client registration (RFC 7591)
  GET  /oauth/authorize                          — show login + authorize form
  POST /oauth/authorize                          — process login, issue code, redirect
  POST /oauth/token                              — exchange code → access token
  POST /oauth/revoke                             — revoke token

PKCE S256 is required for all authorization code flows.
"""

import json
import logging
import secrets
import urllib.parse

from starlette.requests import Request
from starlette.responses import HTMLResponse, JSONResponse, Response
from starlette.routing import Route

import config
from .store import authenticate_user, create_oauth_code, exchange_oauth_code, create_token

_logger = logging.getLogger("lm-mcp-ai.oauth")

BASE = config.MCP_EXTERNAL_URL.rstrip("/")


# ---------------------------------------------------------------------------
# Discovery endpoints
# ---------------------------------------------------------------------------

async def well_known_server(request: Request) -> JSONResponse:
    return JSONResponse({
        "issuer": BASE,
        "authorization_endpoint": f"{BASE}/oauth/authorize",
        "token_endpoint": f"{BASE}/oauth/token",
        "registration_endpoint": f"{BASE}/oauth/register",
        "revocation_endpoint": f"{BASE}/oauth/revoke",
        "response_types_supported": ["code"],
        "grant_types_supported": ["authorization_code"],
        "code_challenge_methods_supported": ["S256"],
        "token_endpoint_auth_methods_supported": ["none"],
    })


async def well_known_resource(request: Request) -> JSONResponse:
    return JSONResponse({
        "resource": BASE,
        "authorization_servers": [BASE],
        "bearer_methods_supported": ["header", "query"],
    })


# ---------------------------------------------------------------------------
# Dynamic client registration (RFC 7591) — stateless, public clients only
# ---------------------------------------------------------------------------

async def oauth_register(request: Request) -> JSONResponse:
    try:
        body = await request.json()
    except Exception:
        return JSONResponse({"error": "invalid_request"}, status_code=400)

    client_id = secrets.token_urlsafe(16)
    redirect_uris = body.get("redirect_uris", [])
    client_name = body.get("client_name", "MCP Client")

    return JSONResponse({
        "client_id": client_id,
        "client_name": client_name,
        "redirect_uris": redirect_uris,
        "grant_types": ["authorization_code"],
        "response_types": ["code"],
        "token_endpoint_auth_method": "none",
    }, status_code=201)


# ---------------------------------------------------------------------------
# Authorization endpoint — GET (show form) + POST (submit)
# ---------------------------------------------------------------------------

_AUTHORIZE_HTML = """<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8" />
  <meta name="viewport" content="width=device-width, initial-scale=1.0" />
  <title>Authorize — lm-mcp-ai</title>
  <style>
    *, *::before, *::after {{ box-sizing: border-box; margin: 0; padding: 0; }}
    body {{ font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', sans-serif;
            background: #f8fafc; display: flex; min-height: 100vh;
            align-items: center; justify-content: center; }}
    .card {{ background: #fff; border: 1px solid #e2e8f0; border-radius: 16px;
             padding: 40px; width: 100%; max-width: 400px; box-shadow: 0 4px 24px rgba(0,0,0,.06); }}
    .logo {{ font-size: 14px; font-weight: 600; color: #64748b; letter-spacing: .05em;
             text-transform: uppercase; margin-bottom: 24px; }}
    h1 {{ font-size: 22px; font-weight: 700; color: #0f172a; margin-bottom: 6px; }}
    .sub {{ font-size: 14px; color: #64748b; margin-bottom: 28px; }}
    .sub strong {{ color: #0f172a; }}
    label {{ display: block; font-size: 13px; font-weight: 500; color: #374151; margin-bottom: 5px; }}
    input {{ width: 100%; padding: 10px 12px; border: 1px solid #d1d5db; border-radius: 8px;
             font-size: 14px; outline: none; transition: border-color .15s; margin-bottom: 16px; }}
    input:focus {{ border-color: #3b82f6; box-shadow: 0 0 0 3px rgba(59,130,246,.15); }}
    .btn {{ width: 100%; padding: 11px; border: none; border-radius: 8px; font-size: 14px;
            font-weight: 600; cursor: pointer; transition: background .15s; }}
    .btn-primary {{ background: #2563eb; color: #fff; margin-bottom: 10px; }}
    .btn-primary:hover {{ background: #1d4ed8; }}
    .btn-secondary {{ background: #f1f5f9; color: #475569; }}
    .btn-secondary:hover {{ background: #e2e8f0; }}
    .error {{ background: #fef2f2; border: 1px solid #fecaca; color: #dc2626;
              border-radius: 8px; padding: 10px 14px; font-size: 13px; margin-bottom: 16px; }}
    .scope-box {{ background: #f8fafc; border: 1px solid #e2e8f0; border-radius: 8px;
                  padding: 12px 14px; margin-bottom: 20px; font-size: 13px; color: #475569; }}
    .scope-box strong {{ color: #0f172a; }}
  </style>
</head>
<body>
<div class="card">
  <div class="logo">lm-mcp-ai</div>
  <h1>Authorize Access</h1>
  <p class="sub"><strong>{client_name}</strong> is requesting access to your account.</p>
  {error_html}
  <div class="scope-box">
    <strong>Permissions requested:</strong><br/>
    Full MCP access (read + write sessions, skills, Docker management)
  </div>
  <form method="POST">
    <input type="hidden" name="client_id" value="{client_id}" />
    <input type="hidden" name="redirect_uri" value="{redirect_uri}" />
    <input type="hidden" name="code_challenge" value="{code_challenge}" />
    <input type="hidden" name="state" value="{state}" />
    <label for="username">Username or email</label>
    <input id="username" name="username" type="text" autocomplete="username" required placeholder="your-username" />
    <label for="password">Password</label>
    <input id="password" name="password" type="password" autocomplete="current-password" required />
    <button class="btn btn-primary" type="submit">Authorize</button>
    <button class="btn btn-secondary" type="button"
      onclick="window.location='{cancel_url}'">Cancel</button>
  </form>
</div>
</body>
</html>"""


async def oauth_authorize_get(request: Request) -> Response:
    params = request.query_params
    client_id = params.get("client_id", "")
    redirect_uri = params.get("redirect_uri", "")
    code_challenge = params.get("code_challenge", "")
    code_challenge_method = params.get("code_challenge_method", "S256")
    state = params.get("state", "")
    client_name = params.get("client_name", client_id or "MCP Client")

    if not redirect_uri or not code_challenge or code_challenge_method != "S256":
        return JSONResponse({"error": "invalid_request", "error_description": "Missing required params or unsupported challenge method"}, status_code=400)

    cancel_url = _build_redirect(redirect_uri, {"error": "access_denied", "state": state})

    html = _AUTHORIZE_HTML.format(
        client_id=_esc(client_id),
        redirect_uri=_esc(redirect_uri),
        code_challenge=_esc(code_challenge),
        state=_esc(state),
        client_name=_esc(client_name),
        error_html="",
        cancel_url=_esc(cancel_url),
    )
    return HTMLResponse(html)


async def oauth_authorize_post(request: Request) -> Response:
    form = await request.form()
    client_id = str(form.get("client_id", ""))
    redirect_uri = str(form.get("redirect_uri", ""))
    code_challenge = str(form.get("code_challenge", ""))
    state = str(form.get("state", ""))
    username = str(form.get("username", "")).strip()
    password = str(form.get("password", ""))
    client_name = client_id or "MCP Client"

    cancel_url = _build_redirect(redirect_uri, {"error": "access_denied", "state": state})

    def _render_error(msg: str) -> HTMLResponse:
        error_html = f'<div class="error">{_esc(msg)}</div>'
        html = _AUTHORIZE_HTML.format(
            client_id=_esc(client_id), redirect_uri=_esc(redirect_uri),
            code_challenge=_esc(code_challenge), state=_esc(state),
            client_name=_esc(client_name), error_html=error_html,
            cancel_url=_esc(cancel_url),
        )
        return HTMLResponse(html, status_code=400)

    if not username or not password:
        return _render_error("Username and password are required.")

    user = await authenticate_user(username, password)
    if not user:
        return _render_error("Invalid credentials. Please try again.")

    code = await create_oauth_code(user["id"], client_id, redirect_uri, code_challenge)
    redirect = _build_redirect(redirect_uri, {"code": code, "state": state})
    from starlette.responses import RedirectResponse
    return RedirectResponse(redirect, status_code=302)


# ---------------------------------------------------------------------------
# Token endpoint
# ---------------------------------------------------------------------------

async def oauth_token(request: Request) -> JSONResponse:
    try:
        content_type = request.headers.get("content-type", "")
        if "application/json" in content_type:
            body = await request.json()
        else:
            form = await request.form()
            body = dict(form)
    except Exception:
        return JSONResponse({"error": "invalid_request"}, status_code=400)

    grant_type = body.get("grant_type", "")
    if grant_type != "authorization_code":
        return JSONResponse({"error": "unsupported_grant_type"}, status_code=400)

    code = str(body.get("code", ""))
    client_id = str(body.get("client_id", ""))
    redirect_uri = str(body.get("redirect_uri", ""))
    code_verifier = str(body.get("code_verifier", ""))

    if not all([code, client_id, redirect_uri, code_verifier]):
        return JSONResponse({"error": "invalid_request", "error_description": "Missing required parameters"}, status_code=400)

    user = await exchange_oauth_code(code, client_id, redirect_uri, code_verifier)
    if not user:
        return JSONResponse({"error": "invalid_grant"}, status_code=400)

    raw_token, _ = await create_token(user["id"], f"OAuth ({client_id[:20]})")

    return JSONResponse({
        "access_token": raw_token,
        "token_type": "Bearer",
        "scope": "mcp",
    })


# ---------------------------------------------------------------------------
# Revoke endpoint
# ---------------------------------------------------------------------------

async def oauth_revoke(request: Request) -> JSONResponse:
    try:
        form = await request.form()
        raw_token = str(form.get("token", ""))
    except Exception:
        return JSONResponse({"error": "invalid_request"}, status_code=400)

    if raw_token:
        import hashlib
        token_hash = hashlib.sha256(raw_token.encode()).hexdigest()
        pool = await db.get_pool()
        async with pool.acquire() as conn:
            await conn.execute(
                "UPDATE user_tokens SET revoked = true WHERE token_hash = $1", token_hash
            )

    return JSONResponse({}, status_code=200)


# ---------------------------------------------------------------------------
# Route list (added to Starlette app in server.py)
# ---------------------------------------------------------------------------

oauth_routes = [
    Route("/.well-known/oauth-authorization-server", endpoint=well_known_server, methods=["GET"]),
    Route("/.well-known/oauth-protected-resource", endpoint=well_known_resource, methods=["GET"]),
    Route("/oauth/register", endpoint=oauth_register, methods=["POST"]),
    Route("/oauth/authorize", endpoint=oauth_authorize_get, methods=["GET"]),
    Route("/oauth/authorize", endpoint=oauth_authorize_post, methods=["POST"]),
    Route("/oauth/token", endpoint=oauth_token, methods=["POST"]),
    Route("/oauth/revoke", endpoint=oauth_revoke, methods=["POST"]),
]


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _esc(s: str) -> str:
    return s.replace("&", "&amp;").replace('"', "&quot;").replace("<", "&lt;").replace(">", "&gt;")


def _build_redirect(base_uri: str, params: dict) -> str:
    cleaned = {k: v for k, v in params.items() if v}
    return base_uri + ("&" if "?" in base_uri else "?") + urllib.parse.urlencode(cleaned)


# late import to avoid circular at module load
import db
