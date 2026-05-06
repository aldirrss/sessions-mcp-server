export const dynamic = 'force-dynamic'

import { NextRequest, NextResponse } from 'next/server'
import { cookies } from 'next/headers'
import { getIronSession } from 'iron-session'
import { sessionOptions } from '@/lib/auth'
import type { SessionData } from '@/lib/auth'
import sql from '@/lib/db'

type Params = { params: Promise<{ teamId: string; id: string }> }

export async function POST(req: NextRequest, { params }: Params) {
  const { teamId, id } = await params
  const session = await getIronSession<SessionData>(await cookies(), sessionOptions)
  if (!session.userId) return NextResponse.json({ error: 'Unauthorized' }, { status: 401 })

  const [member] = await sql`SELECT role FROM team_members WHERE team_id = ${teamId}::uuid AND user_id = ${session.userId}::uuid`
  if (!member || member.role !== 'admin') return NextResponse.json({ error: 'Forbidden' }, { status: 403 })

  const [sessionRow] = await sql`SELECT session_id FROM sessions WHERE session_id = ${id} AND team_id = ${teamId}::uuid`
  if (!sessionRow) return NextResponse.json({ error: 'Not found' }, { status: 404 })

  const { content } = await req.json() as { content: string }
  if (!content?.trim()) return NextResponse.json({ error: 'content required' }, { status: 400 })

  await sql`INSERT INTO notes (session_id, content, source) VALUES (${id}, ${content.trim()}, 'web')`
  await sql`UPDATE sessions SET updated_at = NOW() WHERE session_id = ${id}`

  return NextResponse.json({ ok: true })
}
