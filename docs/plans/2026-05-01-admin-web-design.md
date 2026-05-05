# Admin Web Panel — Design Document

**Date:** 2026-05-01
**Updated:** 2026-05-05
**Status:** Implemented
**URL:** `https://mcp.lemacore.com/panel/mcp-admin`

---

## Overview

A full-stack TypeScript web panel for managing sessions, skills, users, config, and tokens
stored in PostgreSQL. Deployed as a separate Docker service (`lema-mcp-web`) alongside
the MCP server (`lema-mcp-ai`).

---

## Stack

| Layer | Choice | Reason |
|-------|--------|--------|
| Framework | Next.js 15 (App Router) | Full-stack, SSR, API routes, TypeScript native |
| UI | Tailwind CSS | Utility-first, no component library dependency |
| Database | `postgres` library | Lightweight, TypeScript-native, direct SQL |
| Auth | `iron-session` | Encrypted cookie, no extra DB table needed |
| Validation | `zod` | Schema validation on all API route inputs |
| Runtime | Node.js 20 Alpine (Docker) | Small image, multi-stage build |

---

## Project Structure

```
web/
├── app/
│   ├── mcp-admin/
│   │   ├── login/page.tsx
│   │   └── (protected)/
│   │       ├── layout.tsx               # sidebar + nav
│   │       ├── loading.tsx              # global loading spinner
│   │       ├── error.tsx                # global error boundary
│   │       ├── page.tsx                 # dashboard
│   │       ├── sessions/page.tsx
│   │       ├── sessions/[id]/page.tsx
│   │       ├── skills/page.tsx
│   │       ├── skills/[slug]/page.tsx
│   │       ├── skills/import/page.tsx
│   │       ├── users/page.tsx
│   │       └── config/page.tsx
│   ├── mcp-user/
│   │   ├── login/page.tsx
│   │   ├── register/page.tsx
│   │   ├── portal/
│   │   │   ├── page.tsx                 # token management + GitHub PAT
│   │   │   ├── loading.tsx
│   │   │   └── error.tsx
│   │   └── skills/page.tsx
│   └── api/
│       ├── auth/
│       │   ├── login/route.ts           # admin login (bcrypt + rate limit)
│       │   ├── logout/route.ts
│       │   ├── user-login/route.ts
│       │   ├── user-logout/route.ts
│       │   └── register/route.ts        # user registration (Zod validated)
│       ├── users/
│       │   ├── route.ts                 # GET all users (admin only)
│       │   └── [id]/route.ts            # PATCH role/is_active (admin only)
│       ├── sessions/
│       │   ├── route.ts                 # GET list, POST create (admin only)
│       │   └── [id]/
│       │       ├── route.ts             # GET, PATCH, DELETE (admin only)
│       │       ├── notes/route.ts
│       │       └── notes/[noteId]/route.ts
│       ├── skills/
│       │   ├── route.ts                 # GET list, POST create (admin only)
│       │   ├── [slug]/route.ts          # GET, PATCH, DELETE (admin only)
│       │   └── import/route.ts
│       ├── config/
│       │   ├── route.ts                 # GET list, POST create (admin only)
│       │   └── [key]/route.ts           # GET, PATCH, DELETE (admin only)
│       ├── portal/
│       │   ├── tokens/
│       │   │   ├── route.ts             # GET, POST (user session auth)
│       │   │   └── [id]/route.ts        # DELETE
│       │   ├── github-token/route.ts
│       │   └── skills/route.ts
│       └── dashboard/route.ts
├── components/
│   └── nav-sidebar.tsx
├── lib/
│   ├── auth.ts                          # iron-session config + SessionData type
│   ├── db.ts                            # postgres connection pool
│   ├── require-session.ts               # requireAdmin() helper
│   ├── schemas.ts                       # Zod schemas (login, register, token, user)
│   └── config.ts
├── middleware.ts                         # page-level route protection
├── next.config.ts                        # basePath: /panel
└── Dockerfile
```

---

## Pages & Features

### Admin (`/panel/mcp-admin/*`)

