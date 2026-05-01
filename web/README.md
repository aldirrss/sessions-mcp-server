# web/

Next.js 15 web admin panel for `lm-mcp-ai`.

Provides a browser-based UI to inspect and manage sessions, skills, and server configuration without using an MCP client. Useful for reviewing session history, editing notes, managing the config table, and monitoring skill usage.

---

## Tech Stack

| Layer       | Library / Framework                   |
|-------------|---------------------------------------|
| Framework   | Next.js 15 (App Router)               |
| Auth        | `iron-session` (encrypted cookie)     |
| Database    | `postgres` npm (tagged template SQL)  |
| Styling     | Tailwind CSS v4                       |
| Icons       | `lucide-react`                        |
| Deploy      | Node.js inside Docker container       |

All database-touching routes use `export const dynamic = 'force-dynamic'` to disable Next.js caching and always return fresh data.

---

## URL Structure

The panel is served at the sub-path `/panel/mcp-admin` (set via `basePath` in `next.config.ts`). This allows it to share a domain with the MCP server through a reverse proxy.

| Path                            | Description                         |
|---------------------------------|-------------------------------------|
| `/panel/mcp-admin/`             | Redirects to Dashboard              |
| `/panel/mcp-admin/dashboard`    | Overview stats                      |
| `/panel/mcp-admin/sessions`     | Session list with search/filter     |
| `/panel/mcp-admin/sessions/:id` | Session detail — context, notes, repo |
| `/panel/mcp-admin/skills`       | Skill library list                  |
| `/panel/mcp-admin/skills/:slug` | Skill detail — full content, usage  |
| `/panel/mcp-admin/config`       | Config key-value table              |
| `/panel/mcp-admin/auth/login`   | Login page                          |

---

## Authentication

All admin routes are protected by `iron-session`. The middleware checks for a valid encrypted session cookie on every request to `(admin)` layout pages.

Credentials are set via environment variables:

| Env Var          | Description                             |
|------------------|-----------------------------------------|
| `ADMIN_USER`     | Admin username (default: `admin`)       |
| `ADMIN_PASSWORD` | Admin password                          |
| `SESSION_SECRET` | 32-byte secret for cookie encryption   |

Log in at `/panel/mcp-admin/auth/login`. The session cookie expires after 7 days.

---

## Pages

### Dashboard (`/dashboard`)
High-level stats: total sessions, total notes, total skills, recent activity.

### Sessions (`/sessions`)
- Search by session ID or title
- Filter by source (`web`, `cli`, `vscode`, `unknown`)
- Toggle to show archived sessions
- Create a new session via modal form
- Delete sessions inline
- Navigate to session detail

### Session Detail (`/sessions/:id`)
- View and edit session title and tags
- Link / unlink a GitHub repository
- Pin or archive/restore the session
- View notes in chronological order (pinned notes highlighted in amber)
- Pin / unpin individual notes
- Append new notes via inline form
- View linked skills (with navigation to skill detail)

### Skills (`/skills`)
- Browse all skills with category/tag/source filters
- Search by keyword
- Navigate to skill detail

### Skill Detail (`/skills/:slug`)
- View full skill content (rendered Markdown preview)
- See which sessions have used this skill
- View skill metadata: category, tags, source, last updated

### Config (`/config`)
- View all config key-value pairs
- Inline edit: click the edit icon to edit value or description in-place
- Create new entries via modal form
- Delete entries with confirmation

---

## API Routes

All API routes live under `web/app/api/` and are consumed by the client-side pages.

| Route                                  | Methods          | Description                         |
|----------------------------------------|------------------|-------------------------------------|
| `/api/sessions`                        | GET, POST        | List / create sessions              |
| `/api/sessions/:id`                    | GET, PATCH, DELETE | Read / update / delete session    |
| `/api/sessions/:id/notes`              | POST             | Append note to session              |
| `/api/sessions/:id/notes/:noteId`      | PATCH, DELETE    | Pin/unpin / delete a note           |
| `/api/skills`                          | GET              | List skills                         |
| `/api/skills/:slug`                    | GET              | Read skill detail                   |
| `/api/config`                          | GET, POST        | List / create config entries        |
| `/api/config/:key`                     | GET, PATCH, DELETE | Read / update / delete config key |

---

## Environment Variables

Create `web/.env.local` (or set via Docker Compose `environment:`):

```
DATABASE_URL=postgresql://lmuser:lmpass@lm-mcp-postgres:5432/lmdb
ADMIN_USER=admin
ADMIN_PASSWORD=your-strong-password
SESSION_SECRET=your-32-char-secret-here-please!!
```

---

## Development

```bash
cd web
npm install
npm run dev     # starts on http://localhost:3100
```

The dev server proxies database calls to the PostgreSQL container. Set `DATABASE_URL` in `web/.env.local`.

---

## Project Structure

```
web/
├── app/
│   ├── (admin)/          # Protected admin pages (iron-session auth)
│   │   ├── dashboard/
│   │   ├── sessions/
│   │   │   └── [id]/
│   │   ├── skills/
│   │   │   └── [slug]/
│   │   └── config/
│   ├── (auth)/           # Login page (unauthenticated)
│   │   └── auth/login/
│   └── api/              # REST API routes (force-dynamic)
│       ├── sessions/
│       ├── skills/
│       └── config/
├── components/
│   └── nav-sidebar.tsx   # Left navigation
├── lib/
│   ├── db.ts             # postgres (npm) singleton
│   └── session.ts        # iron-session config
├── next.config.ts        # basePath: '/panel/mcp-admin'
└── package.json
```
