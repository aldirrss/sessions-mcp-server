# tools/sessions

Persistent session store — create, read, update, search, and manage the lifecycle of AI conversation sessions backed by PostgreSQL.

Sessions are the core primitive of `lm-mcp-ai`. Each session has a unique ID, a title, a context block (free-form Markdown), and an append-only list of timestamped notes.

---

## Data Model

| Field        | Type       | Description                                           |
|--------------|------------|-------------------------------------------------------|
| `session_id` | text (PK)  | Unique slug, e.g. `feat-auth-dev`                    |
| `title`      | text       | Short human-readable label                            |
| `context`    | text       | Full working context — goals, state, decisions        |
| `source`     | text       | Origin client: `web`, `cli`, `vscode`, `unknown`      |
| `tags`       | text[]     | Free tags for filtering and skill recommendations     |
| `pinned`     | boolean    | Protected from auto-vacuum                            |
| `archived`   | boolean    | Soft-deleted; hidden from list by default             |
| `repo_url`   | text       | Optional linked GitHub repository URL                 |
| `created_at` | timestamptz| Creation timestamp                                    |
| `updated_at` | timestamptz| Last-modified timestamp                               |

Notes are stored in a separate `notes` table, linked by `session_id`.

---

## Tools

### Core CRUD

#### `session_write`
Create or overwrite a session context in the shared store.

Overwrites `context` and `title` but **preserves existing notes**.

| Parameter    | Type     | Required | Description                                  |
|--------------|----------|----------|----------------------------------------------|
| `session_id` | string   | yes      | Unique session key (e.g. `feat-auth-dev`)    |
| `title`      | string   | yes      | Short human-readable title                   |
| `context`    | string   | yes      | Full context (Markdown)                      |
| `source`     | string   | no       | `web` / `cli` / `vscode` (default: `web`)   |
| `tags`       | string[] | no       | Tags for filtering                           |

---

#### `session_read`
Read the full context of a session, including notes.

Pinned notes appear first in a dedicated `📌 Pinned Notes` section. Regular notes follow in chronological order. Each note shows its ID (`[id:N]`) so you can reference it in `note_pin`.

| Parameter    | Type   | Required | Description      |
|--------------|--------|----------|------------------|
| `session_id` | string | yes      | Session ID to read |

---

#### `session_list`
List all sessions (summary only — no context or notes).

Pinned sessions appear first. Archived sessions are hidden by default.

| Parameter       | Type    | Required | Default | Description                          |
|-----------------|---------|----------|---------|--------------------------------------|
| `tag`           | string  | no       |         | Filter by tag                        |
| `show_archived` | boolean | no       | false   | Include archived sessions            |

---

#### `session_append`
Append a timestamped note to an existing session without overwriting its context.

Use this to log progress updates, decisions, or blockers mid-session.

| Parameter    | Type   | Required | Description                                |
|--------------|--------|----------|--------------------------------------------|
| `session_id` | string | yes      | Session ID to append to                   |
| `content`    | string | yes      | Note content                               |
| `source`     | string | no       | `web` / `cli` / `vscode` (default: `web`) |

---

#### `session_delete`
Permanently delete a session and all its notes.

| Parameter    | Type   | Required | Description         |
|--------------|--------|----------|---------------------|
| `session_id` | string | yes      | Session ID to delete |

---

#### `session_search`
Full-text search across session title, context, notes, and tags.

Uses PostgreSQL `tsvector` for efficient full-text search with trigram fallback.

| Parameter | Type   | Required | Description         |
|-----------|--------|----------|---------------------|
| `query`   | string | yes      | Keyword to search   |

Returns matching sessions with a content snippet and last-updated date.

---

### Note Management

#### `note_pin`
Pin a note so it always appears at the top of `session_read` output.

Pinned notes are **never** deleted by `session_compact` or auto-vacuum. Use for critical decisions, blockers, or constraints.

| Parameter    | Type    | Required | Description                               |
|--------------|---------|----------|-------------------------------------------|
| `note_id`    | integer | yes      | Note ID (shown as `[id:N]` in session_read) |
| `session_id` | string  | yes      | Session ID the note belongs to            |

---

#### `note_unpin`
Remove the pin from a note, returning it to chronological order.

After unpinning, the note becomes eligible for `session_compact` and auto-vacuum.

| Parameter    | Type    | Required | Description                      |
|--------------|---------|----------|----------------------------------|
| `note_id`    | integer | yes      | Note ID to unpin                 |
| `session_id` | string  | yes      | Session ID the note belongs to   |

---

#### `session_compact`
Merge old unpinned notes into the session context and delete them.

Appends a `## Compacted Notes (before YYYY-MM-DD)` section to the context field, then deletes those notes from the database. Keeps the notes table lean while preserving history. Pinned notes are **never** compacted.

Use this when `session_read` is becoming too long to fit in context.

| Parameter      | Type    | Required | Default | Description                                    |
|----------------|---------|----------|---------|------------------------------------------------|
| `session_id`   | string  | yes      |         | Session to compact                             |
| `before_days`  | integer | no       | 30      | Compact notes older than N days                |

---

### Session Lifecycle

#### `session_pin`
Pin a session to protect it from auto-vacuum (archive and delete).

Pinned sessions are excluded from **all** vacuum operations regardless of age.

| Parameter    | Type   | Required | Description         |
|--------------|--------|----------|---------------------|
| `session_id` | string | yes      | Session ID to pin   |

---

#### `session_unpin`
Remove the pin from a session, making it eligible for auto-vacuum again.

| Parameter    | Type   | Required | Description           |
|--------------|--------|----------|-----------------------|
| `session_id` | string | yes      | Session ID to unpin   |

---

#### `session_archive`
Soft-delete a session by marking it `archived = true`.

Archived sessions are hidden from `session_list` by default but can be recovered with `session_restore`. They are permanently deleted after `vacuum_sessions_days` (default 180 days) by auto-vacuum.

| Parameter    | Type   | Required | Description            |
|--------------|--------|----------|------------------------|
| `session_id` | string | yes      | Session ID to archive  |

---

#### `session_restore`
Restore an archived session, setting `archived = false`.

| Parameter    | Type   | Required | Description             |
|--------------|--------|----------|-------------------------|
| `session_id` | string | yes      | Session ID to restore   |

---

## Lifecycle Flow

```
session_write          ← create / overwrite context
    │
    ├── session_append ← log notes mid-conversation
    ├── note_pin       ← pin critical notes
    ├── session_compact← compress old notes into context
    │
    ├── session_pin    ← protect forever
    ├── session_archive← soft delete (recoverable)
    └── session_delete ← hard delete immediately
```

Auto-vacuum runs daily and archives inactive unpinned sessions, then hard-deletes sessions that have been archived for more than `vacuum_sessions_days` days. See [`tools/vacuum/README.md`](../vacuum/README.md).
