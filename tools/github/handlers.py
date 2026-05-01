import logging

from mcp.server.fastmcp import FastMCP

import db
from .client import get_repo_context, format_repo_context, _parse_repo
from .models import SessionLinkRepoInput, SessionUnlinkRepoInput, RepoGetContextInput

_logger = logging.getLogger("lm-mcp-ai.github")


def _error(msg: str) -> str:
    _logger.error(msg)
    return f"Error: {msg}"


def register(mcp: FastMCP) -> None:
    """Register all GitHub integration tools on the given FastMCP instance."""

    @mcp.tool(
        name="session_link_repo",
        annotations={
            "title": "Link GitHub Repo to Session",
            "readOnlyHint": False,
            "destructiveHint": False,
            "idempotentHint": True,
            "openWorldHint": True,
        },
    )
    async def session_link_repo(params: SessionLinkRepoInput) -> str:
        """
        Link a GitHub repository to a session.

        Stores the repo URL in the session record so repo_get_context can
        fetch branch, commit, and PR info without repeating the URL.

        Args:
            params.session_id: Session ID to link.
            params.repo_url: Full GitHub repo URL (https://github.com/owner/repo).
        """
        try:
            # Validate URL parses correctly before saving
            owner, repo = _parse_repo(params.repo_url)
        except ValueError as e:
            return _error(str(e))

        try:
            pool = await db.get_pool()
            async with pool.acquire() as conn:
                updated = await conn.fetchval(
                    """
                    UPDATE sessions SET repo_url = $1, updated_at = NOW()
                    WHERE session_id = $2
                    RETURNING session_id
                    """,
                    params.repo_url.strip(),
                    params.session_id,
                )
            if updated is None:
                return _error(
                    f"Session '{params.session_id}' not found. "
                    "Create it first with session_write."
                )
            return (
                f"Repository linked to session `{params.session_id}`.\n"
                f"**Repo:** {owner}/{repo}\n"
                f"**URL:** {params.repo_url}\n\n"
                "Use `repo_get_context` to fetch current branch, commits, and PRs."
            )
        except Exception as e:
            return _error(str(e))

    @mcp.tool(
        name="session_unlink_repo",
        annotations={
            "title": "Unlink GitHub Repo from Session",
            "readOnlyHint": False,
            "destructiveHint": False,
            "idempotentHint": True,
            "openWorldHint": False,
        },
    )
    async def session_unlink_repo(params: SessionUnlinkRepoInput) -> str:
        """
        Remove the GitHub repository link from a session.

        Args:
            params.session_id: Session ID to unlink.
        """
        try:
            pool = await db.get_pool()
            async with pool.acquire() as conn:
                updated = await conn.fetchval(
                    """
                    UPDATE sessions SET repo_url = NULL, updated_at = NOW()
                    WHERE session_id = $1
                    RETURNING session_id
                    """,
                    params.session_id,
                )
            if updated is None:
                return _error(f"Session '{params.session_id}' not found.")
            return f"Repository unlinked from session `{params.session_id}`."
        except Exception as e:
            return _error(str(e))

    @mcp.tool(
        name="repo_get_context",
        annotations={
            "title": "Get GitHub Repo Context",
            "readOnlyHint": True,
            "destructiveHint": False,
            "idempotentHint": False,
            "openWorldHint": True,
        },
    )
    async def repo_get_context(params: RepoGetContextInput) -> str:
        """
        Fetch live GitHub context for the repository linked to a session.

        Returns: default branch, recent commits (author, message, date),
        and open pull requests. Call this at the start of any coding session
        to get current repo state.

        Args:
            params.session_id: Session ID whose linked repo will be queried.
            params.include_prs: Include open PRs (default true).
            params.commit_limit: Number of recent commits to return (1–30).
        """
        try:
            pool = await db.get_pool()
            async with pool.acquire() as conn:
                row = await conn.fetchrow(
                    "SELECT repo_url FROM sessions WHERE session_id = $1",
                    params.session_id,
                )
            if row is None:
                return _error(f"Session '{params.session_id}' not found.")
            if not row["repo_url"]:
                return (
                    f"Session `{params.session_id}` has no linked repository.\n"
                    "Use `session_link_repo` to link one first."
                )

            data = await get_repo_context(
                row["repo_url"],
                commit_limit=params.commit_limit,
                include_prs=params.include_prs,
            )
            return format_repo_context(data)
        except ValueError as e:
            return _error(str(e))
        except Exception as e:
            return _error(str(e))
