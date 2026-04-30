'use client'

import { use, useState, useEffect, useCallback } from 'react'
import { useRouter } from 'next/navigation'
import Link from 'next/link'
import { ArrowLeft, Trash2, Plus, BookOpen } from 'lucide-react'

const API_BASE = '/panel/mcp-admin'

type Note = { id: number; content: string; source: string; created_at: string }
type Skill = { slug: string; name: string; category: string | null; used_at: string }
type Session = {
  session_id: string; title: string; context: string; source: string
  tags: string[]; notes: Note[]; skills: Skill[]; updated_at: string
}

export default function SessionDetailPage({ params }: { params: Promise<{ id: string }> }) {
  const { id } = use(params)
  const router = useRouter()
  const [session, setSession] = useState<Session | null>(null)
  const [loading, setLoading] = useState(true)
  const [editing, setEditing] = useState(false)
  const [title, setTitle] = useState('')
  const [tags, setTags] = useState('')
  const [noteContent, setNoteContent] = useState('')
  const [addingNote, setAddingNote] = useState(false)
  const [saving, setSaving] = useState(false)

  const fetchSession = useCallback(async () => {
    const res = await fetch(`${BASE}/api/sessions/${id}`)
    if (!res.ok) { router.push("/sessions"); return }
    const data = await res.json()
    setSession(data)
    setTitle(data.title)
    setTags(data.tags.join(', '))
    setLoading(false)
  }, [id, router])

  useEffect(() => { fetchSession() }, [fetchSession])

  async function handleSave() {
    setSaving(true)
    await fetch(`${BASE}/api/sessions/${id}`, {
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
    await fetch(`${BASE}/api/sessions/${id}`, { method: 'DELETE' })
    router.push("/sessions")
  }

  async function handleAddNote(e: React.FormEvent) {
    e.preventDefault()
    setAddingNote(true)
    await fetch(`${BASE}/api/sessions/${id}/notes`, {
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
    <div className="max-w-3xl space-y-6">
      <div className="flex items-center justify-between">
        <Link href="/sessions" className="flex items-center gap-1.5 text-sm text-gray-500 hover:text-gray-900 transition-colors">
          <ArrowLeft className="w-4 h-4" /> Sessions
        </Link>
        <button onClick={handleDelete} className="flex items-center gap-1.5 px-3 py-1.5 text-sm text-red-600 hover:bg-red-50 rounded-lg transition-colors">
          <Trash2 className="w-4 h-4" /> Delete
        </button>
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

      {session.skills.length > 0 && (
        <div className="bg-white rounded-2xl border border-gray-200 p-5">
          <h2 className="text-sm font-semibold text-gray-900 mb-3 flex items-center gap-2">
            <BookOpen className="w-4 h-4 text-violet-600" /> Skills Used
          </h2>
          <div className="flex flex-wrap gap-2">
            {session.skills.map((sk) => (
              <Link
                key={sk.slug}
                href={`/skills/${sk.slug}`}
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
          <div className="space-y-3">
            {session.notes.map((note) => (
              <div key={note.id} className="rounded-xl bg-gray-50 border border-gray-100 p-4">
                <p className="text-sm text-gray-900 whitespace-pre-wrap">{note.content}</p>
                <p className="text-xs text-gray-400 mt-2">{note.source} · {new Date(note.created_at).toLocaleString()}</p>
              </div>
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
