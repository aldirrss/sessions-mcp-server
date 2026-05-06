export const dynamic = 'force-dynamic'

import { NextRequest, NextResponse } from 'next/server'
import { cookies } from 'next/headers'
import { getIronSession } from 'iron-session'
import { sessionOptions } from '@/lib/auth'
import type { SessionData } from '@/lib/auth'
import sql from '@/lib/db'

type Params = { params: Promise<{ sessionId: string }> }

async function requireOwner(sessionId: string, userId: string) {
  const [row] = await sql`
    SELECT session_id FROM sessions
    WHERE session_id = ${sessionId} AND owner_id = ${userId}::uuid AND team_id IS NULL
  `
  return row ?? null
}

export async function GET(_req: NextRequest, { params }: Params) {
  const session = await getIronSession<SessionData>(await cookies(), sessionOptions)
  if (!session.userId) return NextResponse.json({ error: 'Unauthorized' }, { status: 401 })

  const { sessionId } = await params
  if (!await requireOwner(sessionId, session.userId)) {
    return NextResponse.json({ error: 'Not found' }, { status: 404 })
  }

  const [row] = await sql`SELECT * FROM sessions WHERE session_id = ${sessionId}`
  const notes = await sql`
    SELECT id, content, source, pinned, created_at
    FROM notes WHERE session_id = ${sessionId}
    ORDER BY pinned DESC, created_at ASC
  `
  return NextResponse.json({ ...row, notes })
}

export async function DELETE(_req: NextRequest, { params }: Params) {
  const session = await getIronSession<SessionData>(await cookies(), sessionOptions)
  if (!session.userId) return NextResponse.json({ error: 'Unauthorized' }, { status: 401 })

  const { sessionId } = await params
  if (!await requireOwner(sessionId, session.userId)) {
    return NextResponse.json({ error: 'Not found' }, { status: 404 })
  }

  await sql`DELETE FROM sessions WHERE session_id = ${sessionId}`
  return NextResponse.json({ ok: true })
}

export async function PATCH(req: NextRequest, { params }: Params) {
  const session = await getIronSession<SessionData>(await cookies(), sessionOptions)
  if (!session.userId) return NextResponse.json({ error: 'Unauthorized' }, { status: 401 })

  const { sessionId } = await params
  if (!await requireOwner(sessionId, session.userId)) {
    return NextResponse.json({ error: 'Not found' }, { status: 404 })
  }

  const { pinned } = await req.json() as { pinned?: boolean }
  if (typeof pinned === 'boolean') {
    await sql`UPDATE sessions SET pinned = ${pinned}, updated_at = NOW() WHERE session_id = ${sessionId}`
  }
  return NextResponse.json({ ok: true })
}
