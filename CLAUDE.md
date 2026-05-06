# lm-mcp-ai — Claude Behavior Instructions

This project uses a custom MCP server (`lm-mcp-ai`) that provides session continuity,
skill library, and config management tools. Follow the rules below in every conversation.

---

## Session Management

At the start of every conversation:
1. Call `session_list` to see available sessions.
2. If the user mentions a project, feature, or topic that matches a session ID or title,
   call `session_read` with that session ID to restore full context before responding.
3. Call `config_list` to load any dynamic project instructions stored in the database.
   Apply any `claude_*` config keys as additional behavioral instructions for this conversation.

During the conversation:
- Call `session_append` to log important decisions, blockers, or progress updates.
- Call `session_write` before ending a conversation that has unfinished work,
  saving the current state so it can be resumed from any client.

---

## GitHub Integration

When working on a session that has a linked GitHub repository:
- Call `repo_get_context` at the start to fetch the current default branch,
  recent commits, and open PRs — this gives real-time repo state.
- Use `session_link_repo` to link a repo URL to a session.
- Use `session_unlink_repo` to remove the link.

---

## Skill Tracking

Whenever you invoke a skill (`/skill-name`), immediately call `skill_track` with:
- `session_id`: the active session ID (from session_list or session context)
- `skill_slug`: the skill name without the leading slash (e.g. `mcp-builder`)

### Rules
- Track every skill invocation, including: `/mcp-builder`, `/brainstorming`,
  `/postgresql-best-practices`, `/python`, `/ci-cd-best-practices`, etc.
- First use of a skill in a session → `skill_track` auto-appends a compact note.
  You do NOT need to manually append a note for skill activation.
- Subsequent uses of the same skill in the same session → silently idempotent,
  no duplicate note is created.
- If no active session exists yet, create one with `session_write` first,
  then call `skill_track`.

### Example flow
```
User: help me build an MCP server  /mcp-builder
→ You invoke /mcp-builder skill
→ Immediately call: skill_track(session_id="current-session", skill_slug="mcp-builder")
→ skill_track auto-appends: "Skill activated: mcp-builder — MCP Server Development Guide"
→ Continue with the skill's instructions
```

---

## Skill Library

The MCP server maintains a skill library in PostgreSQL. You can:
- `skill_list` — see all available skills and their summaries
- `skill_read <slug>` — load a skill's full Markdown content
- `skill_search <query>` — find skills by keyword
- `skill_recommend <session_id>` — get suggestions based on session tags

When a user asks "what skills are available?" or "do you have a skill for X?",
use `skill_search` or `skill_list` instead of relying on memory.

---

## MCP Server Tools Reference

### Sessions
`session_write`, `session_read`, `session_list`, `session_append`,
`session_delete`, `session_search`

### Skills
`skill_write`, `skill_read`, `skill_list`, `skill_search`, `skill_delete`,
`skill_sync`, `skill_track`, `session_skills_list`, `skill_sessions_list`,
`skill_stats`, `skill_recommend`

### GitHub Integration
`session_link_repo`, `session_unlink_repo`, `repo_get_context`

### Config
`config_write`, `config_read`, `config_list`, `config_delete`

### Notes (Ide 3 — auto-notes)
`note_pin`, `note_unpin`, `session_compact`

Pinned notes always appear at the top of `session_read` and are never deleted by vacuum.
Use `note_pin` for critical decisions that must stay visible across long sessions.
Use `session_compact` when a session has too many old notes to fit in context — it merges
them into the context field and deletes them, keeping the session lean.

### Session lifecycle (Ide 4 — auto-vacuum)
`session_pin`, `session_unpin`, `session_archive`, `session_restore`, `vacuum_run`

- `session_pin` — protect session from auto-vacuum indefinitely
- `session_archive` — soft-delete (hidden from list, restored with session_restore)
- `vacuum_run(dry_run=true)` — preview what would be cleaned up
- `vacuum_run(dry_run=false)` — execute vacuum (also runs automatically daily if vacuum_enabled=true)

Vacuum config keys (set via `config_write`):
- `vacuum_enabled` — 'true'/'false' (default false)
- `vacuum_notes_days` — int, default 90
- `vacuum_sessions_days` — int, default 180
