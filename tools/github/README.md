# tools/github

GitHub integration — link sessions to repositories and fetch live repo context
(default branch, recent commits, open PRs) via the GitHub REST API.

---

## Authentication

GitHub API calls use a **per-user Personal Access Token (PAT)**. Each user sets their
own token in the user portal at `/panel/mcp-user/portal`. One token per user is stored
in `users.github_token`.

When a user has no personal token set, the server falls back to the `GITHUB_TOKEN`
environment variable.

| Source | Priority | Scope needed |
|--------|----------|--------------|
| User's PAT (set in portal) | First | `repo` read for private repos; no scope for public |
| `GITHUB_TOKEN` env var | Fallback | Same as above |

Without any token, requests hit the unauthenticated rate limit (60 requests/hour per IP).
With a token, the limit is 5,000 requests/hour.

---

## Tools

#### `session_link_repo`
Link a GitHub repository to a session. Stores the repo URL in the session record so
`repo_get_context` can query the correct repository without repeating the URL each time.

| Parameter | Type | Required | Description |
|-----------|------|----------|-------------|
| `session_id` | string | yes | Session ID to link |
| `repo_url` | string | yes | Full GitHub URL: `https://github.com/owner/repo` |

The URL is validated on input — malformed URLs are rejected before saving.

**Example:**
```
session_link_repo(
    session_id="feat-auth-dev",
    repo_url="https://github.com/acme/backend"
)
```

---

#### `session_unlink_repo`
Remove the GitHub repository link from a session. Sets `repo_url = NULL` on the session record.

| Parameter | Type | Required | Description |
|-----------|------|----------|-------------|
| `session_id` | string | yes | Session ID to unlink |

---

#### `repo_get_context`
Fetch live GitHub context for the repository linked to a session.

Returns:
- Default branch name
- Recent commits (SHA, author, message, date)
- Open pull requests (number, title, author, head branch, draft status)

Call this at the start of any coding session to get current repository state without
leaving the conversation.

| Parameter | Type | Required | Default | Description |
|-----------|------|----------|---------|-------------|
| `session_id` | string | yes | — | Session whose linked repo will be queried |
| `include_prs` | boolean | no | `true` | Include open pull requests |
| `commit_limit` | integer | no | `10` | Number of recent commits to return (1–30) |

The session must have a linked repo (`session_link_repo`) before calling this tool.

**Example:**
```
repo_get_context(session_id="feat-auth-dev", commit_limit=5)
```

---

## Setting a GitHub PAT

Users set their own PAT in the user portal:

1. Log in at `https://mcp.example.com/panel/mcp-user/login`
2. Go to **Portal**
3. Enter your GitHub PAT in the GitHub Token section and save

The token is stored per-user in `users.github_token`. Only one token per user.
To use a different token, enter the new value — it replaces the existing one.

To set the fallback server-level token, add it to the server's `.env`:

```
GITHUB_TOKEN=ghp_xxxxxxxxxxxxxxxxxxxx
```

---

## Typical Workflow

```
# 1. Link a repo once per session
session_link_repo(session_id="my-feature", repo_url="https://github.com/owner/repo")

# 2. Fetch context at the start of each conversation
repo_get_context(session_id="my-feature")

# 3. Unlink if the project repo changes
session_unlink_repo(session_id="my-feature")
```
