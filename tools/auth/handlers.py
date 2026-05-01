import logging

from mcp.server.fastmcp import FastMCP

from auth.context import get_current_user
from auth.store import (
    create_token, list_tokens, revoke_token,
    get_user, list_users, set_user_role, set_user_active,
)
from .models import TokenCreateInput, TokenRevokeInput, UserSetRoleInput, UserSetActiveInput

_logger = logging.getLogger("lm-mcp-ai.auth")


def _error(msg: str) -> str:
    _logger.error(msg)
    return f"Error: {msg}"


def _require_auth() -> dict | None:
    user = get_current_user()
    return user


def _require_admin(user: dict | None) -> bool:
    return user is not None and user.get("role") == "admin"


def register(mcp: FastMCP) -> None:
    """Register auth-related MCP tools."""

    # -----------------------------------------------------------------------
    # Current user info
    # -----------------------------------------------------------------------

    @mcp.tool(
        name="user_me",
        annotations={"title": "Get Current User", "readOnlyHint": True},
    )
    async def user_me() -> str:
        """Return info about the currently authenticated user."""
        user = _require_auth()
        if not user:
            return _error("Not authenticated. Connect with a valid Bearer token.")
        return (
            f"**Username:** {user['username']}\n"
            f"**Email:** {user['email']}\n"
            f"**Role:** {user['role']}\n"
            f"**User ID:** `{user['id']}`"
        )

    # -----------------------------------------------------------------------
    # Token management (self-service)
    # -----------------------------------------------------------------------

    @mcp.tool(
        name="token_create",
        annotations={"title": "Create Access Token", "readOnlyHint": False, "idempotentHint": False},
    )
    async def token_create(params: TokenCreateInput) -> str:
        """
        Create a new Personal Access Token for the authenticated user.

        The raw token is shown ONCE — copy it immediately. It cannot be retrieved again.

        Args:
            params.name: Label for this token (e.g. 'VSCode laptop').
            params.expires_days: Days until expiry. Omit for no expiry.
        """
        user = _require_auth()
        if not user:
            return _error("Not authenticated.")
        try:
            raw, record = await create_token(user["id"], params.name, params.expires_days)
            expiry = f"Expires: {record['expires_at']}" if record["expires_at"] else "No expiry"
            return (
                f"Token created: **{params.name}**\n"
                f"**ID:** `{record['id']}`\n"
                f"**{expiry}**\n\n"
                f"```\n{raw}\n```\n\n"
                "⚠️ Copy this token now — it will NOT be shown again.\n"
                "Use it as: `Authorization: Bearer <token>` or `?token=<token>`"
            )
        except Exception as e:
            return _error(str(e))

    @mcp.tool(
        name="token_list",
        annotations={"title": "List Access Tokens", "readOnlyHint": True},
    )
    async def token_list() -> str:
        """List all Personal Access Tokens for the authenticated user (masked)."""
        user = _require_auth()
        if not user:
            return _error("Not authenticated.")
        try:
            tokens = await list_tokens(user["id"])
            if not tokens:
                return "No tokens found. Use `token_create` to create one."
            lines = [
                f"## Tokens for {user['username']} ({len(tokens)})",
                "",
                "| ID | Name | Expires | Last Used | Revoked |",
                "|----|------|---------|-----------|---------|",
            ]
            for t in tokens:
                expires = t["expires_at"][:10] if t["expires_at"] else "never"
                last = t["last_used_at"][:10] if t["last_used_at"] else "never"
                lines.append(
                    f"| `{t['id'][:8]}…` | {t['name']} | {expires} | {last} | {'yes' if t['revoked'] else 'no'} |"
                )
            return "\n".join(lines)
        except Exception as e:
            return _error(str(e))

    @mcp.tool(
        name="token_revoke",
        annotations={"title": "Revoke Access Token", "readOnlyHint": False, "destructiveHint": True},
    )
    async def token_revoke(params: TokenRevokeInput) -> str:
        """
        Revoke a Personal Access Token permanently.

        Args:
            params.token_id: UUID of the token to revoke (from token_list).
        """
        user = _require_auth()
        if not user:
            return _error("Not authenticated.")
        try:
            ok = await revoke_token(params.token_id, user_id=user["id"])
            if ok:
                return f"Token `{params.token_id}` revoked."
            return _error("Token not found or does not belong to your account.")
        except Exception as e:
            return _error(str(e))

    # -----------------------------------------------------------------------
    # Admin tools
    # -----------------------------------------------------------------------

    @mcp.tool(
        name="user_list",
        annotations={"title": "List All Users (Admin)", "readOnlyHint": True},
    )
    async def user_list() -> str:
        """[Admin only] List all registered users."""
        user = _require_auth()
        if not _require_admin(user):
            return _error("Admin role required.")
        try:
            users = await list_users()
            if not users:
                return "No users found."
            lines = [
                f"## Users ({len(users)})", "",
                "| ID | Username | Email | Role | Active | Created |",
                "|----|----------|-------|------|--------|---------|",
            ]
            for u in users:
                lines.append(
                    f"| `{u['id'][:8]}…` | {u['username']} | {u['email']} "
                    f"| {u['role']} | {'✓' if u['is_active'] else '✗'} | {u['created_at'][:10]} |"
                )
            return "\n".join(lines)
        except Exception as e:
            return _error(str(e))

    @mcp.tool(
        name="user_set_role",
        annotations={"title": "Set User Role (Admin)", "readOnlyHint": False},
    )
    async def user_set_role(params: UserSetRoleInput) -> str:
        """
        [Admin only] Change a user's role.

        Args:
            params.user_id: UUID of the target user.
            params.role: 'user' or 'admin'.
        """
        user = _require_auth()
        if not _require_admin(user):
            return _error("Admin role required.")
        try:
            ok = await set_user_role(params.user_id, params.role)
            if ok:
                return f"User `{params.user_id}` role set to '{params.role}'."
            return _error(f"User `{params.user_id}` not found.")
        except Exception as e:
            return _error(str(e))

    @mcp.tool(
        name="user_set_active",
        annotations={"title": "Activate/Deactivate User (Admin)", "readOnlyHint": False},
    )
    async def user_set_active(params: UserSetActiveInput) -> str:
        """
        [Admin only] Activate or deactivate a user account.

        Deactivated users cannot authenticate and all their tokens are rejected.

        Args:
            params.user_id: UUID of the target user.
            params.active: True to activate, False to deactivate.
        """
        user = _require_auth()
        if not _require_admin(user):
            return _error("Admin role required.")
        try:
            ok = await set_user_active(params.user_id, params.active)
            state = "activated" if params.active else "deactivated"
            if ok:
                return f"User `{params.user_id}` {state}."
            return _error(f"User `{params.user_id}` not found.")
        except Exception as e:
            return _error(str(e))
