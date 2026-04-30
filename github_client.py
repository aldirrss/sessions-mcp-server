"""
github_client.py — Async GitHub REST API v3 helpers for lm-mcp-ai.

All functions use httpx with a shared async client.
Token is read from config.GITHUB_TOKEN — never hardcoded.
"""

import base64
import logging
from typing import Any, Optional

import httpx

import config

_logger = logging.getLogger("lm-docker-mcp.github")

GITHUB_API = "https://api.github.com"
TIMEOUT = 30.0


def _headers() -> dict[str, str]:
    if not config.GITHUB_TOKEN:
        raise RuntimeError(
            "GITHUB_TOKEN is not set. Add it to your .env file and rebuild the container."
        )
    return {
        "Authorization": f"Bearer {config.GITHUB_TOKEN}",
        "Accept": "application/vnd.github+json",
        "X-GitHub-Api-Version": "2022-11-28",
    }


def _resolve_owner(owner: Optional[str]) -> str:
    """Use provided owner or fall back to GITHUB_DEFAULT_OWNER."""
    resolved = owner or config.GITHUB_DEFAULT_OWNER
    if not resolved:
        raise ValueError(
            "owner is required. Either pass it explicitly or set GITHUB_DEFAULT_OWNER in .env."
        )
    return resolved


async def _get(path: str, params: Optional[dict] = None) -> Any:
    async with httpx.AsyncClient(timeout=TIMEOUT) as client:
        resp = await client.get(f"{GITHUB_API}{path}", headers=_headers(), params=params)
        resp.raise_for_status()
        return resp.json()


async def _post(path: str, body: dict) -> Any:
    async with httpx.AsyncClient(timeout=TIMEOUT) as client:
        resp = await client.post(f"{GITHUB_API}{path}", headers=_headers(), json=body)
        resp.raise_for_status()
        return resp.json()


async def _patch(path: str, body: dict) -> Any:
    async with httpx.AsyncClient(timeout=TIMEOUT) as client:
        resp = await client.patch(f"{GITHUB_API}{path}", headers=_headers(), json=body)
        resp.raise_for_status()
        return resp.json()


async def _put(path: str, body: dict) -> Any:
    async with httpx.AsyncClient(timeout=TIMEOUT) as client:
        resp = await client.put(f"{GITHUB_API}{path}", headers=_headers(), json=body)
        resp.raise_for_status()
        return resp.json()


async def _delete(path: str) -> int:
    async with httpx.AsyncClient(timeout=TIMEOUT) as client:
        resp = await client.delete(f"{GITHUB_API}{path}", headers=_headers())
        return resp.status_code


# ---------------------------------------------------------------------------
# Repository
# ---------------------------------------------------------------------------

async def list_repos(owner: Optional[str] = None, type: str = "all", per_page: int = 30) -> list[dict]:
    """List repositories for an owner (user or org)."""
    resolved = _resolve_owner(owner)
    # Try org endpoint first, fall back to user
    try:
        return await _get(f"/orgs/{resolved}/repos", params={"type": type, "per_page": per_page, "sort": "updated"})
    except httpx.HTTPStatusError as e:
        if e.response.status_code == 404:
            return await _get(f"/users/{resolved}/repos", params={"type": type, "per_page": per_page, "sort": "updated"})
        raise


async def get_repo(owner: Optional[str], repo: str) -> dict:
    return await _get(f"/repos/{_resolve_owner(owner)}/{repo}")


# ---------------------------------------------------------------------------
# Branches
# ---------------------------------------------------------------------------

async def list_branches(owner: Optional[str], repo: str) -> list[dict]:
    return await _get(f"/repos/{_resolve_owner(owner)}/{repo}/branches")


async def get_branch(owner: Optional[str], repo: str, branch: str) -> dict:
    return await _get(f"/repos/{_resolve_owner(owner)}/{repo}/branches/{branch}")


