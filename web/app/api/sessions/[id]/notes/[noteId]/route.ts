export const dynamic = 'force-dynamic'

import { NextRequest, NextResponse } from 'next/server'
import sql from '@/lib/db'

type Params = { params: Promise<{ id: string; noteId: string }> }

export async function PATCH(req: NextRequest, { params }: Params) {
  const { id, noteId } = await params
  const body = await req.json()

  const [row] = await sql`
    UPDATE notes SET pinned = ${body.pinned ?? false}
    WHERE id = ${parseInt(noteId)} AND session_id = ${id}
    RETURNING id, content, source, pinned, created_at
  `
  if (!row) return NextResponse.json({ error: 'Note not found' }, { status: 404 })
  return NextResponse.json(row)
}

export async function DELETE(_req: NextRequest, { params }: Params) {
  const { id, noteId } = await params
  const result = await sql`DELETE FROM notes WHERE id = ${parseInt(noteId)} AND session_id = ${id}`
  if (result.count === 0) return NextResponse.json({ error: 'Note not found' }, { status: 404 })
  await sql`UPDATE sessions SET updated_at = NOW() WHERE session_id = ${id}`
  return NextResponse.json({ ok: true })
}
