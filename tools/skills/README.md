# tools/skills

Persistent skill library — store, version, search, and track Markdown-based AI skills in PostgreSQL.

A **skill** is a named set of instructions or best practices (stored as Markdown) that Claude loads into context on demand. Skills are linked to sessions to track which skills were applied to which work.

---

## Data Model

| Field      | Type       | Description                                         |
|------------|------------|-----------------------------------------------------|
| `slug`     | text (PK)  | Unique identifier, e.g. `mcp-builder`               |
| `name`     | text       | Human-readable name, e.g. `MCP Server Development` |
| `content`  | text       | Full Markdown content                               |
| `summary`  | text       | Short 1–2 sentence description (shown in lists)    |
| `source`   | text       | `file` (imported) or `manual` (written via tool)   |
| `category` | text       | Group category, e.g. `development`, `devops`        |
| `tags`     | text[]     | Tags for filtering and recommendations              |
| `updated_at`| timestamptz | Last-modified timestamp                            |

Skill version history is stored in a separate `skill_versions` table (previous content preserved on every update).

Session-skill associations are stored in `session_skills` (many-to-many).

---

## Tools

### Skill CRUD

#### `skill_write`
Create or update a skill in the library.

On update, the previous content is automatically saved to version history.

| Parameter   | Type     | Required | Description                                       |
|-------------|----------|----------|---------------------------------------------------|
| `slug`      | string   | yes      | Unique slug (e.g. `mcp-builder`)                 |
| `name`      | string   | yes      | Human-readable name                               |
| `content`   | string   | yes      | Full Markdown content                             |
| `summary`   | string   | no       | Short description (shown in `skill_list`)         |
| `source`    | string   | no       | `manual` or `file` (default: `manual`)            |
| `category`  | string   | no       | Group category                                    |
| `tags`      | string[] | no       | Tags for filtering and recommendation matching    |

---

#### `skill_read`
Read the full content of a skill from the library.

Returns the complete Markdown content with metadata header.

| Parameter | Type   | Required | Description      |
|-----------|--------|----------|------------------|
| `slug`    | string | yes      | Skill slug to read |

---

#### `skill_list`
List all skills (summary only — no full content).

| Parameter  | Type   | Required | Description                          |
|------------|--------|----------|--------------------------------------|
| `category` | string | no       | Filter by category                   |
| `tag`      | string | no       | Filter by tag                        |
| `source`   | string | no       | Filter by source: `file` or `manual` |

Returns a Markdown table with Slug, Name, Category, Tags, Source.

---

#### `skill_search`
Full-text search across skill name, summary, content, and tags.

Uses PostgreSQL `tsvector` + trigram index for fast matching.

| Parameter | Type   | Required | Description         |
|-----------|--------|----------|---------------------|
| `query`   | string | yes      | Keyword to search   |

Returns matching skills with a content snippet.

---

#### `skill_delete`
Permanently delete a skill from the library.

Also removes all `session_skills` associations for this slug. Version history (`skill_versions`) is preserved.

| Parameter | Type   | Required | Description        |
|-----------|--------|----------|--------------------|
| `slug`    | string | yes      | Skill slug to delete |

---

#### `skill_sync`
Bulk import or update skills from a list of skill definitions.

All imported skills get `source='file'`. Existing skills are updated (with version history preserved); new ones are created.

| Parameter | Type       | Required | Description                               |
|-----------|------------|----------|-------------------------------------------|
| `skills`  | list[dict] | yes      | List of skill objects (see schema below)  |

Each item in `skills` must have: `slug`, `name`, `content`.
Optional fields per item: `summary`, `category`, `tags`.

---

### Session-Skill Tracking

#### `skill_track`
Record that a skill was invoked in a session.

Call this immediately after invoking any `/skill-name`.

- **First use** in a session: appends a compact note `"Skill activated: <slug> — <name>"` to the session automatically.
- **Subsequent calls** for the same skill + session: silently idempotent (no duplicate note).

> Note: The skill must exist in the database (`skill_write` / `skill_sync`) before it can be tracked. Skills stored only in Claude's user settings are not automatically present in the DB.

| Parameter     | Type   | Required | Description                          |
|---------------|--------|----------|--------------------------------------|
| `session_id`  | string | yes      | Active session ID                    |
| `skill_slug`  | string | yes      | Slug of the skill that was invoked   |

---

#### `session_skills_list`
List all skills that have been used in a specific session.

| Parameter    | Type   | Required | Description         |
|--------------|--------|----------|---------------------|
| `session_id` | string | yes      | Session ID to query |

Returns a table with Slug, Name, Category, and First Used timestamp.

---

#### `skill_sessions_list`
List all sessions in which a specific skill has been used.

Useful for finding related work: *"which sessions used the docker skill?"*

| Parameter | Type   | Required | Description           |
|-----------|--------|----------|-----------------------|
| `slug`    | string | yes      | Skill slug to look up |

---

### Analytics

#### `skill_stats`
Show usage statistics for all skills.

Returns each skill with total sessions used and last used timestamp, ordered by most-used first. No parameters required.

---

#### `skill_recommend`
Recommend skills not yet used in this session, ranked by tag overlap with the session's tags and overall usage frequency.

| Parameter    | Type    | Required | Default | Description                          |
|--------------|---------|----------|---------|--------------------------------------|
| `session_id` | string  | yes      |         | Active session to base recs on       |
| `limit`      | integer | no       | 5       | Max recommendations (max 20)         |

---

## Typical Workflow

```
# Import skills from a CI/CD pipeline or setup script
skill_sync(skills=[...])

# During a conversation
skill_list()                    # browse available skills
skill_search(query="docker")    # find relevant skills
skill_read(slug="docker")       # load full content into context
skill_track(session_id="...", skill_slug="docker")  # record usage

# Review after session
session_skills_list(session_id="...")  # what was used
skill_stats()                          # usage across all sessions
skill_recommend(session_id="...")      # what to try next
```
