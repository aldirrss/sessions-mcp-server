export const dynamic = 'force-dynamic'

import { NextRequest, NextResponse } from 'next/server'
import { createHash, randomBytes } from 'crypto'
import sql from '@/lib/db'
import bcrypt from 'bcryptjs'

export async function POST(req: NextRequest) {
  const { username, email, password } = await req.json()

  if (!username || !email || !password) {
    return NextResponse.json({ error: 'username, email and password are required' }, { status: 400 })
  }
  if (password.length < 8) {
    return NextResponse.json({ error: 'Password must be at least 8 characters' }, { status: 400 })
  }

  const usernameClean = username.trim().toLowerCase()
  const emailClean = email.trim().toLowerCase()

  const passwordHash = await bcrypt.hash(password, 12)

  let user: { id: string; username: string } | null = null
  try {
    const [row] = await sql`
      INSERT INTO users (username, email, password_hash)
      VALUES (${usernameClean}, ${emailClean}, ${passwordHash})
      RETURNING id, username
    `
    user = row as { id: string; username: string }
  } catch (err: unknown) {
    const msg = String(err)
    if (msg.includes('username') && msg.includes('unique')) {
      return NextResponse.json({ error: `Username '${usernameClean}' is already taken` }, { status: 409 })
    }
    if (msg.includes('email') && msg.includes('unique')) {
      return NextResponse.json({ error: `Email '${emailClean}' is already registered` }, { status: 409 })
    }
    throw err
  }

  // Generate default token shown once
  const rawToken = randomBytes(32).toString('hex')
  const tokenHash = createHash('sha256').update(rawToken).digest('hex')

  await sql`
    INSERT INTO user_tokens (user_id, token_hash, name)
    VALUES (${user.id}, ${tokenHash}, ${'Default'})
  `

  return NextResponse.json({ username: user.username, token: rawToken })
}