| Page | Path | Description |
|------|------|-------------|
| Login | `/panel/mcp-admin/login` | Username + bcrypt password form |
| Dashboard | `/panel/mcp-admin` | Stats: sessions, notes, skills, recent activity |
| Sessions | `/panel/mcp-admin/sessions` | List, search, filter (archived toggle) |
| Session Detail | `/panel/mcp-admin/sessions/:id` | Edit, pin, archive, link GitHub repo, manage notes |
| Skills | `/panel/mcp-admin/skills` | List, search, filter by category/tag/source |
| Skill Detail | `/panel/mcp-admin/skills/:slug` | Edit content, version history, sessions used |
| Skill Import | `/panel/mcp-admin/skills/import` | Drag & drop `.md` files, preview before confirm |
| Users | `/panel/mcp-admin/users` | List users, promote/demote role, activate/deactivate |
| Config | `/panel/mcp-admin/config` | CRUD for config key-value store |

### User Portal (`/panel/mcp-user/*`)

| Page | Path | Description |
|------|------|-------------|
| Login | `/panel/mcp-user/login` | User login |
| Register | `/panel/mcp-user/register` | Create account → receive first PAT |
| Portal | `/panel/mcp-user/portal` | Create/revoke PATs, set GitHub PAT |
| Skills | `/panel/mcp-user/skills` | Browse global skills (read-only) |

---

## Auth Flow

### Admin

```
POST /api/auth/login
  → Zod validates { username, password }
  → rate limit: max 5 attempts / 15 min per IP → 429
  → bcrypt.compare(password, ADMIN_PASSWORD_HASH)
  → set encrypted iron-session cookie (8h TTL)

middleware.ts
  → protect all mcp-admin/(protected) pages
  → no valid cookie → redirect /panel/mcp-admin/login

lib/require-session.ts → requireAdmin()
  → protects ALL /api/* admin routes (not just pages)
  → no valid session → 401 Unauthorized

POST /api/auth/logout
  → destroy cookie → redirect /panel/mcp-admin/login
```

### User

```
POST /api/auth/register
  → Zod validates { username, email, password (min 8) }
  → bcrypt hash password → insert into users table
  → auto-generate first PAT (shown once)

POST /api/auth/user-login
  → bcrypt.compare → set iron-session cookie

/api/portal/* routes
  → getIronSession() → check session.userId → 401 if missing
```

---

## API Security

All admin API routes protected by `requireAdmin()` from `lib/require-session.ts`.
All write endpoints validated by Zod schemas from `lib/schemas.ts`.

| Schema | Used in |
|--------|---------|
| `LoginSchema` | `POST /api/auth/login` |
| `RegisterSchema` | `POST /api/auth/register` |
| `CreateTokenSchema` | `POST /api/portal/tokens` |
| `PatchUserSchema` | `PATCH /api/users/[id]` |

---

## Database Access

Direct PostgreSQL connection via `postgres` library — no ORM.

```ts
// lib/db.ts
import postgres from 'postgres'
const sql = postgres(process.env.DATABASE_URL!, { max: 5 })
export default sql
```

Shares the same schema as the MCP server — no separate schema needed.

---

## Docker

```yaml
web:
  build:
    context: ./web
    dockerfile: Dockerfile
  container_name: lema-mcp-web
  restart: unless-stopped
  depends_on:
    postgres:
      condition: service_healthy
  ports:
    - "127.0.0.1:3100:3000"
  environment:
    DATABASE_URL:        postgresql://user:pass@postgres:5432/mcp_sessions
    ADMIN_USER:          ${ADMIN_USER}
    ADMIN_PASSWORD_HASH: ${ADMIN_PASSWORD_HASH}
    SESSION_SECRET:      ${SESSION_SECRET}
  security_opt:
    - no-new-privileges:true
```

Multi-stage Dockerfile: `node:20-alpine` builder → slim runner.

---

## Environment Variables

| Variable | Required | Description |
|----------|----------|-------------|
| `DATABASE_URL` | ✅ | PostgreSQL connection string |
| `ADMIN_USER` | ✅ | Admin username |
| `ADMIN_PASSWORD_HASH` | ✅ | bcrypt hash of admin password. Generate: `node -e "require('bcryptjs').hash('pass', 12).then(console.log)"` |
| `SESSION_SECRET` | ✅ | 32-char random string for cookie encryption |

---

## nginx

```nginx
server {
    server_name mcp.lemacore.com;

    location ~ ^/(mcp|oauth|\.well-known) {
        proxy_pass       http://127.0.0.1:8765;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_read_timeout 300s;
    }

    location /panel {
        proxy_pass       http://127.0.0.1:3100;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
    }
}
```
