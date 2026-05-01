# lm-mcp-ai

A self-hosted **MCP (Model Context Protocol) server** running in Docker on a VPS.
Connects **claude.ai Web**, **Claude Code CLI**, and **VSCode** to a shared backend —
providing Docker stack management, persistent session memory, a skill library,
GitHub integration, dynamic configuration, and automated data retention,
all backed by PostgreSQL.

---

## Table of Contents

1. [Architecture](#architecture)
2. [Prerequisites](#prerequisites)
3. [Installation](#installation)
4. [Environment Variables](#environment-variables)
5. [Reverse Proxy Setup](#reverse-proxy-setup)
6. [Connecting Clients](#connecting-clients)
7. [URL Structure](#url-structure)
8. [Tools Reference](#tools-reference)
9. [Web Panel](#web-panel)
10. [Auto-Vacuum](#auto-vacuum)
11. [Security](#security)

---

## Architecture

```
┌─────────────────────────────────────────────────────────────────┐
│  Clients                                                         │
│  ┌──────────────────┐  ┌─────────────────┐  ┌───────────────┐  │
│  │  claude.ai Web   │  │ Claude Code CLI │  │  VSCode       │  │
│  │  (OAuth / PAT)   │  │  (Bearer token) │  │ (Bearer token)│  │
│  └────────┬─────────┘  └───────┬─────────┘  └───────┬───────┘  │
│           └────────────── HTTPS ──────────────────── ┘          │
│                                ▼                                 │
│  ┌─────────────────────────────────────────────────────────┐    │
│  │  nginx / Cloudflare  (TLS termination)                  │    │
│  └───────────────────────┬─────────────────────────────────┘    │
│          ┌───────────────┴──────────────────────┐               │
│          ▼  :8765                                ▼  :3100        │
│  ┌───────────────────────────┐  ┌───────────────────────────┐   │
│  │  lm-mcp-ai (FastMCP)      │  │  lm-mcp-web (Next.js 15)  │   │
│  │  /mcp  /oauth/*           │  │  /panel/mcp-admin/*       │   │
│  │  /.well-known/*           │  │  /panel/mcp-user/*        │   │
│  └──────────────┬────────────┘  └──────────────┬────────────┘   │
│                 └──────────────┬───────────────┘                │
│                                ▼                                 │
│  ┌─────────────────────────────────────────────────────────┐    │
│  │  PostgreSQL 15  (127.0.0.1:15432)                       │    │
│  │  sessions · notes · skills · skill_versions             │    │
│  │  session_skills · config · users                        │    │
│  └─────────────────────────────────────────────────────────┘    │
│                                                                  │
│  ┌─────────────────────────────────────────────────────────┐    │
│  │  Docker Engine (VPS host)  /opt/stacks/                 │    │
│  │    ├── odoo/     ├── monitoring/     └── ...            │    │
│  └─────────────────────────────────────────────────────────┘    │
└─────────────────────────────────────────────────────────────────┘
```

### Containers

| Container | Image | Port (loopback) | Purpose |
|-----------|-------|-----------------|---------|
| `lm-mcp-postgres` | `postgres:15` | `127.0.0.1:15432` | Database |
| `lm-mcp-ai` | custom (Python) | `127.0.0.1:8765` | MCP server + OAuth AS |
| `lm-mcp-web` | custom (Next.js) | `127.0.0.1:3100` | Web panel |

---

## Prerequisites

| Component | Minimum | Recommended |
|-----------|---------|-------------|
| OS | Ubuntu 22.04 LTS | Ubuntu 24.04 LTS |
| CPU | 1 vCPU | 2 vCPU |
| RAM | 1 GB | 2 GB |
| Disk | 10 GB | 20 GB |
| Docker | 24.x+ | 27.x+ |
| Docker Compose | v2.20+ | v2.27+ |
| Public IP | Required | — |
| Domain/subdomain | Required (HTTPS) | — |

---

## Installation

### 1. Install Docker

```bash
curl -fsSL https://get.docker.com | sh
sudo usermod -aG docker $USER && newgrp docker
```

### 2. Clone the repository

```bash
git clone https://github.com/aldirrss/lm-mcp-ai.git /opt/lm-mcp-ai
cd /opt/lm-mcp-ai
```

### 3. Find your Docker group GID

```bash
stat -c '%g' /var/run/docker.sock   # e.g. 988
```

### 4. Configure environment

```bash
cp .env.example .env
```

Generate secret values:

```bash
python3 -c "import secrets; print(secrets.token_hex(32))"   # SESSION_SECRET
python3 -c "import secrets; print(secrets.token_hex(24))"   # POSTGRES_PASSWORD
```

Edit `.env` with at minimum the required variables (see table below).

### 5. Build and start

```bash
docker compose up -d --build
docker compose ps
# Expected:
#   lm-mcp-postgres   Up (healthy)
#   lm-mcp-ai         Up
#   lm-mcp-web        Up
```

---

## Environment Variables

### Required

| Variable | Description |
|----------|-------------|
| `DATABASE_URL` | PostgreSQL connection string: `postgresql://user:pass@host:5432/db` |
| `MCP_EXTERNAL_URL` | Public base URL of the server, e.g. `https://mcp.example.com` |
| `SESSION_SECRET` | Cookie encryption key, minimum 32 characters |
| `ADMIN_USER` | Admin username for the web panel |
| `ADMIN_PASSWORD` | Admin password for the web panel |

### Optional

| Variable | Default | Description |
|----------|---------|-------------|
| `MCP_API_KEY` | — | Master key fallback for Bearer auth (any user) |
| `MCP_HOST` | `0.0.0.0` | Bind address inside the container |
| `MCP_PORT` | `8765` | Port inside the container |
| `COMPOSE_BASE_DIR` | `/opt/stacks` | Root directory containing Compose project subdirectories |
| `LOG_MAX_LINES` | `200` | Hard cap on log lines returned per request |
| `DOCKER_TIMEOUT` | `60` | Docker CLI subprocess timeout in seconds |
| `GITHUB_TOKEN` | — | Fallback GitHub PAT when a user has no personal token set |

### PostgreSQL (when running the bundled container)

| Variable | Default | Description |
|----------|---------|-------------|
| `POSTGRES_PASSWORD` | — | Database password |
| `POSTGRES_DB` | `mcp_sessions` | Database name |
| `POSTGRES_USER` | `mcp_user` | Database user |
| `POSTGRES_HOST_PORT` | `15432` | Host-side port for SSH tunnel or pgAdmin |

---

## Reverse Proxy Setup

All traffic must reach the server over HTTPS. nginx must rewrite the `Host` header to `localhost` for the `/mcp` location — required by FastMCP's transport security.

```nginx
server {
    listen 443 ssl;
    server_name mcp.example.com;

    # MCP server — OAuth AS + MCP endpoint
    location ~ ^/(mcp|oauth|\.well-known) {
        proxy_pass         http://127.0.0.1:8765;
        proxy_http_version 1.1;
        proxy_set_header   Host "localhost";   # REQUIRED
        proxy_set_header   X-Real-IP $remote_addr;
        proxy_set_header   Upgrade $http_upgrade;
        proxy_set_header   Connection "upgrade";
        proxy_read_timeout 300s;
    }

    # Web panel (Next.js)
    location /panel {
        proxy_pass         http://127.0.0.1:3100;
        proxy_http_version 1.1;
        proxy_set_header   Host $host;
        proxy_set_header   X-Real-IP $remote_addr;
    }
}
```

> For Cloudflare DNS Proxy, use `listen 80;` and omit SSL directives.
> For Cloudflare Tunnel, add `httpHostHeader: "localhost"` to the `/mcp` ingress rule.

---

## Connecting Clients

### OAuth auto-discovery (claude.ai / VSCode)

The server exposes `/.well-known/oauth-authorization-server` and supports PKCE S256.
Clients that support OAuth 2.0 auto-discovery will find the authorization endpoint automatically when pointed at `https://mcp.example.com/mcp`.

OAuth login page: `https://mcp.example.com/oauth/authorize`

### Bearer token (PAT)

Users create personal access tokens in the user portal (`/panel/mcp-user/portal`).
Tokens are stored as SHA-256 hashes and sent as `Authorization: Bearer <token>`.

### claude.ai Web (manual key)

1. Go to **Settings → Connectors → Add custom connector**
2. Set the URL to: `https://mcp.example.com/mcp?key=YOUR_TOKEN`

> The `?key=` parameter is accepted as a Bearer token equivalent.

### Claude Code CLI

```bash
claude mcp add --transport http --scope user mcp-lema \
  https://mcp.example.com/mcp \
  --header "Authorization: Bearer YOUR_TOKEN"
```

### VSCode

Create `.vscode/mcp.json` in your project:

```json
{
  "servers": {
    "mcp-lema": {
      "type": "http",
      "url": "https://mcp.example.com/mcp",
      "headers": { "Authorization": "Bearer YOUR_TOKEN" }
    }
  }
}
```

### Verify connection

```bash
curl -s -X POST "https://mcp.example.com/mcp" \
  -H "Authorization: Bearer YOUR_TOKEN" \
  -H "Content-Type: application/json" \
  -d '{"jsonrpc":"2.0","id":1,"method":"tools/list","params":{}}' \
  | jq '[.result.tools[].name]'
```

---

## URL Structure

| URL | Description |
|-----|-------------|
| `https://mcp.example.com/` | Redirect to user login |
| `https://mcp.example.com/mcp` | MCP endpoint (Bearer auth) |
| `https://mcp.example.com/oauth/authorize` | OAuth login page |
| `https://mcp.example.com/.well-known/oauth-authorization-server` | OAuth AS metadata |
| `https://mcp.example.com/panel/mcp-user/login` | User login |
| `https://mcp.example.com/panel/mcp-user/register` | User registration |
| `https://mcp.example.com/panel/mcp-user/portal` | Token management (user) |
| `https://mcp.example.com/panel/mcp-user/skills` | Global skills browser (user) |
| `https://mcp.example.com/panel/mcp-admin/login` | Admin login |
| `https://mcp.example.com/panel/mcp-admin` | Admin dashboard |

---

## Tools Reference

Tools are grouped into 7 categories. See each category's `README.md` under `tools/` for full parameter documentation.

### Docker (11 tools)

> [`tools/docker/README.md`](tools/docker/README.md)

| Tool | Type | Description |
|------|------|-------------|
| `docker_list_stacks` | read | List all Compose stacks under `COMPOSE_BASE_DIR` |
| `docker_stack_ps` | read | Container state within a stack |
| `docker_stack_logs` | read | Recent log output from a stack or service |
| `docker_list_containers` | read | All containers on the host |
| `docker_inspect_container` | read | Full `docker inspect` JSON |
| `docker_stats` | read | CPU/memory/network snapshot |
| `docker_stack_up` | write | Start a stack or service |
| `docker_stack_down` | write | Stop and remove containers |
| `docker_stack_restart` | write | Restart a stack or service |
| `docker_stack_pull` | write | Pull latest images |
| `docker_exec` | write | Execute a command inside a container |

### Sessions (13 tools)

> [`tools/sessions/README.md`](tools/sessions/README.md)

| Tool | Type | Description |
|------|------|-------------|
| `session_write` | write | Create or overwrite a session context |
| `session_read` | read | Full context + pinned notes + all notes |
| `session_list` | read | List sessions (pinned first, archived hidden by default) |
| `session_append` | write | Append a timestamped note to a session |
| `session_delete` | write | Permanently delete a session and its notes |
| `session_search` | read | Full-text search across sessions and notes |
| `session_compact` | write | Merge old notes into context field and delete them |
| `session_pin` | write | Protect a session from auto-vacuum |
| `session_unpin` | write | Remove protection from a session |
| `session_archive` | write | Soft-delete a session |
| `session_restore` | write | Restore an archived session |
| `note_pin` | write | Pin a note (always at top, never vacuumed) |
| `note_unpin` | write | Remove pin from a note |

### Skills (11 tools)

> [`tools/skills/README.md`](tools/skills/README.md)

| Tool | Type | Description |
|------|------|-------------|
| `skill_write` | write | Create or update a skill |
| `skill_read` | read | Load a skill's full Markdown content |
| `skill_list` | read | List all skills (summary only) |
| `skill_search` | read | Full-text search across skills |
| `skill_delete` | write | Delete a skill |
| `skill_sync` | write | Bulk import skills from a list |
| `skill_track` | write | Record that a skill was used in a session |
| `session_skills_list` | read | Skills used in a specific session |
| `skill_sessions_list` | read | Sessions that used a specific skill |
| `skill_stats` | read | Usage statistics for all skills |
| `skill_recommend` | read | Suggest skills based on session tags |

### GitHub Integration (3 tools)

> [`tools/github/README.md`](tools/github/README.md)

| Tool | Type | Description |
|------|------|-------------|
| `session_link_repo` | write | Link a GitHub repo URL to a session |
| `session_unlink_repo` | write | Remove the repo link from a session |
| `repo_get_context` | read | Fetch default branch, recent commits, and open PRs |

### Config (4 tools)

> [`tools/config/README.md`](tools/config/README.md)

| Tool | Type | Description |
|------|------|-------------|
| `config_write` | write | Create or update a config entry |
| `config_read` | read | Read a single config value |
| `config_list` | read | List all config entries |
| `config_delete` | write | Delete a config entry |

### Vacuum (1 tool)

> [`tools/vacuum/README.md`](tools/vacuum/README.md)

| Tool | Type | Description |
|------|------|-------------|
| `vacuum_run` | write | Clean up old notes and archive/delete inactive sessions |

### Auth (7 tools)

| Tool | Type | Description |
|------|------|-------------|
| `user_me` | read | Return the currently authenticated user |
| `token_create` | write | Create a new personal access token for the current user |
| `token_list` | read | List all active tokens for the current user |
| `token_revoke` | write | Revoke a token by ID |
| `user_list` | read | List all users (admin only) |
| `user_set_role` | write | Change a user's role: `user` or `admin` (admin only) |
| `user_set_active` | write | Enable or disable a user account (admin only) |

---

## Web Panel

The web panel has two sections served under `/panel`:

### Admin (`/panel/mcp-admin/*`)

Full management interface — sessions, skills, config, notes, and import.
Requires admin credentials set via `ADMIN_USER` / `ADMIN_PASSWORD`.

| Page | Path | Description |
|------|------|-------------|
| Dashboard | `/panel/mcp-admin` | Stats: sessions, notes, skills, recent activity |
| Sessions | `/panel/mcp-admin/sessions` | List, search, filter (including archived) |
| Session Detail | `/panel/mcp-admin/sessions/:id` | Edit, pin, archive, link GitHub repo, manage notes |
| Skills | `/panel/mcp-admin/skills` | List, search, create skills |
| Skill Import | `/panel/mcp-admin/skills/import` | Drag & drop .md files, preview before confirm |
| Config | `/panel/mcp-admin/config` | CRUD for config key-value store |

### User Portal (`/panel/mcp-user/*`)

Self-service interface for registered users — token management and global skills.

| Page | Path | Description |
|------|------|-------------|
| Login | `/panel/mcp-user/login` | User login |
| Register | `/panel/mcp-user/register` | User registration |
| Portal | `/panel/mcp-user/portal` | Create, list, and revoke personal access tokens; set GitHub PAT |
| Skills | `/panel/mcp-user/skills` | Browse global skills |

> See [`web/README.md`](web/README.md) for full web panel documentation.

---

## Auto-Vacuum

Automated retention to keep the database lean. Controlled by config keys in the `config` table.

### Config Keys

| Key | Default | Description |
|-----|---------|-------------|
| `vacuum_enabled` | `false` | Enable the daily vacuum task |
| `vacuum_notes_days` | `90` | Delete unpinned notes older than N days |
| `vacuum_sessions_days` | `180` | Archive inactive sessions after N days; hard-delete archived sessions after another N days |

### Enable

```
config_write(key="vacuum_enabled", value="true")
```

### Manual run

```
vacuum_run(dry_run=true)    # preview — no changes made
vacuum_run(dry_run=false)   # execute
```

### Opt-out

| Method | Effect |
|--------|--------|
| `session_pin(session_id)` | Session excluded from all vacuum phases |
| Add tag `keep` to a session | Session excluded from archive phase |
| `note_pin(note_id, session_id)` | Note excluded from deletion |

---

## Security

| Measure | Detail |
|---------|--------|
| OAuth 2.0 AS (PKCE S256) | Standard authorization code flow for VSCode, CLI, and claude.ai |
| Per-user Bearer tokens (PAT) | Stored as SHA-256 hash; never logged or returned after creation |
| Roles | `user` (portal access) and `admin` (full panel); enforced on all routes |
| Master key fallback | `MCP_API_KEY` env var accepted as a valid Bearer token for any user |
| No shell injection | All subprocess calls use `asyncio.create_subprocess_exec` — no `shell=True` |
| Path traversal prevention | All Compose paths validated to stay within `COMPOSE_BASE_DIR` |
| Pydantic validation | All tool inputs validated with regex, length limits, and type checks |
| Non-root container | MCP process runs as `mcpuser` (UID 1000) |
| Loopback binding | Ports 8765, 3100, and 15432 bound to `127.0.0.1` — not internet-exposed |
| Web session cookie | `lm_oauth_session` encrypted via `iron-session`; 7-day expiry |
