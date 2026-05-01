# tools/vacuum

Auto-vacuum — clean up old notes and archive/hard-delete inactive sessions on a configurable schedule.

The vacuum job runs automatically once per day (via an `asyncio` background task started in server lifespan). It can also be triggered manually with `vacuum_run`.

---

## Tools

#### `vacuum_run`
Clean up old notes and archive/delete inactive sessions.

Always run with `dry_run=true` first to preview what would be deleted before committing changes.

| Parameter  | Type    | Required | Default | Description                                    |
|------------|---------|----------|---------|------------------------------------------------|
| `dry_run`  | boolean | no       | false   | Preview mode — shows candidates without changes |

**Example (preview first):**
```
vacuum_run(dry_run=true)
```

**Example (execute):**
```
vacuum_run(dry_run=false)
```

**Output includes:**
- Settings used (notes_days, sessions_days, enabled)
- Count of notes deleted
- Count of sessions archived
- Count of sessions hard-deleted
- List of session candidates (IDs + titles + last active date)

---

## Vacuum Criteria

### Notes
An unpinned note is deleted when:
- `pinned = false`
- `created_at < NOW() - vacuum_notes_days days`

Pinned notes (`pinned = true`) are **never** deleted.

### Sessions — Archive Phase
A session is soft-archived (`archived = true`) when **all** of the following are true:
- `pinned = false`
- No tag `keep` or `archive`
- `updated_at < NOW() - vacuum_sessions_days days`
- `archived = false` (not already archived)

### Sessions — Hard-Delete Phase
An already-archived session is permanently deleted when:
- `archived = true`
- `updated_at < NOW() - vacuum_sessions_days days` (the same window is used for both phases)

This creates a two-phase safety window: sessions pass through `archived` state before being destroyed, giving you time to call `session_restore` if the deletion was unintentional.

---

## Configuration

Vacuum behavior is controlled by entries in the `config` table. Change these with `config_write` — no server restart required.

| Config Key              | Default | Description                                                    |
|-------------------------|---------|----------------------------------------------------------------|
| `vacuum_enabled`        | `true`  | Set to `false` to disable the daily background job entirely    |
| `vacuum_notes_days`     | `90`    | Notes older than this (in days) are deleted                    |
| `vacuum_sessions_days`  | `180`   | Sessions inactive for this many days are archived / hard-deleted|

**Example — shorten the note retention window:**
```
config_write(key="vacuum_notes_days", value="30", description="Keep notes for 30 days only")
```

**Example — disable auto-vacuum entirely:**
```
config_write(key="vacuum_enabled", value="false")
```

---

## Opt-out Mechanisms

Individual sessions and notes can be excluded from vacuum:

| Method                           | Effect                                                  |
|----------------------------------|---------------------------------------------------------|
| `session_pin(session_id="...")`  | Session excluded from all vacuum phases, forever        |
| Add tag `keep` to a session      | Session excluded from archive phase                     |
| `note_pin(note_id=N, ...)`       | Note excluded from deletion phase                       |

---

## Daily Background Job

The vacuum loop is started automatically in server lifespan (`server.py`):

```python
async def _daily_vacuum_loop():
    while True:
        await asyncio.sleep(24 * 3600)
        if vacuum_enabled:
            await run_vacuum(dry_run=False)
```

The loop fires **after** a 24-hour delay on first run (not at startup), so a fresh deployment will not immediately vacuum. Trigger `vacuum_run` manually for an immediate run.
