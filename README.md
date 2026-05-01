# lm-mcp-ai

A self-hosted **MCP (Model Context Protocol) server** running in Docker on a VPS.
Connects **claude.ai Web**, **Claude Code CLI**, and **VSCode** to a shared backend —
providing Docker stack management, persistent session memory, a skill library, GitHub integration,
dynamic configuration, and automated data retention — all backed by PostgreSQL.

---

## Table of Contents

1. [Why This Exists](#why-this-exists)
2. [Architecture](#architecture)
3. [VPS Requirements](#vps-requirements)
4. [Installation](#installation)
5. [Configuration](#configuration)
6. [Reverse Proxy Setup](#reverse-proxy-setup)
7. [Connect Clients](#connect-clients)
8. [Tools Reference](#tools-reference)
9. [Web Admin Panel](#web-admin-panel)
10. [Session Continuity Workflow](#session-continuity-workflow)
11. [Auto-Vacuum](#auto-vacuum)
12. [Database Schema](#database-schema)
13. [Database Monitoring with pgAdmin](#database-monitoring-with-pgadmin)
14. [Security](#security)
15. [Troubleshooting](#troubleshooting)

---

## Why This Exists

Without a persistent backend, every Claude conversation starts from scratch. Context, decisions,
and progress are lost between sessions and across clients.

**lm-mcp-ai** solves this by giving Claude a permanent memory store and set of server-side tools:

| Problem | Solution |
|---------|----------|
| No memory across sessions | Session store in PostgreSQL — read/write context from any client |
| No memory across clients | Web, CLI, VSCode all connect to the same server |
| Can't manage Docker from Claude | 11 Docker tools — list stacks, read logs, restart services, exec commands |
| Instructions drift between conversations | Skill library + dynamic config table — load knowledge and instructions on demand |
| Can't see current repo state | GitHub integration — link a session to a repo, fetch live commits and PRs |
| Database grows unbounded | Auto-vacuum with configurable retention, note pinning, session archiving |

---

## Architecture

```
┌──────────────────────────────────────────────────────────────────────────┐
│  Clients                                                                  │
│  ┌───────────────────┐  ┌──────────────────┐  ┌──────────────────┐       │
│  │  claude.ai Web    │  │ Claude Code CLI  │  │  VSCode          │       │
│  │  (?key= param)    │  │ (X-API-Key hdr)  │  │ (X-API-Key hdr)  │       │
│  └─────────┬─────────┘  └────────┬─────────┘  └────────┬─────────┘       │
│            └───────────────────── HTTPS ───────────────┘                 │
│                                   ▼                                       │
│  ┌────────────────────────────────────────────────────────────────────┐   │
│  │  nginx / Cloudflare  (TLS + Host header rewrite)                   │   │
│  └─────────────────────────┬──────────────────────────────────────────┘   │
│                             │  http://127.0.0.1:8765/mcp                  │
│                             │  http://127.0.0.1:3100  (web admin)         │
│  ┌──────────────────────────▼──────────────────────────────────────────┐  │
│  │  lm-mcp-ai  (FastMCP — Streamable HTTP)                             │  │
│  │  43 tools across 6 categories                                       │  │
│  └───────────────┬─────────────────────────────────────────────────────┘  │
│                  │                                                         │
│    ┌─────────────▼──────────────┐   ┌──────────────────────────────────┐  │
│    │  Docker Engine (VPS host)  │   │  PostgreSQL 15                   │  │
│    │  /opt/stacks/              │   │  sessions, notes, skills,        │  │
│    │    ├── odoo/               │   │  config, skill_versions,         │  │
│    │    ├── monitoring/         │   │  session_skills                  │  │
│    │    └── ...                 │   │  port: 127.0.0.1:15432           │  │
│    └────────────────────────────┘   └──────────────────────────────────┘  │
│                                                                            │
│  ┌──────────────────────────────────────────────────────────────────────┐  │
│  │  lm-mcp-web  (Next.js 15 — Web Admin Panel)                         │  │
│  │  https://mcp.yourdomain.com/panel/mcp-admin                         │  │
│  └──────────────────────────────────────────────────────────────────────┘  │
└──────────────────────────────────────────────────────────────────────────┘
```

### Containers

| Container | Image | Port (loopback) | Purpose |
|-----------|-------|-----------------|---------|
| `lm-mcp-postgres` | `postgres:15` | `127.0.0.1:15432` | Database |
| `lm-mcp-ai` | custom (Python) | `127.0.0.1:8765` | MCP server |
| `lm-mcp-web` | custom (Next.js) | `127.0.0.1:3100` | Web admin |

---

## VPS Requirements

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

Generate secret keys:

```bash
python3 -c "import secrets; print(secrets.token_hex(32))"   # MCP_API_KEY
python3 -c "import secrets; print(secrets.token_hex(24))"   # POSTGRES_PASSWORD
python3 -c "import secrets; print(secrets.token_hex(32))"   # SESSION_SECRET
```

Edit `.env` and fill in at minimum:

```env
# MCP Server
MCP_API_KEY=<generated>
MCP_EXTERNAL_HOST=mcp.yourdomain.com
COMPOSE_BASE_DIR=/opt           # parent dir of your compose project dirs

# Docker
DOCKER_GID=988                  # from stat output above

# PostgreSQL
POSTGRES_PASSWORD=<generated>

# Web Admin
ADMIN_USER=admin
ADMIN_PASSWORD=<strong password>
SESSION_SECRET=<generated>

# GitHub (optional — for private repos + higher API rate limits)
GITHUB_TOKEN=ghp_xxxxxxxxxxxx
```

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

## Configuration

### MCP Server variables

| Variable | Required | Default | Description |
|----------|----------|---------|-------------|
| `MCP_API_KEY` | **Yes** | — | Secret key for client authentication |
| `MCP_HOST` | No | `0.0.0.0` | Bind address inside the container |
| `MCP_PORT` | No | `8765` | Port inside the container |
| `MCP_EXTERNAL_HOST` | No | `mcp.lemacore.com` | Public hostname shown in server metadata |
| `COMPOSE_BASE_DIR` | No | `/opt/stacks` | Root directory containing compose project subdirs |
| `LOG_MAX_LINES` | No | `200` | Hard cap on log lines returned per request |
| `DOCKER_TIMEOUT` | No | `60` | Docker CLI subprocess timeout (seconds) |
| `DOCKER_GID` | No | `999` | Numeric GID of the docker group on host |
| `GITHUB_TOKEN` | No | — | GitHub PAT for repo context (read-only scope) |

### PostgreSQL variables

| Variable | Required | Default | Description |
|----------|----------|---------|-------------|
| `POSTGRES_PASSWORD` | **Yes** | — | Database password |
| `POSTGRES_DB` | No | `mcp_sessions` | Database name |
| `POSTGRES_USER` | No | `mcp_user` | Database user |
| `POSTGRES_HOST_PORT` | No | `15432` | Host-side port for SSH tunnel / pgAdmin access |
| `DATABASE_URL` | No | *(auto-built)* | Full DSN — only set to use an external PostgreSQL |

### Web Admin variables

| Variable | Required | Default | Description |
|----------|----------|---------|-------------|
| `ADMIN_USER` | **Yes** | — | Admin username for web panel login |
| `ADMIN_PASSWORD` | **Yes** | — | Admin password for web panel login |
| `SESSION_SECRET` | **Yes** | — | Encryption key for iron-session cookies (min 32 chars) |

---

## Reverse Proxy Setup

The MCP server (`/mcp`) and web admin (`/panel/mcp-admin`) must be accessible over HTTPS.
nginx must rewrite the `Host` header to `localhost` — required by FastMCP's transport security.

### nginx config

```nginx
server {
    listen 443 ssl;                         # or listen 80; for Cloudflare proxy
    server_name mcp.yourdomain.com;

    # MCP server (claude.ai / CLI / VSCode)
    location /mcp {
        proxy_pass         http://127.0.0.1:8765;
        proxy_http_version 1.1;
        proxy_set_header   Host "localhost";    # REQUIRED
        proxy_set_header   X-Real-IP $remote_addr;
        proxy_set_header   Upgrade $http_upgrade;
        proxy_set_header   Connection "upgrade";
        proxy_read_timeout 300s;
    }

    # Web admin panel (Next.js)
    location /panel/mcp-admin {
        proxy_pass         http://127.0.0.1:3100;
        proxy_http_version 1.1;
        proxy_set_header   Host $host;
        proxy_set_header   X-Real-IP $remote_addr;
    }
}
```

> For Cloudflare DNS Proxy (HTTP + orange cloud), use `listen 80;` and omit SSL directives.
> For Cloudflare Tunnel, add `httpHostHeader: "localhost"` to the `/mcp` ingress rule.

---

## Connect Clients

### claude.ai Web

1. Go to **Settings → Connectors → Add custom connector**
2. Fill in:

   | Field | Value |
   |-------|-------|
   | Name | `MCP Lema` |
   | Remote MCP server URL | `https://mcp.yourdomain.com/mcp?key=YOUR_MCP_API_KEY` |

> The `?key=` parameter is required — claude.ai web has no header field.

### Claude Code CLI

```bash
claude mcp add --transport http --scope user mcp-lema \
  https://mcp.yourdomain.com/mcp \
  --header "X-API-Key: YOUR_MCP_API_KEY"
```

### VSCode

Create `.vscode/mcp.json` in your project:

```json
{
  "servers": {
    "mcp-lema": {
      "type": "http",
      "url": "https://mcp.yourdomain.com/mcp",
      "headers": { "X-API-Key": "YOUR_MCP_API_KEY" }
    }
  }
}
```

### Verify connection

```bash
curl -s -X POST "https://mcp.yourdomain.com/mcp?key=YOUR_MCP_API_KEY" \
  -H "Content-Type: application/json" \
  -d '{"jsonrpc":"2.0","id":1,"method":"tools/list","params":{}}' \
  | jq '[.result.tools[].name]'
```

---

## Tools Reference

43 tools across 6 categories. See each category's `README.md` in [`tools/`](tools/) for full
parameter documentation and examples.

### Docker (11 tools)

> [`tools/docker/README.md`](tools/docker/README.md)

| Tool | Type | Description |
|------|------|-------------|
| `docker_list_stacks` | read | List all compose stacks under `COMPOSE_BASE_DIR` |
| `docker_stack_ps` | read | Container state within a stack |
| `docker_stack_logs` | read | Recent log output from a stack or service |
| `docker_list_containers` | read | All containers on the host |
| `docker_inspect_container` | read | Full `docker inspect` JSON |
| `docker_stats` | read | CPU/memory/network snapshot |
| `docker_stack_up` | **write** | Start a stack or service |
| `docker_stack_down` | **write** | Stop and remove containers |
| `docker_stack_restart` | **write** | Restart a stack or service |
| `docker_stack_pull` | **write** | Pull latest images |
| `docker_exec` | **write** | Execute a command in a container |

### Sessions (13 tools)

> [`tools/sessions/README.md`](tools/sessions/README.md)

| Tool | Type | Description |
|------|------|-------------|
| `session_write` | write | Create or overwrite a session context |
| `session_read` | read | Full context + pinned notes + notes |
| `session_list` | read | List sessions (pinned first, archived hidden by default) |
| `session_append` | write | Append a timestamped note |
| `session_delete` | write | Permanently delete a session |
| `session_search` | read | Full-text search across sessions and notes |
| `note_pin` | write | Pin a note (always at top, never vacuumed) |
| `note_unpin` | write | Remove pin from a note |
| `session_compact` | write | Merge old notes into context field, delete them |
| `session_pin` | write | Protect a session from auto-vacuum |
| `session_unpin` | write | Remove protection |
| `session_archive` | write | Soft-delete a session |
| `session_restore` | write | Restore an archived session |

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
| `session_unlink_repo` | write | Remove the repo link |
| `repo_get_context` | read | Fetch branch, recent commits, and open PRs |

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

---

## Web Admin Panel

A Next.js 15 web interface for managing sessions, skills, and config without using Claude.

**URL:** `https://mcp.yourdomain.com/panel/mcp-admin`

> See [`web/README.md`](web/README.md) for full documentation.

| Page | URL | Description |
|------|-----|-------------|
| Dashboard | `/` | Stats: sessions, notes, skills, skill usage (7d) |
| Sessions | `/sessions` | List, search, filter (including archived) |
| Session Detail | `/sessions/:id` | Edit, pin, archive, link GitHub repo, manage notes |
| Skills | `/skills` | List, search, create skill |
| Skill Detail | `/skills/:slug` | Edit content, view version history and sessions |
| Config | `/config` | CRUD for config key-value store |

---

## Session Continuity Workflow

```
Morning — claude.ai Web
  → session_list()                         # see active sessions
  → session_read("feat-auth-dev")          # restore context
  → config_list()                          # load any dynamic instructions
  → repo_get_context("feat-auth-dev")      # get current branch + open PRs
  → ... work ...
  → session_append("feat-auth-dev", "Completed token refresh. PR #12 created.")

Afternoon — Claude Code CLI (different machine)
  → session_read("feat-auth-dev")          # same context + note from Web session
  → note_pin(note_id, "feat-auth-dev")     # mark important decision as pinned
  → ... work ...
  → session_write("feat-auth-dev", ...)    # update context with new progress

Next day — VSCode
  → session_read("feat-auth-dev")          # pinned note always visible at top
  → session_compact("feat-auth-dev", before_days=7)  # merge week-old notes into context
```

### Recommended CLAUDE.md / system prompt

```
At the start of every conversation:
1. Call session_list to see active sessions.
2. Call session_read if a relevant session exists.
3. Call config_list to load dynamic instructions.
4. Call repo_get_context if the session has a linked GitHub repo.

During the conversation:
- Call session_append to log important decisions or blockers.
- Call note_pin to mark notes that must stay visible long-term.

Before ending a conversation with unfinished work:
- Call session_write to save current state.
```

---

## Auto-Vacuum

Automated retention to keep the database lean. Disabled by default — enable via the Config page
or with `config_write`.

### How it works

Runs once per day (asyncio task in the MCP server). Two-phase for sessions:

```
Phase 1 — inactive sessions → archived=true (hidden from session_list)
Phase 2 — sessions that have been archived for another vacuum_sessions_days → hard deleted
```

### Vacuum criteria (ALL must be true to archive a session)

- `pinned = false` — pinned sessions are never touched
- No tag `keep` or `archive` in the session's tags
- `updated_at < NOW() - vacuum_sessions_days days`

### Config keys

Set these via `config_write` or the Config page in the web admin:

| Key | Default | Description |
|-----|---------|-------------|
| `vacuum_enabled` | `false` | Enable the daily vacuum task |
| `vacuum_notes_days` | `90` | Delete unpinned notes older than N days |
| `vacuum_sessions_days` | `180` | Archive/delete inactive sessions after N days |

### Enable vacuum

```
config_write(key="vacuum_enabled", value="true")
```

### Manual run

```
vacuum_run(dry_run=true)    # preview — no changes
vacuum_run(dry_run=false)   # execute
```

---

## Database Schema

| Table | Key Columns | Description |
|-------|-------------|-------------|
| `sessions` | `session_id PK`, `title`, `context`, `tags[]`, `pinned`, `archived`, `repo_url`, `search_vec` | Main session records |
| `notes` | `id PK`, `session_id FK`, `content`, `source`, `pinned` | Timestamped notes appended to sessions |
| `skills` | `slug PK`, `name`, `content`, `summary`, `category`, `tags[]`, `source`, `search_vec` | Skill library |
| `skill_versions` | `id PK`, `slug`, `content`, `changed_at` | Content snapshots before each skill update |
| `session_skills` | `(session_id, skill_slug) PK`, `used_at` | Many-to-many: which skills were used in which sessions |
| `config` | `key PK`, `value`, `description` | Global key-value configuration store |

All tables use `TIMESTAMPTZ` for timestamps. Full-text search uses `TSVECTOR` columns populated
by `BEFORE INSERT OR UPDATE` triggers. Trigram indexes (`gin_trgm_ops`) enable fast `ILIKE` title search.

---

## Database Monitoring with pgAdmin

```bash
# Open SSH tunnel on your local machine
ssh -L 15432:127.0.0.1:15432 your-user@your-vps-ip -N
```

Connect pgAdmin Desktop to `localhost:15432`, database `mcp_sessions`, user `mcp_user`.

Useful queries:

```sql
-- All sessions ordered by last update
SELECT session_id, title, pinned, archived, tags, updated_at
FROM sessions ORDER BY pinned DESC, updated_at DESC;

-- Sessions approaching vacuum threshold (90 days inactive)
SELECT session_id, title, updated_at,
       NOW() - updated_at AS inactive_for
FROM sessions
WHERE pinned = false AND archived = false
  AND NOT (tags && ARRAY['keep','archive'])
ORDER BY updated_at ASC;

-- Skill usage leaderboard
SELECT sk.slug, sk.name, COUNT(ss.session_id) AS uses
FROM skills sk
LEFT JOIN session_skills ss ON ss.skill_slug = sk.slug
GROUP BY sk.slug, sk.name
ORDER BY uses DESC;

-- Full-text search across sessions and notes
SELECT DISTINCT s.session_id, s.title
FROM sessions s
LEFT JOIN notes n ON n.session_id = s.session_id
WHERE s.search_vec @@ plainto_tsquery('english', 'docker deployment')
   OR n.content ILIKE '%docker deployment%';
```

---

## Security

| Measure | Detail |
|---------|--------|
| API key auth | Every `/mcp` request requires `X-API-Key` header or `?key=` param |
| No shell injection | All subprocess calls use `asyncio.create_subprocess_exec` — no `shell=True` |
| Docker socket read-only | Mounted as `:ro`; container cannot modify the socket |
| Path traversal prevention | All compose paths are validated to stay within `COMPOSE_BASE_DIR` |
| Pydantic validation | All tool inputs validated with regex, length limits, and type checks |
| Non-root container | MCP process runs as `mcpuser` (UID 1000) |
| Loopback binding | Ports 8765, 3100, and 15432 are bound to `127.0.0.1` — not internet-exposed |
| Read-only container filesystem | `read_only: true` in compose; only `/tmp` writable via tmpfs |
| Web admin auth | iron-session encrypted cookie; credentials via `ADMIN_USER`/`ADMIN_PASSWORD` env vars |

---

## Troubleshooting

### Server does not start

```bash
docker compose logs mcp
# Look for: missing MCP_API_KEY, database connection errors, port conflicts
```

### PostgreSQL not healthy

```bash
docker compose logs postgres
docker compose restart postgres
```

### Web admin not reachable

```bash
docker compose logs web
# Check: ADMIN_USER, ADMIN_PASSWORD, SESSION_SECRET are set in .env
# Check nginx: location /panel/mcp-admin proxies to 127.0.0.1:3100
```

### 421 Misdirected Request

nginx must rewrite the Host header:
```nginx
proxy_set_header Host "localhost";
```

### 401 Unauthorized from claude.ai

- URL must include `/mcp` path: `https://mcp.yourdomain.com/mcp?key=...`
- Key must exactly match `MCP_API_KEY` in `.env`

### `Unable to find group docker`

`group_add` requires a numeric GID:
```bash
stat -c '%g' /var/run/docker.sock   # e.g. 988
# Set DOCKER_GID=988 in .env, then: docker compose up -d --build
```

### `repo_get_context` returns rate limit error

Set `GITHUB_TOKEN` in `.env` — unauthenticated requests are limited to 60/hour.
With a token: 5000/hour. Token requires `repo` read scope for private repos,
or no scope for public repos.

### Test MCP connection

```bash
curl -s -X POST "https://mcp.yourdomain.com/mcp?key=YOUR_KEY" \
  -H "Content-Type: application/json" \
  -d '{"jsonrpc":"2.0","id":1,"method":"tools/list","params":{}}' \
  | jq '[.result.tools[].name] | length'
# Expected: 43
```
