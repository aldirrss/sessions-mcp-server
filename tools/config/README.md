# tools/config

Dynamic configuration store — a PostgreSQL key-value table that lets you change
Claude's behavior and server settings across all sessions without redeploying.

Config entries are loaded at the start of every conversation via `config_list`
(as instructed in `CLAUDE.md`). Any key prefixed with `claude_` is treated as
additional behavioral guidance for Claude.

---

## Data Model

| Column | Type | Description |
|--------|------|-------------|
| `key` | text (PK) | Config key in `snake_case` |
| `value` | text | String value |
| `description` | text | Human-readable explanation |
| `updated_at` | timestamptz | Last-modified timestamp (auto-updated) |

---

## Tools

#### `config_write`
Create or update a configuration entry.

| Parameter | Type | Required | Description |
|-----------|------|----------|-------------|
| `key` | string | yes | Config key (`snake_case`, e.g. `vacuum_notes_days`) |
| `value` | string | yes | Value to store (always stored as text) |
| `description` | string | no | What this config controls (preserved on update if omitted) |

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

| Parameter | Type | Required | Description |
|-----------|------|----------|-------------|
| `key` | string | yes | Config key to read |

---

#### `config_list`
List all config entries, optionally filtered by key prefix.

Called automatically at the start of every conversation. If `claude_project_instructions`
is present, Claude reads it and applies it as additional behavioral guidance.

| Parameter | Type | Required | Description |
|-----------|------|----------|-------------|
| `prefix` | string | no | Filter keys by prefix (e.g. `claude_` or `vacuum_`) |

---

#### `config_delete`
Permanently delete a config entry.

| Parameter | Type | Required | Description |
|-----------|------|----------|-------------|
| `key` | string | yes | Config key to delete |

---

## Built-in Config Keys

These keys control server behavior and take effect on the next relevant cycle
without requiring a server restart.

| Key | Default | Description |
|-----|---------|-------------|
| `vacuum_enabled` | `false` | Enable the daily auto-vacuum background job |
| `vacuum_notes_days` | `90` | Delete unpinned notes older than N days |
| `vacuum_sessions_days` | `180` | Archive inactive sessions after N days; hard-delete archived sessions after another N days |

---

## Claude Instruction Keys

Any key prefixed with `claude_` is read by Claude at conversation start and applied
as additional instructions. You can define any key — there is no fixed schema.

| Key | Description |
|-----|-------------|
| `claude_project_instructions` | Extra instructions loaded at every conversation start |
| `claude_response_language` | Language preference override for responses |

---

## Key Naming Convention

Use `snake_case` with a meaningful prefix:

| Prefix | Purpose |
|--------|---------|
| `claude_` | Behavioral instructions for Claude |
| `vacuum_` | Auto-vacuum tuning |
| `project_` | Project-specific settings |

**Example — enable vacuum and shorten retention:**
```
config_write(key="vacuum_enabled", value="true")
config_write(key="vacuum_notes_days", value="30", description="Keep notes for 30 days")
config_write(key="vacuum_sessions_days", value="90", description="Archive after 90 days")
```
