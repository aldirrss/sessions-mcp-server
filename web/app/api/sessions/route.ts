export const dynamic = 'force-dynamic'

import { NextRequest, NextResponse } from 'next/server'
import sql from '@/lib/db'
import { requireAdmin } from '@/lib/require-session'

export async function GET(req: NextRequest) {
  const guard = await requireAdmin()
  if ('error' in guard) return guard.error

  const { searchParams } = req.nextUrl
  const search = searchParams.get('search') ?? ''
  const source = searchParams.get('source') ?? ''
  const page = Math.max(1, parseInt(searchParams.get('page') ?? '1'))
  const limit = 20
  const offset = (page - 1) * limit

  const showArchived = searchParams.get('archived') === 'true'

  const rows = await sql`
    SELECT
      s.session_id, s.title, s.source, s.tags, s.pinned, s.archived, s.updated_at,
      COUNT(n.id)::int AS notes_count
    FROM sessions s
    LEFT JOIN notes n ON n.session_id = s.session_id
    WHERE
      (${search} = '' OR s.title ILIKE ${'%' + search + '%'} OR s.session_id ILIKE ${'%' + search + '%'})
      AND (${source} = '' OR s.source = ${source})
      AND (${showArchived} OR s.archived = false)
    GROUP BY s.session_id
    ORDER BY s.pinned DESC, s.updated_at DESC
    LIMIT ${limit} OFFSET ${offset}
  `

  const [total] = await sql`
    SELECT COUNT(*)::int AS count FROM sessions
    WHERE
      (${search} = '' OR title ILIKE ${'%' + search + '%'} OR session_id ILIKE ${'%' + search + '%'})
      AND (${source} = '' OR source = ${source})
      AND (${showArchived} OR archived = false)
  `

  return NextResponse.json({ rows, total: total.count, page, limit })
}

export async function POST(req: NextRequest) {
  const guard = await requireAdmin()
  if ('error' in guard) return guard.error

  const { session_id, title, context, source, tags } = await req.json()

  if (!session_id || !title) {
    return NextResponse.json({ error: 'session_id and title required' }, { status: 400 })
  }

  const [row] = await sql`
    INSERT INTO sessions (session_id, title, context, source, tags)
    VALUES (${session_id}, ${title}, ${context ?? ''}, ${source ?? 'web'}, ${tags ?? []})
    ON CONFLICT (session_id) DO UPDATE
      SET title = EXCLUDED.title, context = EXCLUDED.context,
          source = EXCLUDED.source, tags = EXCLUDED.tags
    RETURNING session_id, title, source, tags, updated_at
  `

  return NextResponse.json(row, { status: 201 })
}
