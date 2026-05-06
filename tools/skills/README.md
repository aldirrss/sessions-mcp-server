# tools/skills

Persistent skill library — store, version, search, and track Markdown-based AI skills in PostgreSQL.

A **skill** is a named set of instructions or best practices (stored as Markdown) that Claude loads
into context on demand. Skills are linked to sessions to track which skills were applied to which work.

---

## Data Model

### `skills` table

| Column | Type | Description |
|--------|------|-------------|
| `slug` | text (PK) | Unique identifier, e.g. `mcp-builder` |
| `name` | text | Human-readable name, e.g. `MCP Server Development` |
| `content` | text | Full Markdown content |
| `summary` | text | Short 1–2 sentence description (shown in lists) |
| `source` | text | `file` (imported) or `manual` (written via tool) |
| `category` | text | Group category, e.g. `development`, `devops` |
| `tags` | text[] | Tags for filtering and recommendations |
| `is_global` | boolean | When `true`, skill is visible to all users in the portal skills browser and auto-available in MCP |
| `updated_at` | timestamptz | Last-modified timestamp |

### Related tables

| Table | Description |
|-------|-------------|
| `skill_versions` | Content snapshots saved automatically before each update |
| `session_skills` | Many-to-many: which skills were used in which sessions |

---

## Global Skills

Setting `is_global = true` on a skill makes it:

- Visible to all authenticated users in the **skills browser** at `/panel/mcp-user/skills`
- Auto-available in MCP without requiring admin action per user

Non-global skills are accessible only to admins via the admin panel and through direct
MCP tool calls (`skill_read`, `skill_list`, etc.).

---

## Import Formats

Skills can be imported from `.md` files via the admin panel (`/panel/mcp-admin/skills/import`).
Three file formats are supported:

### Claude format

YAML frontmatter with `name` and `description` fields:

```markdown
---
name: MCP Server Development
description: Guide for creating high-quality MCP servers with FastMCP.
---

# MCP Server Development

...skill content...
```

### Copilot format

YAML frontmatter with an `applyTo` field:

```markdown
---
applyTo: "**/*.py"
---

# Python Style Guide

...skill content...
```

### Plain Markdown

No frontmatter. The filename (without `.md`) is used as the slug, and the first `#` heading
is used as the skill name.

---

## Tools

Skill authoring (`skill_write`, `skill_delete`, `skill_sync`) and analytics
(`skill_stats`, `session_skills_list`, `skill_sessions_list`) are available in the
admin panel. The MCP tools below cover read-only access and session tracking.

### Skill CRUD

#### `skill_read`
Load the full content of a skill. When `session_id` is provided, usage is automatically
recorded in `session_skills` — the same as calling `skill_track`.

| Parameter | Type | Required | Description |
|-----------|------|----------|-------------|
| `slug` | string | yes | Skill slug to read |
| `session_id` | string | no | Active session ID — auto-tracks usage when provided |

---

#### `skill_list`
List all skills (summary only — no full content).

| Parameter | Type | Required | Description |
|-----------|------|----------|-------------|
| `category` | string | no | Filter by category |
| `tag` | string | no | Filter by tag |
| `source` | string | no | Filter by source: `file` or `manual` |

Returns a Markdown table with Slug, Name, Category, Tags, Source, and Is Global.

---

#### `skill_search`
Full-text search across skill name, summary, content, and tags.
Uses PostgreSQL `tsvector` + trigram index for fast matching.

| Parameter | Type | Required | Description |
|-----------|------|----------|-------------|
| `query` | string | yes | Keyword to search |

Returns matching skills with a content snippet.

---

### Session-Skill Tracking

#### `skill_track`
Record that a skill was invoked in a session.

- **First use** in a session: appends a compact note `"Skill activated: <slug> — <name>"` automatically.
- **Subsequent calls** for the same skill and session: silently idempotent, no duplicate note.

| Parameter | Type | Required | Description |
|-----------|------|----------|-------------|
| `session_id` | string | yes | Active session ID |
| `skill_slug` | string | yes | Slug of the skill that was invoked |

---

#### `skill_recommend`
Recommend skills not yet used in this session, ranked by tag overlap with the session's
tags and overall usage frequency.

| Parameter | Type | Required | Default | Description |
|-----------|------|----------|---------|-------------|
| `session_id` | string | yes | — | Active session to base recommendations on |
| `limit` | integer | no | 5 | Max recommendations (max 20) |

---

## Typical Workflow

```
# During a conversation
skill_list()                                         # browse available skills
skill_search(query="docker")                         # find relevant skills
skill_read(slug="docker", session_id="my-session")  # load content and auto-track
skill_recommend(session_id="my-session")             # what to try next
```

Skill authoring and usage analytics are available via the admin panel at
`/panel/mcp-admin/skills`.
