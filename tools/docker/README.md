# tools/docker

Docker Compose management tools — read container state, tail logs, and control stack
lifecycle via `docker compose` and `docker` CLI commands.

All commands run on the **host machine** where the MCP server is deployed. The server
process requires access to the Docker socket (`/var/run/docker.sock`).

---

## Tools

### Read-only

#### `docker_list_stacks`
List all Docker Compose stacks known to this host.

Returns a Markdown table with each stack's Name, Status, and Config Files path.
Runs `docker compose ls --all` internally.

**Parameters:** none

**Example output:**
```
| Name        | Status  | Config Files                        |
|-------------|---------|-------------------------------------|
| lm-mcp-ai   | running | /opt/lm-mcp-ai/docker-compose.yml   |
| my-app      | exited  | /opt/my-app/docker-compose.yml      |
```

---

#### `docker_stack_ps`
List all containers in a specific Docker Compose stack with their current state.

| Parameter | Type | Required | Description |
|-----------|------|----------|-------------|
| `project` | string | yes | Compose project name |

Returns a table of container Name, Image, Status, and published Ports.

**Example:**
```
docker_stack_ps(project="lm-mcp-ai")
```

---

#### `docker_stack_logs`
Retrieve recent log output from a stack or a single service.

| Parameter | Type | Required | Default | Description |
|-----------|------|----------|---------|-------------|
| `project` | string | yes | — | Compose project name |
| `service` | string | no | — | Specific service name (omit for all services) |
| `tail` | integer | no | `100` | Number of lines to return (max capped by `LOG_MAX_LINES`) |

**Example:**
```
docker_stack_logs(project="lm-mcp-ai", service="lm-mcp-ai", tail=200)
```

---

#### `docker_list_containers`
List Docker containers on this host.

| Parameter | Type | Required | Default | Description |
|-----------|------|----------|---------|-------------|
| `all_containers` | boolean | no | `false` | Include stopped containers when `true` |

---

#### `docker_inspect_container`
Return low-level JSON information about a container (equivalent to `docker inspect`).

| Parameter | Type | Required | Description |
|-----------|------|----------|-------------|
| `container` | string | yes | Container name or ID |

---

#### `docker_stats`
Return a one-shot CPU, memory, and network usage snapshot for all running containers.

Runs `docker stats --no-stream`. Returns current values only — does not stream.

**Parameters:** none

**Example output:**
```
| Container         | CPU %  | Mem Usage    | Mem % | Net I/O         | Block I/O  |
|-------------------|--------|--------------|-------|-----------------|------------|
| lm-mcp-postgres   | 0.12%  | 42MiB / 8GiB | 0.51% | 1.2MB / 800kB   | 5MB / 2MB  |
| lm-mcp-ai         | 0.03%  | 80MiB / 8GiB | 0.97% | 300kB / 200kB   | 0B / 0B    |
```

---

### Write / Lifecycle

These tools modify container state. Review the target stack before use in production.

#### `docker_stack_up`
Start a Docker Compose stack (or a specific service) in detached mode.

| Parameter | Type | Required | Description |
|-----------|------|----------|-------------|
| `project` | string | yes | Compose project name |
| `service` | string | no | Start only this service (omit for all) |

---

#### `docker_stack_down`
Stop and remove containers for a Docker Compose stack.

| Parameter | Type | Required | Default | Description |
|-----------|------|----------|---------|-------------|
| `project` | string | yes | — | Compose project name |
| `remove_volumes` | boolean | no | `false` | Also remove named volumes — irreversible |

---

#### `docker_stack_restart`
Restart all services (or one) in a Docker Compose stack.

| Parameter | Type | Required | Description |
|-----------|------|----------|-------------|
| `project` | string | yes | Compose project name |
| `service` | string | no | Restart only this service (omit for all) |

---

#### `docker_stack_pull`
Pull the latest Docker images for a Compose stack or specific service.

| Parameter | Type | Required | Description |
|-----------|------|----------|-------------|
| `project` | string | yes | Compose project name |
| `service` | string | no | Pull only this service's image (optional) |

---

#### `docker_exec`
Execute a command inside a running container.

The command is passed as a **list of tokens** — no shell expansion occurs.

| Parameter | Type | Required | Description |
|-----------|------|----------|-------------|
| `container` | string | yes | Container name or ID |
| `command` | list[string] | yes | Command tokens to execute (max 20 tokens) |

**Example:**
```
docker_exec(
    container="lm-mcp-postgres",
    command=["psql", "-U", "mcp_user", "-d", "mcp_sessions", "-c", "SELECT COUNT(*) FROM sessions;"]
)
```

---

## Configuration

| Env Variable | Default | Description |
|--------------|---------|-------------|
| `COMPOSE_BASE_DIR` | `/opt/stacks` | Root directory containing Compose project subdirectories |
| `LOG_MAX_LINES` | `200` | Hard cap on log lines returned per request |
| `DOCKER_TIMEOUT` | `60` | Docker CLI subprocess timeout in seconds |

---

## Safety Notes

- `docker_stack_down` with `remove_volumes=true` permanently deletes database volumes. This cannot be undone.
- `docker_exec` runs as the container's default user — scope commands carefully.
- Read-only tools (`docker_list_stacks`, `docker_stack_ps`, `docker_stack_logs`, `docker_list_containers`, `docker_inspect_container`, `docker_stats`) are safe to call at any time.
- All Compose project paths are validated to stay within `COMPOSE_BASE_DIR` — path traversal is prevented.
