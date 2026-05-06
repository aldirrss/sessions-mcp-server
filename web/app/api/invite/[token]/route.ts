export const dynamic = 'force-dynamic'

import { NextRequest, NextResponse } from 'next/server'
import { cookies } from 'next/headers'
import { getIronSession } from 'iron-session'
import { sessionOptions } from '@/lib/auth'
import type { SessionData } from '@/lib/auth'
import sql from '@/lib/db'

type Params = { params: Promise<{ token: string }> }

async function resolveInvite(token: string) {
  const [invite] = await sql`
    SELECT ti.token, ti.team_id, ti.used_by, ti.expires_at, t.name AS team_name
    FROM team_invites ti
    JOIN teams t ON t.id = ti.team_id
    WHERE ti.token = ${token}
  `
  return invite ?? null
}

export async function GET(_req: NextRequest, { params }: Params) {
  const { token } = await params
  const session = await getIronSession<SessionData>(await cookies(), sessionOptions)
  if (!session.userId) return NextResponse.json({ error: 'Unauthorized' }, { status: 401 })

  const invite = await resolveInvite(token)
  if (!invite) return NextResponse.json({ error: 'Invite not found' }, { status: 404 })
  if (invite.used_by) return NextResponse.json({ error: 'This invite has already been used' }, { status: 410 })
  if (new Date(invite.expires_at) < new Date()) return NextResponse.json({ error: 'This invite has expired' }, { status: 410 })

  const [already] = await sql`
    SELECT 1 FROM team_members WHERE team_id = ${invite.team_id}::uuid AND user_id = ${session.userId}::uuid
  `
  return NextResponse.json({
    team_id: invite.team_id,
    team_name: invite.team_name,
    expires_at: invite.expires_at,
    already_member: !!already,
  })
}

export async function POST(_req: NextRequest, { params }: Params) {
  const { token } = await params
  const session = await getIronSession<SessionData>(await cookies(), sessionOptions)
  if (!session.userId) return NextResponse.json({ error: 'Unauthorized' }, { status: 401 })

  const invite = await resolveInvite(token)
  if (!invite) return NextResponse.json({ error: 'Invite not found' }, { status: 404 })
  if (invite.used_by) return NextResponse.json({ error: 'This invite has already been used' }, { status: 410 })
  if (new Date(invite.expires_at) < new Date()) return NextResponse.json({ error: 'This invite has expired' }, { status: 410 })

  const [already] = await sql`
    SELECT 1 FROM team_members WHERE team_id = ${invite.team_id}::uuid AND user_id = ${session.userId}::uuid
  `
  if (already) return NextResponse.json({ team_id: invite.team_id, already_member: true })

  await sql`
    INSERT INTO team_members (team_id, user_id, role)
    VALUES (${invite.team_id}::uuid, ${session.userId}::uuid, 'member')
    ON CONFLICT DO NOTHING
  `
  await sql`
    UPDATE team_invites SET used_by = ${session.userId}::uuid, used_at = NOW()
    WHERE token = ${token}
  `
  return NextResponse.json({ ok: true, team_id: invite.team_id })
}
