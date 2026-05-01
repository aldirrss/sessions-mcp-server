# web/

Next.js 15 web panel for `lm-mcp-ai`.

Provides a browser-based UI to manage sessions, skills, configuration, and user accounts
without requiring an MCP client. The panel is split into two sections: an **admin area**
for server operators and a **user portal** for registered users.

---

## Tech Stack

| Layer | Library / Framework |
|-------|---------------------|
| Framework | Next.js 15 (App Router) |
| Auth | `iron-session` (encrypted cookie) |
| Database | `postgres` npm (tagged template SQL) |
| Styling | Tailwind CSS v4 |
| Icons | `lucide-react` |
| Deploy | Node.js inside Docker container |

All database-touching routes use `export const dynamic = 'force-dynamic'` to disable
Next.js caching and always return fresh data.

---

## Route Structure

The panel is served at sub-path `/panel` (configured via `basePath` in `next.config.ts`),
allowing it to share a domain with the MCP server through a reverse proxy.

### Admin (`/panel/mcp-admin/*`)

Requires admin credentials. Login at `/panel/mcp-admin/login`.

| Path | Description |
|------|-------------|
| `/panel/mcp-admin` | Redirect to dashboard |
| `/panel/mcp-admin/dashboard` | Overview stats: sessions, notes, skills, recent activity |
| `/panel/mcp-admin/sessions` | Session list — search, filter by source, toggle archived |
| `/panel/mcp-admin/sessions/:id` | Session detail — context, notes, GitHub repo, pin/archive |
| `/panel/mcp-admin/skills` | Skill library — browse, search, create |
| `/panel/mcp-admin/skills/:slug` | Skill detail — full content, version history, usage |
| `/panel/mcp-admin/skills/import` | Drag & drop .md files — preview and confirm bulk import |
| `/panel/mcp-admin/config` | Config key-value store — create, edit, delete entries |
| `/panel/mcp-admin/login` | Admin login page |

### User Portal (`/panel/mcp-user/*`)

Available to all registered users. Login at `/panel/mcp-user/login`.

| Path | Description |
|------|-------------|
| `/panel/mcp-user/login` | User login |
| `/panel/mcp-user/register` | User self-registration |
| `/panel/mcp-user/portal` | Personal access token management; GitHub PAT configuration |
| `/panel/mcp-user/skills` | Browse global skills |

---

## Authentication

### Admin

All `/panel/mcp-admin/*` routes are protected by `iron-session`. Credentials are set
via environment variables. The session cookie `lm_oauth_session` expires after 7 days.

| Env Var | Description |
|---------|-------------|
| `ADMIN_USER` | Admin username |
| `ADMIN_PASSWORD` | Admin password |
| `SESSION_SECRET` | Encryption key for cookie (minimum 32 characters) |

### Users

Registered users authenticate with username and password. Roles:

| Role | Access |
|------|--------|
| `user` | User portal only (`/panel/mcp-user/*`) |
| `admin` | Full admin panel + user portal |

Users manage their own personal access tokens (PAT) in the portal. Each user can also
set a personal GitHub PAT for `repo_get_context` — one token per user, stored in
`users.github_token`.

---

## Pages

### Dashboard (`/panel/mcp-admin/dashboard`)

High-level stats: total sessions, total notes, total skills, skill usage over the last 7 days.

### Sessions (`/panel/mcp-admin/sessions`)

- Search by session ID or title
- Filter by source (`web`, `cli`, `vscode`, `unknown`)
- Toggle to show archived sessions
- Create a new session via modal form
- Delete sessions inline
- Navigate to session detail

### Session Detail (`/panel/mcp-admin/sessions/:id`)

- View and edit session title and tags
- Link or unlink a GitHub repository
- Pin or archive/restore the session
- View notes in chronological order (pinned notes highlighted)
- Pin or unpin individual notes
- Append new notes via inline form
- View linked skills with navigation to skill detail

