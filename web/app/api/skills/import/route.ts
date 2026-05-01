export const dynamic = 'force-dynamic'

import { NextRequest, NextResponse } from 'next/server'
import sql from '@/lib/db'

// ---------------------------------------------------------------------------
// Markdown parser — detects Claude / Copilot / plain format
// ---------------------------------------------------------------------------

type ParsedSkill = {
  slug: string
  name: string
  summary: string
  content: string
  category: string | null
  tags: string[]
  format: 'claude' | 'copilot' | 'plain'
  conflict: boolean
}

function slugify(str: string): string {
  return str
    .toLowerCase()
    .replace(/[^a-z0-9]+/g, '-')
    .replace(/^-+|-+$/g, '')
    .slice(0, 100)
}

function parseFrontmatter(raw: string): { meta: Record<string, string>; body: string } {
  const match = raw.match(/^---\r?\n([\s\S]*?)\r?\n---\r?\n?([\s\S]*)$/)
  if (!match) return { meta: {}, body: raw }
  const meta: Record<string, string> = {}
  for (const line of match[1].split('\n')) {
    const idx = line.indexOf(':')
    if (idx > 0) {
      const key = line.slice(0, idx).trim()
      const val = line.slice(idx + 1).trim().replace(/^["']|["']$/g, '')
      meta[key] = val
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
  const tags: string[] = []

  if (meta.name && meta.description) {
    format = 'claude'
    name = meta.name
    summary = meta.description
    if (meta.type) category = meta.type
  } else if ('applyTo' in meta || filename.endsWith('.instructions.md')) {
    format = 'copilot'
    name = baseName.replace(/-/g, ' ').replace(/\b\w/g, c => c.toUpperCase())
    const firstLine = body.split('\n').find(l => l.trim())
    summary = firstLine?.replace(/^#+\s*/, '').slice(0, 200) ?? ''
  } else {
    const firstLine = body.split('\n').find(l => l.trim())
    summary = firstLine?.replace(/^#+\s*/, '').slice(0, 200) ?? ''
  }

  const slug = slugify(name || baseName)

  return { slug, name, summary, content: body, category, tags, format, conflict: false }
}

// ---------------------------------------------------------------------------
// POST /api/skills/import
// Body: { action: 'preview' | 'confirm', files: [{name, content}], selected?: string[] }
// ---------------------------------------------------------------------------

export async function POST(req: NextRequest) {
  const body = await req.json()
  const { action, files, selected } = body as {
    action: 'preview' | 'confirm'
    files: { name: string; content: string }[]
    selected?: string[]
  }

  if (!files?.length) return NextResponse.json({ error: 'No files provided' }, { status: 400 })

  const parsed: ParsedSkill[] = files.map(f => parseFile(f.name, f.content))

  // Check for slug conflicts
  const slugs = parsed.map(p => p.slug)
  const existing = slugs.length
    ? await sql`SELECT slug FROM skills WHERE slug = ANY(${slugs})`
    : []
  const existingSlugs = new Set(existing.map((r: { slug: string }) => r.slug))
  parsed.forEach(p => { p.conflict = existingSlugs.has(p.slug) })

  if (action === 'preview') {
    return NextResponse.json({ skills: parsed })
  }

  if (action === 'confirm') {
    const toImport = selected
      ? parsed.filter(p => selected.includes(p.slug))
      : parsed

    let created = 0, updated = 0
    for (const s of toImport) {
      const [ex] = await sql`SELECT content FROM skills WHERE slug = ${s.slug}`
      if (ex && ex.content !== s.content) {
        await sql`INSERT INTO skill_versions (slug, content) VALUES (${s.slug}, ${ex.content})`
      }
      await sql`
        INSERT INTO skills (slug, name, summary, content, source, category, tags, is_global)
        VALUES (${s.slug}, ${s.name}, ${s.summary}, ${s.content}, ${'import'},
                ${s.category}, ${s.tags}, ${true})
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
