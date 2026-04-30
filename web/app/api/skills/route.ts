export const dynamic = 'force-dynamic'

import { NextRequest, NextResponse } from 'next/server'
import sql from '@/lib/db'

export async function GET(req: NextRequest) {
  const { searchParams } = req.nextUrl
  const search = searchParams.get('search') ?? ''
  const category = searchParams.get('category') ?? ''
  const source = searchParams.get('source') ?? ''
  const tag = searchParams.get('tag') ?? ''
  const page = Math.max(1, parseInt(searchParams.get('page') ?? '1'))
  const limit = 20
  const offset = (page - 1) * limit

  const rows = await sql`
    SELECT
      sk.slug, sk.name, sk.summary, sk.category, sk.tags, sk.source, sk.updated_at,
      COUNT(ss.session_id)::int AS session_count
    FROM skills sk
    LEFT JOIN session_skills ss ON ss.skill_slug = sk.slug
    WHERE
      (${search} = '' OR sk.name ILIKE ${'%' + search + '%'} OR sk.summary ILIKE ${'%' + search + '%'} OR sk.slug ILIKE ${'%' + search + '%'})
      AND (${category} = '' OR sk.category = ${category})
      AND (${source} = '' OR sk.source = ${source})
      AND (${tag} = '' OR ${tag} = ANY(sk.tags))
    GROUP BY sk.slug
    ORDER BY sk.name ASC
    LIMIT ${limit} OFFSET ${offset}
  `

  const [total] = await sql`
    SELECT COUNT(*)::int AS count FROM skills
    WHERE
      (${search} = '' OR name ILIKE ${'%' + search + '%'} OR summary ILIKE ${'%' + search + '%'} OR slug ILIKE ${'%' + search + '%'})
      AND (${category} = '' OR category = ${category})
      AND (${source} = '' OR source = ${source})
      AND (${tag} = '' OR ${tag} = ANY(tags))
  `

  return NextResponse.json({ rows, total: total.count, page, limit })
}

export async function POST(req: NextRequest) {
  const { slug, name, content, summary, source, category, tags } = await req.json()

  if (!slug || !name || !content) {
    return NextResponse.json({ error: 'slug, name, and content required' }, { status: 400 })
  }

  const [existing] = await sql`SELECT content FROM skills WHERE slug = ${slug}`

  if (existing && existing.content !== content) {
    await sql`INSERT INTO skill_versions (slug, content) VALUES (${slug}, ${existing.content})`
  }

  const [row] = await sql`
    INSERT INTO skills (slug, name, summary, content, source, category, tags)
    VALUES (${slug}, ${name}, ${summary ?? ''}, ${content}, ${source ?? 'manual'}, ${category ?? null}, ${tags ?? []})
    ON CONFLICT (slug) DO UPDATE SET
      name     = EXCLUDED.name,
      summary  = EXCLUDED.summary,
      content  = EXCLUDED.content,
      source   = EXCLUDED.source,
      category = EXCLUDED.category,
      tags     = EXCLUDED.tags
    RETURNING slug, name, summary, source, category, tags, updated_at
  `

  return NextResponse.json(row, { status: 201 })
}
