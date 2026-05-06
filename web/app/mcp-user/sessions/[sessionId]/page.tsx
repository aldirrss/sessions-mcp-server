'use client'

import { use, useState, useEffect, useCallback } from 'react'
import { useRouter } from 'next/navigation'
import Link from 'next/link'
import { ArrowLeft, Pin, Trash2, Plus, ChevronLeft, ChevronRight, Github, BookOpen } from 'lucide-react'
import { API_BASE } from '@/lib/config'
import UserPortalHeader from '@/components/user-portal-header'
import NoteCard from '@/components/note-card'

const NOTES_PER_PAGE = 10

type Note = { id: number; content: string; source: string; pinned: boolean; created_at: string }
type Skill = { skill_slug: string; name: string | null; category: string | null; used_at: string }
type Session = {
  session_id: string; title: string; context: string; source: string
  tags: string[]; pinned: boolean; archived: boolean; updated_at: string
  repo_url: string | null; notes: Note[]; skills: Skill[]
}

export default function PersonalSessionDetailPage({ params }: { params: Promise<{ sessionId: string }> }) {
  const { sessionId } = use(params)
  const router = useRouter()
  const [session, setSession] = useState<Session | null>(null)
  const [loading, setLoading] = useState(true)
  const [noteContent, setNoteContent] = useState('')
  const [addingNote, setAddingNote] = useState(false)
  const [pinning, setPinning] = useState(false)
  const [deleting, setDeleting] = useState(false)
  const [notePage, setNotePage] = useState(1)

  const fetchSession = useCallback(async () => {
    const res = await fetch(`${API_BASE}/portal/sessions/${sessionId}`)
    if (res.status === 401) { window.location.href = '/panel/mcp-user/login'; return }
    if (!res.ok) { router.push('/mcp-user/sessions'); return }
    setSession(await res.json())
    setLoading(false)
  }, [sessionId, router])

  useEffect(() => { fetchSession() }, [fetchSession])

  async function handleTogglePin() {
    if (!session) return
    setPinning(true)
    await fetch(`${API_BASE}/portal/sessions/${sessionId}`, {
      method: 'PATCH',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ pinned: !session.pinned }),
    })
    setPinning(false)
    fetchSession()
  }

  async function handleDelete() {
    if (!confirm(`Delete session "${session?.title}"? This cannot be undone.`)) return
    setDeleting(true)
    await fetch(`${API_BASE}/portal/sessions/${sessionId}`, { method: 'DELETE' })
    router.push('/mcp-user/sessions')
  }

  async function handleAddNote(e: React.FormEvent) {
    e.preventDefault()
    setAddingNote(true)
    await fetch(`${API_BASE}/portal/sessions/${sessionId}/notes`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ content: noteContent }),
    })
    setNoteContent('')
    setAddingNote(false)
    setNotePage(999)
    fetchSession()
  }

  if (loading) {
    return (
      <div className="min-h-screen bg-gray-50">
        <UserPortalHeader title="Session" subtitle="Loading…" accentColor="bg-blue-600" />
        <div className="flex items-center justify-center py-20">
          <p className="text-sm text-gray-400">Loading…</p>
        </div>
      </div>
    )
  }

  if (!session) return null

  const pinnedNotes = session.notes.filter(n => n.pinned)
  const regularNotes = session.notes.filter(n => !n.pinned)
  const totalPages = Math.max(1, Math.ceil(regularNotes.length / NOTES_PER_PAGE))
  const currentPage = Math.min(notePage, totalPages)
  const paginatedNotes = regularNotes.slice((currentPage - 1) * NOTES_PER_PAGE, currentPage * NOTES_PER_PAGE)

  return (
    <div className="min-h-screen bg-gray-50">
      <UserPortalHeader title={session.title} subtitle="Personal session" accentColor="bg-blue-600" />

      <main className="max-w-5xl mx-auto px-4 py-5 md:px-6 md:py-6 space-y-4">
        {/* Back + actions */}
        <div className="flex items-center justify-between">
          <Link href="/mcp-user/sessions" className="flex items-center gap-1.5 text-sm text-gray-500 hover:text-gray-900 transition-colors">
            <ArrowLeft className="w-4 h-4" /> Sessions
          </Link>
          <div className="flex items-center gap-2">
            <button onClick={handleTogglePin} disabled={pinning}
              className={`flex items-center gap-1.5 px-3 py-1.5 text-sm rounded-lg transition-colors disabled:opacity-40 ${
                session.pinned ? 'bg-blue-50 text-blue-700 hover:bg-blue-100' : 'text-gray-500 hover:bg-gray-100'
              }`}>
              <Pin className="w-3.5 h-3.5" /> {session.pinned ? 'Pinned' : 'Pin'}
            </button>
            <button onClick={handleDelete} disabled={deleting}
              className="flex items-center gap-1.5 px-3 py-1.5 text-sm text-red-600 hover:bg-red-50 rounded-lg transition-colors disabled:opacity-40">
              <Trash2 className="w-3.5 h-3.5" /> Delete
            </button>
          </div>
        </div>

        {/* Metadata */}
        <div className="bg-white rounded-2xl border border-gray-200 p-4 md:p-5 space-y-3">
          <div>
            <h1 className="text-lg font-semibold text-gray-900">{session.title}</h1>
            <div className="flex flex-wrap items-center gap-2 mt-2">
              <span className="text-xs font-mono bg-gray-100 text-gray-600 px-2 py-0.5 rounded-full">{session.session_id}</span>
              <span className="text-xs bg-blue-50 text-blue-700 px-2 py-0.5 rounded-full">{session.source}</span>
              {session.tags.map(t => (
                <span key={t} className="text-xs bg-gray-100 text-gray-500 px-2 py-0.5 rounded-full">{t}</span>
              ))}
            </div>
            <p className="text-xs text-gray-400 mt-2">Updated {new Date(session.updated_at).toLocaleString()}</p>
          </div>
        </div>

        {/* GitHub Repository */}
        <div className="bg-white rounded-2xl border border-gray-200 p-4 md:p-5">
          <h2 className="text-sm font-semibold text-gray-700 flex items-center gap-1.5 mb-2">
            <Github className="w-4 h-4" /> GitHub Repository
          </h2>
          {session.repo_url ? (
            <a href={session.repo_url} target="_blank" rel="noopener noreferrer"
              className="text-sm text-blue-600 hover:underline break-all">
              {session.repo_url}
            </a>
          ) : (
            <p className="text-sm text-gray-400">No repository linked.</p>
          )}
        </div>

        {/* Skills Used */}
        {session.skills.length > 0 && (
          <div className="bg-white rounded-2xl border border-gray-200 p-4 md:p-5">
            <h2 className="text-sm font-semibold text-gray-700 flex items-center gap-1.5 mb-3">
              <BookOpen className="w-4 h-4" /> Skills Used
            </h2>
            <div className="flex flex-wrap gap-2">
              {session.skills.map(s => (
                <span key={s.skill_slug}
                  className="inline-flex items-center gap-1.5 px-3 py-1 rounded-full bg-purple-50 text-purple-700 text-xs font-medium">
                  {s.name ?? s.skill_slug}
                  {s.category && (
                    <span className="text-purple-400">· {s.category}</span>
                  )}
                </span>
              ))}
            </div>
          </div>
        )}

        {/* Context */}
        <div className="bg-white rounded-2xl border border-gray-200 p-4 md:p-5">
          <h2 className="text-sm font-semibold text-gray-700 mb-3">Context</h2>
          <pre className="text-sm text-gray-800 whitespace-pre-wrap font-mono bg-gray-50 rounded-xl p-4 overflow-x-auto max-h-[500px] overflow-y-auto">
            {session.context || <span className="text-gray-400 italic">No context saved.</span>}
          </pre>
        </div>

        {/* Pinned notes */}
        {pinnedNotes.length > 0 && (
          <div className="bg-white rounded-2xl border border-gray-200 p-4 md:p-5 space-y-3">
            <h2 className="text-sm font-semibold text-gray-700 flex items-center gap-1.5">
              <Pin className="w-3.5 h-3.5 text-blue-500" /> Pinned Notes ({pinnedNotes.length})
            </h2>
            <div className="space-y-2">
              {pinnedNotes.map(n => (
                <NoteCard key={n.id} {...n} pinned />
              ))}
            </div>
          </div>
        )}

        {/* Notes + append */}
        <div className="bg-white rounded-2xl border border-gray-200 p-4 md:p-5 space-y-3">
          <h2 className="text-sm font-semibold text-gray-700">
            Notes {regularNotes.length > 0 ? `(${regularNotes.length})` : ''}
          </h2>

          {regularNotes.length === 0 && pinnedNotes.length === 0 ? (
            <p className="text-sm text-gray-400">No notes yet.</p>
          ) : (
            <>
              <div className="space-y-2">
                {paginatedNotes.map(n => (
                  <NoteCard key={n.id} {...n} />
                ))}
              </div>
              {totalPages > 1 && (
                <div className="flex items-center justify-between pt-2 border-t border-gray-100">
                  <p className="text-xs text-gray-400">
                    {(currentPage - 1) * NOTES_PER_PAGE + 1}–{Math.min(currentPage * NOTES_PER_PAGE, regularNotes.length)} of {regularNotes.length} notes
                  </p>
                  <div className="flex items-center gap-1">
                    <button onClick={() => setNotePage(p => Math.max(1, p - 1))} disabled={currentPage === 1}
                      className="p-1.5 rounded-lg text-gray-400 hover:text-gray-700 hover:bg-gray-100 disabled:opacity-30 transition-colors">
                      <ChevronLeft className="w-4 h-4" />
                    </button>
                    <span className="text-xs text-gray-500 px-1">{currentPage} / {totalPages}</span>
                    <button onClick={() => setNotePage(p => Math.min(totalPages, p + 1))} disabled={currentPage === totalPages}
                      className="p-1.5 rounded-lg text-gray-400 hover:text-gray-700 hover:bg-gray-100 disabled:opacity-30 transition-colors">
                      <ChevronRight className="w-4 h-4" />
                    </button>
                  </div>
                </div>
              )}
            </>
          )}

          <form onSubmit={handleAddNote} className="space-y-2 pt-2 border-t border-gray-100">
            <textarea
              value={noteContent}
              onChange={e => setNoteContent(e.target.value)}
              rows={3}
              placeholder="Append a note…"
              required
              className="w-full px-3 py-2 text-sm rounded-xl border border-gray-300 resize-none focus:outline-none focus:ring-2 focus:ring-blue-500"
            />
            <button type="submit" disabled={addingNote}
              className="flex items-center gap-1.5 px-4 py-2 text-sm bg-blue-600 hover:bg-blue-700 text-white rounded-lg disabled:opacity-60 transition-colors">
              <Plus className="w-4 h-4" /> {addingNote ? 'Adding…' : 'Add note'}
            </button>
          </form>
        </div>
      </main>
    </div>
  )
}
