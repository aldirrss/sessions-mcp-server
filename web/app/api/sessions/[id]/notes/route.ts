import { NextRequest, NextResponse } from 'next/server'
import sql from '@/lib/db'

type Params = { params: Promise<{ id: string }> }

export async function POST(req: NextRequest, { params }: Params) {
  const { id } = await params
  const { content, source } = await req.json()

  if (!content) return NextResponse.json({ error: 'content required' }, { status: 400 })

  const [exists] = await sql`SELECT 1 FROM sessions WHERE session_id = ${id}`
  if (!exists) return NextResponse.json({ error: 'Session not found' }, { status: 404 })

  const [note] = await sql`
    INSERT INTO notes (session_id, content, source)
    VALUES (${id}, ${content}, ${source ?? 'web'})
    RETURNING id, content, source, created_at
  `

  await sql`UPDATE sessions SET updated_at = NOW() WHERE session_id = ${id}`

  return NextResponse.json(note, { status: 201 })
}
