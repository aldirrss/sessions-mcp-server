# lm-docker-mcp

MCP (Model Context Protocol) server for managing Docker Compose stacks on a VPS,
accessible from both **claude.ai web** and **Claude Code CLI (local)**.

---

## Table of Contents

1. [Architecture](#architecture)
2. [VPS Requirements](#vps-requirements)
3. [Installation on VPS](#installation-on-vps)
4. [Configuration](#configuration)
5. [Reverse Proxy Setup](#reverse-proxy-setup)
6. [Connect from claude.ai Web](#connect-from-claudeai-web)
7. [Connect from Local Claude Code CLI](#connect-from-local-claude-code-cli)
8. [Available Tools](#available-tools)
9. [Security](#security)
10. [Troubleshooting](#troubleshooting)

---

## Architecture

```
┌─────────────────────────────────────────────────────────────┐
│  claude.ai/code (Web)                                       │
│  Claude Code CLI (Local)                                    │
│         │                                                   │
│         ▼  HTTPS + X-API-Key header  (or ?key= param)      │
│  ┌──────────────────────────────┐                          │
│  │  nginx / Cloudflare Tunnel   │  ← TLS termination       │
│  └──────────┬───────────────────┘                          │
│             │  HTTP localhost:8765                          │
│  ┌──────────▼───────────────────┐                          │
│  │  lm-docker-mcp (FastMCP)     │  ← this project         │
│  │  transport: streamable-http  │                          │
│  │  path: /mcp                  │                          │
│  └──────────┬───────────────────┘                          │
│             │  Docker socket (read-only)                    │
│  ┌──────────▼───────────────────┐                          │
│  │  Docker Engine on VPS        │                          │
│  │  /opt/                       │                          │
│  │    ├── odoo-lema/            │                          │
│  │    ├── monitoring/           │                          │
│  │    └── ...                   │                          │
│  └──────────────────────────────┘                          │
└─────────────────────────────────────────────────────────────┘
```

---

## VPS Requirements

| Component | Minimum | Recommended |
|-----------|---------|-------------|
| OS | Ubuntu 22.04 LTS | Ubuntu 24.04 LTS |
| CPU | 1 vCPU | 2 vCPU |
| RAM | 512 MB | 1 GB |
| Disk | 5 GB | 10 GB |
| Docker | 24.x+ | 27.x+ |
| Docker Compose | v2.20+ | v2.27+ |
| Python | 3.11+ | 3.12+ |
| Public IP | Required | Required |
| Domain / Subdomain | Required (for HTTPS) | Required |

> The MCP server itself is lightweight. The RAM/disk above covers the MCP server only,
> not the Docker stacks it manages.

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
git clone https://github.com/your-org/lm-docker-mcp.git /opt/lm-docker-mcp
cd /opt/lm-docker-mcp
```

### 3. Identify your compose projects base directory

This server discovers compose projects by scanning a base directory.
Check where your existing `docker-compose.yml` files live:

```bash
find /opt /home /root -name "docker-compose.yml" 2>/dev/null
```

Example output:
```
/opt/odoo-lema/docker-compose.yml
/opt/monitoring/docker-compose.yml
/opt/n8n/docker-compose.yml
```

In this case, `COMPOSE_BASE_DIR=/opt` — each subdirectory is a project.
Set this value in `.env` in the next step.

### 4. Configure environment

```bash
cp .env.example .env
```

Get the numeric GID of the Docker socket group (needed for `group_add`):

```bash
stat -c '%g' /var/run/docker.sock
# Example output: 988
```

Generate a secure API key and edit `.env`:

```bash
python3 -c "import secrets; print(secrets.token_hex(32))"
nano .env
```

Minimal `.env` to fill in:

```env
MCP_API_KEY=<paste your generated key here>
COMPOSE_BASE_DIR=/opt          # adjust to match your setup
DOCKER_GID=988                 # use the output from stat above
```

### 5. Build and start

```bash
docker compose up -d --build
```

Verify it is running:

```bash
docker compose ps
docker compose logs -f
```

The server listens on `127.0.0.1:8765` by default (loopback only, not exposed directly).

---

## Configuration

All configuration is via environment variables (`.env` file):

| Variable | Required | Default | Description |
|----------|----------|---------|-------------|
| `MCP_API_KEY` | **Yes** | — | Secret key sent in `X-API-Key` header by Claude |
| `MCP_HOST` | No | `0.0.0.0` | Bind address inside the container |
| `MCP_PORT` | No | `8765` | Port inside the container |
| `COMPOSE_BASE_DIR` | No | `/opt/stacks` | Root directory containing compose project subdirs |
| `LOG_MAX_LINES` | No | `200` | Hard cap on log lines returned per request |
| `DOCKER_TIMEOUT` | No | `60` | Docker CLI subprocess timeout in seconds |
| `DOCKER_GID` | No | `999` | Numeric GID of the `docker` group on host |

---

## Reverse Proxy Setup

The MCP server must be accessible over **HTTPS** for claude.ai web to connect.
Choose one of the options below.

> **Critical for all options**: nginx **must** rewrite the `Host` header to
> `localhost` before passing the request to the MCP server. Without this, the
> FastMCP `TransportSecurityMiddleware` rejects every request with
> `421 Misdirected Request — Invalid Host header`.
>
> Always include:
> ```nginx
> proxy_set_header   Host "localhost";
> ```

| Option | Nginx on VPS | certbot | cloudflared on VPS | Open port |
|--------|:---:|:---:|:---:|:---:|
| A — Nginx + Let's Encrypt | Yes | Yes | No | 443 |
| B — Cloudflare DNS Proxy (**recommended if DNS is on Cloudflare**) | Yes | **No** | No | 80 |
| C — Cloudflare Tunnel | No | No | Yes | None |

### Option A — Nginx + Let's Encrypt (VPS without Cloudflare DNS)

```bash
sudo apt install -y nginx certbot python3-certbot-nginx

# Replace mcp.yourdomain.com with your actual subdomain
sudo certbot --nginx -d mcp.yourdomain.com
```

Create `/etc/nginx/sites-available/lm-docker-mcp`:

```nginx
server {
    listen 443 ssl;
    server_name mcp.yourdomain.com;

    ssl_certificate     /etc/letsencrypt/live/mcp.yourdomain.com/fullchain.pem;
    ssl_certificate_key /etc/letsencrypt/live/mcp.yourdomain.com/privkey.pem;

    location /mcp {
        proxy_pass         http://127.0.0.1:8765;
        proxy_http_version 1.1;
        proxy_set_header   Host "localhost";        # REQUIRED — rewrites Host for MCP transport security
        proxy_set_header   X-Real-IP $remote_addr;
        proxy_set_header   Upgrade $http_upgrade;
        proxy_set_header   Connection "upgrade";
        proxy_read_timeout 300s;
    }
}
```

```bash
sudo ln -s /etc/nginx/sites-available/lm-docker-mcp /etc/nginx/sites-enabled/
sudo nginx -t && sudo systemctl reload nginx
```

### Option B — Cloudflare DNS Proxy (recommended if DNS is already on Cloudflare)

This is the simplest setup when your domain is already managed by Cloudflare.
Cloudflare acts as TLS termination — **no certbot needed on the VPS**.

**Step 1 — Cloudflare DNS dashboard**

Add an A record for your subdomain with the orange cloud (proxy) enabled:

```
Type  : A
Name  : mcp
Value : <your VPS public IP>
Proxy : ON  ← orange cloud ☁️, not grey
```

**Step 2 — Cloudflare SSL/TLS mode**

Go to Cloudflare dashboard → **SSL/TLS → Overview** → select **Flexible**.

> Flexible = Client ↔ Cloudflare is HTTPS, Cloudflare ↔ VPS is HTTP (port 80).
> No certificate is required on the VPS.

**Step 3 — Install nginx on VPS (HTTP only, no certbot)**

```bash
sudo apt install -y nginx
```

Create `/etc/nginx/sites-available/lm-docker-mcp`:

```nginx
server {
    listen 80;
    server_name mcp.yourdomain.com;

    # Trust Cloudflare real IP headers
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
        proxy_set_header   Host "localhost";        # REQUIRED — rewrites Host for MCP transport security
        proxy_set_header   X-Real-IP $remote_addr;
        proxy_set_header   CF-Connecting-IP $http_cf_connecting_ip;
        proxy_read_timeout 300s;
    }
}
```

```bash
sudo ln -s /etc/nginx/sites-available/lm-docker-mcp /etc/nginx/sites-enabled/
sudo nginx -t && sudo systemctl reload nginx
```

**Step 4 — Open port 80 in VPS firewall**

```bash
sudo ufw allow 80/tcp
sudo ufw reload
```

> Cloudflare connects to your VPS on port 80. Port 443 does NOT need to be open.
> The public internet only sees HTTPS via Cloudflare — direct HTTP to the VPS IP
> is blocked by Cloudflare's WAF if you enable it.

---

### Option C — Cloudflare Tunnel (no open inbound port needed)

```bash
# Install cloudflared
curl -L --output cloudflared.deb \
  https://github.com/cloudflare/cloudflared/releases/latest/download/cloudflared-linux-amd64.deb
sudo dpkg -i cloudflared.deb

# Authenticate and create tunnel
cloudflared tunnel login
cloudflared tunnel create lm-docker-mcp
cloudflared tunnel route dns lm-docker-mcp mcp.yourdomain.com
```

Create `~/.cloudflared/config.yml`:

```yaml
tunnel: lm-docker-mcp
credentials-file: /root/.cloudflared/<tunnel-id>.json

ingress:
  - hostname: mcp.yourdomain.com
    service: http://127.0.0.1:8765
    originRequest:
      httpHostHeader: "localhost"   # REQUIRED — same as proxy_set_header Host "localhost" in nginx
  - service: http_status:404
```

```bash
sudo cloudflared service install
sudo systemctl start cloudflared
```

---

## Connect from claude.ai Web

The claude.ai web connector UI (**Settings → Connectors → Add custom connector**)
only has two fields: **Name** and **Remote MCP server URL**.
There is no field for custom headers.

The API key must be embedded in the URL as a query parameter (`?key=`).
The server accepts this automatically alongside the `X-API-Key` header.

### Step 1 — Open connector settings

Go to: **claude.ai → Settings → Connectors → Add custom connector**

### Step 2 — Fill in the form

| Field | Value |
|-------|-------|
| **Name** | `Docker VPS` |
| **Remote MCP server URL** | `https://mcp.yourdomain.com/mcp?key=YOUR_MCP_API_KEY` |
| **OAuth Client ID** | *(leave empty)* |
| **OAuth Client Secret** | *(leave empty)* |

> Replace `YOUR_MCP_API_KEY` with the value of `MCP_API_KEY` from your `.env` file.
>
> **Important**: The URL must include the `/mcp` path. A URL without the path
> (e.g. `https://mcp.yourdomain.com?key=...`) will not work.

Click **Add**. Claude will immediately list the available Docker tools.

### Note on URL security

Embedding a secret in a URL query string means it may appear in:
- nginx access logs on the VPS
- Cloudflare request logs

To suppress it from nginx logs, add this to your nginx config inside the `server {}` block:

```nginx
access_log off;   # or use a custom log format that omits $request
```

For Cloudflare, go to **Logs → Log Retention** and disable if needed.

---

## Connect from Local Claude Code CLI

### Option A — Remote HTTP (same MCP server on VPS)

This connects your local Claude Code CLI directly to the MCP server running on the VPS.
No local Python environment needed.

Add the server globally (available in all projects):

```bash
claude mcp add --transport http --scope user mcp-lema https://mcp.yourdomain.com/mcp \
  --header "X-API-Key: your-mcp-api-key-here"
```

> **Scope matters**:
> - `--scope user` → stored in `~/.claude.json`, available in all projects on this machine.
> - `--scope local` (default) → stored scoped to the current directory.
>   The MCP will only be active when Claude Code is opened from that directory.
>
> Always use `--scope user` for a VPS MCP you want available in every project.

Verify connection:

```bash
claude mcp list
```

You should see `mcp-lema` listed as connected.

**Manual config** (if you prefer to edit directly):

The config file is `~/.claude.json`. Find or create the `"mcpServers"` key inside the
`"globalMcpServers"` section (global scope) or under the project path (local scope):

```json
{
  "globalMcpServers": {
    "mcp-lema": {
      "type": "http",
      "url": "https://mcp.yourdomain.com/mcp",
      "headers": {
        "X-API-Key": "your-mcp-api-key-here"
      }
    }
  }
}
```

> Note: `~/.claude.json` also contains per-project settings — edit carefully and
> prefer using the `claude mcp add` CLI command to avoid breaking the file structure.

### Option B — Run server locally via stdio (for local Docker only)

If you want to manage Docker on your local machine (not the VPS):

```bash
cd /path/to/lm-docker-mcp
pip install -r requirements.txt
cp .env.example .env && nano .env
```

Add via CLI:

```bash
claude mcp add docker-local --command python --args /path/to/lm-docker-mcp/server.py \
  --env MCP_API_KEY=any-value-for-stdio \
  --env COMPOSE_BASE_DIR=/your/local/stacks
```

Or add manually to `~/.claude/claude_mcp_config.json`:

```json
{
  "mcpServers": {
    "docker-local": {
      "type": "stdio",
      "command": "python",
      "args": ["/path/to/lm-docker-mcp/server.py"],
      "env": {
        "MCP_API_KEY": "any-value-for-stdio",
        "COMPOSE_BASE_DIR": "/your/local/stacks"
      }
    }
  }
}
```

> For stdio mode, the last line of `server.py` must be changed to:
> ```python
> mcp.run()   # stdio (no transport argument)
> ```

---

## Available Tools

| Tool | Description | Modifies State |
|------|-------------|----------------|
| `docker_list_stacks` | List all compose stacks on the host | No |
| `docker_stack_ps` | Show containers and their state in a stack | No |
| `docker_stack_logs` | Fetch recent log output (configurable tail) | No |
| `docker_list_containers` | List all Docker containers | No |
| `docker_inspect_container` | Full JSON inspection of a container | No |
| `docker_stats` | One-shot CPU / RAM / network snapshot | No |
| `docker_stack_up` | Start a stack or service (`up -d`) | Yes |
| `docker_stack_down` | Stop and remove containers (optional: volumes) | Yes |
| `docker_stack_restart` | Restart stack or specific service | Yes |
| `docker_stack_pull` | Pull latest images (does not restart) | Yes |
| `docker_exec` | Execute a command inside a container | Yes |

---

## Security

- **No `shell=True`** — all subprocess calls use `asyncio.create_subprocess_exec`;
  command injection via tool parameters is not possible.
- **API key middleware** — every HTTP request to `/mcp` must carry the correct
  `X-API-Key` header or `?key=` query param; missing or wrong keys receive `401 Unauthorized`.
- **Docker socket is read-only** in the compose mount (`/var/run/docker.sock:ro`);
  the container cannot start new Docker daemons.
- **Path traversal prevention** — `COMPOSE_BASE_DIR` is resolved and all project paths
  are checked to stay within it before any command runs.
- **Input validation** — all tool inputs pass through Pydantic models with regex constraints
  before touching the Docker CLI.
- **Non-root container** — the MCP server process runs as `mcpuser` (UID 1000).
- **Bind loopback** — the container port is bound to `127.0.0.1` only; TLS and auth
  are handled by nginx / Cloudflare in front of it.
- **TransportSecurityMiddleware** — FastMCP includes DNS rebinding protection that
  validates the `Host` header. This server monkey-patches `validate_request` to always
  return `None` (accept), since nginx enforces TLS and API key auth handles all
  authentication. This is safe for reverse-proxy deployments.

---

## Troubleshooting

### Server does not start

```bash
docker compose logs mcp
# Check for: missing MCP_API_KEY, port already in use
```

### `Unable to find group docker` on container start

The `group_add` entry in `docker-compose.yml` must use a **numeric GID**, not the
group name `docker` (which does not exist inside the container).

Get the GID on the VPS host:

```bash
stat -c '%g' /var/run/docker.sock
# Example: 988
```

Set it in `.env`:

```env
DOCKER_GID=988
```

Then rebuild:

```bash
docker compose up -d --build
```

### 401 Unauthorized from claude.ai

- Check that the URL includes the `/mcp` path: `https://mcp.yourdomain.com/mcp?key=...`
- Confirm the key in the URL exactly matches `MCP_API_KEY` in `.env`.
- Rebuild after changing `.env`: `docker compose up -d --build`.

### 421 Misdirected Request — Invalid Host header

FastMCP includes `TransportSecurityMiddleware` that rejects requests whose `Host`
header does not match an allowed list. In reverse-proxy deployments the Host header
is the public domain (e.g. `mcp.yourdomain.com`), which is rejected by default.

**Fix**: ensure nginx rewrites the Host header to `localhost`:

```nginx
proxy_set_header   Host "localhost";
```

This is already included in the nginx configs in this README. If you configured nginx
independently and omitted this line, add it and reload:

```bash
sudo nginx -t && sudo systemctl reload nginx
```

If you are using Cloudflare Tunnel instead of nginx, add `httpHostHeader: "localhost"`
to the ingress rule in `~/.cloudflared/config.yml`.

### "Project directory not found"

- Run `docker compose logs mcp` to see the exact path being searched.
- Make sure `COMPOSE_BASE_DIR` in `.env` points to the parent of your compose project
  directories (e.g. `/opt`, not `/opt/odoo-lema`).
- The volume mount in `docker-compose.yml` must expose that directory into the
  container: `/opt:/opt:ro`.

### `docker_exec` returns permission denied

- The `mcpuser` inside the container calls `docker exec` via the socket.
- Ensure `DOCKER_GID` in `.env` matches the output of `stat -c '%g' /var/run/docker.sock`
  on the VPS host, and that `group_add: ["${DOCKER_GID:-999}"]` is present in
  `docker-compose.yml`.

### Cloudflare Tunnel shows offline

```bash
sudo systemctl status cloudflared
sudo journalctl -u cloudflared -n 50
```

### Test the endpoint manually

```bash
# Using X-API-Key header (Claude Code CLI style)
curl -s -X POST https://mcp.yourdomain.com/mcp \
  -H "X-API-Key: your-key" \
  -H "Content-Type: application/json" \
  -d '{"jsonrpc":"2.0","id":1,"method":"tools/list","params":{}}' | jq .

# Using ?key= query param (claude.ai web style)
curl -s -X POST "https://mcp.yourdomain.com/mcp?key=your-key" \
  -H "Content-Type: application/json" \
  -d '{"jsonrpc":"2.0","id":1,"method":"tools/list","params":{}}' | jq .
```

A successful response will include a `result.tools` array listing all 11 tools.
