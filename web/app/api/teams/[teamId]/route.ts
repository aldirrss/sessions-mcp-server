export const dynamic = 'force-dynamic'

import { NextResponse } from 'next/server'
import { cookies } from 'next/headers'
import { getIronSession } from 'iron-session'
import { sessionOptions } from '@/lib/auth'
import type { SessionData } from '@/lib/auth'
import sql from '@/lib/db'

type Params = { params: Promise<{ teamId: string }> }

async function requireTeamAdmin(teamId: string): Promise<{ userId: string } | { error: NextResponse }> {
  const session = await getIronSession<SessionData>(await cookies(), sessionOptions)
  if (!session.userId) return { error: NextResponse.json({ error: 'Unauthorized' }, { status: 401 }) }
  const [member] = await sql`
    SELECT role FROM team_members WHERE team_id = ${teamId}::uuid AND user_id = ${session.userId}::uuid
  `
  if (!member || member.role !== 'admin') {
    return { error: NextResponse.json({ error: 'Forbidden' }, { status: 403 }) }
  }
  return { userId: session.userId }
}

export async function GET(_req: Request, { params }: Params) {
  const { teamId } = await params
  const session = await getIronSession<SessionData>(await cookies(), sessionOptions)
  if (!session.userId) return NextResponse.json({ error: 'Unauthorized' }, { status: 401 })

  const [member] = await sql`
    SELECT role FROM team_members WHERE team_id = ${teamId}::uuid AND user_id = ${session.userId}::uuid
  `
  if (!member) return NextResponse.json({ error: 'Forbidden' }, { status: 403 })

  const [team] = await sql`SELECT id, name, created_at FROM teams WHERE id = ${teamId}::uuid`
  if (!team) return NextResponse.json({ error: 'Not found' }, { status: 404 })

  return NextResponse.json({ ...team, role: member.role })
}

export { requireTeamAdmin }
