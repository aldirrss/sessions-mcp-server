'use client'

import { useState, useEffect, useCallback } from 'react'
import Link from 'next/link'
import { Search, Plus, Trash2, Eye } from 'lucide-react'

import { API_BASE } from '@/lib/config'

type Skill = {
  slug: string; name: string; summary: string; category: string | null
  tags: string[]; source: string; updated_at: string; session_count: number
}

function Badge({ label, color = 'gray' }: { label: string; color?: string }) {
  const styles: Record<string, string> = {
    gray: 'bg-gray-100 text-gray-600',
    violet: 'bg-violet-50 text-violet-700',
    blue: 'bg-blue-50 text-blue-700',
  }
  return (
    <span className={`inline-flex items-center px-2 py-0.5 rounded-full text-xs font-medium ${styles[color] ?? styles.gray}`}>
      {label}
    </span>
  )
}

export default function SkillsPage() {
  const [rows, setRows] = useState<Skill[]>([])
  const [total, setTotal] = useState(0)
  const [search, setSearch] = useState('')
  const [category, setCategory] = useState('')
  const [source, setSource] = useState('')
  const [page, setPage] = useState(1)
  const [loading, setLoading] = useState(false)
  const [showCreate, setShowCreate] = useState(false)
  const [form, setForm] = useState({ slug: '', name: '', content: '', summary: '', category: '', tags: '', source: 'manual' })
  const [creating, setCreating] = useState(false)

  const fetchSkills = useCallback(async () => {
    setLoading(true)
    const q = new URLSearchParams({ search, category, source, page: String(page) })
    const res = await fetch(`${API_BASE}/api/skills?${q}`)
    const data = await res.json()
    setRows(data.rows)
    setTotal(data.total)
    setLoading(false)
  }, [search, category, source, page])

  useEffect(() => { fetchSkills() }, [fetchSkills])

  async function handleDelete(slug: string) {
    if (!confirm(`Delete skill "${slug}"?`)) return
    await fetch(`${API_BASE}/api/skills/${slug}`, { method: 'DELETE' })
    fetchSkills()
  }

  async function handleCreate(e: React.FormEvent) {
    e.preventDefault()
    setCreating(true)
    await fetch(`${API_BASE}/api/skills`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        ...form,
        tags: form.tags.split(',').map(t => t.trim()).filter(Boolean),
        category: form.category || null,
      }),
    })
    setShowCreate(false)
    setForm({ slug: '', name: '', content: '', summary: '', category: '', tags: '', source: 'manual' })
    setCreating(false)
    fetchSkills()
  }

  const totalPages = Math.ceil(total / 20)

  return (
    <div className="max-w-5xl space-y-5">
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-bold text-gray-900">Skills</h1>
          <p className="text-sm text-gray-500 mt-0.5">{total} skills in library</p>
        </div>
        <button
          onClick={() => setShowCreate(true)}
          className="flex items-center gap-2 px-4 py-2 bg-blue-600 hover:bg-blue-700 text-white text-sm font-medium rounded-lg transition-colors"
        >
          <Plus className="w-4 h-4" /> New Skill
        </button>
      </div>

      <div className="flex gap-3">
        <div className="relative flex-1">
          <Search className="absolute left-3 top-1/2 -translate-y-1/2 w-4 h-4 text-gray-400" />
          <input
            type="text" placeholder="Search by name, slug, summary…"
            value={search} onChange={e => { setSearch(e.target.value); setPage(1) }}
            className="w-full pl-9 pr-3 py-2 rounded-lg border border-gray-300 text-sm focus:outline-none focus:ring-2 focus:ring-blue-500"
          />
        </div>
        <input
          type="text" placeholder="Category"
          value={category} onChange={e => { setCategory(e.target.value); setPage(1) }}
          className="px-3 py-2 rounded-lg border border-gray-300 text-sm w-36 focus:outline-none focus:ring-2 focus:ring-blue-500"
        />
        <select
          value={source} onChange={e => { setSource(e.target.value); setPage(1) }}
          className="px-3 py-2 rounded-lg border border-gray-300 text-sm bg-white focus:outline-none focus:ring-2 focus:ring-blue-500"
        >
          <option value="">All sources</option>
          <option value="manual">manual</option>
          <option value="file">file</option>
        </select>
      </div>

      <div className="bg-white rounded-2xl border border-gray-200 overflow-hidden">
        {loading ? (
          <div className="p-8 text-center text-sm text-gray-400">Loading…</div>
        ) : rows.length === 0 ? (
          <div className="p-8 text-center text-sm text-gray-400">No skills found.</div>
        ) : (
          <table className="w-full text-sm">
            <thead className="bg-gray-50 border-b border-gray-200">
              <tr>
                <th className="text-left px-4 py-3 text-xs font-semibold text-gray-500 uppercase tracking-wider">Slug</th>
                <th className="text-left px-4 py-3 text-xs font-semibold text-gray-500 uppercase tracking-wider">Name</th>
                <th className="text-left px-4 py-3 text-xs font-semibold text-gray-500 uppercase tracking-wider">Category</th>
                <th className="text-left px-4 py-3 text-xs font-semibold text-gray-500 uppercase tracking-wider">Tags</th>
                <th className="text-left px-4 py-3 text-xs font-semibold text-gray-500 uppercase tracking-wider">Source</th>
                <th className="text-left px-4 py-3 text-xs font-semibold text-gray-500 uppercase tracking-wider">Sessions</th>
                <th className="text-left px-4 py-3 text-xs font-semibold text-gray-500 uppercase tracking-wider">Updated</th>
                <th className="px-4 py-3"></th>
              </tr>
            </thead>
            <tbody className="divide-y divide-gray-100">
              {rows.map((s) => (
                <tr key={s.slug} className="hover:bg-gray-50 transition-colors">
                  <td className="px-4 py-3 font-mono text-xs text-gray-500">{s.slug}</td>
                  <td className="px-4 py-3 font-medium text-gray-900">{s.name}</td>
                  <td className="px-4 py-3">{s.category ? <Badge label={s.category} color="violet" /> : <span className="text-gray-300">—</span>}</td>
                  <td className="px-4 py-3">
                    <div className="flex flex-wrap gap-1">
                      {s.tags.slice(0, 3).map(t => <Badge key={t} label={t} />)}
                      {s.tags.length > 3 && <span className="text-xs text-gray-400">+{s.tags.length - 3}</span>}
                    </div>
                  </td>
                  <td className="px-4 py-3"><Badge label={s.source} color={s.source === 'file' ? 'blue' : 'gray'} /></td>
                  <td className="px-4 py-3 text-gray-500">{s.session_count}</td>
                  <td className="px-4 py-3 text-xs text-gray-400">{new Date(s.updated_at).toLocaleDateString()}</td>
                  <td className="px-4 py-3">
                    <div className="flex items-center gap-2 justify-end">
                      <Link href={`/mcp-admin/skills/${s.slug}`} className="p-1.5 rounded-md hover:bg-gray-100 text-gray-500 hover:text-gray-900 transition-colors">
                        <Eye className="w-4 h-4" />
                      </Link>
                      <button onClick={() => handleDelete(s.slug)} className="p-1.5 rounded-md hover:bg-red-50 text-gray-500 hover:text-red-600 transition-colors">
                        <Trash2 className="w-4 h-4" />
                      </button>
                    </div>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        )}
      </div>

      {totalPages > 1 && (
        <div className="flex items-center justify-between">
          <p className="text-sm text-gray-500">Page {page} of {totalPages}</p>
          <div className="flex gap-2">
            <button disabled={page <= 1} onClick={() => setPage(p => p - 1)}
              className="px-3 py-1.5 text-sm rounded-lg border border-gray-300 disabled:opacity-40 hover:bg-gray-50">Prev</button>
            <button disabled={page >= totalPages} onClick={() => setPage(p => p + 1)}
              className="px-3 py-1.5 text-sm rounded-lg border border-gray-300 disabled:opacity-40 hover:bg-gray-50">Next</button>
          </div>
        </div>
      )}

      {showCreate && (
        <div className="fixed inset-0 bg-black/40 flex items-center justify-center z-50">
          <form onSubmit={handleCreate} className="bg-white rounded-2xl shadow-xl p-6 w-full max-w-lg space-y-4 max-h-[90vh] overflow-y-auto">
            <h2 className="text-lg font-semibold text-gray-900">New Skill</h2>
            {[
              { key: 'slug', label: 'Slug', placeholder: 'mcp-builder', mono: true },
              { key: 'name', label: 'Name', placeholder: 'MCP Builder' },
              { key: 'summary', label: 'Summary', placeholder: 'Short description…' },
              { key: 'category', label: 'Category', placeholder: 'development' },
              { key: 'tags', label: 'Tags (comma-separated)', placeholder: 'mcp, python, docker' },
            ].map(({ key, label, placeholder, mono }) => (
              <div key={key}>
                <label className="block text-sm font-medium text-gray-700 mb-1">{label}</label>
                <input
                  value={form[key as keyof typeof form]}
                  onChange={e => setForm(f => ({ ...f, [key]: e.target.value }))}
                  placeholder={placeholder}
                  required={key === 'slug' || key === 'name'}
                  className={`w-full px-3 py-2 rounded-lg border border-gray-300 text-sm focus:outline-none focus:ring-2 focus:ring-blue-500 ${mono ? 'font-mono' : ''}`}
                />
              </div>
            ))}
            <div>
              <label className="block text-sm font-medium text-gray-700 mb-1">Content (Markdown)</label>
              <textarea
                value={form.content}
                onChange={e => setForm(f => ({ ...f, content: e.target.value }))}
                rows={6} required
                placeholder="# Skill Title&#10;&#10;Content in Markdown…"
                className="w-full px-3 py-2 rounded-lg border border-gray-300 text-sm font-mono resize-none focus:outline-none focus:ring-2 focus:ring-blue-500"
              />
            </div>
            <div className="flex justify-end gap-2 pt-2">
              <button type="button" onClick={() => setShowCreate(false)}
                className="px-4 py-2 text-sm rounded-lg border border-gray-300 hover:bg-gray-50">Cancel</button>
              <button type="submit" disabled={creating}
                className="px-4 py-2 text-sm bg-blue-600 hover:bg-blue-700 text-white rounded-lg disabled:opacity-60">
                {creating ? 'Creating…' : 'Create'}
              </button>
            </div>
          </form>
        </div>
      )}
    </div>
  )
}
