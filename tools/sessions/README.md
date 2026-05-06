# tools/sessions

Persistent session store — create, read, update, search, and manage the lifecycle of
AI conversation sessions backed by PostgreSQL.

Sessions are the core primitive of **Sessions MCP Server**. Each session has a unique ID,
a title, a context block (free-form Markdown), and an append-only list of timestamped notes.
All clients (claude.ai, Claude Code CLI, VSCode) share the same session store.

Sessions can be **personal** (owned by a user) or **team-scoped** (shared within a team).
Pass the `team` parameter to any write/list/search tool to operate on team sessions instead
of personal ones. Access is validated against team membership before any operation is
allowed.

---

## Data Model

### `sessions` table

| Column | Type | Description |
|--------|------|-------------|
| `session_id` | text (PK) | Unique slug, e.g. `feat-auth-dev` |
| `title` | text | Short human-readable label |
| `context` | text | Full working context — goals, state, decisions |
| `source` | text | Origin client: `web`, `cli`, `vscode`, `unknown` |
| `tags` | text[] | Free tags for filtering and skill recommendations |
| `pinned` | boolean | Protected from auto-vacuum |
| `archived` | boolean | Soft-deleted; hidden from list by default |
| `repo_url` | text | Optional linked GitHub repository URL |
| `created_at` | timestamptz | Creation timestamp |
| `updated_at` | timestamptz | Last-modified timestamp |

### `notes` table

Notes are stored separately and linked by `session_id`.

| Column | Type | Description |
|--------|------|-------------|
| `id` | integer (PK) | Auto-increment note ID |
| `session_id` | text (FK) | Session this note belongs to |
| `content` | text | Note content |
| `source` | text | Origin client |
| `pinned` | boolean | When `true`, always shown at top, never vacuumed |
| `created_at` | timestamptz | Creation timestamp |

---

## Tools

### Personal Sessions

#### `session_write`
Create or overwrite a **personal** session context. Overwrites `context` and `title`
but preserves existing notes. For team sessions use `session_team_write`.

| Parameter | Type | Required | Description |
|-----------|------|----------|-------------|
| `session_id` | string | yes | Unique session key, e.g. `feat-auth-dev` |
| `title` | string | yes | Short human-readable title |
| `context` | string | yes | Full context (Markdown) |
| `source` | string | no | `web` / `cli` / `vscode` (default: `web`) |
| `tags` | string[] | no | Tags for filtering |

---

#### `session_read`
Read the full context of a session, including all notes.

Pinned notes appear first in a dedicated section. Regular notes follow in chronological
order. Each note shows its ID as `[id:N]` for reference in `note_update`.

| Parameter | Type | Required | Description |
|-----------|------|----------|-------------|
| `session_id` | string | yes | Session ID to read |

---

#### `session_list`
List **personal** sessions (summary only — no context or notes).
Pinned sessions appear first. Archived sessions are hidden by default.
For team sessions use `session_team_list`.

| Parameter | Type | Required | Default | Description |
|-----------|------|----------|---------|-------------|
| `tag` | string | no | — | Filter by tag |
| `show_archived` | boolean | no | `false` | Include archived sessions |

---

#### `session_append`
Append a timestamped note to an existing session without overwriting its context.
Use this to log progress updates, decisions, or blockers mid-session.

| Parameter | Type | Required | Description |
|-----------|------|----------|-------------|
| `session_id` | string | yes | Session ID to append to |
| `content` | string | yes | Note content |
| `source` | string | no | `web` / `cli` / `vscode` (default: `web`) |

---

#### `session_delete`
Permanently delete a session and all its notes.

| Parameter | Type | Required | Description |
|-----------|------|----------|-------------|
| `session_id` | string | yes | Session ID to delete |

---

#### `session_search`
Full-text search across **personal** session title, context, notes, and tags.
Uses PostgreSQL `tsvector` for efficient full-text search with trigram fallback.
For team sessions use `session_team_search`.

| Parameter | Type | Required | Description |
|-----------|------|----------|-------------|
| `query` | string | yes | Keyword to search |

Returns matching sessions with a content snippet and last-updated date.

---

