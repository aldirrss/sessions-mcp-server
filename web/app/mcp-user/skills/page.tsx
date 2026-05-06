'use client'

import { useState, useEffect, useCallback } from 'react'
import Link from 'next/link'
import { BookOpen, Search, ChevronRight } from 'lucide-react'
import { API_BASE } from '@/lib/config'
import UserPortalHeader from '@/components/user-portal-header'

type Skill = {
  slug: string; name: string; summary: string
  category: string | null; tags: string[]; updated_at: string
}

export default function UserSkillsPage() {
  const [skills, setSkills] = useState<Skill[]>([])
  const [loading, setLoading] = useState(true)
  const [search, setSearch] = useState('')

  const fetchSkills = useCallback(async () => {
    const q = new URLSearchParams({ search })
    const res = await fetch(`${API_BASE}/portal/skills?${q}`)
    if (res.status === 401) { window.location.href = '/panel/mcp-user/login'; return }
    const data = await res.json()
    setSkills(data.skills ?? [])
    setLoading(false)
  }, [search])

  useEffect(() => {
    setLoading(true)
    const t = setTimeout(() => fetchSkills(), 300)
    return () => clearTimeout(t)
  }, [fetchSkills])

  return (
    <div className="min-h-screen bg-gray-50">
      <UserPortalHeader title="Skill Library" subtitle="Global skills available to all users" accentColor="bg-violet-600" />

      <main className="max-w-3xl mx-auto px-4 py-5 md:px-6 md:py-6 space-y-4">
        <div className="relative">
          <Search className="absolute left-3 top-1/2 -translate-y-1/2 w-4 h-4 text-gray-400" />
          <input
            type="text"
            placeholder="Search skills by name, slug, or summary…"
            value={search}
            onChange={e => setSearch(e.target.value)}
            className="w-full pl-9 pr-4 py-2.5 rounded-xl border border-gray-300 text-sm focus:outline-none focus:ring-2 focus:ring-violet-500 bg-white"
          />
        </div>

        {loading ? (
          <p className="text-sm text-gray-400 text-center py-8">Loading…</p>
        ) : skills.length === 0 ? (
          <div className="text-center py-12">
            <BookOpen className="w-10 h-10 text-gray-300 mx-auto mb-3" />
            <p className="text-sm text-gray-400">
              {search ? `No skills matching "${search}"` : 'No global skills yet.'}
            </p>
          </div>
        ) : (
          <div className="space-y-1">
            <p className="text-xs text-gray-400 mb-2">{skills.length} skill{skills.length !== 1 ? 's' : ''}</p>
            <div className="bg-white rounded-2xl border border-gray-200 divide-y divide-gray-100 overflow-hidden">
              {skills.map(s => (
                <Link
                  key={s.slug}
                  href={`/mcp-user/skills/${s.slug}`}
                  className="flex items-center gap-3 px-4 py-3.5 hover:bg-gray-50 transition-colors"
                >
                  <div className="flex-1 min-w-0">
                    <div className="flex items-center gap-2 flex-wrap">
                      <span className="text-sm font-medium text-gray-900">{s.name}</span>
                      {s.category && (
                        <span className="text-xs bg-violet-50 text-violet-700 px-1.5 py-0.5 rounded-full">{s.category}</span>
                      )}
                    </div>
                    {s.summary && <p className="text-xs text-gray-500 mt-0.5 truncate">{s.summary}</p>}
                    <div className="flex flex-wrap gap-1 mt-1.5">
                      <span className="text-xs font-mono text-gray-300">{s.slug}</span>
                      {s.tags.slice(0, 3).map(t => (
                        <span key={t} className="text-xs bg-gray-100 text-gray-500 px-1.5 py-0.5 rounded">{t}</span>
                      ))}
                    </div>
                  </div>
                  <ChevronRight className="w-4 h-4 text-gray-300 flex-shrink-0" />
                </Link>
              ))}
            </div>
          </div>
        )}
      </main>
    </div>
  )
}
