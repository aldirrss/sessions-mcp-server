export const dynamic = 'force-dynamic'

import { NextRequest, NextResponse } from 'next/server'
import { cookies } from 'next/headers'
import { getIronSession } from 'iron-session'
import { sessionOptions } from '@/lib/auth'
import type { SessionData } from '@/lib/auth'
import sql from '@/lib/db'

type Params = { params: Promise<{ teamId: string; id: string }> }

async function requireMember(teamId: string, userId: string) {
  const [m] = await sql`SELECT role FROM team_members WHERE team_id = ${teamId}::uuid AND user_id = ${userId}::uuid`
  return m ?? null
}

export async function GET(_req: NextRequest, { params }: Params) {
  const { teamId, id } = await params
  const session = await getIronSession<SessionData>(await cookies(), sessionOptions)
  if (!session.userId) return NextResponse.json({ error: 'Unauthorized' }, { status: 401 })

  const member = await requireMember(teamId, session.userId)
  if (!member) return NextResponse.json({ error: 'Forbidden' }, { status: 403 })

  const [row] = await sql`SELECT * FROM sessions WHERE session_id = ${id} AND team_id = ${teamId}::uuid`
  if (!row) return NextResponse.json({ error: 'Not found' }, { status: 404 })

  const notes = await sql`
    SELECT id, content, source, pinned, created_at
    FROM notes WHERE session_id = ${id}
    ORDER BY pinned DESC, created_at ASC
  `
  const skills = await sql`
    SELECT ss.skill_slug, s.name, s.category, ss.used_at
    FROM session_skills ss
    LEFT JOIN skills s ON s.slug = ss.skill_slug
    WHERE ss.session_id = ${id}
    ORDER BY ss.used_at ASC
  `
  return NextResponse.json({ ...row, notes, skills, viewer_role: member.role })
}

export async function PATCH(req: NextRequest, { params }: Params) {
  const { teamId, id } = await params
  const session = await getIronSession<SessionData>(await cookies(), sessionOptions)
  if (!session.userId) return NextResponse.json({ error: 'Unauthorized' }, { status: 401 })

  const member = await requireMember(teamId, session.userId)
  if (!member || member.role !== 'admin') return NextResponse.json({ error: 'Forbidden' }, { status: 403 })

  const { pinned } = await req.json() as { pinned?: boolean }
  if (typeof pinned === 'boolean') {
    await sql`UPDATE sessions SET pinned = ${pinned}, updated_at = NOW() WHERE session_id = ${id} AND team_id = ${teamId}::uuid`
  }
  return NextResponse.json({ ok: true })
}

export async function DELETE(_req: NextRequest, { params }: Params) {
  const { teamId, id } = await params
  const session = await getIronSession<SessionData>(await cookies(), sessionOptions)
  if (!session.userId) return NextResponse.json({ error: 'Unauthorized' }, { status: 401 })

  const member = await requireMember(teamId, session.userId)
  if (!member || member.role !== 'admin') return NextResponse.json({ error: 'Forbidden' }, { status: 403 })

  await sql`DELETE FROM sessions WHERE session_id = ${id} AND team_id = ${teamId}::uuid`
  return NextResponse.json({ ok: true })
}
