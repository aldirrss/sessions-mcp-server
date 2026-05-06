export const dynamic = 'force-dynamic'

import { NextResponse } from 'next/server'
import sql from '@/lib/db'
import { requireAdmin } from '@/lib/require-session'

export async function GET() {
  const guard = await requireAdmin()
  if ('error' in guard) return guard.error

  const users = await sql`
    SELECT u.id, u.username, u.email, u.role, u.is_active, u.created_at,
           COUNT(t.id) FILTER (WHERE t.revoked = false) AS active_tokens
    FROM users u
    LEFT JOIN user_tokens t ON t.user_id = u.id
    GROUP BY u.id
    ORDER BY u.created_at DESC
  `
  return NextResponse.json({ users })
}
