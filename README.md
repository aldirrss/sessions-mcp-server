# lm-mcp-ai

MCP (Model Context Protocol) server running on a VPS inside Docker.
Connects **claude.ai Web**, **Claude Code CLI**, and **VSCode** to the same server —
enabling Docker stack management and cross-client session continuity backed by PostgreSQL.

---

## Table of Contents

1. [Architecture](#architecture)
2. [VPS Requirements](#vps-requirements)
3. [Installation on VPS](#installation-on-vps)
4. [Configuration](#configuration)
5. [Reverse Proxy Setup](#reverse-proxy-setup)
6. [Connect from claude.ai Web](#connect-from-claudeai-web)
7. [Connect from Claude Code CLI](#connect-from-claude-code-cli)
8. [Connect from VSCode](#connect-from-vscode)
9. [Available Tools](#available-tools)
10. [Session Continuity Workflow](#session-continuity-workflow)
11. [Database Monitoring with pgAdmin](#database-monitoring-with-pgadmin)
12. [Security](#security)
13. [Troubleshooting](#troubleshooting)

---

## Architecture

```
┌────────────────────────────────────────────────────────────────────┐
│  Clients                                                           │
│  ┌──────────────────┐  ┌──────────────────┐  ┌──────────────────┐ │
│  │  claude.ai Web   │  │  Claude Code CLI │  │  VSCode          │ │
│  │  (?key= param)   │  │  (X-API-Key hdr) │  │  (X-API-Key hdr) │ │
│  └────────┬─────────┘  └────────┬─────────┘  └────────┬─────────┘ │
│           └──────────────────── │ HTTPS ─────────────┘            │
│                                 ▼                                  │
│  ┌──────────────────────────────────────────────────────────────┐  │
│  │  nginx / Cloudflare (TLS termination + Host header rewrite)  │  │
│  └─────────────────────────┬────────────────────────────────────┘  │
│                             │  HTTP 127.0.0.1:8765                 │
│  ┌──────────────────────────▼────────────────────────────────────┐ │
│  │  lm-mcp-ai (FastMCP — Streamable HTTP)                        │ │
│  │  container: lm-mcp-ai   port: 8765                            │ │
│  └──────────┬─────────────────────────────┬──────────────────────┘ │
│             │  Docker socket (read-only)   │  asyncpg               │
│  ┌──────────▼──────────────┐  ┌───────────▼──────────────────────┐ │
│  │  Docker Engine on VPS   │  │  PostgreSQL 15                   │ │
│  │  /opt/                  │  │  container: lm-mcp-postgres       │ │
│  │    ├── odoo/            │  │  db: mcp_sessions                 │ │
│  │    ├── monitoring/      │  │  port: 127.0.0.1:5432            │ │
│  │    └── ...              │  │  (accessible via SSH tunnel)      │ │
│  └─────────────────────────┘  └──────────────────────────────────┘ │
└────────────────────────────────────────────────────────────────────┘
```

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
| Public IP | Required | Required |
| Domain / Subdomain | Required (for HTTPS) | Required |

> RAM is higher than before because PostgreSQL runs as a separate container alongside the MCP server.

---

## Installation on VPS

### 1. Install Docker

```bash
curl -fsSL https://get.docker.com | sh
sudo usermod -aG docker $USER
newgrp docker
```

### 2. Clone the repository

```bash
git clone https://github.com/aldirrss/lm-mcp-ai.git /opt/lm-mcp-ai
cd /opt/lm-mcp-ai
```

### 3. Identify your compose projects base directory

The server discovers compose projects by scanning a base directory.
Check where your existing `docker-compose.yml` files live:

```bash
find /opt /home /root -name "docker-compose.yml" 2>/dev/null
```

Example output:
```
/opt/odoo/docker-compose.yml
/opt/monitoring/docker-compose.yml
/opt/n8n/docker-compose.yml
```

In this case, `COMPOSE_BASE_DIR=/opt` — each subdirectory is a project.

### 4. Configure environment

```bash
cp .env.example .env
```

Get the numeric GID of the Docker socket group:

```bash
stat -c '%g' /var/run/docker.sock
# Example output: 988
```

Generate secret keys and edit `.env`:

```bash
python3 -c "import secrets; print(secrets.token_hex(32))"   # for MCP_API_KEY
python3 -c "import secrets; print(secrets.token_hex(24))"   # for POSTGRES_PASSWORD
nano .env
```

Minimum `.env` to fill in:

```env
MCP_API_KEY=<your generated key>
MCP_EXTERNAL_HOST=mcp.yourdomain.com
COMPOSE_BASE_DIR=/opt          # adjust to match your setup
DOCKER_GID=988                 # from stat output above
POSTGRES_PASSWORD=<your generated password>
```

### 5. Build and start

```bash
docker compose up -d --build
```

Verify both containers are running:

```bash
docker compose ps
# Expected:
#   lm-mcp-postgres   Up (healthy)
#   lm-mcp-ai         Up

docker compose logs -f
```

The MCP server listens on `127.0.0.1:8765` and PostgreSQL on `127.0.0.1:5432`
(both loopback only — not exposed to the internet).

---

## Configuration

All configuration is via environment variables (`.env` file):

### MCP Server

| Variable | Required | Default | Description |
|----------|----------|---------|-------------|
| `MCP_API_KEY` | **Yes** | — | Secret key for all client authentication |
| `MCP_HOST` | No | `0.0.0.0` | Bind address inside the container |
| `MCP_PORT` | No | `8765` | Port inside the container |
| `MCP_EXTERNAL_HOST` | No | `mcp.lemacore.com` | Public hostname shown in server metadata |
| `COMPOSE_BASE_DIR` | No | `/opt/stacks` | Root directory containing compose project subdirs |
| `LOG_MAX_LINES` | No | `200` | Hard cap on log lines returned per request |
| `DOCKER_TIMEOUT` | No | `60` | Docker CLI subprocess timeout in seconds |
| `DOCKER_GID` | No | `999` | Numeric GID of the `docker` group on host |

### PostgreSQL

| Variable | Required | Default | Description |
|----------|----------|---------|-------------|
| `POSTGRES_PASSWORD` | **Yes** | — | Database password (strong random value) |
| `POSTGRES_DB` | No | `mcp_sessions` | Database name |
| `POSTGRES_USER` | No | `mcp_user` | Database user |
| `DATABASE_URL` | No | *(auto-built)* | Full DSN — only set to override with an external DB |

> `DATABASE_URL` is automatically constructed from `POSTGRES_USER`, `POSTGRES_PASSWORD`,
> and `POSTGRES_DB` in `docker-compose.yml`. You only need to set it manually if you want
> to use an external PostgreSQL instance.

---

## Reverse Proxy Setup

The MCP server must be accessible over **HTTPS** for claude.ai web to connect.
Choose one of the options below.

> **Critical for all options**: nginx **must** rewrite the `Host` header to `localhost`
> before passing the request to the MCP server. Without this, the FastMCP
> `TransportSecurityMiddleware` rejects every request with
> `421 Misdirected Request — Invalid Host header`.
>
> Always include:
> ```nginx
> proxy_set_header   Host "localhost";
> ```

| Option | nginx on VPS | certbot | cloudflared on VPS | Open port |
|--------|:---:|:---:|:---:|:---:|
| A — nginx + Let's Encrypt | Yes | Yes | No | 443 |
| B — Cloudflare DNS Proxy (recommended) | Yes | No | No | 80 |
| C — Cloudflare Tunnel | No | No | Yes | None |

### Option A — nginx + Let's Encrypt

```bash
sudo apt install -y nginx certbot python3-certbot-nginx
sudo certbot --nginx -d mcp.yourdomain.com
```

Create `/etc/nginx/sites-available/lm-mcp-ai`:

```nginx
server {
    listen 443 ssl;
    server_name mcp.yourdomain.com;

    ssl_certificate     /etc/letsencrypt/live/mcp.yourdomain.com/fullchain.pem;
    ssl_certificate_key /etc/letsencrypt/live/mcp.yourdomain.com/privkey.pem;

    location /mcp {
        proxy_pass         http://127.0.0.1:8765;
        proxy_http_version 1.1;
        proxy_set_header   Host "localhost";        # REQUIRED
        proxy_set_header   X-Real-IP $remote_addr;
        proxy_set_header   Upgrade $http_upgrade;
        proxy_set_header   Connection "upgrade";
        proxy_read_timeout 300s;
    }
}
```

```bash
sudo ln -s /etc/nginx/sites-available/lm-mcp-ai /etc/nginx/sites-enabled/
sudo nginx -t && sudo systemctl reload nginx
```

### Option B — Cloudflare DNS Proxy (recommended if DNS is on Cloudflare)

No certbot needed on the VPS. Cloudflare handles TLS.

**Step 1** — Cloudflare DNS dashboard: add an A record for your subdomain with proxy ON (orange cloud).

**Step 2** — Cloudflare SSL/TLS → Overview → select **Flexible**
(Client ↔ Cloudflare = HTTPS, Cloudflare ↔ VPS = HTTP).

**Step 3** — Install nginx (HTTP only):

```bash
sudo apt install -y nginx
```

Create `/etc/nginx/sites-available/lm-mcp-ai`:

```nginx
server {
    listen 80;
    server_name mcp.yourdomain.com;

    set_real_ip_from 103.21.244.0/22;
    set_real_ip_from 103.22.200.0/22;
    set_real_ip_from 103.31.4.0/22;
    set_real_ip_from 104.16.0.0/13;
    set_real_ip_from 104.24.0.0/14;
    set_real_ip_from 108.162.192.0/18;
    set_real_ip_from 131.0.72.0/22;
    set_real_ip_from 141.101.64.0/18;
    set_real_ip_from 162.158.0.0/15;
    set_real_ip_from 172.64.0.0/13;
    set_real_ip_from 173.245.48.0/20;
    set_real_ip_from 188.114.96.0/20;
    set_real_ip_from 190.93.240.0/20;
    set_real_ip_from 197.234.240.0/22;
    set_real_ip_from 198.41.128.0/17;
    real_ip_header CF-Connecting-IP;

    location /mcp {
        proxy_pass         http://127.0.0.1:8765;
        proxy_http_version 1.1;
        proxy_set_header   Host "localhost";        # REQUIRED
        proxy_set_header   X-Real-IP $remote_addr;
        proxy_set_header   CF-Connecting-IP $http_cf_connecting_ip;
        proxy_read_timeout 300s;
    }
}
```

```bash
sudo ln -s /etc/nginx/sites-available/lm-mcp-ai /etc/nginx/sites-enabled/
sudo nginx -t && sudo systemctl reload nginx
sudo ufw allow 80/tcp && sudo ufw reload
```

### Option C — Cloudflare Tunnel (no open inbound port)

```bash
curl -L --output cloudflared.deb \
  https://github.com/cloudflare/cloudflared/releases/latest/download/cloudflared-linux-amd64.deb
sudo dpkg -i cloudflared.deb
cloudflared tunnel login
cloudflared tunnel create lm-mcp-ai
cloudflared tunnel route dns lm-mcp-ai mcp.yourdomain.com
```

Create `~/.cloudflared/config.yml`:

```yaml
tunnel: lm-mcp-ai
credentials-file: /root/.cloudflared/<tunnel-id>.json

ingress:
  - hostname: mcp.yourdomain.com
    service: http://127.0.0.1:8765
    originRequest:
      httpHostHeader: "localhost"   # REQUIRED
  - service: http_status:404
```

```bash
sudo cloudflared service install
sudo systemctl start cloudflared
```

---

## Connect from claude.ai Web

The claude.ai web connector UI only has two fields: **Name** and **Remote MCP server URL**.
There is no field for custom headers — the API key must be embedded in the URL as `?key=`.

### Steps

1. Go to **claude.ai → Settings → Connectors → Add custom connector**

2. Fill in the form:

   | Field | Value |
   |-------|-------|
   | **Name** | `MCP Lema` |
   | **Remote MCP server URL** | `https://mcp.yourdomain.com/mcp?key=YOUR_MCP_API_KEY` |
   | **OAuth Client ID** | *(leave empty)* |
   | **OAuth Client Secret** | *(leave empty)* |

3. Click **Add**. Claude will list all 17 available tools.

> Replace `YOUR_MCP_API_KEY` with the value of `MCP_API_KEY` from your `.env` file.
> The URL must include the `/mcp` path. A URL without it will not work.

### Note on URL security

The `?key=` parameter may appear in nginx access logs. To suppress it:

```nginx
access_log off;   # inside the server {} block
```

---

## Connect from Claude Code CLI

### Option A — Remote HTTP (recommended)

Connects your local Claude Code CLI directly to the MCP server on the VPS.
No local Python environment needed.

```bash
claude mcp add --transport http --scope user mcp-lema \
  https://mcp.yourdomain.com/mcp \
  --header "X-API-Key: YOUR_MCP_API_KEY"
```

> `--scope user` stores the config in `~/.claude.json`, making it available in all projects.
> Without `--scope user`, the MCP is only active in the current directory.

Verify:

```bash
claude mcp list
# mcp-lema   http   https://mcp.yourdomain.com/mcp   connected
```

**Manual config** — edit `~/.claude.json` directly:

```json
{
  "globalMcpServers": {
    "mcp-lema": {
      "type": "http",
      "url": "https://mcp.yourdomain.com/mcp",
      "headers": {
        "X-API-Key": "YOUR_MCP_API_KEY"
      }
    }
  }
}
```

### Option B — Run server locally via stdio (local Docker only)

For managing Docker on your local machine instead of the VPS:

```bash
cd /path/to/lm-mcp-ai
pip install -r requirements.txt
cp .env.example .env && nano .env
```

```bash
claude mcp add docker-local \
  --command python \
  --args /path/to/lm-mcp-ai/server.py \
  --env MCP_API_KEY=any-value-for-stdio \
  --env COMPOSE_BASE_DIR=/your/local/stacks \
  --env DATABASE_URL=postgresql://mcp_user:password@localhost:5432/mcp_sessions
```

---

## Connect from VSCode

VSCode supports MCP servers via the Claude extension (Anthropic) or via the
`.vscode/mcp.json` workspace file.

### Method 1 — Workspace config (`.vscode/mcp.json`)

Create `.vscode/mcp.json` in your project root:

```json
{
  "servers": {
    "mcp-lema": {
      "type": "http",
      "url": "https://mcp.yourdomain.com/mcp",
      "headers": {
        "X-API-Key": "YOUR_MCP_API_KEY"
      }
    }
  }
}
```

> This config is workspace-scoped. Do NOT commit `YOUR_MCP_API_KEY` to version control.
> Use a `.env`-based substitution or add `.vscode/mcp.json` to `.gitignore`.

### Method 2 — User settings (`settings.json`)

Open **Preferences → Settings → Open Settings (JSON)** and add:

```json
{
  "claude.mcpServers": {
    "mcp-lema": {
      "type": "http",
      "url": "https://mcp.yourdomain.com/mcp",
      "headers": {
        "X-API-Key": "YOUR_MCP_API_KEY"
      }
    }
  }
}
```

This makes the MCP available globally in all VSCode workspaces on your machine.

### Verify in VSCode

After saving the config:
1. Open the Claude panel in VSCode (Anthropic extension)
2. Look for the tools icon or MCP status indicator
3. All 17 tools should appear in the tool list

---

## Available Tools

### Docker Tools — Read-Only

These tools only read state from Docker. They never modify running containers.

| Tool | Description |
|------|-------------|
| `docker_list_stacks` | List all Docker Compose stacks discovered under `COMPOSE_BASE_DIR` |
| `docker_stack_ps` | Show containers and their current state within a specific stack |
| `docker_stack_logs` | Fetch recent log output from a stack or a specific service |
| `docker_list_containers` | List all Docker containers on the host (running and/or stopped) |
| `docker_inspect_container` | Full JSON inspection of a container (like `docker inspect`) |
| `docker_stats` | One-shot CPU, memory, and network usage snapshot for all running containers |

#### `docker_list_stacks`

No parameters required. Returns a Markdown table of all compose stacks.

```
| Name       | Status       | Config Files               |
|------------|--------------|----------------------------|
| odoo       | running(3)   | /opt/odoo/docker-compose.yml |
| monitoring | running(2)   | /opt/monitoring/docker-compose.yml |
```

#### `docker_stack_ps`

```json
{ "project": "odoo" }
```

Returns a table of containers in the stack with name, image, status, and exposed ports.

#### `docker_stack_logs`

```json
{ "project": "odoo", "service": "web", "tail": 100 }
```

- `project` — compose project name (required)
- `service` — specific service name (optional; omit for all services)
- `tail` — number of lines to return (default: 100, max: 500)

#### `docker_list_containers`

```json
{ "all_containers": false }
```

- `all_containers` — include stopped containers if `true` (default: `false`)

#### `docker_inspect_container`

```json
{ "container": "odoo-web-1" }
```

Returns the full JSON object from `docker inspect`.

#### `docker_stats`

No parameters required. Returns a snapshot table of CPU %, memory, network I/O, and block I/O
for all currently running containers.

---

### Docker Tools — Write / Lifecycle

These tools modify the state of running stacks or containers. Use with care.

| Tool | Description | Destructive |
|------|-------------|:-----------:|
| `docker_stack_up` | Start a stack or specific service in detached mode | No |
| `docker_stack_down` | Stop and remove containers (optionally remove volumes) | Conditional |
| `docker_stack_restart` | Restart all services or a specific service in a stack | No |
| `docker_stack_pull` | Pull latest images without restarting | No |
| `docker_exec` | Execute a command inside a running container | Yes |

#### `docker_stack_up`

```json
{ "project": "odoo", "service": "web" }
```

- `project` — compose project name (required)
- `service` — start only this service (optional; omit for all)

Runs `docker compose up -d [service]`.

#### `docker_stack_down`

```json
{ "project": "odoo", "remove_volumes": false }
```

- `project` — compose project name (required)
- `remove_volumes` — also remove named volumes declared in the compose file (default: `false`)

> Setting `remove_volumes: true` is **irreversible** — all data in named volumes will be deleted.

#### `docker_stack_restart`

```json
{ "project": "odoo", "service": "web" }
```

- `project` — compose project name (required)
- `service` — restart only this service (optional; omit for all)

#### `docker_stack_pull`

```json
{ "project": "odoo" }
```

Pulls latest images for the stack. Does **not** restart containers — follow with `docker_stack_up`
to apply the new images.

#### `docker_exec`

```json
{ "container": "odoo-web-1", "command": ["cat", "/etc/os-release"] }
```

- `container` — container name or ID (required)
- `command` — command as a list of tokens (no shell expansion; max 20 tokens)

Example commands:
```json
{ "container": "odoo-db-1", "command": ["psql", "-U", "odoo", "-c", "SELECT version();"] }
{ "container": "odoo-web-1", "command": ["ls", "-la", "/mnt/extra-addons"] }
```

---

### Session Store Tools

These tools enable cross-client session continuity. A **session** is a named context object
(title + body + notes) stored in PostgreSQL. Any client (Web, CLI, VSCode) can read, write,
and append to the same session.

| Tool | Description | Modifies State |
|------|-------------|:--------------:|
| `session_write` | Create or overwrite a session context | Yes |
| `session_read` | Read a session's full context and notes | No |
| `session_list` | List all sessions (optionally filtered by tag) | No |
| `session_append` | Append a timestamped note without overwriting context | Yes |
| `session_delete` | Permanently delete a session | Yes |
| `session_search` | Full-text search across title, context, notes, and tags | No |

#### `session_write`

Creates a new session or overwrites an existing one. Notes are preserved across overwrites.

```json
{
  "session_id": "odoo-refactor-2026",
  "title": "Odoo 17 Module Refactor",
  "context": "## Current State\nRefactoring the custom `hr_attendance` module for Odoo 17.\n\n## Goals\n- Remove deprecated v16 APIs\n- Add new contract types\n- Fix leave calculation bug\n\n## Next Steps\n1. Run test suite after model changes\n2. Update manifest to v17 format",
  "source": "vscode",
  "tags": ["odoo", "backend", "refactor"]
}
```

Parameters:
- `session_id` — unique key (letters, digits, hyphens, underscores; max 100 chars)
- `title` — short human-readable title (max 200 chars)
- `context` — full context body: current state, goals, decisions, next steps
- `source` — origin client: `web`, `cli`, `vscode`, or any identifier (default: `unknown`)
- `tags` — optional list of strings for filtering

Response:
```
Session `odoo-refactor-2026` created.
**Title:** Odoo 17 Module Refactor
**Source:** vscode | tags: odoo, backend, refactor
**Updated:** 2026-04-30 10:15:22+00
```

#### `session_read`

Reads the full context and all notes for a session.

```json
{ "session_id": "odoo-refactor-2026" }
```

Response:
```
# Session: Odoo 17 Module Refactor
**ID:** `odoo-refactor-2026` | **Source:** vscode
**Created:** 2026-04-30 10:15:22+00 | **Updated:** 2026-04-30 14:33:01+00
**Tags:** odoo, backend, refactor

---
## Context
## Current State
Refactoring the custom `hr_attendance` module for Odoo 17.
...

---
## Notes (2)

**[1] 2026-04-30 12:00:00+00 (cli)**
Completed model migration. Tests pass for contract types.

**[2] 2026-04-30 14:33:01+00 (web)**
Leave calculation bug traced to `_get_work_days()` — fix in progress.
```

#### `session_list`

```json
{ "tag": "odoo" }
```

- `tag` — filter by tag (optional; omit to list all)

Response:
```
## Sessions (5 total, 12 notes)
*Last updated: 2026-04-30 14:33:01+00*

| ID | Title | Source | Tags | Notes | Updated |
|----|-------|--------|------|-------|---------|
| `odoo-refactor-2026` | Odoo 17 Module Refactor | vscode | odoo, backend | 2 | 2026-04-30 14:33 |
| `feat-auth-dev` | Auth Feature Development | cli | auth, backend | 5 | 2026-04-29 18:20 |
```

#### `session_append`

Appends a timestamped note to an existing session without overwriting its context.
Use this to log progress, decisions, or blockers mid-work.

```json
{
  "session_id": "odoo-refactor-2026",
  "content": "Leave calculation bug fixed. PR #42 created and waiting for review.",
  "source": "cli"
}
```

Response:
```
Note appended to `odoo-refactor-2026` (total notes: 3).
**Timestamp:** 2026-04-30 15:00:00+00 | **Source:** cli
```

#### `session_delete`

```json
{ "session_id": "odoo-refactor-2026" }
```

Permanently deletes the session and all its notes (cascading delete in PostgreSQL).

#### `session_search`

Full-text search using PostgreSQL `tsvector` + ILIKE fallback.
Searches across title, context, notes content, and tags.

```json
{ "query": "leave calculation" }
```

Response:
```
## Search results for 'leave calculation' (1 found)

### `odoo-refactor-2026` — Odoo 17 Module Refactor
*Updated: 2026-04-30 14:33:01+00*
> Leave calculation bug traced to `_get_work_days()` — fix in progress.
```

---

## Session Continuity Workflow

The session store enables seamless handoff between clients. A typical workflow:

```
Claude Web (morning)
  → session_write("feat-auth", context="Started JWT implementation...")

Claude Code CLI (afternoon)
  → session_read("feat-auth")          ← resumes exactly where Web left off
  → session_append("feat-auth", "Completed token refresh logic. Tests pass.")

VSCode (next day)
  → session_read("feat-auth")          ← sees both original context and CLI note
  → session_write("feat-auth", context="Updated: added refresh token rotation...")
  → session_append("feat-auth", "Deployed to staging. Monitoring for issues.")
```

**Recommended system prompt** (add to your Claude system prompt or project instructions):

```
At the start of each conversation, if the user mentions a project name or session ID,
call session_read with that ID to restore full context before responding.
When ending a conversation with unfinished work, call session_write to save progress.
Use session_append to log important decisions or blockers during the conversation.
```

---

## Database Monitoring with pgAdmin

The PostgreSQL container is accessible from your local machine via SSH tunnel.
No extra Docker service is needed — use pgAdmin Desktop.

### 1. Open SSH tunnel

```bash
ssh -L 5432:127.0.0.1:5432 your-user@your-vps-ip -N
```

> Keep this terminal open while using pgAdmin. The `-N` flag opens the tunnel without
> executing a remote command.

### 2. Connect in pgAdmin Desktop

Add a new server with these settings:

| Field | Value |
|-------|-------|
| **Name** | `MCP Sessions (VPS)` |
| **Host** | `localhost` |
| **Port** | `5432` |
| **Database** | `mcp_sessions` |
| **Username** | `mcp_user` |
| **Password** | *(value of `POSTGRES_PASSWORD` in your `.env`)* |

### Database schema

| Table | Description |
|-------|-------------|
| `sessions` | Main session records: `session_id`, `title`, `context`, `source`, `tags`, `search_vec`, `created_at`, `updated_at` |
| `notes` | Appended notes with FK to `sessions.session_id` (cascading delete) |

Useful queries:

```sql
-- All sessions ordered by last update
SELECT session_id, title, source, tags, updated_at FROM sessions ORDER BY updated_at DESC;

-- Session with its notes
SELECT s.title, n.content, n.source, n.created_at
FROM sessions s
JOIN notes n ON s.session_id = n.session_id
WHERE s.session_id = 'my-session-id'
ORDER BY n.created_at;

-- Full-text search
SELECT session_id, title FROM sessions
WHERE search_vec @@ plainto_tsquery('english', 'your search terms');

-- Note count per session
SELECT s.session_id, s.title, COUNT(n.id) AS notes
FROM sessions s
LEFT JOIN notes n ON s.session_id = n.session_id
GROUP BY s.session_id, s.title
ORDER BY notes DESC;
```

---

## Security

- **No `shell=True`** — all subprocess calls use `asyncio.create_subprocess_exec`;
  command injection via tool parameters is not possible.
- **API key middleware** — every request to `/mcp` must carry the correct `X-API-Key` header
  or `?key=` query param. Missing or wrong keys return `401 Unauthorized`.
- **Docker socket is read-only** — mounted as `:ro` in compose; the container cannot start
  new Docker daemons or modify the socket.
- **Path traversal prevention** — `COMPOSE_BASE_DIR` is resolved once and all project paths
  are checked to stay within it before any command runs.
- **Input validation** — all tool inputs pass through Pydantic models with regex constraints
  and length limits before touching the Docker CLI or database.
- **Non-root container** — the MCP process runs as `mcpuser` (UID 1000).
- **Loopback binding** — both `8765` (MCP) and `5432` (PostgreSQL) are bound to
  `127.0.0.1` only; no direct internet access.
- **Read-only container filesystem** — `read_only: true` in compose; only `/tmp` is writable
  via `tmpfs`.
- **TransportSecurityMiddleware** — FastMCP includes DNS rebinding protection.
  This server disables it at startup because nginx enforces TLS and `ApiKeyMiddleware`
  handles all authentication. This is safe for reverse-proxy deployments.

---

## Troubleshooting

### Server does not start

```bash
docker compose logs mcp
# Check for: missing MCP_API_KEY, POSTGRES_PASSWORD not set, port already in use
```

### PostgreSQL not healthy

```bash
docker compose logs postgres
docker compose ps   # check "health" column
```

If postgres is stuck in `starting` state:

```bash
docker compose restart postgres
```

### MCP server can't connect to database

The MCP container will not start until the `postgres` service passes its healthcheck
(`condition: service_healthy` in compose). If you see a connection error after the
healthcheck passes:

```bash
# Verify DATABASE_URL is constructed correctly
docker compose exec mcp env | grep DATABASE_URL
```

### `Unable to find group docker` on container start

The `group_add` in `docker-compose.yml` must use a numeric GID, not the group name.

```bash
stat -c '%g' /var/run/docker.sock   # e.g. 988
```

Set `DOCKER_GID=988` in `.env`, then rebuild:

```bash
docker compose up -d --build
```

### 401 Unauthorized from claude.ai

- Confirm the URL includes the `/mcp` path: `https://mcp.yourdomain.com/mcp?key=...`
- Confirm the key in the URL exactly matches `MCP_API_KEY` in `.env`.
- Rebuild after changing `.env`: `docker compose up -d --build`.

### 421 Misdirected Request — Invalid Host header

nginx must rewrite the Host header to `localhost`:

```nginx
proxy_set_header   Host "localhost";
```

If using Cloudflare Tunnel, add `httpHostHeader: "localhost"` to the ingress rule.

### "Project directory not found"

- Confirm `COMPOSE_BASE_DIR` points to the **parent** of your compose directories
  (e.g. `/opt`, not `/opt/odoo`).
- Check the volume mount in `docker-compose.yml`: `/opt:/opt:ro` must match your base dir.

### `docker_exec` returns permission denied

```bash
stat -c '%g' /var/run/docker.sock   # must match DOCKER_GID in .env
docker compose exec mcp id          # should show the docker GID in the groups list
```

### Cloudflare Tunnel shows offline

```bash
sudo systemctl status cloudflared
sudo journalctl -u cloudflared -n 50
```

### Test the endpoint manually

```bash
# Using X-API-Key header (Claude Code CLI / VSCode style)
curl -s -X POST https://mcp.yourdomain.com/mcp \
  -H "X-API-Key: YOUR_MCP_API_KEY" \
  -H "Content-Type: application/json" \
  -d '{"jsonrpc":"2.0","id":1,"method":"tools/list","params":{}}' | jq .result.tools[].name

# Using ?key= query param (claude.ai web style)
curl -s -X POST "https://mcp.yourdomain.com/mcp?key=YOUR_MCP_API_KEY" \
  -H "Content-Type: application/json" \
  -d '{"jsonrpc":"2.0","id":1,"method":"tools/list","params":{}}' | jq .result.tools[].name
```

A successful response lists all 17 tool names.
