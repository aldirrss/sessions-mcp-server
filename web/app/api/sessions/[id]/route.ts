import { NextRequest, NextResponse } from 'next/server'
import sql from '@/lib/db'

type Params = { params: Promise<{ id: string }> }

export async function GET(_req: NextRequest, { params }: Params) {
  const { id } = await params

  const [session] = await sql`
    SELECT * FROM sessions WHERE session_id = ${id}
  `
  if (!session) return NextResponse.json({ error: 'Not found' }, { status: 404 })

  const notes = await sql`
    SELECT id, content, source, created_at
    FROM notes WHERE session_id = ${id}
    ORDER BY created_at ASC
  `

  const skills = await sql`
    SELECT ss.skill_slug AS slug, ss.used_at, sk.name, sk.category
    FROM session_skills ss
    JOIN skills sk ON sk.slug = ss.skill_slug
    WHERE ss.session_id = ${id}
    ORDER BY ss.used_at ASC
  `

  return NextResponse.json({ ...session, notes, skills })
}

export async function PATCH(req: NextRequest, { params }: Params) {
  const { id } = await params
  const body = await req.json()

  const [updated] = await sql`
    UPDATE sessions SET
      title   = COALESCE(${body.title ?? null}, title),
      context = COALESCE(${body.context ?? null}, context),
      source  = COALESCE(${body.source ?? null}, source),
      tags    = COALESCE(${body.tags ?? null}, tags)
    WHERE session_id = ${id}
    RETURNING session_id, title, source, tags, updated_at
  `

  if (!updated) return NextResponse.json({ error: 'Not found' }, { status: 404 })
  return NextResponse.json(updated)
}

export async function DELETE(_req: NextRequest, { params }: Params) {
  const { id } = await params
  const result = await sql`DELETE FROM sessions WHERE session_id = ${id}`
  if (result.count === 0) return NextResponse.json({ error: 'Not found' }, { status: 404 })
  return NextResponse.json({ ok: true })
}
