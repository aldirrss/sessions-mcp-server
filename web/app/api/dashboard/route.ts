export const dynamic = 'force-dynamic'

import { NextResponse } from 'next/server'
import sql from '@/lib/db'

export async function GET() {
  const [stats, topSkills, recentSessions] = await Promise.all([
    sql`
      SELECT
        COUNT(DISTINCT s.session_id)::int AS total_sessions,
        COUNT(n.id)::int                  AS total_notes,
        COUNT(DISTINCT sk.slug)::int      AS total_skills
      FROM sessions s
      LEFT JOIN notes n  ON n.session_id = s.session_id
      CROSS JOIN (SELECT COUNT(*) FROM skills) sk(slug)
    `,
    sql`
      SELECT
        sk.slug, sk.name, sk.category,
        COUNT(ss.session_id)::int AS session_count,
        MAX(ss.used_at) AS last_used_at
      FROM skills sk
      LEFT JOIN session_skills ss ON ss.skill_slug = sk.slug
      GROUP BY sk.slug, sk.name, sk.category
      ORDER BY session_count DESC, sk.name ASC
      LIMIT 5
    `,
    sql`
      SELECT
        s.session_id, s.title, s.source, s.tags, s.updated_at,
        COUNT(n.id)::int AS notes_count
      FROM sessions s
      LEFT JOIN notes n ON n.session_id = s.session_id
      GROUP BY s.session_id
      ORDER BY s.updated_at DESC
      LIMIT 10
    `,
  ])

  return NextResponse.json({
    stats: stats[0],
    topSkills,
    recentSessions,
  })
}
