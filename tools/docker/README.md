# tools/docker

Docker Compose management tools — read container state, tail logs, and control stack lifecycle via `docker compose` and `docker` CLI commands.

All commands run on the **host machine** where the MCP server is deployed. The server process must have access to the Docker socket.

---

## Tools

### Read-only

#### `docker_list_stacks`
List all Docker Compose stacks known to this host.

Returns a Markdown table with each stack's **Name**, **Status**, and **Config Files** path.
Runs `docker compose ls --all` under the hood.

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

| Parameter | Type   | Required | Description            |
|-----------|--------|----------|------------------------|
| `project` | string | yes      | Compose project name   |

**Example:**
```
docker_stack_ps(project="lm-mcp-ai")
```

Returns a table of container Name, Image, Status, and published Ports.

---

#### `docker_stack_logs`
Retrieve recent log output from a stack or a single service.

| Parameter | Type    | Required | Default | Description                              |
|-----------|---------|----------|---------|------------------------------------------|
| `project` | string  | yes      |         | Compose project name                     |
| `service` | string  | no       |         | Specific service name (omit for all)     |
| `tail`    | integer | no       | 100     | Number of lines to return (max 500)      |

**Example:**
```
docker_stack_logs(project="lm-mcp-ai", service="lm-mcp-ai", tail=200)
```

---

#### `docker_list_containers`
List Docker containers on this host (all or running only).

| Parameter        | Type    | Required | Default | Description                         |
|------------------|---------|----------|---------|-------------------------------------|
| `all_containers` | boolean | no       | false   | Include stopped containers if true  |

---

#### `docker_inspect_container`
Return low-level JSON information about a container (equivalent to `docker inspect`).

| Parameter   | Type   | Required | Description              |
|-------------|--------|----------|--------------------------|
| `container` | string | yes      | Container name or ID     |

---

#### `docker_stats`
Return a one-shot CPU, memory, and network usage snapshot for all running containers.

Runs `docker stats --no-stream`. Does **not** stream — returns current values only.

**Parameters:** none

**Example output:**
```
| Container         | CPU %  | Mem Usage    | Mem % | Net I/O         | Block I/O    |
|-------------------|--------|--------------|-------|-----------------|--------------|
| lm-mcp-postgres   | 0.12%  | 42MiB / 8GiB | 0.51% | 1.2MB / 800kB   | 5MB / 2MB    |
| lm-mcp-ai         | 0.03%  | 80MiB / 8GiB | 0.97% | 300kB / 200kB   | 0B / 0B      |
```

---

### Write / Lifecycle

> These tools modify container state. Use with care in production environments.

#### `docker_stack_up`
Start a Docker Compose stack (or a specific service) in detached mode.

| Parameter | Type   | Required | Description                              |
|-----------|--------|----------|------------------------------------------|
| `project` | string | yes      | Compose project name                     |
| `service` | string | no       | Start only this service (omit for all)   |

---

#### `docker_stack_down`
Stop and remove containers for a Docker Compose stack.

| Parameter        | Type    | Required | Default | Description                                  |
|------------------|---------|----------|---------|----------------------------------------------|
| `project`        | string  | yes      |         | Compose project name                         |
| `remove_volumes` | boolean | no       | false   | Also remove named volumes — **IRREVERSIBLE** |

---

#### `docker_stack_restart`
Restart all services (or one) in a Docker Compose stack.

| Parameter | Type   | Required | Description                                |
|-----------|--------|----------|--------------------------------------------|
| `project` | string | yes      | Compose project name                       |
| `service` | string | no       | Restart only this service (omit for all)   |

---

#### `docker_stack_pull`
Pull the latest Docker images for a compose stack or specific service.

| Parameter | Type   | Required | Description                               |
|-----------|--------|----------|-------------------------------------------|
| `project` | string | yes      | Compose project name                      |
| `service` | string | no       | Pull only this service's image (optional) |

---

#### `docker_exec`
Execute a command inside a running container.

The command is passed as a **list of tokens** — no shell expansion occurs.

| Parameter   | Type          | Required | Description                            |
|-------------|---------------|----------|----------------------------------------|
| `container` | string        | yes      | Container name or ID                   |
| `command`   | list[string]  | yes      | Command tokens to execute (max 20)     |

**Example:**
```
docker_exec(
    container="lm-mcp-postgres",
    command=["psql", "-U", "lmuser", "-d", "lmdb", "-c", "SELECT COUNT(*) FROM sessions;"]
)
```

---

## Safety Notes

- `docker_stack_down` with `remove_volumes=true` permanently deletes database volumes.
- `docker_exec` runs as the container's default user — scope your commands carefully.
- Read-only tools (`docker_list_*`, `docker_stack_logs`, `docker_stats`, `docker_inspect_container`) are safe to call at any time.
