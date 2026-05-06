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

### Core CRUD

#### `session_write`
Create or overwrite a session context. Overwrites `context` and `title` but preserves
existing notes.

| Parameter | Type | Required | Description |
|-----------|------|----------|-------------|
| `session_id` | string | yes | Unique session key, e.g. `feat-auth-dev` |
| `title` | string | yes | Short human-readable title |
| `context` | string | yes | Full context (Markdown) |
| `source` | string | no | `web` / `cli` / `vscode` (default: `web`) |
| `tags` | string[] | no | Tags for filtering |
| `team` | string | no | Team name slug — writes to team scope instead of personal |

---

#### `session_read`
Read the full context of a session, including all notes.

Pinned notes appear first in a dedicated section. Regular notes follow in chronological
order. Each note shows its ID as `[id:N]` for reference in `note_pin`.

| Parameter | Type | Required | Description |
|-----------|------|----------|-------------|
| `session_id` | string | yes | Session ID to read |

---

#### `session_list`
List all sessions (summary only — no context or notes).
Pinned sessions appear first. Archived sessions are hidden by default.

| Parameter | Type | Required | Default | Description |
|-----------|------|----------|---------|-------------|
| `tag` | string | no | — | Filter by tag |
| `show_archived` | boolean | no | `false` | Include archived sessions |
| `team` | string | no | — | Team name slug — lists team sessions instead of personal |

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
Full-text search across session title, context, notes, and tags.
Uses PostgreSQL `tsvector` for efficient full-text search with trigram fallback.

| Parameter | Type | Required | Description |
|-----------|------|----------|-------------|
| `query` | string | yes | Keyword to search |
| `team` | string | no | Team name slug — searches team sessions instead of personal |

Returns matching sessions with a content snippet and last-updated date.

---

### Note Management

#### `note_pin`
Pin a note so it always appears at the top of `session_read` output.
Pinned notes are never deleted by `session_compact` or auto-vacuum.
Use for critical decisions, blockers, or constraints.

| Parameter | Type | Required | Description |
|-----------|------|----------|-------------|
| `note_id` | integer | yes | Note ID (shown as `[id:N]` in session_read) |
| `session_id` | string | yes | Session ID the note belongs to |

---

#### `note_unpin`
Remove the pin from a note, returning it to chronological order.
After unpinning, the note becomes eligible for `session_compact` and auto-vacuum.

| Parameter | Type | Required | Description |
|-----------|------|----------|-------------|
| `note_id` | integer | yes | Note ID to unpin |
| `session_id` | string | yes | Session ID the note belongs to |

---

#### `session_compact`
Merge old unpinned notes into the session context field and delete them.

Appends a `## Compacted Notes (before YYYY-MM-DD)` section to the context, then
deletes those notes from the `notes` table. Keeps the session lean. Pinned notes
are never compacted.

Use this when `session_read` output is becoming too long to fit in context.

| Parameter | Type | Required | Default | Description |
|-----------|------|----------|---------|-------------|
| `session_id` | string | yes | — | Session to compact |
| `before_days` | integer | no | `30` | Compact notes older than N days |

---

### Session Lifecycle

#### `session_pin`
Pin a session to protect it from auto-vacuum (archive and delete).
Pinned sessions are excluded from all vacuum operations regardless of age.

| Parameter | Type | Required | Description |
|-----------|------|----------|-------------|
| `session_id` | string | yes | Session ID to pin |

---

#### `session_unpin`
Remove the pin from a session, making it eligible for auto-vacuum again.

| Parameter | Type | Required | Description |
|-----------|------|----------|-------------|
| `session_id` | string | yes | Session ID to unpin |

---

#### `session_archive`
Soft-delete a session by marking it `archived = true`.

Archived sessions are hidden from `session_list` by default but can be recovered with
`session_restore`. Auto-vacuum permanently deletes archived sessions after
`vacuum_sessions_days` (default 180 days).

| Parameter | Type | Required | Description |
|-----------|------|----------|-------------|
| `session_id` | string | yes | Session ID to archive |

---

#### `session_restore`
Restore an archived session, setting `archived = false`.

| Parameter | Type | Required | Description |
|-----------|------|----------|-------------|
| `session_id` | string | yes | Session ID to restore |

---

## Session Lifecycle Flow

```
session_write          ← create / overwrite context
    │
    ├── session_append ← log notes mid-conversation
    ├── note_pin       ← pin critical notes (never vacuumed)
    ├── session_compact← merge old notes into context when session is long
    │
    ├── session_pin    ← protect from auto-vacuum forever
    ├── session_archive← soft-delete (recoverable via session_restore)
    └── session_delete ← hard-delete immediately
```

Auto-vacuum runs daily:
1. Archives inactive unpinned sessions older than `vacuum_sessions_days`
2. Hard-deletes sessions that have been archived for more than `vacuum_sessions_days`

See [`tools/vacuum/README.md`](../vacuum/README.md) for full vacuum documentation.

---

## Recommended Usage Pattern

```
# Start of every conversation
session_list()                          # see active sessions
session_read("feat-auth-dev")           # restore context + pinned notes

# During the conversation
session_append("feat-auth-dev", "Completed token refresh logic. PR #12 created.")
note_pin(note_id=42, session_id="feat-auth-dev")   # pin a critical decision

# End of conversation with unfinished work
session_write("feat-auth-dev", title="...", context="<updated context>")

# When session is getting long
session_compact("feat-auth-dev", before_days=7)
```
