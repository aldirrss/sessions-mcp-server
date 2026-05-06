'use client'

import { use, useState, useEffect, useCallback } from 'react'
import { useRouter } from 'next/navigation'
import Link from 'next/link'
import { ArrowLeft, Trash2, Plus, BookOpen, Github, ExternalLink, Unlink, Pin, Archive, RotateCcw } from 'lucide-react'

import { API_BASE } from '@/lib/config'
import NoteCard from '@/components/note-card'

type Note = { id: number; content: string; source: string; pinned: boolean; created_at: string }
type Skill = { slug: string; name: string; category: string | null; used_at: string }
type Session = {
  session_id: string; title: string; context: string; source: string
  tags: string[]; pinned: boolean; archived: boolean; repo_url: string | null
  notes: Note[]; skills: Skill[]; updated_at: string
}

export default function SessionDetailPage({ params }: { params: Promise<{ id: string }> }) {
  const { id } = use(params)
  const router = useRouter()
  const [session, setSession] = useState<Session | null>(null)
  const [loading, setLoading] = useState(true)
  const [editing, setEditing] = useState(false)
  const [title, setTitle] = useState('')
  const [tags, setTags] = useState('')
  const [repoUrl, setRepoUrl] = useState('')
  const [editingRepo, setEditingRepo] = useState(false)
  const [savingRepo, setSavingRepo] = useState(false)
  const [togglingNote, setTogglingNote] = useState<number | null>(null)
  const [noteContent, setNoteContent] = useState('')
  const [addingNote, setAddingNote] = useState(false)
  const [saving, setSaving] = useState(false)

  const fetchSession = useCallback(async () => {
    const res = await fetch(`${API_BASE}/sessions/${id}`)
    if (!res.ok) { router.push("/mcp-admin/sessions"); return }
    const data = await res.json()
    setSession(data)
    setTitle(data.title)
    setTags(data.tags.join(', '))
    setRepoUrl(data.repo_url ?? '')
    setLoading(false)
  }, [id, router])

  useEffect(() => { fetchSession() }, [fetchSession])

  async function handleSave() {
    setSaving(true)
    await fetch(`${API_BASE}/sessions/${id}`, {
      method: 'PATCH',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        title,
        tags: tags.split(',').map(t => t.trim()).filter(Boolean),
      }),
    })
    setSaving(false)
    setEditing(false)
    fetchSession()
  }

  async function handleDelete() {
    if (!confirm(`Delete session "${id}" and all its notes?`)) return
    await fetch(`${API_BASE}/sessions/${id}`, { method: 'DELETE' })
    router.push("/mcp-admin/sessions")
  }

  async function handleSaveRepo() {
    setSavingRepo(true)
    await fetch(`${API_BASE}/sessions/${id}`, {
      method: 'PATCH',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ repo_url: repoUrl.trim() || null }),
    })
    setSavingRepo(false)
    setEditingRepo(false)
    fetchSession()
  }

  async function handleUnlinkRepo() {
    if (!confirm('Remove repository link from this session?')) return
    setSavingRepo(true)
    await fetch(`${API_BASE}/sessions/${id}`, {
      method: 'PATCH',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ repo_url: null }),
    })
    setSavingRepo(false)
    fetchSession()
  }

  async function handleTogglePin() {
    if (!session) return
    await fetch(`${API_BASE}/sessions/${id}`, {
      method: 'PATCH',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ pinned: !session.pinned }),
    })
    fetchSession()
  }

  async function handleToggleArchive() {
    if (!session) return
    const action = session.archived ? 'restore' : 'archive'
    if (!confirm(`${action === 'archive' ? 'Archive' : 'Restore'} session "${id}"?`)) return
    await fetch(`${API_BASE}/sessions/${id}`, {
      method: 'PATCH',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ archived: !session.archived }),
    })
    fetchSession()
  }

  async function handleToggleNotePin(noteId: number, currentPinned: boolean) {
    setTogglingNote(noteId)
    await fetch(`${API_BASE}/sessions/${id}/notes/${noteId}`, {
      method: 'PATCH',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ pinned: !currentPinned }),
    })
    setTogglingNote(null)
    fetchSession()
  }

  async function handleAddNote(e: React.FormEvent) {
    e.preventDefault()
    setAddingNote(true)
    await fetch(`${API_BASE}/sessions/${id}/notes`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ content: noteContent, source: 'web' }),
    })
    setNoteContent('')
    setAddingNote(false)
    fetchSession()
  }

  if (loading) return <div className="text-sm text-gray-400 p-8">Loading…</div>
  if (!session) return null

  return (
    <div className="max-w-5xl space-y-6">
      <div className="flex items-center justify-between">
        <Link href="/mcp-admin/sessions" className="flex items-center gap-1.5 text-sm text-gray-500 hover:text-gray-900 transition-colors">
          <ArrowLeft className="w-4 h-4" /> Sessions
        </Link>
        <div className="flex items-center gap-2">
          <button onClick={handleTogglePin}
            className={`flex items-center gap-1.5 px-3 py-1.5 text-sm rounded-lg transition-colors ${session.pinned ? 'bg-amber-50 text-amber-700 hover:bg-amber-100' : 'text-gray-500 hover:bg-gray-100'}`}
            title={session.pinned ? 'Unpin session' : 'Pin session (protect from auto-vacuum)'}>
            <Pin className="w-4 h-4" /> {session.pinned ? 'Pinned' : 'Pin'}
          </button>
          <button onClick={handleToggleArchive}
            className={`flex items-center gap-1.5 px-3 py-1.5 text-sm rounded-lg transition-colors ${session.archived ? 'bg-gray-100 text-gray-700 hover:bg-gray-200' : 'text-gray-500 hover:bg-gray-100'}`}
            title={session.archived ? 'Restore session' : 'Archive session (soft delete)'}>
            {session.archived ? <RotateCcw className="w-4 h-4" /> : <Archive className="w-4 h-4" />}
            {session.archived ? 'Restore' : 'Archive'}
          </button>
          <button onClick={handleDelete} className="flex items-center gap-1.5 px-3 py-1.5 text-sm text-red-600 hover:bg-red-50 rounded-lg transition-colors">
            <Trash2 className="w-4 h-4" /> Delete
          </button>
        </div>
      </div>

      <div className="bg-white rounded-2xl border border-gray-200 p-6 space-y-4">
        {editing ? (
          <div className="space-y-3">
            <input value={title} onChange={e => setTitle(e.target.value)}
              className="w-full text-xl font-bold px-3 py-2 rounded-lg border border-gray-300 focus:outline-none focus:ring-2 focus:ring-blue-500" />
            <div>
              <label className="block text-xs font-medium text-gray-500 mb-1">Tags (comma-separated)</label>
              <input value={tags} onChange={e => setTags(e.target.value)}
                className="w-full px-3 py-2 text-sm rounded-lg border border-gray-300 focus:outline-none focus:ring-2 focus:ring-blue-500" />
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
          <div>
            <div className="flex items-start justify-between gap-4">
              <h1 className="text-xl font-bold text-gray-900">{session.title}</h1>
              <button onClick={() => setEditing(true)}
                className="text-sm text-blue-600 hover:underline flex-shrink-0">Edit</button>
            </div>
            <div className="flex items-center gap-2 mt-2 flex-wrap">
              <span className="text-xs bg-gray-100 text-gray-600 px-2 py-0.5 rounded-full font-mono">{session.session_id}</span>
              <span className="text-xs bg-blue-50 text-blue-700 px-2 py-0.5 rounded-full">{session.source}</span>
              {session.tags.map(t => (
                <span key={t} className="text-xs bg-gray-100 text-gray-600 px-2 py-0.5 rounded-full">{t}</span>
              ))}
            </div>
            <p className="text-xs text-gray-400 mt-2">Updated {new Date(session.updated_at).toLocaleString()}</p>
          </div>
        )}
      </div>

      {/* GitHub Repo */}
      <div className="bg-white rounded-2xl border border-gray-200 p-5">
        <h2 className="text-sm font-semibold text-gray-900 mb-3 flex items-center gap-2">
          <Github className="w-4 h-4 text-gray-500" /> GitHub Repository
        </h2>
        {editingRepo ? (
          <div className="space-y-2">
            <input
              value={repoUrl}
              onChange={e => setRepoUrl(e.target.value)}
              placeholder="https://github.com/owner/repo"
              className="w-full px-3 py-2 text-sm rounded-lg border border-gray-300 font-mono focus:outline-none focus:ring-2 focus:ring-blue-500"
            />
            <div className="flex gap-2">
              <button onClick={handleSaveRepo} disabled={savingRepo}
                className="px-3 py-1.5 text-sm bg-blue-600 hover:bg-blue-700 text-white rounded-lg disabled:opacity-60">
                {savingRepo ? 'Saving…' : 'Save'}
              </button>
              <button onClick={() => { setEditingRepo(false); setRepoUrl(session.repo_url ?? '') }}
                className="px-3 py-1.5 text-sm border border-gray-300 rounded-lg hover:bg-gray-50">Cancel</button>
            </div>
          </div>
        ) : session.repo_url ? (
          <div className="flex items-center justify-between gap-4">
            <a href={session.repo_url} target="_blank" rel="noopener noreferrer"
              className="flex items-center gap-1.5 text-sm text-blue-600 hover:underline font-mono min-w-0 truncate">
              {session.repo_url} <ExternalLink className="w-3.5 h-3.5 flex-shrink-0" />
            </a>
            <div className="flex items-center gap-2 flex-shrink-0">
              <button onClick={() => setEditingRepo(true)}
                className="text-xs text-blue-600 hover:underline">Edit</button>
              <button onClick={handleUnlinkRepo}
                className="flex items-center gap-1 text-xs text-red-500 hover:text-red-700">
                <Unlink className="w-3.5 h-3.5" /> Unlink
              </button>
            </div>
          </div>
        ) : (
          <div className="flex items-center justify-between">
            <p className="text-sm text-gray-400">No repository linked.</p>
            <button onClick={() => setEditingRepo(true)}
              className="text-sm text-blue-600 hover:underline">Link repo</button>
          </div>
        )}
      </div>

      {session.skills.length > 0 && (
        <div className="bg-white rounded-2xl border border-gray-200 p-5">
          <h2 className="text-sm font-semibold text-gray-900 mb-3 flex items-center gap-2">
            <BookOpen className="w-4 h-4 text-violet-600" /> Skills Used
          </h2>
          <div className="flex flex-wrap gap-2">
            {session.skills.map((sk) => (
              <Link
                key={sk.slug}
                href={`/mcp-admin/skills/${sk.slug}`}
                className="flex items-center gap-1.5 px-3 py-1.5 bg-violet-50 hover:bg-violet-100 text-violet-700 rounded-lg text-sm font-medium transition-colors"
              >
                {sk.name}
                {sk.category && <span className="text-xs text-violet-400">· {sk.category}</span>}
              </Link>
            ))}
          </div>
        </div>
      )}

      <div className="bg-white rounded-2xl border border-gray-200 p-5 space-y-4">
        <h2 className="text-sm font-semibold text-gray-900">Notes ({session.notes.length})</h2>

        {session.notes.length === 0 ? (
          <p className="text-sm text-gray-400">No notes yet.</p>
        ) : (
          <div className="space-y-2">
            {session.notes.map((note) => (
              <NoteCard
                key={note.id}
                {...note}
                onTogglePin={handleToggleNotePin}
                togglingPin={togglingNote === note.id}
              />
            ))}
          </div>
        )}

        <form onSubmit={handleAddNote} className="space-y-2 pt-2 border-t border-gray-100">
          <textarea
            value={noteContent}
            onChange={e => setNoteContent(e.target.value)}
            rows={3}
            placeholder="Append a note…"
            required
            className="w-full px-3 py-2 text-sm rounded-lg border border-gray-300 resize-none focus:outline-none focus:ring-2 focus:ring-blue-500"
          />
          <button type="submit" disabled={addingNote}
            className="flex items-center gap-1.5 px-4 py-2 text-sm bg-blue-600 hover:bg-blue-700 text-white rounded-lg disabled:opacity-60 transition-colors">
            <Plus className="w-4 h-4" />
            {addingNote ? 'Adding…' : 'Add note'}
          </button>
        </form>
      </div>
    </div>
  )
}
