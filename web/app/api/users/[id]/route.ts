export const dynamic = 'force-dynamic'

import { NextRequest, NextResponse } from 'next/server'
import sql from '@/lib/db'

type Params = { params: Promise<{ id: string }> }

export async function PATCH(req: NextRequest, { params }: Params) {
  const { id } = await params
  const body = await req.json()

  const hasRole = Object.hasOwn(body, 'role')
  const hasActive = Object.hasOwn(body, 'is_active')

  const [row] = await sql`
    UPDATE users SET
      role      = CASE WHEN ${hasRole}   THEN ${body.role ?? 'user'}  ELSE role      END,
      is_active = CASE WHEN ${hasActive} THEN ${body.is_active ?? true} ELSE is_active END
    WHERE id = ${id}
    RETURNING id, username, email, role, is_active
  `
  if (!row) return NextResponse.json({ error: 'Not found' }, { status: 404 })
  return NextResponse.json(row)
}
