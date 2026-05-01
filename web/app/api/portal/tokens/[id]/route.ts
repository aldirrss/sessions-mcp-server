export const dynamic = 'force-dynamic'

import { NextRequest, NextResponse } from 'next/server'
import { getIronSession } from 'iron-session'
import { sessionOptions, SessionData } from '@/lib/auth'
import sql from '@/lib/db'

type Params = { params: Promise<{ id: string }> }

export async function DELETE(req: NextRequest, { params }: Params) {
  const { id } = await params
  const res = NextResponse.next()
  const session = await getIronSession<SessionData>(req, res, sessionOptions)
  if (!session.userId) return NextResponse.json({ error: 'Unauthorized' }, { status: 401 })

  const result = await sql`
    UPDATE user_tokens SET revoked = true
    WHERE id = ${id} AND user_id = ${session.userId} AND revoked = false
  `
  if (result.count === 0) return NextResponse.json({ error: 'Token not found' }, { status: 404 })
  return NextResponse.json({ ok: true })
}
