export const dynamic = 'force-dynamic'

import { NextRequest, NextResponse } from 'next/server'
import sql from '@/lib/db'
import { requireAdmin } from '@/lib/require-session'
import { sendUserTeamApproved, sendUserTeamRejected } from '@/lib/email'
import { createHash, randomBytes } from 'crypto'

type Params = { params: Promise<{ id: string }> }

export async function PATCH(req: NextRequest, { params }: Params) {
  const guard = await requireAdmin()
  if ('error' in guard) return guard.error

  const { id } = await params
  const { action } = await req.json() as { action: 'approve' | 'reject' }
  if (action !== 'approve' && action !== 'reject') {
    return NextResponse.json({ error: 'action must be approve or reject' }, { status: 400 })
  }

  const [request] = await sql`SELECT * FROM team_requests WHERE id = ${id}::uuid AND status = 'pending'`
  if (!request) return NextResponse.json({ error: 'Request not found or already reviewed' }, { status: 404 })

  if (action === 'reject') {
    await sql`UPDATE team_requests SET status = 'rejected', reviewed_at = NOW() WHERE id = ${id}::uuid`
    const [user] = await sql`SELECT username, email FROM users WHERE id = ${request.requested_by}::uuid`
    if (user) {
      sendUserTeamRejected({ toEmail: user.email, username: user.username, teamName: request.team_name }).catch(() => {})
    }
    return NextResponse.json({ ok: true, status: 'rejected' })
  }

  // approve — create team + add requester as admin + generate first team token
  const [existing] = await sql`SELECT id FROM teams WHERE name = ${request.team_name}`
  if (existing) {
    return NextResponse.json({ error: 'Team name already exists' }, { status: 409 })
  }

  const [team] = await sql`
    INSERT INTO teams (name, created_by) VALUES (${request.team_name}, ${request.requested_by}::uuid)
    RETURNING id, name
  `
  await sql`
    INSERT INTO team_members (team_id, user_id, role)
    VALUES (${team.id}::uuid, ${request.requested_by}::uuid, 'admin')
  `

  const rawToken = randomBytes(32).toString('hex')
  const tokenHash = createHash('sha256').update(rawToken).digest('hex')
  await sql`
    INSERT INTO team_tokens (team_id, token_hash, name, created_by)
    VALUES (${team.id}::uuid, ${tokenHash}, ${'Default'}, ${request.requested_by}::uuid)
  `

  await sql`UPDATE team_requests SET status = 'approved', reviewed_at = NOW() WHERE id = ${id}::uuid`

  const [user] = await sql`SELECT username, email FROM users WHERE id = ${request.requested_by}::uuid`
  sendUserTeamApproved({ toEmail: user.email, username: user.username, teamName: team.name }).catch(() => {})

  return NextResponse.json({ ok: true, status: 'approved', team_id: team.id, token: rawToken })
}
