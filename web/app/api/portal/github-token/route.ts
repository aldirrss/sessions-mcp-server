import { NextRequest, NextResponse } from 'next/server'
import { getIronSession } from 'iron-session'
import { sessionOptions, SessionData } from '@/lib/auth'
import sql from '@/lib/db'

export async function GET(req: NextRequest) {
  const res = NextResponse.next()
  const session = await getIronSession<SessionData>(req, res, sessionOptions)
  if (!session.userId) return NextResponse.json({ error: 'Unauthorized' }, { status: 401 })

  const row = await sql`
    SELECT github_token IS NOT NULL AS has_token FROM users WHERE id = ${session.userId}
  `
  return NextResponse.json({ has_token: row[0]?.has_token ?? false })
}

export async function PUT(req: NextRequest) {
  const res = NextResponse.next()
  const session = await getIronSession<SessionData>(req, res, sessionOptions)
  if (!session.userId) return NextResponse.json({ error: 'Unauthorized' }, { status: 401 })

  const { token } = await req.json()
  if (!token || typeof token !== 'string' || token.trim().length < 10) {
    return NextResponse.json({ error: 'Invalid token' }, { status: 400 })
  }

  await sql`UPDATE users SET github_token = ${token.trim()} WHERE id = ${session.userId}`
  return NextResponse.json({ ok: true })
}

export async function DELETE(req: NextRequest) {
  const res = NextResponse.next()
  const session = await getIronSession<SessionData>(req, res, sessionOptions)
  if (!session.userId) return NextResponse.json({ error: 'Unauthorized' }, { status: 401 })

  await sql`UPDATE users SET github_token = NULL WHERE id = ${session.userId}`
  return NextResponse.json({ ok: true })
}
