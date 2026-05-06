export const dynamic = 'force-dynamic'

import { NextRequest, NextResponse } from 'next/server'
import { cookies } from 'next/headers'
import { getIronSession } from 'iron-session'
import { sessionOptions } from '@/lib/auth'
import type { SessionData } from '@/lib/auth'
import sql from '@/lib/db'

type Params = { params: Promise<{ teamId: string }> }

async function getMemberRole(teamId: string, userId: string) {
  const [m] = await sql`SELECT role FROM team_members WHERE team_id = ${teamId}::uuid AND user_id = ${userId}::uuid`
  return m?.role ?? null
}

export async function GET(_req: NextRequest, { params }: Params) {
  const { teamId } = await params
  const session = await getIronSession<SessionData>(await cookies(), sessionOptions)
  if (!session.userId) return NextResponse.json({ error: 'Unauthorized' }, { status: 401 })
  if (!await getMemberRole(teamId, session.userId)) return NextResponse.json({ error: 'Forbidden' }, { status: 403 })

  const rows = await sql`
    SELECT s.slug, s.name, s.summary, s.category, s.tags, ts.added_at
    FROM team_skills ts JOIN skills s ON s.slug = ts.skill_slug
    WHERE ts.team_id = ${teamId}::uuid
    ORDER BY s.name
  `
  return NextResponse.json(rows)
}

export async function POST(req: NextRequest, { params }: Params) {
  const { teamId } = await params
  const session = await getIronSession<SessionData>(await cookies(), sessionOptions)
  if (!session.userId) return NextResponse.json({ error: 'Unauthorized' }, { status: 401 })
  if (await getMemberRole(teamId, session.userId) !== 'admin') return NextResponse.json({ error: 'Forbidden' }, { status: 403 })

  const { slug } = await req.json()
  if (!slug) return NextResponse.json({ error: 'slug required' }, { status: 400 })

  await sql`INSERT INTO team_skills (team_id, skill_slug) VALUES (${teamId}::uuid, ${slug}) ON CONFLICT DO NOTHING`
  return NextResponse.json({ ok: true }, { status: 201 })
}