async def create_branch(owner: Optional[str], repo: str, new_branch: str, from_branch: str = "main") -> dict:
    """Create a new branch from an existing branch."""
    resolved = _resolve_owner(owner)
    # Get SHA of source branch
    source = await get_branch(resolved, repo, from_branch)
    sha = source["commit"]["sha"]
    return await _post(f"/repos/{resolved}/{repo}/git/refs", {
        "ref": f"refs/heads/{new_branch}",
        "sha": sha,
    })


# ---------------------------------------------------------------------------
# Files / Contents
# ---------------------------------------------------------------------------

async def get_file(owner: Optional[str], repo: str, path: str, ref: Optional[str] = None) -> dict:
    """Get file content. Returns dict with 'content' (decoded) and 'sha'."""
    params = {"ref": ref} if ref else {}
    data = await _get(f"/repos/{_resolve_owner(owner)}/{repo}/contents/{path}", params=params)
    if isinstance(data, list):
        raise ValueError(f"'{path}' is a directory, not a file.")
    decoded = base64.b64decode(data["content"]).decode("utf-8", errors="replace")
    return {"content": decoded, "sha": data["sha"], "path": data["path"], "size": data["size"]}


async def list_directory(owner: Optional[str], repo: str, path: str = "", ref: Optional[str] = None) -> list[dict]:
    """List contents of a directory in a repo."""
    params = {"ref": ref} if ref else {}
    data = await _get(f"/repos/{_resolve_owner(owner)}/{repo}/contents/{path}", params=params)
    if not isinstance(data, list):
        raise ValueError(f"'{path}' is a file, not a directory.")
    return [{"name": i["name"], "type": i["type"], "path": i["path"], "size": i.get("size", 0)} for i in data]


async def create_or_update_file(
    owner: Optional[str],
    repo: str,
    path: str,
    content: str,
    message: str,
    branch: str = "main",
    sha: Optional[str] = None,
) -> dict:
    """Create or update a file. sha is required for updates."""
    resolved = _resolve_owner(owner)
    encoded = base64.b64encode(content.encode("utf-8")).decode("utf-8")
    body: dict[str, Any] = {"message": message, "content": encoded, "branch": branch}
    if sha:
        body["sha"] = sha
    return await _put(f"/repos/{resolved}/{repo}/contents/{path}", body)


# ---------------------------------------------------------------------------
# Commits
# ---------------------------------------------------------------------------

async def list_commits(
    owner: Optional[str],
    repo: str,
    branch: Optional[str] = None,
    per_page: int = 20,
) -> list[dict]:
    params: dict = {"per_page": per_page}
    if branch:
        params["sha"] = branch
    data = await _get(f"/repos/{_resolve_owner(owner)}/{repo}/commits", params=params)
    return [
        {
            "sha": c["sha"][:7],
            "full_sha": c["sha"],
            "message": c["commit"]["message"].split("\n")[0],
            "author": c["commit"]["author"]["name"],
            "date": c["commit"]["author"]["date"],
        }
        for c in data
    ]


async def get_commit(owner: Optional[str], repo: str, ref: str) -> dict:
    return await _get(f"/repos/{_resolve_owner(owner)}/{repo}/commits/{ref}")


# ---------------------------------------------------------------------------
# Pull Requests
# ---------------------------------------------------------------------------

async def list_prs(owner: Optional[str], repo: str, state: str = "open") -> list[dict]:
    data = await _get(
        f"/repos/{_resolve_owner(owner)}/{repo}/pulls",
        params={"state": state, "per_page": 30, "sort": "updated"},
    )
    return [
        {
            "number": pr["number"],
            "title": pr["title"],
            "state": pr["state"],
            "author": pr["user"]["login"],
            "head": pr["head"]["ref"],
            "base": pr["base"]["ref"],
            "url": pr["html_url"],
            "created_at": pr["created_at"],
            "updated_at": pr["updated_at"],
            "draft": pr.get("draft", False),
        }
        for pr in data
    ]


