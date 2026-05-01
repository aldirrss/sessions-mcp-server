# tools/vacuum

Auto-vacuum — clean up old notes and archive/hard-delete inactive sessions on a
configurable schedule.

The vacuum job runs automatically once per day (via an `asyncio` background task started
in server lifespan). It can also be triggered on demand with `vacuum_run`.

---

## Tools

#### `vacuum_run`
Clean up old notes and archive/delete inactive sessions.

Always run with `dry_run=true` first to preview candidates before committing changes.

| Parameter | Type | Required | Default | Description |
|-----------|------|----------|---------|-------------|
| `dry_run` | boolean | no | `false` | Preview mode — shows candidates without making changes |

**Preview first:**
```
vacuum_run(dry_run=true)
```

**Execute:**
```
vacuum_run(dry_run=false)
```

**Output includes:**
- Settings used (notes_days, sessions_days, enabled)
- Count of notes deleted
- Count of sessions archived
- Count of sessions hard-deleted
- List of session candidates (IDs, titles, last active date)

---

## Vacuum Criteria

### Notes

An unpinned note is deleted when:
- `pinned = false`
- `created_at < NOW() - vacuum_notes_days days`

Pinned notes (`pinned = true`) are never deleted.

### Sessions — Archive Phase

A session is soft-archived (`archived = true`) when all of the following are true:
- `pinned = false`
- No tag `keep` or `archive`
- `updated_at < NOW() - vacuum_sessions_days days`
- `archived = false` (not already archived)

### Sessions — Hard-Delete Phase

An already-archived session is permanently deleted when:
- `archived = true`
- `updated_at < NOW() - vacuum_sessions_days days`

This two-phase approach gives you time to call `session_restore` before a session is
permanently destroyed.

---

## Configuration

Vacuum behavior is controlled by entries in the `config` table. Change these with
`config_write` — no server restart required.

| Config Key | Default | Description |
|------------|---------|-------------|
| `vacuum_enabled` | `false` | Set to `true` to enable the daily background job |
| `vacuum_notes_days` | `90` | Notes older than this many days are deleted |
| `vacuum_sessions_days` | `180` | Sessions inactive for this many days are archived, then hard-deleted after another cycle |

**Enable vacuum:**
```
config_write(key="vacuum_enabled", value="true")
```

**Shorten the note retention window:**
```
config_write(key="vacuum_notes_days", value="30", description="Keep notes for 30 days only")
```

**Disable auto-vacuum entirely:**
```
config_write(key="vacuum_enabled", value="false")
```

---

## Opt-out Mechanisms

Individual sessions and notes can be excluded from all vacuum operations:

| Method | Effect |
|--------|--------|
| `session_pin(session_id)` | Session excluded from all vacuum phases forever |
| Add tag `keep` to a session | Session excluded from the archive phase |
| `note_pin(note_id, session_id)` | Note excluded from deletion |

---

## Daily Background Job

The vacuum loop starts automatically in server lifespan:

```python
async def _daily_vacuum_loop():
    while True:
        await asyncio.sleep(24 * 3600)
        if vacuum_enabled:
            await run_vacuum(dry_run=False)
```

The loop fires after a 24-hour delay on first run (not at startup), so a fresh
deployment will not immediately vacuum. Use `vacuum_run(dry_run=false)` for an
immediate manual run.
