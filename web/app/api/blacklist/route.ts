export const dynamic = 'force-dynamic'

import { NextRequest, NextResponse } from 'next/server'
import sql from '@/lib/db'
import { requireAdmin } from '@/lib/require-session'
import { BlacklistEmailSchema } from '@/lib/schemas'
import { sendUserEmailBlacklisted } from '@/lib/email'

export async function GET() {
  const guard = await requireAdmin()
  if ('error' in guard) return guard.error

  const rows = await sql`
    SELECT id, email, reason, created_at
    FROM email_blacklist
    ORDER BY created_at DESC
  `
  return NextResponse.json(rows)
}

export async function POST(req: NextRequest) {
  const guard = await requireAdmin()
  if ('error' in guard) return guard.error

  const body = await req.json()
  const parsed = BlacklistEmailSchema.safeParse(body)
  if (!parsed.success) {
    return NextResponse.json(
      { error: parsed.error.issues[0]?.message ?? 'Invalid request' },
      { status: 400 }
    )
  }

  const { email, reason = '' } = parsed.data
  const [row] = await sql`
    INSERT INTO email_blacklist (email, reason)
    VALUES (${email.toLowerCase()}, ${reason})
    ON CONFLICT (email) DO NOTHING
    RETURNING id, email, reason, created_at
  `
  if (!row) {
    return NextResponse.json({ error: 'Email already blacklisted' }, { status: 409 })
  }
  sendUserEmailBlacklisted({ toEmail: row.email, reason: row.reason || undefined }).catch(() => {})
  return NextResponse.json(row, { status: 201 })
}
