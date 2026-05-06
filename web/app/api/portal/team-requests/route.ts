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

  const [requests, adminTeamRows] = await Promise.all([
    sql`
      SELECT tr.id, tr.team_name, tr.reason, tr.status, tr.created_at, tr.reviewed_at,
             t.id AS team_id
      FROM team_requests tr
      LEFT JOIN teams t ON t.name = tr.team_name
      WHERE tr.requested_by = ${session.userId}::uuid
      ORDER BY tr.created_at DESC
    `,
    sql`
      SELECT t.id, t.name
      FROM team_members tm
      JOIN teams t ON t.id = tm.team_id
      WHERE tm.user_id = ${session.userId}::uuid AND tm.role = 'admin'
      LIMIT 1
    `,
  ])

  const adminTeam = adminTeamRows[0] ?? null
  return NextResponse.json({ requests, admin_team: adminTeam })
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

  const [adminCheck, pendingCheck] = await Promise.all([
    sql`SELECT 1 FROM team_members WHERE user_id = ${session.userId}::uuid AND role = 'admin' LIMIT 1`,
    sql`SELECT id FROM team_requests WHERE requested_by = ${session.userId}::uuid AND status = 'pending'`,
  ])

  if (adminCheck.length > 0) {
    return NextResponse.json({ error: 'You are already an admin of a team' }, { status: 409 })
  }
  if (pendingCheck.length > 0) {
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
