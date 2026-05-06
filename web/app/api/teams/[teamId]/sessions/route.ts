export const dynamic = 'force-dynamic'

import { NextRequest, NextResponse } from 'next/server'
import { cookies } from 'next/headers'
import { getIronSession } from 'iron-session'
import { sessionOptions } from '@/lib/auth'
import type { SessionData } from '@/lib/auth'
import sql from '@/lib/db'
import { z } from 'zod'

type Params = { params: Promise<{ teamId: string }> }

async function requireMember(teamId: string, userId: string) {
  const [m] = await sql`SELECT role FROM team_members WHERE team_id = ${teamId}::uuid AND user_id = ${userId}::uuid`
  return m ?? null
}

export async function GET(req: NextRequest, { params }: Params) {
  const { teamId } = await params
  const session = await getIronSession<SessionData>(await cookies(), sessionOptions)
  if (!session.userId) return NextResponse.json({ error: 'Unauthorized' }, { status: 401 })
  if (!await requireMember(teamId, session.userId)) return NextResponse.json({ error: 'Forbidden' }, { status: 403 })

  const { searchParams } = new URL(req.url)
  const search = searchParams.get('q') ?? ''
  const showArchived = searchParams.get('archived') === '1'

  const rows = await sql`
    SELECT s.session_id, s.title, s.source, s.tags, s.pinned, s.archived, s.updated_at,
           COUNT(n.id) AS notes_count
    FROM sessions s
    LEFT JOIN notes n ON n.session_id = s.session_id
    WHERE s.team_id = ${teamId}::uuid
      AND (${!showArchived} = false OR s.archived = false)
      AND (${search} = '' OR s.title ILIKE ${'%' + search + '%'})
    GROUP BY s.session_id
    ORDER BY s.pinned DESC, s.updated_at DESC
  `
  return NextResponse.json(rows)
}

const CreateSessionSchema = z.object({
  session_id: z.string().min(1).max(100),
  title: z.string().min(1).max(200),
  context: z.string().max(50000).optional(),
  source: z.string().max(50).optional(),
  tags: z.array(z.string()).optional(),
})

export async function POST(req: NextRequest, { params }: Params) {
  const { teamId } = await params
  const session = await getIronSession<SessionData>(await cookies(), sessionOptions)
  if (!session.userId) return NextResponse.json({ error: 'Unauthorized' }, { status: 401 })

  const member = await requireMember(teamId, session.userId)
  if (!member || member.role !== 'admin') return NextResponse.json({ error: 'Forbidden' }, { status: 403 })

  const body = await req.json()
  const parsed = CreateSessionSchema.safeParse(body)
  if (!parsed.success) return NextResponse.json({ error: parsed.error.issues[0]?.message ?? 'Invalid' }, { status: 400 })

  const { session_id, title, context = '', source = 'web', tags = [] } = parsed.data
  const [row] = await sql`
    INSERT INTO sessions (session_id, title, context, source, tags, owner_id, team_id)
    VALUES (${session_id}, ${title}, ${context}, ${source}, ${tags}, ${session.userId}::uuid, ${teamId}::uuid)
    ON CONFLICT (session_id) DO UPDATE SET title = EXCLUDED.title, context = EXCLUDED.context
    RETURNING session_id, title, source, tags, updated_at
  `
  return NextResponse.json(row, { status: 201 })
}
