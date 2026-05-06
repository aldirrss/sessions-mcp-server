'use client'

import { useState, useEffect, useCallback } from 'react'
import { BookOpen, Search, ChevronDown, ChevronUp, LogOut, Key } from 'lucide-react'
import Link from 'next/link'
import { API_BASE } from '@/lib/config'

type Skill = {
  slug: string; name: string; summary: string
  category: string | null; tags: string[]; updated_at: string
}

function SkillCard({ skill }: { skill: Skill }) {
  const [open, setOpen] = useState(false)
  const [content, setContent] = useState<string | null>(null)
  const [loading, setLoading] = useState(false)

  async function toggle() {
    if (!open && content === null) {
      setLoading(true)
      const res = await fetch(`${API_BASE}/skills/${skill.slug}`)
      const data = await res.json()
      setContent(data.content ?? '')
      setLoading(false)
    }
    setOpen(o => !o)
  }

  return (
    <div className="bg-white rounded-2xl border border-gray-200 overflow-hidden">
      <button onClick={toggle} className="w-full text-left p-5 flex items-start justify-between gap-4 hover:bg-gray-50 transition-colors">
        <div className="flex-1 min-w-0">
          <div className="flex items-center gap-2 flex-wrap mb-1">
            <span className="text-sm font-semibold text-gray-900">{skill.name}</span>
            {skill.category && (
              <span className="px-2 py-0.5 rounded-full text-xs font-medium bg-violet-50 text-violet-700">{skill.category}</span>
            )}
          </div>
          {skill.summary && <p className="text-xs text-gray-500 line-clamp-2">{skill.summary}</p>}
          <div className="flex flex-wrap gap-1 mt-2">
            {skill.tags.map(t => (
              <span key={t} className="px-1.5 py-0.5 rounded text-xs bg-gray-100 text-gray-500">{t}</span>
            ))}
            <span className="text-xs text-gray-300 font-mono ml-1">{skill.slug}</span>
          </div>
        </div>
        <div className="flex-shrink-0 text-gray-400 mt-0.5">
          {open ? <ChevronUp className="w-4 h-4" /> : <ChevronDown className="w-4 h-4" />}
        </div>
      </button>

      {open && (
        <div className="border-t border-gray-100 px-5 py-4">
          {loading
            ? <p className="text-sm text-gray-400">Loading…</p>
            : <pre className="text-xs text-gray-700 whitespace-pre-wrap font-mono bg-gray-50 rounded-xl p-4 overflow-x-auto max-h-96">{content}</pre>
          }
        </div>
      )}
    </div>
  )
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

  async function handleLogout() {
    await fetch(`${API_BASE}/auth/user-logout`, { method: 'POST' })
    window.location.href = '/panel/mcp-user/login'
  }

  return (
    <div className="min-h-screen bg-gray-50">
      <header className="bg-white border-b border-gray-200 px-6 py-4 flex items-center justify-between">
        <div className="flex items-center gap-6">
          <div className="flex items-center gap-3">
            <div className="w-8 h-8 rounded-lg bg-violet-600 flex items-center justify-center">
              <BookOpen className="w-4 h-4 text-white" />
            </div>
            <div>
              <h1 className="text-sm font-semibold text-gray-900">Skill Library</h1>
              <p className="text-xs text-gray-500">Global skills available to all users</p>
            </div>
          </div>
          <nav className="flex items-center gap-1">
            <Link href="/mcp-user/portal"
              className="flex items-center gap-1.5 px-3 py-1.5 text-sm text-gray-500 hover:text-gray-900 hover:bg-gray-100 rounded-lg transition-colors">
              <Key className="w-3.5 h-3.5" /> Tokens
            </Link>
            <Link href="/mcp-user/skills"
              className="flex items-center gap-1.5 px-3 py-1.5 text-sm bg-gray-100 text-gray-900 rounded-lg font-medium">
              <BookOpen className="w-3.5 h-3.5" /> Skills
            </Link>
          </nav>
        </div>
        <button onClick={handleLogout}
          className="flex items-center gap-1.5 text-sm text-gray-500 hover:text-gray-900 transition-colors">
          <LogOut className="w-4 h-4" /> Sign out
        </button>
      </header>

      <main className="max-w-3xl mx-auto p-6 space-y-5">
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
              {search ? `No skills matching "${search}"` : 'No global skills yet. Ask your admin to import some.'}
            </p>
          </div>
        ) : (
          <div className="space-y-3">
            <p className="text-xs text-gray-400">{skills.length} skill{skills.length !== 1 ? 's' : ''}</p>
            {skills.map(s => <SkillCard key={s.slug} skill={s} />)}
          </div>
        )}
      </main>
    </div>
  )
}
