export const dynamic = 'force-dynamic'

import { NextRequest, NextResponse } from 'next/server'
import sql from '@/lib/db'

export async function GET(req: NextRequest) {
  const prefix = req.nextUrl.searchParams.get('prefix') ?? ''

  const rows = prefix
    ? await sql`SELECT * FROM config WHERE key LIKE ${prefix + '%'} ORDER BY key`
    : await sql`SELECT * FROM config ORDER BY key`

  return NextResponse.json({ rows, total: rows.length })
}

export async function POST(req: NextRequest) {
  const body = await req.json()
  const { key, value, description = '' } = body

  if (!key || value === undefined) {
    return NextResponse.json({ error: 'key and value are required' }, { status: 400 })
  }

  const [row] = await sql`
    INSERT INTO config (key, value, description)
    VALUES (${key}, ${value}, ${description})
    ON CONFLICT (key) DO UPDATE
      SET value = EXCLUDED.value,
          description = CASE
            WHEN EXCLUDED.description = '' THEN config.description
            ELSE EXCLUDED.description
          END
    RETURNING *
  `

  return NextResponse.json(row, { status: 201 })
}
