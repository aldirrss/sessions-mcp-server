export const dynamic = 'force-dynamic'

import { NextRequest, NextResponse } from 'next/server'
import { cookies } from 'next/headers'
import { getIronSession } from 'iron-session'
import { sessionOptions } from '@/lib/auth'
import type { SessionData } from '@/lib/auth'
import sql from '@/lib/db'
import { randomBytes } from 'crypto'

type Params = { params: Promise<{ teamId: string }> }

async function requireTeamAdmin(teamId: string, userId: string) {
  const [m] = await sql`SELECT role FROM team_members WHERE team_id = ${teamId}::uuid AND user_id = ${userId}::uuid`
  return m?.role === 'admin'
}

export async function GET(_req: NextRequest, { params }: Params) {
  const { teamId } = await params
  const session = await getIronSession<SessionData>(await cookies(), sessionOptions)
  if (!session.userId) return NextResponse.json({ error: 'Unauthorized' }, { status: 401 })
  if (!await requireTeamAdmin(teamId, session.userId)) return NextResponse.json({ error: 'Forbidden' }, { status: 403 })

  const rows = await sql`
    SELECT ti.token, ti.expires_at, ti.created_at, ti.used_at,
           u.username AS used_by_username
    FROM team_invites ti
    LEFT JOIN users u ON u.id = ti.used_by
    WHERE ti.team_id = ${teamId}::uuid
    ORDER BY ti.created_at DESC
  `
  return NextResponse.json(rows)
}

export async function POST(_req: NextRequest, { params }: Params) {
  const { teamId } = await params
  const session = await getIronSession<SessionData>(await cookies(), sessionOptions)
  if (!session.userId) return NextResponse.json({ error: 'Unauthorized' }, { status: 401 })
  if (!await requireTeamAdmin(teamId, session.userId)) return NextResponse.json({ error: 'Forbidden' }, { status: 403 })

  const token = randomBytes(24).toString('hex')
  const [invite] = await sql`
    INSERT INTO team_invites (token, team_id, created_by, expires_at)
    VALUES (${token}, ${teamId}::uuid, ${session.userId}::uuid, NOW() + INTERVAL '7 days')
    RETURNING token, expires_at, created_at
  `
  return NextResponse.json(invite, { status: 201 })
}
