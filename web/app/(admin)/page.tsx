import Link from 'next/link'
import sql from '@/lib/db'
import { MessageSquare, BookOpen, FileText, TrendingUp } from 'lucide-react'

async function getDashboardData() {
  const [stats, topSkills, recentSessions] = await Promise.all([
    sql`
      SELECT
        (SELECT COUNT(*)::int FROM sessions)                     AS total_sessions,
        (SELECT COUNT(*)::int FROM notes)                        AS total_notes,
        (SELECT COUNT(*)::int FROM skills)                       AS total_skills,
        (SELECT COUNT(*)::int FROM session_skills
         WHERE used_at > NOW() - INTERVAL '7 days')             AS skills_used_this_week
    `,
    sql`
      SELECT sk.slug, sk.name, sk.category, COUNT(ss.session_id)::int AS session_count
      FROM skills sk
      LEFT JOIN session_skills ss ON ss.skill_slug = sk.slug
      GROUP BY sk.slug, sk.name, sk.category
      ORDER BY session_count DESC, sk.name ASC
      LIMIT 5
    `,
    sql`
      SELECT s.session_id, s.title, s.source, s.tags, s.updated_at,
             COUNT(n.id)::int AS notes_count
      FROM sessions s
      LEFT JOIN notes n ON n.session_id = s.session_id
      GROUP BY s.session_id
      ORDER BY s.updated_at DESC
      LIMIT 8
    `,
  ])

  return { stats: stats[0], topSkills, recentSessions }
}

const BASE = '/panel/mcp-admin'

function StatCard({ label, value, icon: Icon, color }: {
  label: string; value: number; icon: React.ElementType; color: string
}) {
  return (
    <div className="bg-white rounded-2xl border border-gray-200 p-5">
      <div className="flex items-center justify-between mb-3">
        <p className="text-sm font-medium text-gray-500">{label}</p>
        <div className={`w-9 h-9 rounded-xl flex items-center justify-center ${color}`}>
          <Icon className="w-4.5 h-4.5" />
        </div>
      </div>
      <p className="text-3xl font-bold text-gray-900">{value.toLocaleString()}</p>
    </div>
  )
}

export default async function DashboardPage() {
  const { stats, topSkills, recentSessions } = await getDashboardData()

  return (
    <div className="max-w-5xl space-y-6">
      <div>
        <h1 className="text-2xl font-bold text-gray-900">Dashboard</h1>
        <p className="text-sm text-gray-500 mt-0.5">Overview of sessions and skills</p>
      </div>

      <div className="grid grid-cols-2 lg:grid-cols-4 gap-4">
        <StatCard label="Sessions" value={stats.total_sessions} icon={MessageSquare} color="bg-blue-50 text-blue-600" />
        <StatCard label="Skills" value={stats.total_skills} icon={BookOpen} color="bg-violet-50 text-violet-600" />
        <StatCard label="Notes" value={stats.total_notes} icon={FileText} color="bg-emerald-50 text-emerald-600" />
        <StatCard label="Skill uses (7d)" value={stats.skills_used_this_week} icon={TrendingUp} color="bg-amber-50 text-amber-600" />
      </div>

      <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
        <div className="bg-white rounded-2xl border border-gray-200 p-5">
          <h2 className="text-sm font-semibold text-gray-900 mb-4">Top Skills by Usage</h2>
          {topSkills.length === 0 ? (
            <p className="text-sm text-gray-400">No skills yet.</p>
          ) : (
            <div className="space-y-2">
              {topSkills.map((s) => (
                <Link
                  key={s.slug}
                  href={`${BASE}/skills/${s.slug}`}
                  className="flex items-center justify-between py-2 px-3 rounded-lg hover:bg-gray-50 transition-colors"
                >
                  <div>
                    <p className="text-sm font-medium text-gray-900">{s.name}</p>
                    {s.category && <p className="text-xs text-gray-400">{s.category}</p>}
                  </div>
                  <span className="text-sm font-semibold text-blue-600">{s.session_count}</span>
                </Link>
              ))}
            </div>
          )}
        </div>

        <div className="bg-white rounded-2xl border border-gray-200 p-5">
          <h2 className="text-sm font-semibold text-gray-900 mb-4">Recent Sessions</h2>
          {recentSessions.length === 0 ? (
            <p className="text-sm text-gray-400">No sessions yet.</p>
          ) : (
            <div className="space-y-2">
              {recentSessions.map((s) => (
                <Link
                  key={s.session_id}
                  href={`${BASE}/sessions/${s.session_id}`}
                  className="flex items-center justify-between py-2 px-3 rounded-lg hover:bg-gray-50 transition-colors"
                >
                  <div className="min-w-0 mr-4">
                    <p className="text-sm font-medium text-gray-900 truncate">{s.title}</p>
                    <p className="text-xs text-gray-400">{s.source} · {s.notes_count} notes</p>
                  </div>
                  <p className="text-xs text-gray-400 flex-shrink-0">
                    {new Date(s.updated_at).toLocaleDateString()}
                  </p>
                </Link>
              ))}
            </div>
          )}
        </div>
      </div>
    </div>
  )
}
