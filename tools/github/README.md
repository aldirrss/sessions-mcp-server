# tools/github

GitHub integration — link sessions to repositories and fetch live repo context (branch, commits, open PRs) via the GitHub REST API.

Requires a `GITHUB_TOKEN` environment variable with at least `repo` read scope.

---

## Tools

#### `session_link_repo`
Link a GitHub repository to a session.

Stores the repo URL in the session record so `repo_get_context` can query the correct repository without repeating the URL each time.

| Parameter    | Type   | Required | Description                                         |
|--------------|--------|----------|-----------------------------------------------------|
| `session_id` | string | yes      | Session ID to link                                  |
| `repo_url`   | string | yes      | Full GitHub URL: `https://github.com/owner/repo`   |

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
Remove the GitHub repository link from a session.

Sets `repo_url = NULL` on the session record.

| Parameter    | Type   | Required | Description         |
|--------------|--------|----------|---------------------|
| `session_id` | string | yes      | Session ID to unlink |

---

#### `repo_get_context`
Fetch live GitHub context for the repository linked to a session.

Returns:
- Default branch name
- Recent commits (SHA, author, message, date)
- Open pull requests (number, title, author, head branch, draft status)

Call this at the start of any coding session to get current repository state without leaving the conversation.

| Parameter       | Type    | Required | Default | Description                              |
|-----------------|---------|----------|---------|------------------------------------------|
| `session_id`    | string  | yes      |         | Session whose linked repo will be queried|
| `include_prs`   | boolean | no       | true    | Include open pull requests               |
| `commit_limit`  | integer | no       | 10      | Number of recent commits to return (1–30)|

The session must have a linked repo (`session_link_repo`) before this tool can be called.

**Example:**
```
repo_get_context(session_id="feat-auth-dev", commit_limit=5)
```

---

## Configuration

| Env Variable   | Description                              | Required |
|----------------|------------------------------------------|----------|
| `GITHUB_TOKEN` | Personal access token or GitHub App token | Yes (for private repos / higher rate limits) |

Without `GITHUB_TOKEN`, requests hit the unauthenticated GitHub API rate limit (60 req/hour per IP). With a token, the limit is 5,000 req/hour.

Set it in `.env`:
```
GITHUB_TOKEN=ghp_xxxxxxxxxxxxxxxxxxxx
```

---

## Typical Workflow

```
# 1. Link repo once per session
session_link_repo(session_id="my-feature", repo_url="https://github.com/owner/repo")

# 2. Fetch context at the start of each conversation
repo_get_context(session_id="my-feature")

# 3. Unlink if the project repo changes
session_unlink_repo(session_id="my-feature")
```