async def get_pr(owner: Optional[str], repo: str, pr_number: int) -> dict:
    return await _get(f"/repos/{_resolve_owner(owner)}/{repo}/pulls/{pr_number}")


async def create_pr(
    owner: Optional[str],
    repo: str,
    title: str,
    head: str,
    base: str,
    body: str = "",
    draft: bool = False,
) -> dict:
    return await _post(f"/repos/{_resolve_owner(owner)}/{repo}/pulls", {
        "title": title,
        "head": head,
        "base": base,
        "body": body,
        "draft": draft,
    })


async def merge_pr(owner: Optional[str], repo: str, pr_number: int, method: str = "squash") -> dict:
    return await _put(f"/repos/{_resolve_owner(owner)}/{repo}/pulls/{pr_number}/merge", {
        "merge_method": method,
    })


async def list_pr_reviews(owner: Optional[str], repo: str, pr_number: int) -> list[dict]:
    return await _get(f"/repos/{_resolve_owner(owner)}/{repo}/pulls/{pr_number}/reviews")


# ---------------------------------------------------------------------------
# Issues
# ---------------------------------------------------------------------------

async def list_issues(owner: Optional[str], repo: str, state: str = "open", per_page: int = 20) -> list[dict]:
    data = await _get(
        f"/repos/{_resolve_owner(owner)}/{repo}/issues",
        params={"state": state, "per_page": per_page, "sort": "updated"},
    )
    # Filter out pull requests (GitHub returns PRs in issues endpoint too)
    return [
        {
            "number": i["number"],
            "title": i["title"],
            "state": i["state"],
            "author": i["user"]["login"],
            "labels": [l["name"] for l in i.get("labels", [])],
            "url": i["html_url"],
            "created_at": i["created_at"],
        }
        for i in data
        if "pull_request" not in i
    ]


async def create_issue(owner: Optional[str], repo: str, title: str, body: str = "", labels: Optional[list[str]] = None) -> dict:
    payload: dict[str, Any] = {"title": title, "body": body}
    if labels:
        payload["labels"] = labels
    return await _post(f"/repos/{_resolve_owner(owner)}/{repo}/issues", payload)


# ---------------------------------------------------------------------------
# GitHub Actions
# ---------------------------------------------------------------------------

async def list_workflows(owner: Optional[str], repo: str) -> list[dict]:
    data = await _get(f"/repos/{_resolve_owner(owner)}/{repo}/actions/workflows")
    return [
        {"id": w["id"], "name": w["name"], "state": w["state"], "path": w["path"]}
        for w in data.get("workflows", [])
    ]


async def list_workflow_runs(owner: Optional[str], repo: str, workflow_id: Optional[str] = None, per_page: int = 10) -> list[dict]:
    if workflow_id:
        path = f"/repos/{_resolve_owner(owner)}/{repo}/actions/workflows/{workflow_id}/runs"
    else:
        path = f"/repos/{_resolve_owner(owner)}/{repo}/actions/runs"
    data = await _get(path, params={"per_page": per_page})
    return [
        {
            "id": r["id"],
            "name": r["name"],
            "status": r["status"],
            "conclusion": r.get("conclusion"),
            "branch": r["head_branch"],
            "commit": r["head_sha"][:7],
            "created_at": r["created_at"],
            "url": r["html_url"],
        }
        for r in data.get("workflow_runs", [])
    ]


async def trigger_workflow(owner: Optional[str], repo: str, workflow_id: str, ref: str, inputs: Optional[dict] = None) -> bool:
    """Trigger a workflow_dispatch event."""
    payload: dict[str, Any] = {"ref": ref}
    if inputs:
        payload["inputs"] = inputs
    async with httpx.AsyncClient(timeout=TIMEOUT) as client:
        resp = await client.post(
            f"{GITHUB_API}/repos/{_resolve_owner(owner)}/{repo}/actions/workflows/{workflow_id}/dispatches",
            headers=_headers(),
            json=payload,
        )
        return resp.status_code == 204
