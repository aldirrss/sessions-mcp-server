# Admin Web Panel — Design Document

**Date:** 2026-05-01  
**Status:** Approved  
**URL:** `https://mcp.lemacore.com/panel/mcp-admin`

---

## Overview

A full-stack TypeScript admin panel for managing sessions and skills stored in PostgreSQL.
Deployed as a separate Docker service alongside the existing MCP server.

---

## Stack

| Layer | Choice | Reason |
|-------|--------|--------|
| Framework | Next.js 15 (App Router) | Full-stack, SSR, API routes, TypeScript native |
| UI | Tailwind CSS + shadcn/ui | Ready-made table, dialog, form, badge components |
| Database | `postgres` library | Lightweight, TypeScript-native, direct SQL |
| Auth | `iron-session` | Encrypted cookie, no database needed |
| Runtime | Node.js 20 Alpine (Docker) | Small image, multi-stage build |

---

## Project Structure

```
lm-mcp-ai/
├── web/
│   ├── app/
│   │   ├── (auth)/
│   │   │   └── login/page.tsx
│   │   ├── (admin)/
│   │   │   ├── layout.tsx              # sidebar + nav
│   │   │   ├── page.tsx                # dashboard
│   │   │   ├── sessions/page.tsx       # sessions list
│   │   │   ├── sessions/[id]/page.tsx  # session detail
│   │   │   ├── skills/page.tsx         # skills list
│   │   │   └── skills/[slug]/page.tsx  # skill detail
│   │   └── api/
│   │       ├── auth/login/route.ts
│   │       ├── auth/logout/route.ts
│   │       ├── sessions/route.ts
│   │       ├── sessions/[id]/route.ts
│   │       ├── skills/route.ts
│   │       └── skills/[slug]/route.ts
│   ├── components/
│   │   ├── ui/                         # shadcn/ui components
│   │   ├── sessions-table.tsx
│   │   ├── skills-table.tsx
│   │   └── nav-sidebar.tsx
│   ├── lib/
│   │   ├── db.ts                       # postgres connection pool
│   │   └── auth.ts                     # iron-session config
│   ├── middleware.ts                    # protect (admin) routes
│   ├── next.config.ts                  # basePath: /panel/mcp-admin
│   ├── Dockerfile
│   └── .env.local                      # local dev only
```

---

## Pages & Features

### `/login`
- Username + password form
- Validates against `ADMIN_USER` + `ADMIN_PASSWORD` env vars
- Sets encrypted `iron-session` cookie (8h TTL)
- Redirect to `/` on success

### `/` — Dashboard
- Total sessions, total skills, skills used this week (summary cards)
- Top 5 skills by usage (table)
- Recent 10 sessions (table)

### `/sessions`
- Paginated table: Session ID, Title, Source, Tags, Updated At, Notes count
- Search by title/ID, filter by source
- Actions: View, Delete
- Button: New Session → create form (modal)

### `/sessions/[id]`
- Header: title, source, tags (inline editable)
- Notes timeline (timestamp + source per note)
- Append note form
- Skills used in this session (list)
- Delete session button

### `/skills`
- Paginated table: Slug, Name, Category, Tags, Source, Updated At, Sessions used count
- Full-text search, filter by category/tag/source
- Actions: View, Delete
- Button: New Skill → create form (modal)

### `/skills/[slug]`
- Header: slug, name, category, tags, source (inline editable)
- Markdown content textarea (edit + save)
- Version history list (timestamp per snapshot)
- Sessions that used this skill (list)
- Delete skill button

---

## Auth Flow

```
POST /api/auth/login
  → compare ADMIN_USER + ADMIN_PASSWORD from env
  → set encrypted cookie via iron-session (SESSION_SECRET)
  → redirect to /

middleware.ts
  → protect all (admin) routes
  → no valid cookie → redirect /login

POST /api/auth/logout
  → destroy cookie → redirect /login
```

No user data stored in database. Cookie encrypted with 32-char `SESSION_SECRET`.

**Future migration path:** Replace `iron-session` logic with Auth.js (NextAuth) in `auth.ts` + `middleware.ts` — route protection layer unchanged.

---

## Database Access

Direct PostgreSQL connection via `postgres` library — no ORM.

```ts
// lib/db.ts
import postgres from 'postgres'
const sql = postgres(process.env.DATABASE_URL!, { max: 5 })
export default sql
```

Queries in API routes use the same schema as MCP server (no separate schema needed).

---

## Docker

```yaml
# docker-compose.yml addition
web:
  build:
    context: ./web
    dockerfile: Dockerfile
  ports:
    - "3000:3000"
  environment:
    DATABASE_URL: postgres://user:pass@db:5432/lmdb
    ADMIN_USER: ${ADMIN_USER}
    ADMIN_PASSWORD: ${ADMIN_PASSWORD}
    SESSION_SECRET: ${SESSION_SECRET}
  depends_on:
    - db
  networks:
    - lm-network
```

Multi-stage Dockerfile: `node:20-alpine` builder → slim runner (~150MB).

---

## nginx

```nginx
server {
    server_name mcp.lemacore.com;

    # Existing MCP server
    location /mcp {
        proxy_pass http://localhost:8000;
    }

    # Admin web panel
    location /panel/mcp-admin {
        proxy_pass http://localhost:3000;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
    }
}
```

---

## Environment Variables

| Variable | Description |
|----------|-------------|
| `DATABASE_URL` | PostgreSQL connection string |
| `ADMIN_USER` | Admin username |
| `ADMIN_PASSWORD` | Admin password (plain, stored only in env) |
| `SESSION_SECRET` | 32-char random string for cookie encryption |
