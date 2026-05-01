export const dynamic = 'force-dynamic'

import { NextRequest, NextResponse } from 'next/server'
import sql from '@/lib/db'

// ---------------------------------------------------------------------------
// Types
// ---------------------------------------------------------------------------

export type ParsedSkill = {
  slug: string
  name: string
  summary: string
  content: string
  category: string | null
  tags: string[]
  format: 'claude' | 'copilot' | 'plain'
  conflict: boolean
}

// ---------------------------------------------------------------------------
// Markdown parser
// ---------------------------------------------------------------------------

function slugify(str: string): string {
  return str.toLowerCase().replace(/[^a-z0-9]+/g, '-').replace(/^-+|-+$/g, '').slice(0, 100)
}

function parseFrontmatter(raw: string): { meta: Record<string, string>; body: string } {
  const match = raw.match(/^---\r?\n([\s\S]*?)\r?\n---\r?\n?([\s\S]*)$/)
  if (!match) return { meta: {}, body: raw }
  const meta: Record<string, string> = {}
  for (const line of match[1].split('\n')) {
    const idx = line.indexOf(':')
    if (idx > 0) {
      meta[line.slice(0, idx).trim()] = line.slice(idx + 1).trim().replace(/^["']|["']$/g, '')
    }
  }
  return { meta, body: match[2].trim() }
}

function parseFile(filename: string, raw: string): ParsedSkill {
  const { meta, body } = parseFrontmatter(raw.trim())
  const baseName = filename.replace(/\.md$/i, '').replace(/\.instructions$/i, '')
  let format: 'claude' | 'copilot' | 'plain' = 'plain'
  let name = baseName
  let summary = ''
  let category: string | null = null

  if (meta.name && meta.description) {
    format = 'claude'
    name = meta.name
    summary = meta.description
    if (meta.type) category = meta.type
  } else if ('applyTo' in meta || filename.endsWith('.instructions.md')) {
    format = 'copilot'
    name = baseName.replace(/-/g, ' ').replace(/\b\w/g, (c: string) => c.toUpperCase())
    const firstLine = body.split('\n').find((l: string) => l.trim())
    summary = firstLine?.replace(/^#+\s*/, '').slice(0, 200) ?? ''
  } else {
    const firstLine = body.split('\n').find((l: string) => l.trim())
    summary = firstLine?.replace(/^#+\s*/, '').slice(0, 200) ?? ''
  }

  return {
    slug: slugify(name || baseName),
    name, summary, content: body, category, tags: [], format, conflict: false,
  }
}

// ---------------------------------------------------------------------------
// POST /api/skills/import
//
// action='preview': { action, files: [{name,content}] }
//   → parses files, checks slug conflicts, returns ParsedSkill[]
//
// action='confirm': { action, skills: ParsedSkill[], selected: string[] }
//   → saves selected skills to DB (is_global=true, source='import')
// ---------------------------------------------------------------------------

export async function POST(req: NextRequest) {
  const body = await req.json() as Record<string, unknown>
  const action = body.action as string

  if (action === 'preview') {
    const files = body.files as { name: string; content: string }[]
    if (!files?.length) return NextResponse.json({ error: 'No files provided' }, { status: 400 })

    const parsed = files.map(f => parseFile(f.name, f.content))
    const slugs = parsed.map(p => p.slug)

    const existing: { slug: string }[] = slugs.length > 0
      ? (await sql`SELECT slug FROM skills WHERE slug = ANY(${slugs})`) as { slug: string }[]
      : []

    const existingSet = new Set(existing.map(r => r.slug))
    const result = parsed.map(p => ({ ...p, conflict: existingSet.has(p.slug) }))

    return NextResponse.json({ skills: result })
  }

  if (action === 'confirm') {
    const skills = body.skills as ParsedSkill[]
    const selected = body.selected as string[] | undefined

    if (!skills?.length) return NextResponse.json({ error: 'No skills provided' }, { status: 400 })

    const toImport = selected ? skills.filter(s => selected.includes(s.slug)) : skills

    let created = 0, updated = 0
    for (const s of toImport) {
      const existing = await sql`SELECT content FROM skills WHERE slug = ${s.slug}`
      const ex = existing[0] as { content: string } | undefined
      if (ex && ex.content !== s.content) {
        await sql`INSERT INTO skill_versions (slug, content) VALUES (${s.slug}, ${ex.content})`
      }
      await sql`
        INSERT INTO skills (slug, name, summary, content, source, category, tags, is_global)
        VALUES (
          ${s.slug}, ${s.name}, ${s.summary}, ${s.content}, ${'import'},
          ${s.category ?? null}, ${s.tags}, ${true}
        )
        ON CONFLICT (slug) DO UPDATE SET
          name      = EXCLUDED.name,
          summary   = EXCLUDED.summary,
          content   = EXCLUDED.content,
          source    = EXCLUDED.source,
          category  = EXCLUDED.category,
          tags      = EXCLUDED.tags,
          is_global = EXCLUDED.is_global
      `
      ex ? updated++ : created++
    }
    return NextResponse.json({ created, updated, total: toImport.length })
  }

  return NextResponse.json({ error: 'Invalid action' }, { status: 400 })
}
