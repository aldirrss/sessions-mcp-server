# web/

Next.js 15 web panel for **Sessions MCP Server**.

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
| `/panel/mcp-admin/users` | User management — list, promote/demote role, activate/deactivate |
| `/panel/mcp-admin/blacklist` | Email blacklist — add/remove blocked email addresses |
| `/panel/mcp-admin/team-requests` | Team creation requests — approve or reject |
| `/panel/mcp-admin/login` | Admin login page |

### User Portal (`/panel/mcp-user/*`)

Available to all registered users. Login at `/panel/mcp-user/login`.

| Path | Description |
|------|-------------|
| `/panel/mcp-user/login` | User login |
| `/panel/mcp-user/register` | User self-registration |
| `/panel/mcp-user/portal` | Personal access token management; GitHub PAT configuration; team join requests |
| `/panel/mcp-user/sessions` | Personal session list |
| `/panel/mcp-user/sessions/:id` | Personal session detail — context, notes, pin/unpin, delete, append |
| `/panel/mcp-user/skills` | Browse global skills |
| `/panel/mcp-user/skills/:slug` | Global skill detail — full content (read-only) |
| `/panel/mcp-user/teams/:teamId` | Team management — members, sessions, skills |
| `/panel/mcp-user/teams/:teamId/sessions/:id` | Team session detail — read-only for members, full actions for admin |
| `/panel/mcp-user/teams/:teamId/skills/:slug` | Team skill detail — admin can remove skill from team |

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

Token values are hashed with SHA-256 on creation and cannot be retrieved later. The first
8 characters of the raw token (`token_prefix`) are stored and displayed in the token list
as a visual reminder (e.g. `abc12345••••••••`).

---

## Teams

Users can request to create a team through the portal. An admin approves or rejects the
request in `/panel/mcp-admin/team-requests`. Once approved, the requesting user becomes
the team admin and can manage members, sessions, and skills for that team.

Rules:
- A user can be a member of multiple teams but can be admin of at most one team.
- A user with a pending team request cannot submit another until it is resolved.
- A rejected request allows the user to re-request (as long as they are not yet an admin).

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
- List and revoke existing tokens (token prefix shown for identification)
- Set or update personal GitHub PAT for `repo_get_context`
- Request team creation (one pending request at a time; blocked if already team admin)

### Personal Sessions (`/panel/mcp-user/sessions`)

- List all personal sessions (not associated with a team)
- Search and navigate to session detail

### Personal Session Detail (`/panel/mcp-user/sessions/:id`)

- View session context and metadata
- View pinned notes and regular notes
- Pin/unpin the session
- Append a new note
- Delete the session

### Skills Browser (`/panel/mcp-user/skills`)

- Browse all skills marked as `is_global = true`
- Search by name, slug, or summary
- Navigate to skill detail

### Skill Detail (`/panel/mcp-user/skills/:slug`)

- View full skill content (read-only)
- Shows metadata: slug, category, tags, last updated

### Team Page (`/panel/mcp-user/teams/:teamId`)

- Members tab: list of team members and their roles
- Sessions tab: team sessions list
- Skills tab: team skills list
- Admins can invite members, manage sessions, and remove skills

### Team Session Detail (`/panel/mcp-user/teams/:teamId/sessions/:id`)

- Members: read-only view of session context and notes
- Admins: full actions — pin/unpin, append note, delete session

### Team Skill Detail (`/panel/mcp-user/teams/:teamId/skills/:slug`)

- View full skill content
- Admins can remove the skill from the team

---

## API Routes

All API routes live under `app/api/` and are consumed by client-side pages.

### Admin API

| Route | Methods | Description |
|-------|---------|-------------|
| `/api/sessions` | GET, POST | List / create sessions |
| `/api/sessions/:id` | GET, PATCH, DELETE | Read / update / delete session |
| `/api/sessions/:id/notes` | POST | Append note to session |
| `/api/sessions/:id/notes/:noteId` | PATCH, DELETE | Pin/unpin or delete a note |
| `/api/skills` | GET, POST | List / create skills |
| `/api/skills/:slug` | GET, PATCH, DELETE | Read / update / delete skill |
| `/api/config` | GET, POST | List / create config entries |
| `/api/config/:key` | GET, PATCH, DELETE | Read / update / delete config key |
| `/api/users` | GET | List users |
| `/api/users/:id` | PATCH | Update role or active status |
| `/api/blacklist` | GET, POST | List / add blacklisted emails |
| `/api/blacklist/:id` | DELETE | Remove blacklisted email |
| `/api/admin/team-requests` | GET | List pending team requests |
| `/api/admin/team-requests/:id` | POST | Approve or reject a team request |

