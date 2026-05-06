'use client'

import { useState, useEffect, useCallback } from 'react'
import Link from 'next/link'
import { Search, MessageSquare, Pin, Trash2, Tag } from 'lucide-react'
import { API_BASE } from '@/lib/config'
import UserPortalHeader from '@/components/user-portal-header'

type Session = {
  session_id: string
  title: string
  tags: string[]
  pinned: boolean
  updated_at: string
  notes_count: number
}

export default function UserSessionsPage() {
  const [sessions, setSessions] = useState<Session[]>([])
  const [loading, setLoading] = useState(true)
  const [search, setSearch] = useState('')
  const [deletingId, setDeletingId] = useState<string | null>(null)
  const [togglingId, setTogglingId] = useState<string | null>(null)

  const fetchSessions = useCallback(async () => {
    const q = new URLSearchParams()
    if (search) q.set('search', search)
    const res = await fetch(`${API_BASE}/portal/sessions?${q}`)
    if (res.status === 401) { window.location.href = '/panel/mcp-user/login'; return }
    if (res.ok) setSessions(await res.json())
    setLoading(false)
  }, [search])

  useEffect(() => {
    setLoading(true)
    const t = setTimeout(() => fetchSessions(), 300)
    return () => clearTimeout(t)
  }, [fetchSessions])

  async function handleDelete(sessionId: string, title: string) {
    if (!confirm(`Delete session "${title}"? This cannot be undone.`)) return
    setDeletingId(sessionId)
    await fetch(`${API_BASE}/portal/sessions/${sessionId}`, { method: 'DELETE' })
    setDeletingId(null)
    fetchSessions()
  }

  async function togglePin(s: Session) {
    setTogglingId(s.session_id)
    await fetch(`${API_BASE}/portal/sessions/${s.session_id}`, {
      method: 'PATCH',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ pinned: !s.pinned }),
    })
    setTogglingId(null)
    fetchSessions()
  }

  const pinned = sessions.filter(s => s.pinned)
  const rest = sessions.filter(s => !s.pinned)

  return (
    <div className="min-h-screen bg-gray-50">
      <UserPortalHeader title="My Sessions" subtitle="Personal MCP sessions" accentColor="bg-blue-600" />

      <main className="max-w-3xl mx-auto px-4 py-5 md:px-6 md:py-6 space-y-4">
        {/* Search */}
        <div className="relative">
          <Search className="absolute left-3 top-1/2 -translate-y-1/2 w-4 h-4 text-gray-400" />
          <input
            type="text"
            placeholder="Search by title or tag…"
            value={search}
            onChange={e => setSearch(e.target.value)}
            className="w-full pl-9 pr-4 py-2.5 rounded-xl border border-gray-300 text-sm focus:outline-none focus:ring-2 focus:ring-blue-500 bg-white"
          />
        </div>

        {loading ? (
          <p className="text-sm text-gray-400 text-center py-10">Loading…</p>
        ) : sessions.length === 0 ? (
          <div className="text-center py-14">
            <MessageSquare className="w-10 h-10 text-gray-200 mx-auto mb-3" />
            <p className="text-sm text-gray-400">
              {search ? `No sessions matching "${search}"` : 'No sessions yet. Start a conversation in Claude Code to create one.'}
            </p>
          </div>
        ) : (
          <div className="space-y-4">
            {pinned.length > 0 && (
              <section className="space-y-2">
                <p className="text-xs font-semibold text-gray-400 uppercase tracking-wider flex items-center gap-1.5">
                  <Pin className="w-3 h-3" /> Pinned
                </p>
                <SessionList sessions={pinned} onDelete={handleDelete} onTogglePin={togglePin}
                  deletingId={deletingId} togglingId={togglingId} />
              </section>
            )}

            {rest.length > 0 && (
              <section className="space-y-2">
                {pinned.length > 0 && (
                  <p className="text-xs font-semibold text-gray-400 uppercase tracking-wider">
                    Recent · {rest.length}
                  </p>
                )}
                <SessionList sessions={rest} onDelete={handleDelete} onTogglePin={togglePin}
                  deletingId={deletingId} togglingId={togglingId} />
              </section>
            )}
          </div>
        )}
      </main>
    </div>
  )
}

function SessionList({ sessions, onDelete, onTogglePin, deletingId, togglingId }: {
  sessions: Session[]
  onDelete: (id: string, title: string) => void
  onTogglePin: (s: Session) => void
  deletingId: string | null
  togglingId: string | null
}) {
  return (
    <div className="bg-white rounded-2xl border border-gray-200 divide-y divide-gray-100 overflow-hidden">
      {sessions.map(s => (
        <div key={s.session_id} className="flex items-start gap-3 px-4 py-3.5 hover:bg-gray-50 transition-colors">
          <div className="flex-1 min-w-0">
            <Link href={`/mcp-user/sessions/${s.session_id}`} className="text-sm font-medium text-gray-900 truncate hover:text-blue-600 transition-colors block">{s.title}</Link>
            <div className="flex items-center gap-3 mt-1 flex-wrap">
              <span className="text-xs text-gray-400">
                {new Date(s.updated_at).toLocaleDateString('en-GB', { day: 'numeric', month: 'short', year: 'numeric' })}
              </span>
              {s.notes_count > 0 && (
                <span className="text-xs text-gray-400 flex items-center gap-1">
                  <MessageSquare className="w-3 h-3" /> {s.notes_count}
                </span>
              )}
              {s.tags.length > 0 && (
                <span className="flex items-center gap-1 flex-wrap">
                  <Tag className="w-3 h-3 text-gray-300 flex-shrink-0" />
                  {s.tags.slice(0, 3).map(t => (
                    <span key={t} className="text-xs bg-gray-100 text-gray-500 px-1.5 py-0.5 rounded">{t}</span>
                  ))}
                  {s.tags.length > 3 && <span className="text-xs text-gray-400">+{s.tags.length - 3}</span>}
                </span>
              )}
            </div>
          </div>

          <div className="flex items-center gap-1 flex-shrink-0 mt-0.5">
            <button
              onClick={() => onTogglePin(s)}
              disabled={togglingId === s.session_id}
              title={s.pinned ? 'Unpin' : 'Pin'}
              className={`p-1.5 rounded-md transition-colors disabled:opacity-40 ${
                s.pinned
                  ? 'text-blue-500 hover:bg-blue-50'
                  : 'text-gray-300 hover:text-gray-500 hover:bg-gray-100'
              }`}
            >
              <Pin className="w-3.5 h-3.5" />
            </button>
            <button
              onClick={() => onDelete(s.session_id, s.title)}
              disabled={deletingId === s.session_id}
              title="Delete"
              className="p-1.5 rounded-md text-gray-300 hover:text-red-500 hover:bg-red-50 transition-colors disabled:opacity-40"
            >
              <Trash2 className="w-3.5 h-3.5" />
            </button>
          </div>
        </div>
      ))}
    </div>
  )
}
