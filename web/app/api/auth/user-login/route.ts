export const dynamic = 'force-dynamic'

import { NextRequest, NextResponse } from 'next/server'
import { getIronSession } from 'iron-session'
import { sessionOptions, SessionData } from '@/lib/auth'
import sql from '@/lib/db'
import bcrypt from 'bcryptjs'

export async function POST(req: NextRequest) {
  const { username, password } = await req.json()
  if (!username || !password) {
    return NextResponse.json({ error: 'username and password are required' }, { status: 400 })
  }

  const val = username.trim().toLowerCase()
  const [row] = await sql`
    SELECT id, username, email, role, password_hash, is_active
    FROM users
    WHERE (username = ${val} OR email = ${val})
    LIMIT 1
  `

  if (!row || !row.is_active) {
    return NextResponse.json({ error: 'Invalid credentials' }, { status: 401 })
  }

  const valid = await bcrypt.compare(password, row.password_hash as string)
  if (!valid) {
    return NextResponse.json({ error: 'Invalid credentials' }, { status: 401 })
  }

  const res = NextResponse.json({ ok: true })
  const session = await getIronSession<SessionData>(req, res, sessionOptions)
  session.userId = String(row.id)
  session.username = String(row.username)
  session.email = String(row.email)
  session.role = row.role as 'user' | 'admin'
  await session.save()

  return res
}
