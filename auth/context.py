"""Per-request current user context — set by auth middleware, read by MCP tools."""

from contextvars import ContextVar
from typing import Optional

_current_user: ContextVar[Optional[dict]] = ContextVar("current_user", default=None)


def set_current_user(user: Optional[dict]) -> None:
    _current_user.set(user)


def get_current_user() -> Optional[dict]:
    return _current_user.get()
