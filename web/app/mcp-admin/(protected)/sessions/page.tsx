'use client'

import { useState, useEffect, useCallback } from 'react'
import Link from 'next/link'
import { Search, Plus, Trash2, Eye } from 'lucide-react'

import { API_BASE } from '@/lib/config'

type Session = {
  session_id: string; title: string; source: string
  tags: string[]; pinned: boolean; archived: boolean
  notes_count: number; updated_at: string
}

function Badge({ label }: { label: string }) {
  return (
    <span className="inline-flex items-center px-2 py-0.5 rounded-full text-xs font-medium bg-gray-100 text-gray-600">
      {label}
    </span>
  )
}

export default function SessionsPage() {
  const [rows, setRows] = useState<Session[]>([])
  const [total, setTotal] = useState(0)
  const [search, setSearch] = useState('')
  const [source, setSource] = useState('')
  const [showArchived, setShowArchived] = useState(false)
  const [page, setPage] = useState(1)
  const [loading, setLoading] = useState(false)
  const [showCreate, setShowCreate] = useState(false)
  const [newId, setNewId] = useState('')
  const [newTitle, setNewTitle] = useState('')
  const [newSource, setNewSource] = useState('web')
  const [creating, setCreating] = useState(false)

  const fetchSessions = useCallback(async () => {
    setLoading(true)
    const q = new URLSearchParams({ search, source, page: String(page), archived: String(showArchived) })
    const res = await fetch(`${API_BASE}/api/sessions?${q}`)
    const data = await res.json()
    setRows(data.rows)
    setTotal(data.total)
    setLoading(false)
  }, [search, source, page, showArchived])

  useEffect(() => { fetchSessions() }, [fetchSessions])

  async function handleDelete(id: string) {
    if (!confirm(`Delete session "${id}"?`)) return
    await fetch(`${API_BASE}/api/sessions/${id}`, { method: 'DELETE' })
    fetchSessions()
  }

  async function handleCreate(e: React.FormEvent) {
    e.preventDefault()
    setCreating(true)
    await fetch(`${API_BASE}/api/sessions`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ session_id: newId, title: newTitle, source: newSource }),
    })
    setShowCreate(false)
    setNewId(''); setNewTitle(''); setNewSource('web')
    setCreating(false)
    fetchSessions()
  }

  const totalPages = Math.ceil(total / 20)

  return (
    <div className="space-y-5">
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-bold text-gray-900">Sessions</h1>
          <p className="text-sm text-gray-500 mt-0.5">{total} sessions</p>
        </div>
        <button
          onClick={() => setShowCreate(true)}
          className="flex items-center gap-2 px-4 py-2 bg-blue-600 hover:bg-blue-700 text-white text-sm font-medium rounded-lg transition-colors"
        >
          <Plus className="w-4 h-4" /> New Session
        </button>
      </div>

      <div className="flex gap-3">
        <div className="relative flex-1">
          <Search className="absolute left-3 top-1/2 -translate-y-1/2 w-4 h-4 text-gray-400" />
          <input
            type="text"
            placeholder="Search by ID or title…"
            value={search}
            onChange={e => { setSearch(e.target.value); setPage(1) }}
            className="w-full pl-9 pr-3 py-2 rounded-lg border border-gray-300 text-sm focus:outline-none focus:ring-2 focus:ring-blue-500"
          />
        </div>
        <select
          value={source}
          onChange={e => { setSource(e.target.value); setPage(1) }}
          className="px-3 py-2 rounded-lg border border-gray-300 text-sm focus:outline-none focus:ring-2 focus:ring-blue-500 bg-white"
        >
          <option value="">All sources</option>
          <option value="web">web</option>
          <option value="cli">cli</option>
          <option value="vscode">vscode</option>
          <option value="unknown">unknown</option>
        </select>
        <label className="flex items-center gap-2 px-3 py-2 rounded-lg border border-gray-300 text-sm cursor-pointer select-none hover:bg-gray-50">
          <input
            type="checkbox"
            checked={showArchived}
            onChange={e => { setShowArchived(e.target.checked); setPage(1) }}
            className="rounded"
          />
          Archived
        </label>
      </div>

      <div className="bg-white rounded-2xl border border-gray-200 overflow-hidden">
        {loading ? (
          <div className="p-8 text-center text-sm text-gray-400">Loading…</div>
        ) : rows.length === 0 ? (
          <div className="p-8 text-center text-sm text-gray-400">No sessions found.</div>
        ) : (
          <table className="w-full text-sm">
            <thead className="bg-gray-50 border-b border-gray-200">
              <tr>
                <th className="text-left px-4 py-3 text-xs font-semibold text-gray-500 uppercase tracking-wider">Session ID</th>
                <th className="text-left px-4 py-3 text-xs font-semibold text-gray-500 uppercase tracking-wider">Title</th>
                <th className="text-left px-4 py-3 text-xs font-semibold text-gray-500 uppercase tracking-wider">Source</th>
                <th className="text-left px-4 py-3 text-xs font-semibold text-gray-500 uppercase tracking-wider">Tags</th>
                <th className="text-left px-4 py-3 text-xs font-semibold text-gray-500 uppercase tracking-wider">Notes</th>
                <th className="text-left px-4 py-3 text-xs font-semibold text-gray-500 uppercase tracking-wider">Updated</th>
                <th className="px-4 py-3"></th>
              </tr>
            </thead>
            <tbody className="divide-y divide-gray-100">
              {rows.map((s) => (
                <tr key={s.session_id} className={`hover:bg-gray-50 transition-colors ${s.archived ? 'opacity-60' : ''}`}>
                  <td className="px-4 py-3 font-mono text-xs text-gray-500">
                    <span className="flex items-center gap-1">
                      {s.pinned && <span title="Pinned">📌</span>}
                      {s.archived && <span title="Archived">🗄</span>}
                      {s.session_id}
                    </span>
                  </td>
                  <td className="px-4 py-3 font-medium text-gray-900 max-w-xs truncate">{s.title}</td>
                  <td className="px-4 py-3"><Badge label={s.source} /></td>
                  <td className="px-4 py-3">
                    <div className="flex flex-wrap gap-1">
                      {s.tags.slice(0, 3).map(t => <Badge key={t} label={t} />)}
                      {s.tags.length > 3 && <span className="text-xs text-gray-400">+{s.tags.length - 3}</span>}
                    </div>
                  </td>
                  <td className="px-4 py-3 text-gray-500">{s.notes_count}</td>
                  <td className="px-4 py-3 text-gray-500 text-xs">{new Date(s.updated_at).toLocaleDateString()}</td>
                  <td className="px-4 py-3">
                    <div className="flex items-center gap-2 justify-end">
                      <Link href={`/mcp-admin/sessions/${s.session_id}`} className="p-1.5 rounded-md hover:bg-gray-100 text-gray-500 hover:text-gray-900 transition-colors">
                        <Eye className="w-4 h-4" />
                      </Link>
                      <button onClick={() => handleDelete(s.session_id)} className="p-1.5 rounded-md hover:bg-red-50 text-gray-500 hover:text-red-600 transition-colors">
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
          <form onSubmit={handleCreate} className="bg-white rounded-2xl shadow-xl p-6 w-full max-w-md space-y-4">
            <h2 className="text-lg font-semibold text-gray-900">New Session</h2>
            <div>
              <label className="block text-sm font-medium text-gray-700 mb-1">Session ID</label>
              <input required value={newId} onChange={e => setNewId(e.target.value)}
                placeholder="my-project-dev"
                className="w-full px-3 py-2 rounded-lg border border-gray-300 text-sm font-mono focus:outline-none focus:ring-2 focus:ring-blue-500" />
            </div>
            <div>
              <label className="block text-sm font-medium text-gray-700 mb-1">Title</label>
              <input required value={newTitle} onChange={e => setNewTitle(e.target.value)}
                placeholder="My Project — Development"
                className="w-full px-3 py-2 rounded-lg border border-gray-300 text-sm focus:outline-none focus:ring-2 focus:ring-blue-500" />
            </div>
            <div>
              <label className="block text-sm font-medium text-gray-700 mb-1">Source</label>
              <select value={newSource} onChange={e => setNewSource(e.target.value)}
                className="w-full px-3 py-2 rounded-lg border border-gray-300 text-sm bg-white focus:outline-none focus:ring-2 focus:ring-blue-500">
                <option value="web">web</option>
                <option value="cli">cli</option>
                <option value="vscode">vscode</option>
              </select>
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
