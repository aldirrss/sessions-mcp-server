'use client'

import { use, useState, useEffect, useCallback } from 'react'
import { useRouter } from 'next/navigation'
import Link from 'next/link'
import { ArrowLeft } from 'lucide-react'
import { API_BASE } from '@/lib/config'
import UserPortalHeader from '@/components/user-portal-header'

type Skill = {
  slug: string; name: string; summary: string; content: string
  category: string | null; tags: string[]; source: string; updated_at: string
}

export default function PersonalSkillDetailPage({ params }: { params: Promise<{ slug: string }> }) {
  const { slug } = use(params)
  const router = useRouter()
  const [skill, setSkill] = useState<Skill | null>(null)
  const [loading, setLoading] = useState(true)

  const fetchSkill = useCallback(async () => {
    const res = await fetch(`${API_BASE}/portal/skills/${slug}`)
    if (res.status === 401) { window.location.href = '/panel/mcp-user/login'; return }
    if (!res.ok) { router.push('/mcp-user/skills'); return }
    setSkill(await res.json())
    setLoading(false)
  }, [slug, router])

  useEffect(() => { fetchSkill() }, [fetchSkill])

  if (loading) {
    return (
      <div className="min-h-screen bg-gray-50">
        <UserPortalHeader title="Skill" subtitle="Loading…" accentColor="bg-violet-600" />
        <div className="flex items-center justify-center py-20">
          <p className="text-sm text-gray-400">Loading…</p>
        </div>
      </div>
    )
  }

  if (!skill) return null

  return (
    <div className="min-h-screen bg-gray-50">
      <UserPortalHeader title={skill.name} subtitle="Skill details" accentColor="bg-violet-600" />

      <main className="max-w-3xl mx-auto px-4 py-5 md:px-6 md:py-6 space-y-4">
        <Link href="/mcp-user/skills" className="flex items-center gap-1.5 text-sm text-gray-500 hover:text-gray-900 transition-colors">
          <ArrowLeft className="w-4 h-4" /> Skills
        </Link>

        {/* Metadata */}
        <div className="bg-white rounded-2xl border border-gray-200 p-4 md:p-5 space-y-2">
          <h1 className="text-lg font-semibold text-gray-900">{skill.name}</h1>
          {skill.summary && <p className="text-sm text-gray-500">{skill.summary}</p>}
          <div className="flex flex-wrap items-center gap-2 pt-1">
            <span className="text-xs font-mono bg-gray-100 text-gray-600 px-2 py-0.5 rounded-full">{skill.slug}</span>
            {skill.category && (
              <span className="text-xs bg-violet-50 text-violet-700 px-2 py-0.5 rounded-full">{skill.category}</span>
            )}
            {skill.tags.map(t => (
              <span key={t} className="text-xs bg-gray-100 text-gray-500 px-2 py-0.5 rounded-full">{t}</span>
            ))}
          </div>
          <p className="text-xs text-gray-400">Updated {new Date(skill.updated_at).toLocaleString()}</p>
        </div>

        {/* Content */}
        <div className="bg-white rounded-2xl border border-gray-200 p-4 md:p-5">
          <h2 className="text-sm font-semibold text-gray-700 mb-3">Content</h2>
          <pre className="text-sm text-gray-800 whitespace-pre-wrap font-mono bg-gray-50 rounded-xl p-4 overflow-x-auto max-h-[600px] overflow-y-auto">
            {skill.content}
          </pre>
        </div>
      </main>
    </div>
  )
}