### Team Sessions

Use these tools when the session belongs to a team. The `team` parameter is **required**
in all three tools. `session_read`, `session_append`, `session_delete`, and `session_update`
work on team sessions too — they only need `session_id`.

#### `session_team_write`
Create or overwrite a session in a team namespace. All team members can read it.

| Parameter | Type | Required | Description |
|-----------|------|----------|-------------|
| `session_id` | string | yes | Unique session key, e.g. `sprint-42` |
| `title` | string | yes | Short human-readable title |
| `context` | string | yes | Full context (Markdown) |
| `team` | string | yes | Team name slug, e.g. `mazuta-erp`. Must be a member. |
| `source` | string | no | `web` / `cli` / `vscode` (default: `web`) |
| `tags` | string[] | no | Tags for filtering |

---

#### `session_team_list`
List sessions belonging to a team (summary only — no context or notes).

| Parameter | Type | Required | Default | Description |
|-----------|------|----------|---------|-------------|
| `team` | string | yes | — | Team name slug. Must be a member. |
| `tag` | string | no | — | Filter by tag |
| `show_archived` | boolean | no | `false` | Include archived sessions |

---

#### `session_team_search`
Full-text search across a team's session title, context, notes, and tags.

| Parameter | Type | Required | Description |
|-----------|------|----------|-------------|
| `query` | string | yes | Keyword to search |
| `team` | string | yes | Team name slug to scope the search. Must be a member. |

Returns matching sessions with a content snippet and last-updated date.

---

### Note Management

#### `note_update`
Pin or unpin a note.

Pinned notes always appear at the top of `session_read` output and are never deleted
by auto-vacuum. Use `pin` for critical decisions, blockers, or constraints.

| Parameter | Type | Required | Description |
|-----------|------|----------|-------------|
| `note_id` | integer | yes | Note ID (shown as `[id:N]` in session_read) |
| `session_id` | string | yes | Session ID the note belongs to |
| `action` | string | yes | `pin` or `unpin` |

---

### Session Lifecycle

#### `session_update`
Change the lifecycle state of a session.

| Parameter | Type | Required | Description |
|-----------|------|----------|-------------|
| `session_id` | string | yes | Session ID to update |
| `action` | string | yes | One of `pin`, `unpin`, `archive`, `restore` |

| Action | Effect |
|--------|--------|
| `pin` | Protect from auto-vacuum indefinitely |
| `unpin` | Remove protection; session becomes eligible for auto-vacuum again |
| `archive` | Soft-delete (hidden from list; recoverable with `restore`) |
| `restore` | Un-archive a previously archived session |

Archived sessions are permanently deleted after `vacuum_sessions_days` (default 180 days)
unless restored first.

---

## Session Lifecycle Flow

```
session_write            ← create / overwrite context
    │
    ├── session_append   ← log notes mid-conversation
    ├── note_update(pin) ← pin critical notes (never vacuumed)
    │
    ├── session_update(pin)     ← protect from auto-vacuum forever
    ├── session_update(archive) ← soft-delete (recoverable via restore)
    └── session_delete          ← hard-delete immediately
```

Auto-vacuum runs daily:
1. Archives inactive unpinned sessions older than `vacuum_sessions_days`
2. Hard-deletes sessions that have been archived for more than `vacuum_sessions_days`

See [`tools/vacuum/README.md`](../vacuum/README.md) for full vacuum documentation.

---

## Recommended Usage Pattern

```
# Start of every conversation
session_list()                              # see personal sessions
session_team_list(team="mazuta-erp")        # see team sessions
session_read("feat-auth-dev")               # restore context + pinned notes

# During the conversation
session_append("feat-auth-dev", "Completed token refresh logic. PR #12 created.")
note_update(note_id=42, session_id="feat-auth-dev", action="pin")   # pin a critical decision

# Save personal work at end of conversation
session_write("feat-auth-dev", title="...", context="<updated context>")

# Save team work at end of conversation
session_team_write("sprint-42", title="...", context="...", team="mazuta-erp")

# Protect a long-running session from being auto-archived
session_update(session_id="feat-auth-dev", action="pin")
```
