export const dynamic = 'force-dynamic'

import { NextRequest, NextResponse } from 'next/server'
import { cookies } from 'next/headers'
import { getIronSession } from 'iron-session'
import { sessionOptions } from '@/lib/auth'
import type { SessionData } from '@/lib/auth'
import sql from '@/lib/db'
import { z } from 'zod'

type Params = { params: Promise<{ teamId: string }> }

async function requireTeamAdmin(teamId: string, userId: string) {
  const [m] = await sql`SELECT role FROM team_members WHERE team_id = ${teamId}::uuid AND user_id = ${userId}::uuid`
  return m?.role === 'admin'
}

export async function GET(_req: NextRequest, { params }: Params) {
  const { teamId } = await params
  const session = await getIronSession<SessionData>(await cookies(), sessionOptions)
  if (!session.userId) return NextResponse.json({ error: 'Unauthorized' }, { status: 401 })

  const [member] = await sql`SELECT role FROM team_members WHERE team_id = ${teamId}::uuid AND user_id = ${session.userId}::uuid`
  if (!member) return NextResponse.json({ error: 'Forbidden' }, { status: 403 })

  const rows = await sql`
    SELECT u.id, u.username, u.email, tm.role, tm.joined_at
    FROM team_members tm JOIN users u ON u.id = tm.user_id
    WHERE tm.team_id = ${teamId}::uuid
    ORDER BY CASE tm.role WHEN 'admin' THEN 0 ELSE 1 END, tm.joined_at
  `
  return NextResponse.json(rows)
}

const AddMemberSchema = z.object({ username: z.string().min(1), role: z.enum(['admin', 'member']).optional() })

export async function POST(req: NextRequest, { params }: Params) {
  const { teamId } = await params
  const session = await getIronSession<SessionData>(await cookies(), sessionOptions)
  if (!session.userId) return NextResponse.json({ error: 'Unauthorized' }, { status: 401 })
  if (!await requireTeamAdmin(teamId, session.userId)) return NextResponse.json({ error: 'Forbidden' }, { status: 403 })

  const body = await req.json()
  const parsed = AddMemberSchema.safeParse(body)
  if (!parsed.success) return NextResponse.json({ error: parsed.error.issues[0]?.message ?? 'Invalid' }, { status: 400 })

  const [user] = await sql`SELECT id, username FROM users WHERE username = ${parsed.data.username}`
  if (!user) return NextResponse.json({ error: 'User not found' }, { status: 404 })

  await sql`
    INSERT INTO team_members (team_id, user_id, role)
    VALUES (${teamId}::uuid, ${user.id}::uuid, ${parsed.data.role ?? 'member'})
    ON CONFLICT (team_id, user_id) DO NOTHING
  `
  return NextResponse.json({ ok: true }, { status: 201 })
}
