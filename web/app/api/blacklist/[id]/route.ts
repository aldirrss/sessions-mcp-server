export const dynamic = 'force-dynamic'

import { NextRequest, NextResponse } from 'next/server'
import sql from '@/lib/db'
import { requireAdmin } from '@/lib/require-session'

type Params = { params: Promise<{ id: string }> }

export async function DELETE(_req: NextRequest, { params }: Params) {
  const guard = await requireAdmin()
  if ('error' in guard) return guard.error

  const { id } = await params
  const [row] = await sql`
    DELETE FROM email_blacklist WHERE id = ${id} RETURNING id
  `
  if (!row) return NextResponse.json({ error: 'Not found' }, { status: 404 })
  return NextResponse.json({ ok: true })
}
