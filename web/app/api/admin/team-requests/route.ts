export const dynamic = 'force-dynamic'

import { NextResponse } from 'next/server'
import sql from '@/lib/db'
import { requireAdmin } from '@/lib/require-session'

export async function GET() {
  const guard = await requireAdmin()
  if ('error' in guard) return guard.error

  const rows = await sql`
    SELECT tr.id, tr.team_name, tr.reason, tr.status, tr.created_at, tr.reviewed_at,
           u.username AS requester_username, u.email AS requester_email
    FROM team_requests tr
    JOIN users u ON u.id = tr.requested_by
    ORDER BY
      CASE tr.status WHEN 'pending' THEN 0 ELSE 1 END,
      tr.created_at DESC
  `
  return NextResponse.json(rows)
}
