"""
auth/ — Server authentication infrastructure.

This package handles the auth layer of the MCP server itself:
  - context.py   : per-request current user (ContextVar)
  - middleware.py : Starlette middleware that validates Bearer tokens
  - oauth.py     : OAuth 2.0 Authorization Server HTTP endpoints
  - store.py     : user/token PostgreSQL CRUD

MCP tool handlers (user_me, token_create, etc.) live in tools/auth/handlers.py
and import from this package.
"""