### Skills (`/panel/mcp-admin/skills`)

- Browse all skills with category, tag, and source filters
- Search by keyword
- Navigate to skill detail
- Mark skills as global (visible to all users in the skills browser)

### Skill Import (`/panel/mcp-admin/skills/import`)

Drag and drop one or more `.md` files. Supported formats:

- **Claude format** — YAML frontmatter with `name` and `description` fields
- **Copilot format** — YAML frontmatter with `applyTo` field
- **Plain Markdown** — filename used as slug, first heading as name

Preview each skill before confirming the import.

### Skill Detail (`/panel/mcp-admin/skills/:slug`)

- View full skill content (rendered Markdown)
- Edit content and metadata
- View version history
- See which sessions have used this skill
- Toggle `is_global` flag

### Config (`/panel/mcp-admin/config`)

- View all config key-value pairs
- Inline edit: click the edit icon to update value or description in-place
- Create new entries via modal form
- Delete entries with confirmation

### User Portal (`/panel/mcp-user/portal`)

- View current user information and role
- Create named personal access tokens for MCP clients
- List and revoke existing tokens
- Set or update personal GitHub PAT for `repo_get_context`

### Skills Browser (`/panel/mcp-user/skills`)

- Browse all skills marked as `is_global = true`
- View skill name, summary, and category
- Accessible to all authenticated users

---

## API Routes

All API routes live under `app/api/` and are consumed by client-side pages.

| Route | Methods | Description |
|-------|---------|-------------|
| `/api/sessions` | GET, POST | List / create sessions |
| `/api/sessions/:id` | GET, PATCH, DELETE | Read / update / delete session |
| `/api/sessions/:id/notes` | POST | Append note to session |
| `/api/sessions/:id/notes/:noteId` | PATCH, DELETE | Pin/unpin or delete a note |
| `/api/skills` | GET | List skills |
| `/api/skills/:slug` | GET, PATCH, DELETE | Read / update / delete skill |
| `/api/config` | GET, POST | List / create config entries |
| `/api/config/:key` | GET, PATCH, DELETE | Read / update / delete config key |

---

## Environment Variables

Set these in `web/.env.local` for local development, or via `environment:` in Docker Compose:

```
DATABASE_URL=postgresql://user:pass@lm-mcp-postgres:5432/db
ADMIN_USER=admin
ADMIN_PASSWORD=your-strong-password
SESSION_SECRET=your-32-char-secret-here-minimum!!
```

---

## Build Locally

```bash
cd web
npm install
npm run dev     # starts on http://localhost:3100
```

Set `DATABASE_URL` in `web/.env.local` pointing to your PostgreSQL instance.

## Deploy via Docker

The `web` service is built and started as part of the main `docker compose up -d --build`
command in the project root. No separate build step is required.

The container runs Next.js in production mode (`npm start`) on port 3100, served at
`/panel` through the reverse proxy.

---

## Project Structure

```
web/
├── app/
│   ├── (admin)/              # Protected admin pages
│   │   ├── dashboard/
│   │   ├── sessions/
│   │   │   └── [id]/
│   │   ├── skills/
│   │   │   ├── [slug]/
│   │   │   └── import/
│   │   └── config/
│   ├── (user)/               # User portal pages
│   │   ├── login/
│   │   ├── register/
│   │   ├── portal/
│   │   └── skills/
│   ├── mcp-admin/            # Admin login (unauthenticated)
│   │   └── login/
│   ├── mcp-user/             # User login/register (unauthenticated)
│   │   ├── login/
│   │   └── register/
│   └── api/                  # REST API routes (force-dynamic)
│       ├── sessions/
│       ├── skills/
│       └── config/
├── components/
│   └── nav-sidebar.tsx       # Left navigation
├── lib/
│   ├── db.ts                 # postgres (npm) singleton
│   └── session.ts            # iron-session config
├── next.config.ts            # basePath: '/panel'
└── package.json
```
