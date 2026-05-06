export const dynamic = 'force-dynamic'

import { NextRequest, NextResponse } from 'next/server'
import { createHash, randomBytes } from 'crypto'
import { getIronSession } from 'iron-session'
import { sessionOptions, SessionData } from '@/lib/auth'
import sql from '@/lib/db'
import { CreateTokenSchema } from '@/lib/schemas'

async function getUser(req: NextRequest, res: NextResponse) {
  const session = await getIronSession<SessionData>(req, res, sessionOptions)
  if (!session.userId) return null
  return session
}

export async function GET(req: NextRequest) {
  const res = NextResponse.next()
  const session = await getUser(req, res)
  if (!session) return NextResponse.json({ error: 'Unauthorized' }, { status: 401 })

  const userId = session.userId!
  const tokens = await sql`
    SELECT id, name, last_used_at, expires_at, revoked, created_at
    FROM user_tokens
    WHERE user_id = ${userId}
    ORDER BY created_at DESC
  `
  return NextResponse.json({ tokens })
}

export async function POST(req: NextRequest) {
  const res = NextResponse.next()
  const session = await getUser(req, res)
  if (!session) return NextResponse.json({ error: 'Unauthorized' }, { status: 401 })

  const body = await req.json()
  const parsed = CreateTokenSchema.safeParse(body)
  if (!parsed.success) {
    return NextResponse.json(
      { error: parsed.error.issues[0]?.message ?? 'Invalid request' },
      { status: 400 }
    )
  }
  const { name, expires_days } = parsed.data

  const rawToken = randomBytes(32).toString('hex')
  const tokenHash = createHash('sha256').update(rawToken).digest('hex')

  const expiresAt = expires_days
    ? new Date(Date.now() + expires_days * 86400 * 1000).toISOString()
    : null

  const userId2 = session.userId!
  const [row] = await sql`
    INSERT INTO user_tokens (user_id, token_hash, name, expires_at)
    VALUES (${userId2}, ${tokenHash}, ${name}, ${expiresAt})
    RETURNING id, name, expires_at, created_at
  `

  return NextResponse.json({ token: rawToken, record: row })
}
