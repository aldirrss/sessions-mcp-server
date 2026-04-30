export const dynamic = 'force-dynamic'

import { NextRequest, NextResponse } from 'next/server'
import sql from '@/lib/db'

type Params = { params: Promise<{ slug: string }> }

export async function GET(_req: NextRequest, { params }: Params) {
  const { slug } = await params

  const [skill] = await sql`SELECT * FROM skills WHERE slug = ${slug}`
  if (!skill) return NextResponse.json({ error: 'Not found' }, { status: 404 })

  const versions = await sql`
    SELECT id, slug, changed_at FROM skill_versions
    WHERE slug = ${slug} ORDER BY changed_at DESC
  `

  const sessions = await sql`
    SELECT ss.session_id, ss.used_at, s.title, s.source
    FROM session_skills ss
    JOIN sessions s ON s.session_id = ss.session_id
    WHERE ss.skill_slug = ${slug}
    ORDER BY ss.used_at DESC
  `

  return NextResponse.json({ ...skill, versions, sessions })
}

export async function PATCH(req: NextRequest, { params }: Params) {
  const { slug } = await params
  const body = await req.json()

  const [existing] = await sql`SELECT content FROM skills WHERE slug = ${slug}`
  if (!existing) return NextResponse.json({ error: 'Not found' }, { status: 404 })

  if (body.content && body.content !== existing.content) {
    await sql`INSERT INTO skill_versions (slug, content) VALUES (${slug}, ${existing.content})`
  }

  const [updated] = await sql`
    UPDATE skills SET
      name     = COALESCE(${body.name ?? null}, name),
      summary  = COALESCE(${body.summary ?? null}, summary),
      content  = COALESCE(${body.content ?? null}, content),
      source   = COALESCE(${body.source ?? null}, source),
      category = COALESCE(${body.category ?? null}, category),
      tags     = COALESCE(${body.tags ?? null}, tags)
    WHERE slug = ${slug}
    RETURNING slug, name, summary, source, category, tags, updated_at
  `

  return NextResponse.json(updated)
}

export async function DELETE(_req: NextRequest, { params }: Params) {
  const { slug } = await params
  const result = await sql`DELETE FROM skills WHERE slug = ${slug}`
  if (result.count === 0) return NextResponse.json({ error: 'Not found' }, { status: 404 })
  return NextResponse.json({ ok: true })
}