### User Portal API

| Route | Methods | Description |
|-------|---------|-------------|
| `/api/portal/tokens` | GET, POST | List / create personal tokens |
| `/api/portal/tokens/:id` | DELETE | Revoke a token |
| `/api/portal/github-token` | GET, POST, DELETE | Manage personal GitHub PAT |
| `/api/portal/skills` | GET | List global skills |
| `/api/portal/skills/:slug` | GET | Get full skill content |
| `/api/portal/sessions` | GET | List personal sessions |
| `/api/portal/sessions/:id` | GET, PATCH, DELETE | Read / update / delete personal session |
| `/api/portal/sessions/:id/notes` | POST | Append note to personal session |
| `/api/portal/team-requests` | GET, POST | Get team request status / submit request |
| `/api/teams/:teamId` | GET | Team info + membership role |
| `/api/teams/:teamId/sessions` | GET | List team sessions |
| `/api/teams/:teamId/sessions/:id` | GET, PATCH, DELETE | Team session detail / actions |
| `/api/teams/:teamId/sessions/:id/notes` | POST | Append note (admin only) |
| `/api/teams/:teamId/skills` | GET | List team skills |
| `/api/teams/:teamId/skills/:slug` | DELETE | Remove skill from team (admin only) |

---

## Environment Variables

Set these in `web/.env.local` for local development, or via `environment:` in Docker Compose:

```
DATABASE_URL=postgresql://user:pass@sessions-mcp-postgres:5432/db
ADMIN_USER=admin
ADMIN_PASSWORD=your-strong-password
SESSION_SECRET=your-32-char-secret-here-minimum!!
SMTP_HOST=smtp.example.com
SMTP_PORT=587
SMTP_USER=no-reply@example.com
SMTP_PASS=your-smtp-password
SMTP_FROM=no-reply@example.com
ADMIN_EMAIL=admin@example.com
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
│   ├── mcp-admin/
│   │   ├── login/
│   │   └── (protected)/
│   │       ├── layout.tsx
│   │       ├── page.tsx              # dashboard
│   │       ├── sessions/
│   │       │   └── [id]/
│   │       ├── skills/
│   │       │   ├── [slug]/
│   │       │   └── import/
│   │       ├── users/
│   │       ├── config/
│   │       ├── blacklist/
│   │       └── team-requests/
│   ├── mcp-user/
│   │   ├── login/
│   │   ├── register/
│   │   ├── portal/
│   │   ├── sessions/
│   │   │   └── [sessionId]/
│   │   ├── skills/
│   │   │   └── [slug]/
│   │   └── teams/
│   │       └── [teamId]/
│   │           ├── page.tsx          # members, sessions, skills tabs
│   │           ├── sessions/
│   │           │   └── [sessionId]/
│   │           └── skills/
│   │               └── [slug]/
│   └── api/
│       ├── auth/
│       ├── sessions/
│       ├── skills/
│       ├── config/
│       ├── users/
│       ├── blacklist/
│       ├── admin/
│       │   └── team-requests/
│       ├── portal/
│       │   ├── tokens/
│       │   ├── github-token/
│       │   ├── skills/
│       │   │   └── [slug]/
│       │   ├── sessions/
│       │   │   └── [sessionId]/
│       │   │       └── notes/
│       │   └── team-requests/
│       └── teams/
│           └── [teamId]/
│               ├── route.ts
│               ├── sessions/
│               │   └── [id]/
│               │       └── notes/
│               └── skills/
│                   └── [slug]/
├── components/
│   ├── nav-sidebar.tsx
│   └── user-portal-header.tsx
├── lib/
│   ├── db.ts
│   ├── session.ts
│   └── config.ts
├── next.config.ts                    # basePath: '/panel'
└── package.json
```
