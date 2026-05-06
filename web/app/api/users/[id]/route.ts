export const dynamic = 'force-dynamic'

import { NextRequest, NextResponse } from 'next/server'
import sql from '@/lib/db'
import { requireAdmin } from '@/lib/require-session'
import { PatchUserSchema } from '@/lib/schemas'

type Params = { params: Promise<{ id: string }> }

export async function PATCH(req: NextRequest, { params }: Params) {
  const guard = await requireAdmin()
  if ('error' in guard) return guard.error

  const body = await req.json()
  const parsed = PatchUserSchema.safeParse(body)
  if (!parsed.success) {
    return NextResponse.json(
      { error: parsed.error.issues[0]?.message ?? 'Invalid request' },
      { status: 400 }
    )
  }

  const { id } = await params
  const hasRole = parsed.data.role !== undefined
  const hasActive = parsed.data.is_active !== undefined

  const [row] = await sql`
    UPDATE users SET
      role      = CASE WHEN ${hasRole}   THEN ${parsed.data.role ?? 'user'}    ELSE role      END,
      is_active = CASE WHEN ${hasActive} THEN ${parsed.data.is_active ?? true} ELSE is_active END
    WHERE id = ${id}
    RETURNING id, username, email, role, is_active
  `
  if (!row) return NextResponse.json({ error: 'Not found' }, { status: 404 })
  return NextResponse.json(row)
}
