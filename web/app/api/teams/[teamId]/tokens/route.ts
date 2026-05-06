export const dynamic = 'force-dynamic'

import { NextRequest, NextResponse } from 'next/server'
import { cookies } from 'next/headers'
import { getIronSession } from 'iron-session'
import { sessionOptions } from '@/lib/auth'
import type { SessionData } from '@/lib/auth'
import sql from '@/lib/db'
import { createHash, randomBytes } from 'crypto'
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
    SELECT id, name, revoked, created_at FROM team_tokens
    WHERE team_id = ${teamId}::uuid ORDER BY created_at DESC
  `
  return NextResponse.json(rows)
}

const CreateTokenSchema = z.object({ name: z.string().min(1).max(100) })

export async function POST(req: NextRequest, { params }: Params) {
  const { teamId } = await params
  const session = await getIronSession<SessionData>(await cookies(), sessionOptions)
  if (!session.userId) return NextResponse.json({ error: 'Unauthorized' }, { status: 401 })
  if (!await requireTeamAdmin(teamId, session.userId)) return NextResponse.json({ error: 'Forbidden' }, { status: 403 })

  const body = await req.json()
  const parsed = CreateTokenSchema.safeParse(body)
  if (!parsed.success) return NextResponse.json({ error: parsed.error.issues[0]?.message ?? 'Invalid' }, { status: 400 })

  const rawToken = randomBytes(32).toString('hex')
  const tokenHash = createHash('sha256').update(rawToken).digest('hex')
  const [row] = await sql`
    INSERT INTO team_tokens (team_id, token_hash, name, created_by)
    VALUES (${teamId}::uuid, ${tokenHash}, ${parsed.data.name}, ${session.userId}::uuid)
    RETURNING id, name, created_at
  `
  return NextResponse.json({ ...row, token: rawToken }, { status: 201 })
}
