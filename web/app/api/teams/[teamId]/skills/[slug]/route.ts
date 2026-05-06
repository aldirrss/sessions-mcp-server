export const dynamic = 'force-dynamic'

import { NextRequest, NextResponse } from 'next/server'
import { cookies } from 'next/headers'
import { getIronSession } from 'iron-session'
import { sessionOptions } from '@/lib/auth'
import type { SessionData } from '@/lib/auth'
import sql from '@/lib/db'

type Params = { params: Promise<{ teamId: string; slug: string }> }

export async function GET(req: NextRequest, { params }: Params) {
  const { teamId, slug } = await params
  const session = await getIronSession<SessionData>(await cookies(), sessionOptions)
  if (!session.userId) return NextResponse.json({ error: 'Unauthorized' }, { status: 401 })

  const [member] = await sql`SELECT role FROM team_members WHERE team_id = ${teamId}::uuid AND user_id = ${session.userId}::uuid`
  if (!member) return NextResponse.json({ error: 'Forbidden' }, { status: 403 })

  const [row] = await sql`
    SELECT s.slug, s.name, s.summary, s.content, s.category, s.tags, s.source, s.updated_at
    FROM skills s
    JOIN team_skills ts ON ts.skill_slug = s.slug AND ts.team_id = ${teamId}::uuid
    WHERE s.slug = ${slug}
  `
  if (!row) return NextResponse.json({ error: 'Not found' }, { status: 404 })
  return NextResponse.json({ ...row, viewer_role: member.role })
}

export async function DELETE(_req: NextRequest, { params }: Params) {
  const { teamId, slug } = await params
  const session = await getIronSession<SessionData>(await cookies(), sessionOptions)
  if (!session.userId) return NextResponse.json({ error: 'Unauthorized' }, { status: 401 })

  const [member] = await sql`SELECT role FROM team_members WHERE team_id = ${teamId}::uuid AND user_id = ${session.userId}::uuid`
  if (!member || member.role !== 'admin') return NextResponse.json({ error: 'Forbidden' }, { status: 403 })

  await sql`DELETE FROM team_skills WHERE team_id = ${teamId}::uuid AND skill_slug = ${slug}`
  return NextResponse.json({ ok: true })
}
