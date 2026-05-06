export const dynamic = 'force-dynamic'

import { NextRequest, NextResponse } from 'next/server'
import { cookies } from 'next/headers'
import { getIronSession } from 'iron-session'
import { sessionOptions } from '@/lib/auth'
import type { SessionData } from '@/lib/auth'
import sql from '@/lib/db'

type Params = { params: Promise<{ teamId: string; id: string }> }

export async function DELETE(_req: NextRequest, { params }: Params) {
  const { teamId, id } = await params
  const session = await getIronSession<SessionData>(await cookies(), sessionOptions)
  if (!session.userId) return NextResponse.json({ error: 'Unauthorized' }, { status: 401 })

  const [member] = await sql`SELECT role FROM team_members WHERE team_id = ${teamId}::uuid AND user_id = ${session.userId}::uuid`
  if (!member || member.role !== 'admin') return NextResponse.json({ error: 'Forbidden' }, { status: 403 })

  await sql`DELETE FROM sessions WHERE session_id = ${id} AND team_id = ${teamId}::uuid`
  return NextResponse.json({ ok: true })
}
