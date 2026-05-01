"""
GitHub REST API v3 client — async, read-only.

Parses GitHub repo URLs and fetches: repo info, recent commits, open PRs.
Uses GITHUB_TOKEN for auth if set (higher rate limits + private repos).
"""

import re
from typing import Optional

import httpx

import config

_API_BASE = "https://api.github.com"
_REPO_PATTERN = re.compile(
    r"https?://github\.com/([^/]+)/([^/]+?)(?:\.git)?(?:/.*)?$"
)


def _parse_repo(repo_url: str) -> tuple[str, str]:
    """Extract (owner, repo) from a GitHub URL. Raises ValueError on invalid URL."""
    m = _REPO_PATTERN.match(repo_url.strip())
    if not m:
        raise ValueError(
            f"Invalid GitHub URL: '{repo_url}'. "
            "Expected format: https://github.com/owner/repo"
        )
    return m.group(1), m.group(2)


def _headers() -> dict[str, str]:
    h = {"Accept": "application/vnd.github+json", "X-GitHub-Api-Version": "2022-11-28"}
    if config.GITHUB_TOKEN:
        h["Authorization"] = f"Bearer {config.GITHUB_TOKEN}"
    return h


async def get_repo_context(
    repo_url: str,
    commit_limit: int = 10,
    include_prs: bool = True,
) -> dict:
    """
    Fetch repo info, recent commits, and optionally open PRs.
    Returns a dict with keys: owner, repo, info, commits, prs, error.
    """
    owner, repo = _parse_repo(repo_url)

    async with httpx.AsyncClient(headers=_headers(), timeout=15) as client:
        # Fetch in parallel where possible
        info_resp = await client.get(f"{_API_BASE}/repos/{owner}/{repo}")

        if info_resp.status_code == 404:
            return {"error": f"Repository '{owner}/{repo}' not found or not accessible."}
        if info_resp.status_code == 403:
            return {"error": "GitHub API rate limit exceeded or access denied. Set GITHUB_TOKEN to increase limits."}
        info_resp.raise_for_status()
        info = info_resp.json()

        commits_resp = await client.get(
            f"{_API_BASE}/repos/{owner}/{repo}/commits",
            params={"per_page": commit_limit},
        )
        commits_resp.raise_for_status()
        commits_raw = commits_resp.json()

        prs = []
        if include_prs:
            prs_resp = await client.get(
                f"{_API_BASE}/repos/{owner}/{repo}/pulls",
                params={"state": "open", "per_page": 10, "sort": "updated"},
            )
            prs_resp.raise_for_status()
            prs_raw = prs_resp.json()
            prs = [
                {
                    "number": pr["number"],
                    "title": pr["title"],
                    "author": pr["user"]["login"],
                    "branch": pr["head"]["ref"],
                    "updated_at": pr["updated_at"],
                    "url": pr["html_url"],
                }
                for pr in prs_raw
            ]

    commits = [
        {
            "sha": c["sha"][:8],
            "message": c["commit"]["message"].split("\n")[0],
            "author": c["commit"]["author"]["name"],
            "date": c["commit"]["author"]["date"],
        }
        for c in commits_raw
    ]

    return {
        "owner": owner,
        "repo": repo,
        "full_name": info["full_name"],
        "description": info.get("description") or "",
        "default_branch": info["default_branch"],
        "stars": info["stargazers_count"],
        "open_issues": info["open_issues_count"],
        "private": info["private"],
        "updated_at": info["updated_at"],
        "commits": commits,
        "prs": prs,
    }


def format_repo_context(data: dict) -> str:
    """Format repo context dict as a Markdown string for Claude."""
    if "error" in data:
        return f"GitHub Error: {data['error']}"

    lines = [
        f"## GitHub: {data['full_name']}",
        f"**Branch:** `{data['default_branch']}` | "
        f"**Stars:** {data['stars']} | "
        f"**Open issues:** {data['open_issues']}",
    ]
    if data["description"]:
        lines.append(f"*{data['description']}*")
    lines.append(f"**Last updated:** {data['updated_at']}")

    lines.append(f"\n### Recent Commits ({len(data['commits'])})")
    for c in data["commits"]:
        lines.append(f"- `{c['sha']}` {c['message']} — {c['author']} ({c['date'][:10]})")

    if data["prs"]:
        lines.append(f"\n### Open Pull Requests ({len(data['prs'])})")
        for pr in data["prs"]:
            lines.append(
                f"- **#{pr['number']}** {pr['title']} "
                f"(`{pr['branch']}`) by {pr['author']} — {pr['updated_at'][:10]}"
            )
    else:
        lines.append("\n*No open pull requests.*")

    return "\n".join(lines)
