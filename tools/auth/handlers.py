import logging

from mcp.server.fastmcp import FastMCP

from auth.context import get_current_user

_logger = logging.getLogger("lm-mcp-ai.auth")


def _error(msg: str) -> str:
    _logger.error(msg)
    return f"Error: {msg}"


def _require_auth() -> dict | None:
    user = get_current_user()
    return user



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

