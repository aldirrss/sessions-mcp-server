# lm-mcp-ai

A self-hosted **MCP (Model Context Protocol) server** running in Docker on a VPS.
Connects **claude.ai Web**, **Claude Code CLI**, and **VSCode** to a shared backend —
providing persistent session memory, a skill library, GitHub integration, dynamic
configuration, and automated data retention, all backed by PostgreSQL.

---

## Table of Contents

1. [Architecture](#architecture)
2. [Prerequisites](#prerequisites)
3. [Installation](#installation)
4. [Environment Variables](#environment-variables)
5. [Reverse Proxy Setup](#reverse-proxy-setup)
6. [User Onboarding](#user-onboarding)
7. [Connecting Clients](#connecting-clients)
8. [URL Structure](#url-structure)
9. [Tools Reference](#tools-reference)
10. [Web Panel](#web-panel)
11. [Auto-Vacuum](#auto-vacuum)
12. [Security](#security)

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
│  │  lema-mcp-ai (FastMCP)     │  │  lema-mcp-web (Next.js 15) │   │
│  │  /mcp  /oauth/*           │  │  /panel/mcp-admin/*       │   │
│  │  /.well-known/*           │  │  /panel/mcp-user/*        │   │
│  └──────────────┬────────────┘  └──────────────┬────────────┘   │
│                 └──────────────┬───────────────┘                │
│                                ▼                                 │
│  ┌─────────────────────────────────────────────────────────┐    │
│  │  PostgreSQL 15  (127.0.0.1:15432)                       │    │
│  │  sessions · notes · skills · skill_versions             │    │
│  │  session_skills · config · users · user_tokens          │    │
│  └─────────────────────────────────────────────────────────┘    │
└─────────────────────────────────────────────────────────────────┘
```

### Containers

| Container | Image | Port (loopback) | Purpose |
|-----------|-------|-----------------|---------|
| `lema-mcp-postgres` | `postgres:15` | `127.0.0.1:15432` | Database |
| `lema-mcp-ai` | custom (Python) | `127.0.0.1:8765` | MCP server + OAuth AS |
| `lema-mcp-web` | custom (Next.js) | `127.0.0.1:3100` | Web panel |

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
git clone https://github.com/aldirrss/sessions-mcp-server.git /opt/lm-mcp-ai
cd /opt/lm-mcp-ai
```

### 3. Configure environment

```bash
cp web/.env.example web/.env
```

Generate all required secret values:

```bash
# SESSION_SECRET — cookie encryption key
openssl rand -hex 32

# POSTGRES_PASSWORD
openssl rand -hex 24

# ADMIN_PASSWORD_HASH — bcrypt hash of your admin password
node -e "require('bcryptjs').hash('your-strong-password', 12).then(console.log)"
```

Edit `web/.env` with the generated values (see [Environment Variables](#environment-variables) below).

### 4. Build and start

```bash
docker compose up -d --build
docker compose ps
# Expected:
#   lema-mcp-postgres   Up (healthy)
#   lema-mcp-ai         Up
#   lema-mcp-web        Up
```

---

## Environment Variables

### MCP Server

| Variable | Required | Default | Description |
|----------|----------|---------|-------------|
| `DATABASE_URL` | ✅ | — | PostgreSQL DSN: `postgresql://user:pass@host:5432/db` |
| `MCP_EXTERNAL_URL` | ✅ | — | Public base URL, e.g. `https://mcp.example.com` |
| `MCP_API_KEY` | — | — | Master key fallback for Bearer auth (admin access) |
| `MCP_HOST` | — | `0.0.0.0` | Bind address inside the container |
| `MCP_PORT` | — | `8765` | Port inside the container |
| `MCP_EXTERNAL_HOST` | — | — | External hostname (derived from `MCP_EXTERNAL_URL` if unset) |
| `MCP_ALLOWED_ORIGINS` | — | — | Comma-separated extra hostnames allowed by transport security (in addition to `MCP_EXTERNAL_URL` hostname, `localhost`, and `127.0.0.1`) |
| `TOKEN_TTL_DAYS` | — | `30` | OAuth access token lifetime in days |
| `GITHUB_TOKEN` | — | — | Fallback GitHub PAT when a user has no personal token set |

### Web Panel

| Variable | Required | Default | Description |
|----------|----------|---------|-------------|
| `DATABASE_URL` | ✅ | — | Same PostgreSQL DSN as above |
| `SESSION_SECRET` | ✅ | — | Cookie encryption key, minimum 32 characters |
| `ADMIN_USER` | ✅ | — | Admin username for the web panel |
| `ADMIN_PASSWORD_HASH` | ✅ | — | bcrypt hash of the admin password. Generate with: `node -e "require('bcryptjs').hash('yourpass', 12).then(console.log)"` |

### PostgreSQL (bundled container)

| Variable | Default | Description |
|----------|---------|-------------|
| `POSTGRES_PASSWORD` | — | Database password (required) |
| `POSTGRES_DB` | `mcp_sessions` | Database name |
| `POSTGRES_USER` | `mcp_user` | Database user |
| `POSTGRES_HOST_PORT` | `15432` | Host-side port for SSH tunnel or pgAdmin |

---

## Reverse Proxy Setup

All traffic must reach the server over HTTPS. The MCP server validates the `Host` header
against an allowlist derived from `MCP_EXTERNAL_URL`. Set the header correctly in your proxy:

```nginx
server {
    listen 443 ssl;
    server_name mcp.example.com;

    # MCP server — OAuth AS + MCP endpoint
    location ~ ^/(mcp|oauth|\.well-known) {
        proxy_pass         http://127.0.0.1:8765;
        proxy_http_version 1.1;
        proxy_set_header   Host $host;
        proxy_set_header   X-Real-IP $remote_addr;
        proxy_set_header   X-Forwarded-For $proxy_add_x_forwarded_for;
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
        proxy_set_header   X-Forwarded-For $proxy_add_x_forwarded_for;
    }
}
```

> **Cloudflare Tunnel:** use `listen 80;` and omit SSL directives. The `Host` header is
> automatically forwarded as the public domain — no extra config needed.

---

## User Onboarding

New users need an account and a Personal Access Token (PAT) before connecting any client.

### Step 1 — Register

Go to the registration page and create an account:

```
https://mcp.example.com/panel/mcp-user/register
```

Fill in **username** (lowercase, 3–50 chars), **email**, and **password** (minimum 8 characters).

### Step 2 — Save your token

After registration, your first PAT is displayed **once** — copy it immediately.

> This token cannot be retrieved again. If lost, log in to the portal and create a new one.

### Step 3 — Connect a client

Use the token as a Bearer header in your MCP client (see [Connecting Clients](#connecting-clients) below).

### Managing tokens

Log in to the portal to create additional tokens, revoke old ones, or set your GitHub PAT:

```
https://mcp.example.com/panel/mcp-user/portal
```

---

## Connecting Clients

### OAuth auto-discovery (claude.ai / VSCode)

The server exposes `/.well-known/oauth-authorization-server` and supports PKCE S256.
Clients that support OAuth 2.0 auto-discovery will find the authorization endpoint
automatically when pointed at `https://mcp.example.com/mcp`.

OAuth login page: `https://mcp.example.com/oauth/authorize`

### Bearer token (PAT)

Users create personal access tokens from the user portal (`/panel/mcp-user/portal`).
Tokens are stored as SHA-256 hashes and sent as `Authorization: Bearer <token>`.

### claude.ai Web (manual key)

1. Go to **Settings → Connectors → Add custom connector**
2. Set the URL to: `https://mcp.example.com/mcp?key=YOUR_TOKEN`

> The `?key=` query parameter is accepted as a Bearer token equivalent.

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
| `https://mcp.example.com/mcp` | MCP endpoint (Bearer auth required) |
| `https://mcp.example.com/oauth/authorize` | OAuth login page |
| `https://mcp.example.com/.well-known/oauth-authorization-server` | OAuth AS metadata |
| `https://mcp.example.com/.well-known/oauth-protected-resource` | OAuth resource metadata |
| `https://mcp.example.com/panel/mcp-user/login` | User login |
| `https://mcp.example.com/panel/mcp-user/register` | User registration |
| `https://mcp.example.com/panel/mcp-user/portal` | Token management |
| `https://mcp.example.com/panel/mcp-user/skills` | Global skills browser |
| `https://mcp.example.com/panel/mcp-admin/login` | Admin login |
| `https://mcp.example.com/panel/mcp-admin` | Admin dashboard |

---

## Tools Reference

Tools are grouped into 6 categories.

### Sessions (13 tools)

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
| `note_pin` | write | Pin a note (always visible, never vacuumed) |
| `note_unpin` | write | Unpin a note |

> **User isolation:** each authenticated user only sees their own sessions.
> Sessions created before isolation was introduced (no `owner_id`) remain visible to all users.
> Admin access (master key) bypasses isolation and sees all sessions.

### Skills (11 tools)

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

| Tool | Type | Description |
|------|------|-------------|
| `session_link_repo` | write | Link a GitHub repo URL to a session |
| `session_unlink_repo` | write | Remove the repo link from a session |
| `repo_get_context` | read | Fetch default branch, recent commits, and open PRs |

### Config (4 tools)

| Tool | Type | Description |
|------|------|-------------|
| `config_write` | write | Create or update a config entry |
| `config_read` | read | Read a single config value |
| `config_list` | read | List all config entries |
| `config_delete` | write | Delete a config entry |

### Vacuum (1 tool)

| Tool | Type | Description |
|------|------|-------------|
| `vacuum_run` | write | Clean up old notes and archive/delete inactive sessions |

### Auth (7 tools)

| Tool | Type | Description |
|------|------|-------------|
| `user_me` | read | Return the currently authenticated user |
| `token_create` | write | Create a new personal access token |
| `token_list` | read | List all active tokens for the current user |
| `token_revoke` | write | Revoke a token by ID |
| `user_list` | read | List all users (admin only) |
| `user_set_role` | write | Change a user's role: `user` or `admin` (admin only) |
| `user_set_active` | write | Enable or disable a user account (admin only) |

---

## Web Panel

The web panel has two sections served under `/panel`.

### Admin (`/panel/mcp-admin/*`)

Full management interface for sessions, skills, config, and users.
Login requires `ADMIN_USER` + `ADMIN_PASSWORD_HASH` credentials.
All admin API routes are protected by a server-side session guard — unauthenticated
requests return `401 Unauthorized`.

| Page | Path | Description |
|------|------|-------------|
| Dashboard | `/panel/mcp-admin` | Stats: sessions, notes, skills, recent activity |
| Sessions | `/panel/mcp-admin/sessions` | List, search, filter (including archived) |
| Session Detail | `/panel/mcp-admin/sessions/:id` | Edit, pin, archive, link GitHub repo, manage notes |
| Skills | `/panel/mcp-admin/skills` | List, search, create skills |
| Skill Import | `/panel/mcp-admin/skills/import` | Drag & drop `.md` files, preview before confirm |
| Users | `/panel/mcp-admin/users` | List users, promote/demote, activate/deactivate |
| Config | `/panel/mcp-admin/config` | CRUD for config key-value store |

### User Portal (`/panel/mcp-user/*`)

Self-service interface for registered users.

| Page | Path | Description |
|------|------|-------------|
| Login | `/panel/mcp-user/login` | User login |
| Register | `/panel/mcp-user/register` | User registration |
| Portal | `/panel/mcp-user/portal` | Create, list, and revoke personal access tokens; set GitHub PAT |
| Skills | `/panel/mcp-user/skills` | Browse global skills |

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
| OAuth token TTL | Access tokens expire after `TOKEN_TTL_DAYS` days (default 30); `expires_in` included in token response (RFC 6749) |
| Per-user Bearer tokens (PAT) | Stored as SHA-256 hash; never logged or returned after creation |
| Admin password hashing | Admin login uses bcrypt (`ADMIN_PASSWORD_HASH`); plain-text passwords not accepted |
| Admin login rate limiting | Max 5 failed attempts per IP per 15 minutes; returns `429 Too Many Requests` |
| Admin API auth guard | All `/api/*` admin routes require a valid admin session; unauthenticated requests return `401` |
| Transport security | MCP `Host`/`Origin` headers validated against an allowlist derived from `MCP_EXTERNAL_URL` (+ optional `MCP_ALLOWED_ORIGINS`); unknown hosts return `403` |
| User isolation | Sessions are scoped to `owner_id`; users cannot read or modify each other's sessions |
| Input validation | All API route inputs validated with Zod schemas (login, register, token creation, user management) |
| Roles | `user` (portal access) and `admin` (full panel); enforced on all routes |
| Master key fallback | `MCP_API_KEY` env var accepted as admin Bearer token for emergency access |
| Non-root container | MCP process runs as `mcpuser` (UID 1000) |
| Loopback binding | Ports 8765, 3100, and 15432 bound to `127.0.0.1` — not internet-exposed |
| No shell injection | All subprocess calls use `asyncio.create_subprocess_exec` — no `shell=True` |
| Pydantic validation | All MCP tool inputs validated with type checks, regex, and length limits |
| Web session cookie | `lm-session` encrypted via `iron-session`; 8-hour expiry; `httpOnly`, `SameSite=lax`, `Secure` in production |
