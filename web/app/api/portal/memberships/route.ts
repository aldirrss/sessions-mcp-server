export const dynamic = 'force-dynamic'

import { NextRequest, NextResponse } from 'next/server'
import { getIronSession } from 'iron-session'
import { sessionOptions, SessionData } from '@/lib/auth'
import sql from '@/lib/db'

export async function GET(req: NextRequest) {
  const res = NextResponse.next()
  const session = await getIronSession<SessionData>(req, res, sessionOptions)
  if (!session.userId) return NextResponse.json({ error: 'Unauthorized' }, { status: 401 })

  const rows = await sql`
    SELECT t.id, t.name, tm.role, tm.joined_at
    FROM team_members tm
    JOIN teams t ON t.id = tm.team_id
    WHERE tm.user_id = ${session.userId}::uuid
    ORDER BY tm.joined_at DESC
  `
  return NextResponse.json(rows)
}
