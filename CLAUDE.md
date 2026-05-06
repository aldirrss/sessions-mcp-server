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

18 tools total — focused on what's actually useful in a conversation.

### Sessions (6)
`session_write`, `session_read`, `session_list`, `session_append`,
`session_delete`, `session_search`

### Session & Note Lifecycle (2)
`session_update(action)`, `note_update(action)`

- `session_update(session_id, action: 'pin'|'unpin'|'archive'|'restore')` — manage session lifecycle
- `note_update(note_id, session_id, action: 'pin'|'unpin')` — pin/unpin individual notes

Pinned notes always appear at the top of `session_read` and are never deleted by vacuum.
Auto-vacuum runs daily and archives/deletes inactive unpinned sessions automatically.

### Skills (5)
`skill_read`, `skill_list`, `skill_search`, `skill_track`, `skill_recommend`

Use the admin web panel to create, edit, delete, or bulk-import skills.

### GitHub Integration (2)
`session_link_repo`, `repo_get_context`

### Config (3)
`config_write`, `config_read`, `config_list`

Use the admin web panel to delete config keys.

### Auth (1)
`user_me`

Use the web portal to manage tokens and user accounts.
