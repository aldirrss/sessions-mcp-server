'use client'

import { use, useState, useEffect, useCallback } from 'react'
import { useRouter } from 'next/navigation'
import Link from 'next/link'
import { ArrowLeft, Trash2, Clock, MessageSquare } from 'lucide-react'

import { API_BASE } from '@/lib/config'

type Version = { id: number; slug: string; changed_at: string }
type SessionRef = { session_id: string; title: string; source: string; used_at: string }
type Skill = {
  slug: string; name: string; summary: string; content: string
  category: string | null; tags: string[]; source: string; updated_at: string
  versions: Version[]; sessions: SessionRef[]
}

export default function SkillDetailPage({ params }: { params: Promise<{ slug: string }> }) {
  const { slug } = use(params)
  const router = useRouter()
  const [skill, setSkill] = useState<Skill | null>(null)
  const [loading, setLoading] = useState(true)
  const [editing, setEditing] = useState(false)
  const [form, setForm] = useState({ name: '', summary: '', content: '', category: '', tags: '' })
  const [saving, setSaving] = useState(false)

  const fetchSkill = useCallback(async () => {
    const res = await fetch(`${API_BASE}/api/skills/${slug}`)
    if (!res.ok) { router.push("/mcp-admin/skills"); return }
    const data = await res.json()
    setSkill(data)
    setForm({
      name: data.name,
      summary: data.summary ?? '',
      content: data.content,
      category: data.category ?? '',
      tags: (data.tags ?? []).join(', '),
    })
    setLoading(false)
  }, [slug, router])

  useEffect(() => { fetchSkill() }, [fetchSkill])

  async function handleSave() {
    setSaving(true)
    await fetch(`${API_BASE}/api/skills/${slug}`, {
      method: 'PATCH',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        ...form,
        category: form.category || null,
        tags: form.tags.split(',').map(t => t.trim()).filter(Boolean),
      }),
    })
    setSaving(false)
    setEditing(false)
    fetchSkill()
  }

  async function handleDelete() {
    if (!confirm(`Delete skill "${slug}" permanently?`)) return
    await fetch(`${API_BASE}/api/skills/${slug}`, { method: 'DELETE' })
    router.push("/mcp-admin/skills")
  }

  if (loading) return <div className="text-sm text-gray-400 p-8">Loading…</div>
  if (!skill) return null

  return (
    <div className="max-w-5xl space-y-6">
      <div className="flex items-center justify-between">
        <Link href="/mcp-admin/skills" className="flex items-center gap-1.5 text-sm text-gray-500 hover:text-gray-900 transition-colors">
          <ArrowLeft className="w-4 h-4" /> Skills
        </Link>
        <button onClick={handleDelete} className="flex items-center gap-1.5 px-3 py-1.5 text-sm text-red-600 hover:bg-red-50 rounded-lg transition-colors">
          <Trash2 className="w-4 h-4" /> Delete
        </button>
      </div>

      <div className="bg-white rounded-2xl border border-gray-200 p-6 space-y-4">
        {editing ? (
          <div className="space-y-4">
            {[
              { key: 'name', label: 'Name' },
              { key: 'summary', label: 'Summary' },
              { key: 'category', label: 'Category' },
              { key: 'tags', label: 'Tags (comma-separated)' },
            ].map(({ key, label }) => (
              <div key={key}>
                <label className="block text-xs font-medium text-gray-500 mb-1">{label}</label>
                <input value={form[key as keyof typeof form]}
                  onChange={e => setForm(f => ({ ...f, [key]: e.target.value }))}
                  className="w-full px-3 py-2 text-sm rounded-lg border border-gray-300 focus:outline-none focus:ring-2 focus:ring-blue-500" />
              </div>
            ))}
            <div>
              <label className="block text-xs font-medium text-gray-500 mb-1">Content (Markdown)</label>
              <textarea value={form.content}
                onChange={e => setForm(f => ({ ...f, content: e.target.value }))}
                rows={12}
                className="w-full px-3 py-2 text-sm font-mono rounded-lg border border-gray-300 resize-none focus:outline-none focus:ring-2 focus:ring-blue-500" />
            </div>
            <div className="flex gap-2">
              <button onClick={handleSave} disabled={saving}
                className="px-4 py-2 text-sm bg-blue-600 hover:bg-blue-700 text-white rounded-lg disabled:opacity-60">
                {saving ? 'Saving…' : 'Save'}
              </button>
              <button onClick={() => setEditing(false)}
                className="px-4 py-2 text-sm border border-gray-300 rounded-lg hover:bg-gray-50">Cancel</button>
            </div>
          </div>
        ) : (
          <div className="space-y-3">
            <div className="flex items-start justify-between gap-4">
              <div>
                <h1 className="text-xl font-bold text-gray-900">{skill.name}</h1>
                {skill.summary && <p className="text-sm text-gray-500 mt-1">{skill.summary}</p>}
              </div>
              <button onClick={() => setEditing(true)}
                className="text-sm text-blue-600 hover:underline flex-shrink-0">Edit</button>
            </div>
            <div className="flex items-center gap-2 flex-wrap">
              <span className="text-xs bg-gray-100 text-gray-600 px-2 py-0.5 rounded-full font-mono">{skill.slug}</span>
              <span className="text-xs bg-blue-50 text-blue-700 px-2 py-0.5 rounded-full">{skill.source}</span>
              {skill.category && <span className="text-xs bg-violet-50 text-violet-700 px-2 py-0.5 rounded-full">{skill.category}</span>}
              {(skill.tags ?? []).map(t => (
                <span key={t} className="text-xs bg-gray-100 text-gray-600 px-2 py-0.5 rounded-full">{t}</span>
              ))}
            </div>
            <p className="text-xs text-gray-400">Updated {new Date(skill.updated_at).toLocaleString()}</p>
            <div className="border-t border-gray-100 pt-4">
              <pre className="text-sm text-gray-800 whitespace-pre-wrap font-mono bg-gray-50 rounded-xl p-4 overflow-x-auto">{skill.content}</pre>
            </div>
          </div>
        )}
      </div>

      {skill.versions.length > 0 && (
        <div className="bg-white rounded-2xl border border-gray-200 p-5">
          <h2 className="text-sm font-semibold text-gray-900 mb-3 flex items-center gap-2">
            <Clock className="w-4 h-4 text-gray-400" /> Version History ({skill.versions.length})
          </h2>
          <div className="space-y-1">
            {skill.versions.map((v) => (
              <div key={v.id} className="flex items-center gap-3 px-3 py-2 rounded-lg text-sm text-gray-500">
                <span className="w-6 h-6 rounded-full bg-gray-100 flex items-center justify-center text-xs font-mono text-gray-400">
                  {skill.versions.length - skill.versions.indexOf(v)}
                </span>
                <span>Snapshot saved {new Date(v.changed_at).toLocaleString()}</span>
              </div>
            ))}
          </div>
        </div>
      )}

      {skill.sessions.length > 0 && (
        <div className="bg-white rounded-2xl border border-gray-200 p-5">
          <h2 className="text-sm font-semibold text-gray-900 mb-3 flex items-center gap-2">
            <MessageSquare className="w-4 h-4 text-gray-400" /> Used in Sessions ({skill.sessions.length})
          </h2>
          <div className="space-y-1">
            {skill.sessions.map((s) => (
              <Link
                key={s.session_id}
                href={`/mcp-admin/sessions/${s.session_id}`}
                className="flex items-center justify-between px-3 py-2 rounded-lg hover:bg-gray-50 transition-colors"
              >
                <div>
                  <p className="text-sm font-medium text-gray-900">{s.title}</p>
                  <p className="text-xs text-gray-400">{s.session_id} · {s.source}</p>
                </div>
                <p className="text-xs text-gray-400">{new Date(s.used_at).toLocaleDateString()}</p>
              </Link>
            ))}
          </div>
        </div>
      )}
    </div>
  )
}
