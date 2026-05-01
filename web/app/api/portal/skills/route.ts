export const dynamic = 'force-dynamic'

import { NextRequest, NextResponse } from 'next/server'
import { getIronSession } from 'iron-session'
import { sessionOptions, SessionData } from '@/lib/auth'
import sql from '@/lib/db'

export async function GET(req: NextRequest) {
  const res = NextResponse.next()
  const session = await getIronSession<SessionData>(req, res, sessionOptions)
  if (!session.userId) return NextResponse.json({ error: 'Unauthorized' }, { status: 401 })

  const { searchParams } = req.nextUrl
  const search = searchParams.get('search') ?? ''
  const category = searchParams.get('category') ?? ''

  const rows = await sql`
    SELECT slug, name, summary, category, tags, source, updated_at
    FROM skills
    WHERE is_global = true
      AND (${search} = '' OR name ILIKE ${'%' + search + '%'} OR summary ILIKE ${'%' + search + '%'} OR slug ILIKE ${'%' + search + '%'})
      AND (${category} = '' OR category = ${category})
    ORDER BY name ASC
  `

  return NextResponse.json({ skills: rows })
}
