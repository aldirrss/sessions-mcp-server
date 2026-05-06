export const dynamic = 'force-dynamic'

import { NextRequest, NextResponse } from 'next/server'
import { cookies } from 'next/headers'
import { getIronSession } from 'iron-session'
import { sessionOptions } from '@/lib/auth'
import type { SessionData } from '@/lib/auth'
import sql from '@/lib/db'

type Params = { params: Promise<{ sessionId: string }> }

export async function DELETE(_req: NextRequest, { params }: Params) {
  const session = await getIronSession<SessionData>(await cookies(), sessionOptions)
  if (!session.userId) return NextResponse.json({ error: 'Unauthorized' }, { status: 401 })

  const { sessionId } = await params

  const [row] = await sql`
    SELECT session_id FROM sessions
    WHERE session_id = ${sessionId} AND owner_id = ${session.userId}::uuid AND team_id IS NULL
  `
  if (!row) return NextResponse.json({ error: 'Not found' }, { status: 404 })

  await sql`DELETE FROM sessions WHERE session_id = ${sessionId}`
  return NextResponse.json({ ok: true })
}

export async function PATCH(req: NextRequest, { params }: Params) {
  const session = await getIronSession<SessionData>(await cookies(), sessionOptions)
  if (!session.userId) return NextResponse.json({ error: 'Unauthorized' }, { status: 401 })

  const { sessionId } = await params
  const { pinned } = await req.json() as { pinned?: boolean }

  const [row] = await sql`
    SELECT session_id FROM sessions
    WHERE session_id = ${sessionId} AND owner_id = ${session.userId}::uuid AND team_id IS NULL
  `
  if (!row) return NextResponse.json({ error: 'Not found' }, { status: 404 })

  if (typeof pinned === 'boolean') {
    await sql`UPDATE sessions SET pinned = ${pinned} WHERE session_id = ${sessionId}`
  }
  return NextResponse.json({ ok: true })
}
