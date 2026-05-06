export const dynamic = 'force-dynamic'

import { NextRequest, NextResponse } from 'next/server'
import { cookies } from 'next/headers'
import { getIronSession } from 'iron-session'
import { sessionOptions } from '@/lib/auth'
import type { SessionData } from '@/lib/auth'
import sql from '@/lib/db'

type Params = { params: Promise<{ teamId: string; userId: string }> }

export async function DELETE(_req: NextRequest, { params }: Params) {
  const { teamId, userId } = await params
  const session = await getIronSession<SessionData>(await cookies(), sessionOptions)
  if (!session.userId) return NextResponse.json({ error: 'Unauthorized' }, { status: 401 })

  const [caller] = await sql`SELECT role FROM team_members WHERE team_id = ${teamId}::uuid AND user_id = ${session.userId}::uuid`
  if (!caller || (caller.role !== 'admin' && session.userId !== userId)) {
    return NextResponse.json({ error: 'Forbidden' }, { status: 403 })
  }
  await sql`DELETE FROM team_members WHERE team_id = ${teamId}::uuid AND user_id = ${userId}::uuid`
  return NextResponse.json({ ok: true })
}
