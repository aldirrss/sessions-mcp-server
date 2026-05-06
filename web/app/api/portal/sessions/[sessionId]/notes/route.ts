export const dynamic = 'force-dynamic'

import { NextRequest, NextResponse } from 'next/server'
import { cookies } from 'next/headers'
import { getIronSession } from 'iron-session'
import { sessionOptions } from '@/lib/auth'
import type { SessionData } from '@/lib/auth'
import sql from '@/lib/db'

type Params = { params: Promise<{ sessionId: string }> }

export async function POST(req: NextRequest, { params }: Params) {
  const session = await getIronSession<SessionData>(await cookies(), sessionOptions)
  if (!session.userId) return NextResponse.json({ error: 'Unauthorized' }, { status: 401 })

  const { sessionId } = await params
  const [owner] = await sql`
    SELECT session_id FROM sessions
    WHERE session_id = ${sessionId} AND owner_id = ${session.userId}::uuid AND team_id IS NULL
  `
  if (!owner) return NextResponse.json({ error: 'Not found' }, { status: 404 })

  const { content } = await req.json() as { content: string }
  if (!content?.trim()) return NextResponse.json({ error: 'content required' }, { status: 400 })

  await sql`INSERT INTO notes (session_id, content, source) VALUES (${sessionId}, ${content.trim()}, 'web')`
  await sql`UPDATE sessions SET updated_at = NOW() WHERE session_id = ${sessionId}`

  return NextResponse.json({ ok: true })
}
