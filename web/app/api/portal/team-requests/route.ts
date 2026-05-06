export const dynamic = 'force-dynamic'

import { NextRequest, NextResponse } from 'next/server'
import { cookies } from 'next/headers'
import { getIronSession } from 'iron-session'
import { sessionOptions } from '@/lib/auth'
import type { SessionData } from '@/lib/auth'
import sql from '@/lib/db'
import { z } from 'zod'
import { sendAdminTeamRequest } from '@/lib/email'

const CreateTeamRequestSchema = z.object({
  team_name: z.string().min(2).max(80).regex(/^[a-z0-9_-]+$/, 'lowercase letters, numbers, _ and - only'),
  reason: z.string().max(500).optional(),
})

export async function GET() {
  const session = await getIronSession<SessionData>(await cookies(), sessionOptions)
  if (!session.userId) return NextResponse.json({ error: 'Unauthorized' }, { status: 401 })

  const rows = await sql`
    SELECT tr.id, tr.team_name, tr.reason, tr.status, tr.created_at, tr.reviewed_at,
           t.id AS team_id
    FROM team_requests tr
    LEFT JOIN teams t ON t.name = tr.team_name
    WHERE tr.requested_by = ${session.userId}::uuid
    ORDER BY tr.created_at DESC
  `
  return NextResponse.json(rows)
}

export async function POST(req: NextRequest) {
  const session = await getIronSession<SessionData>(await cookies(), sessionOptions)
  if (!session.userId) return NextResponse.json({ error: 'Unauthorized' }, { status: 401 })

  const body = await req.json()
  const parsed = CreateTeamRequestSchema.safeParse(body)
  if (!parsed.success) {
    return NextResponse.json({ error: parsed.error.issues[0]?.message ?? 'Invalid request' }, { status: 400 })
  }

  const { team_name, reason = '' } = parsed.data

  const existing = await sql`SELECT id FROM team_requests WHERE requested_by = ${session.userId}::uuid AND status = 'pending'`
  if (existing.length > 0) {
    return NextResponse.json({ error: 'You already have a pending team request' }, { status: 409 })
  }

  const [user] = await sql`SELECT username, email FROM users WHERE id = ${session.userId}::uuid`
  const [row] = await sql`
    INSERT INTO team_requests (requested_by, team_name, reason)
    VALUES (${session.userId}::uuid, ${team_name}, ${reason})
    RETURNING id, team_name, reason, status, created_at
  `

  sendAdminTeamRequest({
    requesterUsername: user.username,
    requesterEmail: user.email,
    teamName: team_name,
    reason,
    requestId: row.id,
  }).catch(() => {})

  return NextResponse.json(row, { status: 201 })
}
