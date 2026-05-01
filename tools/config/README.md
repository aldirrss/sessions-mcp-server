# tools/config

Dynamic configuration store — a PostgreSQL key-value table that lets you change Claude's behavior across all sessions without redeploying the server.

Config entries are loaded at the start of every conversation via `config_list` (as instructed in `CLAUDE.md`).

---

## Data Model

| Column        | Type        | Description                             |
|---------------|-------------|-----------------------------------------|
| `key`         | text (PK)   | Config key in `snake_case`              |
| `value`       | text        | String value                            |
| `description` | text        | Human-readable explanation              |
| `updated_at`  | timestamptz | Last-modified timestamp (auto-updated)  |

---

## Tools

#### `config_write`
Create or update a configuration entry.

| Parameter     | Type   | Required | Description                                         |
|---------------|--------|----------|-----------------------------------------------------|
| `key`         | string | yes      | Config key (`snake_case`, e.g. `vacuum_notes_days`) |
| `value`       | string | yes      | Value to store (always stored as text)              |
| `description` | string | no       | What this config controls (preserved if omitted on update) |

**Example:**
```
config_write(
    key="claude_project_instructions",
    value="Always use PostgreSQL best practices. Prefer asyncpg over SQLAlchemy.",
    description="Additional instructions injected at conversation start"
)
```

---

#### `config_read`
Read a single config entry by key.

| Parameter | Type   | Required | Description      |
|-----------|--------|----------|------------------|
| `key`     | string | yes      | Config key to read |

---

#### `config_list`
List all config entries, optionally filtered by key prefix.

**Called automatically at the start of every conversation** (per `CLAUDE.md`). If `claude_project_instructions` is set, Claude reads it and treats it as additional behavioral guidance.

| Parameter | Type   | Required | Description                                     |
|-----------|--------|----------|-------------------------------------------------|
| `prefix`  | string | no       | Filter keys by prefix (e.g. `claude_` or `vacuum_`) |

---

#### `config_delete`
Permanently delete a config entry.

| Parameter | Type   | Required | Description        |
|-----------|--------|----------|--------------------|
| `key`     | string | yes      | Config key to delete |

---

## Built-in Config Keys

These keys are seeded with defaults on server startup. Changing them takes effect on the next vacuum cycle (no restart required).

| Key                        | Default | Description                                                  |
|----------------------------|---------|--------------------------------------------------------------|
| `vacuum_enabled`           | `true`  | Enable/disable the daily auto-vacuum job                     |
| `vacuum_notes_days`        | `90`    | Delete unpinned notes older than N days                      |
| `vacuum_sessions_days`     | `180`   | Archive inactive sessions, then hard-delete archived ones after N more days |

## Custom Claude Keys (examples)

| Key                           | Description                                              |
|-------------------------------|----------------------------------------------------------|
| `claude_project_instructions` | Extra instructions loaded at conversation start          |
| `claude_response_language`    | Language preference override for responses               |

You can define any key — there is no fixed schema. Prefer `snake_case` with a meaningful prefix (e.g., `claude_`, `vacuum_`, `project_`).
