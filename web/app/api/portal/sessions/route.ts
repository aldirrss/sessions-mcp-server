export const dynamic = 'force-dynamic'

import { NextRequest, NextResponse } from 'next/server'
import { cookies } from 'next/headers'
import { getIronSession } from 'iron-session'
import { sessionOptions } from '@/lib/auth'
import type { SessionData } from '@/lib/auth'
import sql from '@/lib/db'

export async function GET(req: NextRequest) {
  const session = await getIronSession<SessionData>(await cookies(), sessionOptions)
  if (!session.userId) return NextResponse.json({ error: 'Unauthorized' }, { status: 401 })

  const search = req.nextUrl.searchParams.get('search') ?? ''

  const rows = search
    ? await sql`
        SELECT s.session_id, s.title, s.tags, s.pinned, s.updated_at,
               COUNT(n.id)::int AS notes_count
        FROM sessions s
        LEFT JOIN notes n ON n.session_id = s.session_id
        WHERE s.owner_id = ${session.userId}::uuid
          AND s.team_id IS NULL
          AND s.archived = false
          AND (s.title ILIKE ${'%' + search + '%'} OR ${search} = ANY(s.tags))
        GROUP BY s.session_id
        ORDER BY s.pinned DESC, s.updated_at DESC
        LIMIT 100
      `
    : await sql`
        SELECT s.session_id, s.title, s.tags, s.pinned, s.updated_at,
               COUNT(n.id)::int AS notes_count
        FROM sessions s
        LEFT JOIN notes n ON n.session_id = s.session_id
        WHERE s.owner_id = ${session.userId}::uuid
          AND s.team_id IS NULL
          AND s.archived = false
        GROUP BY s.session_id
        ORDER BY s.pinned DESC, s.updated_at DESC
        LIMIT 100
      `

  return NextResponse.json(rows)
}
